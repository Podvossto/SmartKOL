"""Brand Profile: the structured brand understanding the rest of the pipeline works from."""
import json
import logging
import re
from typing import Literal

import httpx
from pydantic import BaseModel, ValidationError, field_validator, model_validator

from . import llm
from .clients import UpstreamError
from .config import LlmConfig

log = logging.getLogger("smartkol.brand")

PAGE_CHARS = 6000  # per website page sent to the model
POST_CHARS = 300


def _clean_tag(tag: str) -> str:
    return re.sub(r"\s+", "", tag.strip().lstrip("#"))


def _tags(values: list[str], limit: int) -> list[str]:
    seen: dict[str, str] = {}
    for value in values:
        tag = _clean_tag(str(value))
        if tag and tag.lower() not in seen:
            seen[tag.lower()] = tag
    return list(seen.values())[:limit]


class Audience(BaseModel):
    description: str
    age_range: str
    gender: str
    interests: list[str]
    lifestyle: str
    media_habits: list[str] = []


class Voice(BaseModel):
    traits: list[str] = []
    style: str = ""
    dos: list[str] = []
    donts: list[str] = []


class Pillar(BaseModel):
    theme: str
    detail: str = ""
    performance: Literal["strong", "average", "weak", "unknown"] = "unknown"


class CreatorFit(BaseModel):
    niches: list[str] = []
    content_styles: list[str] = []
    audience_match: str = ""
    language: str = ""
    avoid: list[str] = []


class Evidence(BaseModel):
    fact: str
    source: Literal["website", "facebook", "both"] = "both"

    @model_validator(mode="before")
    @classmethod
    def _plain_text(cls, v):
        return {"fact": v} if isinstance(v, str) else v  # profiles saved by older versions hold plain strings


class TikTokPlan(BaseModel):
    hashtags_th: list[str]
    hashtags_en: list[str]
    keywords: list[str]

    @field_validator("hashtags_th", "hashtags_en")
    @classmethod
    def _hashtags(cls, v: list[str]) -> list[str]:
        return _tags(v, 12)

    @field_validator("keywords")
    @classmethod
    def _keywords(cls, v: list[str]) -> list[str]:
        return list(dict.fromkeys(k.strip() for k in v if k.strip()))[:10]


class SourceSummary(BaseModel):
    summary: str
    key_points: list[str] = []


class BrandProfile(BaseModel):
    """A brief an agency could hand to a creator: who the brand is, who it speaks to, how it sounds, what it posts,
    and the kind of creator that fits. `gaps` says what the sources did not reveal."""

    brand_name: str
    category: str
    price_tier: Literal["budget", "mid", "premium", "unknown"]
    positioning: str = ""
    summary: str
    products: list[str]
    audience: Audience
    voice: Voice = Voice()
    pillars: list[Pillar] = []
    formats: list[str] = []
    creator_fit: CreatorFit = CreatorFit()
    language: str = ""
    tiktok: TikTokPlan
    evidence: list[Evidence] = []
    gaps: list[str] = []
    by_source: dict[str, SourceSummary] = {}
    edited: list[Literal["creator_fit", "tiktok"]] = []  # sections the user changed after the model wrote them

    @model_validator(mode="before")
    @classmethod
    def _upgrade_old_profile(cls, v):
        """Profiles saved before the brief structure: carry their tone and style over so they still open."""
        if isinstance(v, dict) and "voice" not in v and ("tone" in v or "content_style" in v):
            v = {**v, "voice": {"traits": v.get("tone", []), "style": v.get("content_style", "")}}
        return v


SYSTEM = """You are an influencer-marketing strategist for the Thai market. You read a brand's website and/or \
Facebook page and write the brand brief an agency would hand to a creator: it will be used to find and judge \
matching Thai TikTok creators. When both sources are given, the main brief combines them (if they clearly describe \
different businesses, say so in the summary and base the brief on the website); by_source keeps what each one says alone.

Rules:
- Use ONLY the evidence provided. Infer cautiously from it; never invent facts, numbers, competitors or prices.
- Write descriptive text in English. Keep brand names, product names and hashtags in their original language.
- category: a short label of 2-4 words (e.g. "Dessert cafe", "Suki restaurant chain"); details belong in summary.
- positioning: ONE sentence, "For <target customer>, <brand> is the <category> that <main benefit>". Add "unlike ..." only if the evidence names an alternative.
- summary: 2-3 sentences on what the brand is and how it is doing (scale, activity).
- products: the 4-8 most representative products or services (group similar items).
- audience: the likely customers, not staff. age_range and gender: your best estimate from the products, prices and posts (e.g. "18-34", "mostly women"); never write "not stated" or "unknown" there, because gaps is where missing information goes. description = who they are; lifestyle = how they live; media_habits = 2-4 platforms or content habits the evidence suggests (e.g. the brand's own channels, delivery apps, TikTok).
- voice: traits = 3-5 adjectives; style = one sentence on how its captions are written (length, language, emoji, calls to action); dos = 3-4 things a creator promoting this brand should do; donts = 3-4 things to avoid. dos/donts must follow from the brand's own voice, category and claims in the evidence (never invent legal or health claims).
- pillars: 3-5 content themes the brand actually posts about. detail = one sentence with a concrete example from the evidence. performance = "strong" if its posts clearly beat the average likes/comments/shares of the posts listed, "weak" if clearly below, "average" otherwise, "unknown" if there is no post data.
- formats: the content formats the evidence shows (e.g. "short video / reels", "photo posts", "carousel"), most used first.
- creator_fit: niches = 3-5 TikTok creator niches that fit, each a short label (e.g. "cafe and dessert reviewer"); content_styles = 2-4 formats or styles (e.g. "eating close-ups", "cafe vlog"); audience_match = ONE sentence on the follower audience to look for; language = the language creators should post in; avoid = 2-4 creator types or conflicts to avoid. Keep every item under 12 words.
- tiktok.hashtags_th / hashtags_en: hashtags Thai TikTok viewers and creators actually use for this kind of content (category, product, occasion, review style), broad and niche mixed. No '#', no spaces. At most one containing the brand name. 6-10 Thai and 3-6 English.
- tiktok.keywords: 4-8 short search phrases (Thai or English) a creator in this niche would post about.
- evidence: 4-6 short facts copied or closely paraphrased from the input, each tagged with where it came from ("website", "facebook" or "both").
- gaps: 1-4 things a creator brief would need that the sources do NOT show (e.g. prices, target age stated by the brand, campaign goals, competitors). Say plainly that it was not found.
- by_source: one entry for EACH source present in the input, keyed "website" and/or "facebook". summary: 2-3 sentences about what that source alone shows. key_points: up to 3 short bullets.
- Reply with ONE JSON object and nothing else (no markdown fences).

JSON shape:
{"brand_name": str, "category": str, "price_tier": "budget"|"mid"|"premium"|"unknown", "positioning": str, "summary": str, \
"products": [str], "audience": {"description": str, "age_range": str, "gender": str, "interests": [str], "lifestyle": str, "media_habits": [str]}, \
"voice": {"traits": [str], "style": str, "dos": [str], "donts": [str]}, \
"pillars": [{"theme": str, "detail": str, "performance": "strong"|"average"|"weak"|"unknown"}], "formats": [str], \
"creator_fit": {"niches": [str], "content_styles": [str], "audience_match": str, "language": str, "avoid": [str]}, \
"language": str, "tiktok": {"hashtags_th": [str], "hashtags_en": [str], "keywords": [str]}, \
"evidence": [{"fact": str, "source": "website"|"facebook"|"both"}], "gaps": [str], \
"by_source": {"website": {"summary": str, "key_points": [str]}, "facebook": {"summary": str, "key_points": [str]}}}"""


def build_evidence(site_pages: list[dict], facebook: dict | None, posts: list[dict]) -> str:
    parts = []
    for page in site_pages:
        parts.append(
            f"## WEBSITE PAGE {page['url']}\nTitle: {page.get('title')}\nDescription: {page.get('description')}\n"
            f"{(page.get('text') or '')[:PAGE_CHARS]}"
        )
    if facebook:
        parts.append(
            "## FACEBOOK PAGE\n"
            f"Name: {facebook.get('title')}\nCategory: {facebook.get('category')}\nFollowers: {facebook.get('followers')}\n"
            f"Address: {facebook.get('address')}\nIntro: {facebook.get('intro')}"
        )
    if posts:
        lines = [
            f"- {(p.get('time') or '')[:10]} | {'video' if p.get('isVideo') else 'post'} | likes {p.get('likes')} comments {p.get('comments')} shares {p.get('shares')} | "
            f"{' '.join(str(p.get('text') or '').split())[:POST_CHARS]}"
            for p in posts
        ]
        parts.append("## RECENT FACEBOOK POSTS\n" + "\n".join(lines))
    return "\n\n".join(parts)


def parse_profile(text: str, sources: set[str] | None = None) -> BrandProfile:
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("no JSON object in the reply")
    profile = BrandProfile.model_validate(json.loads(text[start : end + 1]))
    sources = sources or set()
    profile.by_source = {k: v for k, v in profile.by_source.items() if k in sources}  # drop invented sources
    missing = [f"by_source.{name}" for name in sorted(sources) if not (profile.by_source.get(name) and profile.by_source[name].summary.strip())]
    missing += [
        name
        for name, ok in {
            "brand_name": profile.brand_name.strip(),
            "category": profile.category.strip(),
            "positioning": profile.positioning.strip(),
            "summary": profile.summary.strip(),
            "products": profile.products,
            "audience.description": profile.audience.description.strip(),
            "voice.traits": profile.voice.traits,
            "pillars": profile.pillars,
            "creator_fit.niches": profile.creator_fit.niches,
            "tiktok.hashtags_th": profile.tiktok.hashtags_th,
        }.items()
        if not ok
    ]
    if missing:
        raise ValueError("empty fields: " + ", ".join(missing))
    return profile


def build_profile(
    http: httpx.Client, cfg: LlmConfig, site_pages: list[dict], facebook: dict | None, posts: list[dict]
) -> tuple[BrandProfile, dict]:
    """Returns (profile, usage) where usage sums tokens/cost over the (at most two) model calls."""
    user = build_evidence(site_pages, facebook, posts)
    sources = ({"website"} if site_pages else set()) | ({"facebook"} if facebook else set())
    usage = {"input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0, "calls": 0, "model": cfg.model}
    problem = ""
    for _ in range(2):
        prompt = user if not problem else f"{user}\n\nYour previous reply was rejected ({problem}). Reply again with the complete JSON object."
        out = llm.complete(http, cfg, SYSTEM, prompt, max_tokens=8000)
        usage["calls"] += 1
        usage["input_tokens"] += out.input_tokens or 0
        usage["output_tokens"] += out.output_tokens or 0
        usage["cost_usd"] += out.cost_usd or 0.0
        usage["model"] = out.model
        try:
            return parse_profile(out.text, sources), usage
        except (ValueError, ValidationError) as exc:  # JSONDecodeError is a ValueError
            problem = str(exc)[:200]
            log.warning("profile reply rejected (%s, %s output tokens): %s", out.model, out.output_tokens, problem)
    raise UpstreamError("The model could not produce a complete brand profile. Try again or pick a stronger model.")
