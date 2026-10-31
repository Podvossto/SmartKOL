"""The ranked creator list as a CSV file a marketer can open in Excel or Sheets.

Only public, business-relevant fields go in: no bio (it can carry contact details), no picture links.
"""
import csv
import io

from . import discovery

COLUMNS = [
    ("rank", lambda c: c.get("rank")),
    ("username", lambda c: c["username"]),
    ("name", lambda c: c["nickname"]),
    ("tiktok_url", lambda c: c["url"]),
    ("contact_in_bio", lambda c: " | ".join(discovery.contacts(c.get("bio")))),
    ("followers", lambda c: c["followers"]),
    ("total_score", lambda c: c.get("total")),
    ("fit_score", lambda c: (c.get("score") or {}).get("relevance")),
    ("engagement_score", lambda c: (c.get("score") or {}).get("engagement")),
    ("audience_fit_score_estimated", lambda c: (c.get("score") or {}).get("audience")),
    ("audience_confidence", lambda c: (c.get("score") or {}).get("confidence")),
    ("audience_age_estimated", lambda c: ((c.get("score") or {}).get("viewers") or {}).get("age")),
    ("audience_gender_estimated", lambda c: ((c.get("score") or {}).get("viewers") or {}).get("gender")),
    ("audience_interests_estimated", lambda c: ", ".join(((c.get("score") or {}).get("viewers") or {}).get("interests") or [])),
    ("activity_score", lambda c: (c.get("score") or {}).get("activity")),
    ("why_it_fits", lambda c: (c.get("score") or {}).get("reason")),
    ("audience_note", lambda c: (c.get("score") or {}).get("audience_reason")),
    ("warnings", lambda c: " | ".join((c.get("score") or {}).get("flags") or [])),
    ("typical_views", lambda c: (c.get("metrics") or {}).get("median_views", c.get("median_views"))),
    ("engagement_rate_pct", lambda c: _pct((c.get("metrics") or {}).get("median_er"))),
    ("posts_per_week", lambda c: (c.get("metrics") or {}).get("posts_per_week")),
    ("last_post", lambda c: ((c.get("metrics") or {}).get("last_post") or c.get("last_post") or "")[:10]),
    ("ad_share_pct", lambda c: _pct((c.get("metrics") or {}).get("ad_share"))),
    ("videos_read", lambda c: (c.get("metrics") or {}).get("videos")),
    ("account_type", lambda c: "competitor" if c.get("competitor") else c.get("kind")),
]


def _pct(value):
    return None if value is None else round(value * 100, 1)


def _safe(value) -> str:
    """A spreadsheet runs a cell that starts with = + - @ as a formula; a caption or name must never be one."""
    text = "" if value is None else str(value)
    return "'" + text if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text


def creators_csv(creators: list[dict]) -> str:
    """Ranked creators first (best total first), then the ones not scored, biggest first. Starts with a byte-order mark so
    Excel reads the Thai names as UTF-8."""
    ordered = sorted(creators, key=lambda c: (c.get("rank") is None, c.get("rank") or 0, -(c.get("followers") or 0)))
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\r\n")
    writer.writerow([name for name, _ in COLUMNS])
    for c in ordered:
        writer.writerow([_safe(get(c)) for _, get in COLUMNS])
    return "﻿" + out.getvalue()
