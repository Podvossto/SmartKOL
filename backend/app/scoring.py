"""Score and rank the creators whose latest videos have been read.

Four axes, each 0-100. Engagement and Activity are computed from the numbers (no model involved). Relevance and
Audience fit are the model's judgement of the creator against the brand brief; Audience fit is an estimate (TikTok
does not publish a creator's audience) and is labelled so. The total is a weighted mean computed when the list is
shown, so changing the weights costs nothing.
"""
import re
import json
from datetime import datetime, timezone

import httpx

from . import analyses, config, discovery, llm, prompts
from .clients import UpstreamError

AXES = ("relevance", "engagement", "audience", "activity")
BATCH = 10
TIERS = ((10_000, "nano"), (100_000, "micro"), (500_000, "mid"), (1_000_000, "macro"))


class ScoreError(ValueError):
    """The request is not allowed. The message is shown to the user as it is."""


# ---------- weights and totals ----------

def clean_weights(raw: dict[str, float]) -> dict[str, int]:
    """Whole numbers that add up to 100, however the user typed them."""
    values = {a: max(float(raw.get(a, 0)), 0.0) for a in AXES}
    total = sum(values.values())
    if total <= 0:
        raise ScoreError("Give at least one axis a weight above 0.")
    weights = {a: int(v / total * 100) for a, v in values.items()}
    biggest = max(weights, key=lambda a: values[a])
    weights[biggest] += 100 - sum(weights.values())
    return weights


def total(score: dict, weights: dict[str, int]) -> int:
    return round(sum(score[a] * weights[a] for a in AXES) / sum(weights.values()))


def attach(creators: list[dict], weights: dict[str, int]) -> list[dict]:
    """Copies of the creators with their total and their rank among the scored ones in this list."""
    out = [dict(c) for c in creators]
    for c in out:
        c["total"] = total(c["score"], weights) if c.get("score") else None
    for rank, c in enumerate(sorted((c for c in out if c["total"] is not None), key=lambda c: -c["total"]), start=1):
        c["rank"] = rank
    return out


# ---------- the two computed axes ----------

def tier(followers: int | None) -> str:
    n = followers or 0
    return next((name for limit, name in TIERS if n < limit), "mega")


def _percentile(value: float, pool: list[float]) -> float:
    below = sum(v < value for v in pool)
    equal = sum(v == value for v in pool)
    return (below + 0.5 * equal) / len(pool) * 100


def engagement(c: dict, read: list[dict]) -> tuple[int, str]:
    """Median engagement rate by views (70%) and views per follower (30%), each as a percentile among the creators of
    the same size that were read in this search (all of them when fewer than 3 share the size)."""
    peers = [p for p in read if tier(p["followers"]) == tier(c["followers"])]
    basis = f"{tier(c['followers'])} creators read here"
    if len(peers) < 3:
        peers, basis = read, "all creators read here"
    m = c["metrics"]
    reach = lambda x: x["metrics"]["median_views"] / x["followers"] if x["followers"] else 0.0
    er = [p["metrics"]["median_er"] for p in peers if p["metrics"]["median_er"] is not None]
    if m["median_er"] is None or not er:
        return 0, "No views to measure engagement from."
    score = 0.7 * _percentile(m["median_er"], er) + 0.3 * _percentile(reach(c), [reach(p) for p in peers])
    note = f"Engagement rate {m['median_er']:.1%} of views, {reach(c):.1%} of followers watch; ranked against {len(peers)} ({basis})."
    return round(score), note


def _ramp(x: float, zero: float, full: float) -> float:
    """0 at `zero`, 1 at `full`, straight line between, either direction."""
    return min(max((x - zero) / (full - zero), 0.0), 1.0)


def activity(c: dict) -> tuple[int, str, list[str]]:
    """Cadence 35, recency 25, few ads 20, steady views 20; cut by a third when views are tiny next to followers."""
    m, flags, notes = c["metrics"], [], []
    ppw, days, cv = m["posts_per_week"], m["days_since_last_post"], m.get("views_cv")
    cadence = 17.5 if ppw is None else 35 * _ramp(ppw, 0, 3)
    recency = 0.0 if days is None else 25 * _ramp(days, 60, 7)
    ads = 20 * _ramp(m["ad_share"], 0.5, 0.1)
    steady = 10.0 if cv is None else 20 * _ramp(cv, 2.0, 0.5)
    score = cadence + recency + ads + steady
    if c["followers"] and m["median_views"] / c["followers"] < 0.002:
        score *= 0.67
        flags.append("Views are under 0.2% of followers: the follower count may be inflated.")
    if m["ad_share"] >= 0.3:
        flags.append(f"{m['ad_share']:.0%} of recent videos are ads or sponsored.")
    notes.append(f"{ppw if ppw is not None else '?'} posts a week, last post {days if days is not None else '?'} days ago, {m['ad_share']:.0%} ads"
                 + (f", views vary by {cv:.0%}" if cv is not None else "") + ".")
    return round(score), " ".join(notes), flags


# ---------- the two judged axes ----------

SYSTEM = """You judge TikTok creators for an influencer-marketing agency in Thailand. For each creator, decide how well they fit the brand below, using only what is given (bio, captions, hashtags, numbers). Never invent facts about a creator.

Give each creator these scores, 0-100:
- category: do they usually make content about the brand's category and the niches it wants?
- style: does their content style and tone match the brand's voice and the content styles it wants?
- product: how naturally could they feature this brand's products (not just the category)?
- safety: how safe is the match for the brand? Lower it for conflicts the brand wants to avoid, content that clashes with the brand's image, or a creator who mainly promotes competitors.
- audience: how likely is it that their audience is the brand's target audience (age, interests, lifestyle)? This is an ESTIMATE from content only; nobody can see a TikTok creator's real audience, so stay near the middle unless the content clearly points one way.
- confidence: "low", "medium" or "high" for the audience estimate (high only when the captions and bio clearly say who the audience is).
- viewers: your best guess at who watches them, from the content only: age (ONE range such as "18-24"), gender ("mostly women", "mostly men" or "mixed") and 2-3 interests (short English labels). Always give a guess, and set confidence to "low" when the content does not say; it is an estimate, never a fact.
Be strict: 80+ means a clear, specific fit. Most creators should land between 30 and 75.
reason: at most 25 words, English, why this creator fits or not, naming the strongest evidence. audience_reason: at most 15 words.

Reply with ONE JSON array and nothing else, one object per creator, in this shape:
[{"u": "<username>", "category": int, "style": int, "product": int, "safety": int, "audience": int, "confidence": "low"|"medium"|"high", "age": str, "gender": "mostly women"|"mostly men"|"mixed", "interests": [str], "reason": str, "audience_reason": str}]"""


prompts.register(prompts.Prompt(
    id="creator_scoring",
    title="Creator scoring",
    description="How the AI judges how well each creator fits the brand (category, style, product, brand safety) and estimates whether their audience matches the brand's target.",
    used_when="When creators are scored, for every creator that has not been judged yet.",
    default=SYSTEM,
    marker="Reply with ONE JSON array and nothing else",
))


def _brand(profile: dict) -> str:
    fit, aud, voice = profile["creator_fit"], profile["audience"], profile["voice"]
    return "\n".join([
        f"Brand: {profile['brand_name']}. Category: {profile['category']}. Price level: {profile['price_tier']}. Sells: {', '.join(profile['products'][:6])}.",
        f"Target audience: {aud['description']} Age {aud['age_range']}. Interests: {', '.join(aud['interests'][:6])}.",
        f"Voice: {', '.join(voice['traits'][:5])}. {voice['style']}",
        f"Wants creators in: {', '.join(fit['niches'])}. Content styles: {', '.join(fit['content_styles'])}. Audience to look for: {fit['audience_match']}. Language: {fit['language']}.",
        f"Avoid: {', '.join(fit['avoid'])}.",
    ])


def _creator_line(c: dict) -> str:
    m = c["metrics"]
    captions = " / ".join(s["text"] for s in c["samples"][:3] if s.get("text"))
    return (f"@{c['username']} | {c['followers']} followers | name: {c['nickname']} | bio: {' '.join(discovery.mask_contacts(c['bio']).split())[:200]} | "
            f"hashtags: {', '.join(c['hashtags'][:6])} | captions: {captions[:300]} | "
            f"median views {m['median_views']}, ads {m['ad_share']:.0%}, TikTok Shop {m['shop_share']:.0%} | label: {c.get('kind') or 'unknown'}")


GENDERS = ("mostly women", "mostly men", "mixed")


def _viewers(row: dict) -> dict | None:
    """The model's guess at who watches a creator (age range, gender lean, interests), or None when it gave nothing usable."""
    age = " ".join(str(row.get("age") or "").split())[:20]
    gender = row.get("gender") if row.get("gender") in GENDERS else ""
    raw = row.get("interests")
    interests = [" ".join(str(i).split())[:30] for i in raw if isinstance(i, str) and i.strip()][:3] if isinstance(raw, list) else []
    return {"age": age, "gender": gender, "interests": interests} if age or gender or interests else None


def _pct(value) -> int | None:
    return min(max(int(value), 0), 100) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def judge(http: httpx.Client, cfg, profile: dict, creators: list[dict]) -> tuple[dict[str, dict], dict]:
    """Ask the model about each creator. Returns ({username: judgement}, usage). A creator the model skips or answers
    badly for is simply left out: a bad reply never produces a made-up score."""
    usage = {"input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0, "model": cfg.model}
    judged: dict[str, dict] = {}
    system = prompts.system("creator_scoring")
    for start in range(0, len(creators), BATCH):
        batch = creators[start : start + BATCH]
        out = llm.complete(http, cfg, system, _brand(profile) + "\n\nCreators:\n" + "\n".join(_creator_line(c) for c in batch), max_tokens=8000)
        usage["input_tokens"] += out.input_tokens or 0
        usage["output_tokens"] += out.output_tokens or 0
        usage["cost_usd"] += out.cost_usd or 0.0
        usage["model"] = out.model
        known = {c["username"] for c in batch}
        for found in re.finditer(r"\{[^{}]*\}", out.text):  # every complete object, so a reply cut off at the limit still counts
            try:
                row = json.loads(found.group())
            except ValueError:
                continue
            name = str(row.get("u", "")).lstrip("@") if isinstance(row, dict) else ""
            subs = {k: _pct(row.get(k)) for k in ("category", "style", "product", "safety", "audience")}
            if name in known and None not in subs.values():
                judged[name] = {**subs, "confidence": row.get("confidence") if row.get("confidence") in ("low", "medium", "high") else "low",
                                "reason": str(row.get("reason") or "")[:200], "audience_reason": str(row.get("audience_reason") or "")[:140],
                                "viewers": _viewers(row)}
    return judged, usage


def relevance(j: dict) -> tuple[int, list[str]]:
    """Mean of the four rubric scores; a creator who is unsafe for the brand cannot rank high however well they fit."""
    score, flags = round((j["category"] + j["style"] + j["product"] + j["safety"]) / 4), []
    if j["safety"] < 40:
        score, flags = min(score, 40), ["Brand safety is low: the match is capped."]
    return score, flags


# ---------- put it together ----------

def build(creators: list[dict]) -> int:
    """(Re)compute the stored score of every creator that has been read and judged. Engagement is relative, so the
    whole pool is recomputed each time. Returns how many creators have a score."""
    read = [c for c in creators if c.get("metrics")]
    now = datetime.now(timezone.utc).isoformat()
    scored = 0
    for c in read:
        j = c.get("judged")
        if not j:
            c.pop("score", None)
            continue
        rel, rel_flags = relevance(j)
        eng, eng_note = engagement(c, read)
        act, act_note, act_flags = activity(c)
        c["score"] = {"relevance": rel, "engagement": eng, "audience": j["audience"], "activity": act,
                      "category": j["category"], "style": j["style"], "product": j["product"], "safety": j["safety"],
                      "reason": j["reason"], "audience_reason": j["audience_reason"], "confidence": j["confidence"], "viewers": j.get("viewers"),
                      "engagement_note": eng_note, "activity_note": act_note, "flags": rel_flags + act_flags,
                      "model": j.get("model"), "scored_at": now}
        scored += 1
    return scored


def clean(usernames: list[str] | None, known: list[dict]) -> list[str]:
    read = {c["username"] for c in known if c.get("metrics")}
    if not read:
        raise ScoreError("Read the latest videos of some creators first: scores are built from them.")
    chosen = list(dict.fromkeys(u.lstrip("@") for u in usernames)) if usernames else sorted(read)
    unread = [u for u in chosen if u not in read]
    if unread:
        raise ScoreError(f"Videos have not been read for: {', '.join(unread[:3])}.")
    return chosen


# ---------- the job ----------

def start(aid: str, usernames: list[str], redo: bool) -> dict:
    state = analyses.update(aid, lambda s: s["creators"].update(scoring={"status": "running", "usernames": usernames, "error": None, "scored": 0, "failed": 0, "model": None, "usd": 0.0}))
    analyses.spawn(run, aid, usernames, redo)
    return state


def run(aid: str, usernames: list[str], redo: bool) -> None:
    state = analyses.load(aid)
    if state is None or not state["profile"]:
        return
    cfg = config.llm_config()

    def fail(message: str):
        analyses.update(aid, lambda s: s["creators"]["scoring"].update(status="error", error=message))
    if not cfg:
        return fail("No language model is set. Add one in Settings first.")
    todo = [c for c in state["creators"]["items"] if c["username"] in usernames and c.get("metrics") and (redo or not c.get("judged") or "viewers" not in c["judged"])]  # a judgement from before viewers were asked is asked again once
    judged, usage = {}, {"input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0, "model": cfg.model}
    try:
        if todo:
            with httpx.Client(timeout=180) as http:
                judged, usage = judge(http, cfg, state["profile"], todo)
    except (UpstreamError, httpx.HTTPError) as exc:
        return fail(str(exc) if isinstance(exc, UpstreamError) else "Network error while contacting the language model.")
    except Exception:
        analyses.log.exception("creator scoring %s failed", aid)
        return fail("Something unexpected went wrong. Check the server log and try again.")

    def done(s):
        for c in s["creators"]["items"]:
            if c["username"] in judged:
                c["judged"] = {**judged[c["username"]], "model": usage["model"]}
        scored = build(s["creators"]["items"])
        cost = s["cost"]
        cost["llm_input_tokens"] += usage["input_tokens"]
        cost["llm_output_tokens"] += usage["output_tokens"]
        if todo:
            cost["llm_model"] = usage["model"]
        if usage["cost_usd"]:
            cost["llm_usd"] = round(cost["llm_usd"] + usage["cost_usd"], 6)
        elif todo:
            cost["llm_known"] = False
        s["creators"]["scoring"].update(status="done", scored=scored, failed=len(todo) - len(judged), model=usage["model"], usd=round(usage["cost_usd"], 6))
    analyses.update(aid, done)
