"""Brand analysis API: start (after checking the links), poll, confirm the Facebook page, retry, edit the profile."""
import httpx
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel

from .. import analyses, brand, clients, config, discovery, enrichment, logos, media, preflight
from ..social import normalize_facebook, validate_public_url
from .settings import get_http

router = APIRouter(prefix="/api/analyses", tags=["analyses"])


class StartIn(BaseModel):
    website_url: str | None = None
    facebook_url: str | None = None
    find_facebook: bool = False  # website only: also look for its Facebook page and let the user confirm one


class PlanItem(BaseModel):
    hashtag: str
    videos: int


class SearchIn(BaseModel):
    plan: list[PlanItem]  # which hashtags to search and how many videos to read from each


class EnrichIn(BaseModel):
    usernames: list[str]
    videos: int = enrichment.DEFAULT_VIDEOS


class ConfirmIn(BaseModel):
    facebook_url: str | None = None  # None = continue with the website only


def _problem(message: str, field: str | None = None, status: int = 400) -> HTTPException:
    """`field` tells the form which input to blame."""
    return HTTPException(status_code=status, detail={"field": field, "message": message})


def _facebook(raw: str | None) -> str | None:
    if not raw or not raw.strip():
        return None
    url = normalize_facebook(raw if "://" in raw else f"https://{raw.strip()}")
    if not url:
        raise _problem("That doesn't look like a Facebook page link (e.g. https://www.facebook.com/yourbrand).", "facebook_url")
    return url


def _get(aid: str) -> dict:
    state = analyses.load(aid)
    if not state:
        raise _problem("Analysis not found", status=404)
    return state


@router.post("/estimate")
def estimate(body: StartIn, http: httpx.Client = Depends(get_http)) -> dict:
    """What this analysis would cost in Apify credits, and how many are left. Nothing paid runs here."""
    site, fb = (body.website_url or "").strip(), (body.facebook_url or "").strip()
    try:
        fb_url = _facebook(fb) if fb else None
    except HTTPException:
        fb_url = None  # the form reports a bad link on submit; here we just estimate without it
    cost = analyses.estimate(site or None, fb_url, body.find_facebook and not fb_url) if (site or fb_url) else None
    token, _ = config.apify_token()
    account = None
    if token:
        try:
            account = clients.apify_account(http, token)
        except (clients.UpstreamError, httpx.HTTPError):
            account = None  # shown as "unknown" rather than blocking the form
    llm = config.llm_config()
    return {"apify": cost, "account": account, "llm": {"model": llm.model, "provider": llm.provider} if llm else None}


@router.post("")
def start(body: StartIn, http: httpx.Client = Depends(get_http)) -> dict:
    site_raw, fb_raw = (body.website_url or "").strip(), (body.facebook_url or "").strip()
    if not site_raw and not fb_raw:
        raise _problem("Enter a website, a Facebook page, or both.", "website_url")
    if not config.apify_token()[0]:
        raise _problem("Apify token is not set. Add it in Settings first.")
    if not config.llm_config():
        raise _problem("No language model is configured. Add one in Settings first.")

    # Cheap checks first: nothing paid runs until both links are known to lead somewhere.
    warnings: list[str] = []
    website = facebook = None
    if site_raw:
        try:
            checked = preflight.check_website(validate_public_url(site_raw), http)
        except (ValueError, preflight.LinkError) as exc:
            raise _problem(str(exc), "website_url")
        website = checked.url
        if checked.warning:
            warnings.append(checked.warning)
    if fb_raw:
        url = _facebook(fb_raw)
        try:
            checked = preflight.check_facebook(url)
        except preflight.LinkError as exc:
            raise _problem(str(exc), "facebook_url")
        facebook = checked.url
        if checked.warning:
            warnings.append(checked.warning)

    discover = bool(website and not facebook and body.find_facebook)
    state = analyses.create(website, facebook, warnings, discover, analyses.eta_seconds(facebook, discover))
    analyses.spawn(analyses.run_discovery if discover else analyses.run_direct, state["id"])
    return analyses.public(state)


@router.get("")
def recent() -> list[dict]:
    return analyses.recent()


@router.get("/{aid}")
def read(aid: str) -> dict:
    return analyses.public(_get(aid))


def _image(content_type: str, data: bytes) -> Response:
    return Response(data, media_type=content_type, headers={
        "Cache-Control": "private, max-age=86400",
        "X-Content-Type-Options": "nosniff",
        "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; sandbox",  # an SVG can't run script
    })


@router.get("/{aid}/logo")
def logo(aid: str) -> Response:
    found = logos.load(aid)
    if not found:
        raise _problem("No logo", status=404)
    return _image(*found)


@router.get("/{aid}/media/{key}")
def picture(aid: str, key: str) -> Response:
    found = media.load(aid, key) if media.KEY.match(key) else None
    if not found:
        raise _problem("No such picture", status=404)
    return _image(*found)


@router.delete("/{aid}")
def delete(aid: str) -> dict:
    if not analyses.remove(aid):
        raise _problem("Analysis not found", status=404)
    return {"deleted": aid}


@router.post("/{aid}/profile")
def confirm_facebook(aid: str, body: ConfirmIn) -> dict:
    state = _get(aid)
    if not state["discover"] or state["status"] not in ("awaiting_facebook", "done", "error") or not state["internal"]["site_pages"]:
        raise _problem("This analysis is not ready for a profile yet.", status=409)
    return analyses.public(analyses.begin_profile(aid, _facebook(body.facebook_url)))


@router.post("/{aid}/retry")
def retry(aid: str) -> dict:
    if _get(aid)["status"] != "error":
        raise _problem("Only a failed analysis can be retried.", status=409)
    return analyses.public(analyses.retry(aid))


@router.put("/{aid}/profile")
def edit_profile(aid: str, body: brand.BrandProfile) -> dict:
    current = _get(aid)["profile"]
    if not current:
        raise _problem("There is no profile to edit yet.", status=409)
    # Only what the user may edit is taken from the request; everything else stays as the model wrote it.
    edited = {**current, "tiktok": body.tiktok.model_dump(), "creator_fit": body.creator_fit.model_dump()}
    changed = {key for key in ("tiktok", "creator_fit") if edited[key] != current.get(key)}
    edited["edited"] = sorted(set(current.get("edited", [])) | changed)
    return analyses.public(analyses.update(aid, lambda s: s.update(profile=edited)))


def _plan(body: SearchIn) -> list[dict]:
    try:
        return discovery.clean_plan([(item.hashtag, item.videos) for item in body.plan])
    except discovery.PlanError as exc:
        raise _problem(str(exc), "plan")


def _ready_profile(state: dict) -> dict:
    if not state["profile"]:
        raise _problem("Finish the brand profile before searching for creators.", status=409)
    return state["profile"]


@router.post("/{aid}/creators/estimate")
def creators_estimate(aid: str, body: SearchIn, http: httpx.Client = Depends(get_http)) -> dict:
    """What a creator search would cost, and how many Apify credits are left. Nothing paid runs here."""
    _ready_profile(_get(aid))
    cost = discovery.estimate(_plan(body))
    token, _ = config.apify_token()
    account = None
    if token:
        try:
            account = clients.apify_account(http, token)
        except (clients.UpstreamError, httpx.HTTPError):
            account = None
    return {"estimate": cost, "account": account}


@router.post("/{aid}/creators/search")
def creators_search(aid: str, body: SearchIn, http: httpx.Client = Depends(get_http)) -> dict:
    state = _get(aid)
    _ready_profile(state)
    plan = _plan(body)
    if state["creators"]["status"] == "running":
        raise _problem("A search is already running.", status=409)
    token, _ = config.apify_token()
    if not token:
        raise _problem("Apify token is not set. Add it in Settings first.")
    cost = discovery.estimate(plan)
    try:
        left = clients.apify_account(http, token)["remaining_usd"]
    except (clients.UpstreamError, httpx.HTTPError):
        left = None  # unknown: the run itself will fail clearly if the account is empty
    if left is not None and cost["usd"] > left:
        raise _problem(f"This search needs about ${cost['usd']:.2f} but only ${left:.2f} of Apify credit is left.")
    return analyses.public(discovery.start(aid, plan))


@router.get("/{aid}/creators")
def creators(aid: str, thai_min: float = 0.6, skip_private: bool = True, max_age_days: int = 30, min_followers: int = 10_000,
             max_followers: int = 0, skip_shops: bool = True) -> dict:
    """The found creators after the hard filters. A numeric filter set to 0 is off. Costs nothing."""
    found = _get(aid)["creators"]["items"]
    filters = discovery.Filters(thai_min or None, skip_private, max_age_days or None, min_followers or None, max_followers or None, skip_shops)
    kept, dropped = discovery.apply_filters(found, filters)
    return {"total": len(found), "kept": [discovery.public_creator(c) for c in kept], "dropped": dropped}


def _enrich_args(aid: str, body: EnrichIn) -> tuple[dict, list[str]]:
    state = _get(aid)
    try:
        return state, enrichment.clean(body.usernames, body.videos, {c["username"] for c in state["creators"]["items"]})
    except enrichment.EnrichError as exc:
        raise _problem(str(exc), "usernames")


@router.post("/{aid}/creators/enrich/estimate")
def enrich_estimate(aid: str, body: EnrichIn, http: httpx.Client = Depends(get_http)) -> dict:
    """What reading the chosen creators' latest videos would cost, and how many Apify credits are left."""
    _, names = _enrich_args(aid, body)
    token, _ = config.apify_token()
    account = None
    if token:
        try:
            account = clients.apify_account(http, token)
        except (clients.UpstreamError, httpx.HTTPError):
            account = None
    return {"estimate": enrichment.estimate(names, body.videos), "account": account}


@router.post("/{aid}/creators/enrich")
def enrich(aid: str, body: EnrichIn, http: httpx.Client = Depends(get_http)) -> dict:
    state, names = _enrich_args(aid, body)
    if state["creators"]["status"] == "running" or state["creators"]["enrich"].get("status") == "running":
        raise _problem("A search or a read is already running.", status=409)
    token, _ = config.apify_token()
    if not token:
        raise _problem("Apify token is not set. Add it in Settings first.")
    cost = enrichment.estimate(names, body.videos)
    try:
        left = clients.apify_account(http, token)["remaining_usd"]
    except (clients.UpstreamError, httpx.HTTPError):
        left = None
    if left is not None and cost["usd"] > left:
        raise _problem(f"This read needs about ${cost['usd']:.2f} but only ${left:.2f} of Apify credit is left.")
    return analyses.public(enrichment.start(aid, names, body.videos))


def _creator(aid: str, username: str) -> dict:
    creator = next((c for c in _get(aid)["creators"]["items"] if c["username"] == username), None)
    if not creator:
        raise _problem("No such creator in this search", status=404)
    return creator


@router.get("/{aid}/creators/{username}")
def creator(aid: str, username: str) -> dict:
    return discovery.public_creator(_creator(aid, username))


@router.get("/{aid}/creators/{username}/picture/{kind}")
def creator_picture(aid: str, username: str, kind: str, http: httpx.Client = Depends(get_http)) -> Response:
    """Avatar or video cover of a creator, downloaded by the server the first time it is asked for."""
    if kind != "avatar" and not (kind.isdigit() and int(kind) < discovery.SAMPLES):
        raise _problem("No such picture", status=404)
    found = discovery.picture(http, aid, _creator(aid, username), kind)
    if not found:
        raise _problem("No such picture", status=404)
    return _image(*found)
