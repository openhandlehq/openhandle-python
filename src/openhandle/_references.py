from __future__ import annotations

import re
from urllib.parse import urlsplit

from openhandle._errors import OpenHandleReferenceError, ReferenceMismatchError

NUMERIC_ID = re.compile(r"^[0-9]+$")
INSTAGRAM_NAME = re.compile(r"^[A-Za-z0-9._]{1,30}$")
TIKTOK_NAME = re.compile(r"^[A-Za-z0-9._]{2,24}$")
TWITTER_NAME = re.compile(r"^[A-Za-z0-9_]{1,15}$")
SHORTCODE = re.compile(r"^[A-Za-z0-9_-]+$")

SUPPORTED_HOSTS = (
    "instagram.com",
    "tiktok.com",
    "m.tiktok.com",
    "x.com",
    "twitter.com",
    "mobile.twitter.com",
)

INSTAGRAM_RESERVED = ("p", "reel", "reels", "tv", "explore", "accounts", "direct", "stories")
TWITTER_RESERVED = ("home", "explore", "search", "settings", "messages", "notifications", "i", "intent", "share")


def resolve_selector(
    reference: object,
    *,
    username: object = None,
    id: object = None,
    url: object = None,
    platform: str,
    resource: str,
) -> str:
    provided = [
        (kind, value)
        for kind, value in (("raw", reference), ("username", username), ("id", id), ("url", url))
        if value is not None
    ]
    if len(provided) != 1:
        raise OpenHandleReferenceError(
            "A reference must be a positional string or exactly one of the username, id, or url keywords."
        )
    kind, value = provided[0]
    if isinstance(value, (int, float)):
        raise OpenHandleReferenceError("Platform IDs are opaque strings; numeric reference values are not accepted.")
    if not isinstance(value, str):
        raise OpenHandleReferenceError("Reference values must be strings.")
    return resolve_reference(kind, value, platform, resource)


def resolve_reference(kind: str, value: str, platform: str, resource: str) -> str:
    value = value.strip()
    if not value:
        raise OpenHandleReferenceError("Reference values must not be empty.")
    if kind == "raw":
        if looks_like_supported_social_url(value):
            return resolve_url_reference(value, platform, resource)
        if resource == "profile":
            return username_reference(value, platform)
        return value
    if kind == "username":
        if resource != "profile":
            raise OpenHandleReferenceError(f"The {resource} resource does not accept username references.")
        return username_reference(value, platform)
    if kind == "id":
        return value
    if kind == "url":
        return resolve_url_reference(value, platform, resource)
    raise OpenHandleReferenceError(f"Unknown reference kind {kind}.")


def resolve_url_reference(value: str, platform: str, resource: str) -> str:
    resolved_platform, resolved_resource, identifier = resolve_social_url(value)
    if resolved_platform != platform or resolved_resource != resource:
        raise ReferenceMismatchError(platform, resource, resolved_platform, resolved_resource)
    return identifier


def looks_like_supported_social_url(reference: str) -> bool:
    value = reference.strip().lower()
    scheme = value.find("://")
    has_scheme = scheme >= 0
    if has_scheme:
        value = value[scheme + 3 :]
    separator = min(
        (index for index in (value.find("/"), value.find("?"), value.find("#")) if index >= 0),
        default=-1,
    )
    if not has_scheme and separator < 0:
        return False
    authority = value[:separator] if separator >= 0 else value
    credentials = authority.rfind("@")
    if credentials >= 0:
        authority = authority[credentials + 1 :]
    port = authority.rfind(":")
    if port >= 0:
        authority = authority[:port]
    host = authority.removeprefix("www.")
    return host in SUPPORTED_HOSTS


def username_reference(reference: str, platform: str) -> str:
    username = reference.removeprefix("@")
    if platform == "instagram":
        pattern = INSTAGRAM_NAME
    elif platform == "tiktok":
        pattern = TIKTOK_NAME
    else:
        pattern = TWITTER_NAME
    if not pattern.match(username):
        raise OpenHandleReferenceError(f"Invalid {platform} username.")
    return f"@{username}"


def resolve_social_url(reference: str) -> tuple[str, str, str]:
    target = reference if "://" in reference else f"https://{reference}"
    try:
        parsed = urlsplit(target)
    except ValueError as cause:
        raise OpenHandleReferenceError(f"Invalid social URL: {cause}.") from cause
    if parsed.scheme not in ("http", "https") or parsed.username or parsed.password:
        raise OpenHandleReferenceError("Social URLs must use HTTP or HTTPS and cannot contain credentials.")

    host = (parsed.hostname or "").lower().removeprefix("www.")
    parts = [part for part in parsed.path.split("/") if part]
    if host == "instagram.com":
        return resolve_instagram_url(parts)
    if host in ("tiktok.com", "m.tiktok.com"):
        return resolve_tiktok_url(parts)
    if host in ("x.com", "twitter.com", "mobile.twitter.com"):
        return resolve_twitter_url(parts)
    raise OpenHandleReferenceError(f"Unsupported social domain {host}.")


def resolve_instagram_url(parts: list[str]) -> tuple[str, str, str]:
    if len(parts) == 2 and parts[0] in ("p", "reel", "tv") and SHORTCODE.match(parts[1]):
        return ("instagram", "post", parts[1])
    if len(parts) == 3 and parts[0] == "stories" and parts[1] == "highlights" and NUMERIC_ID.match(parts[2]):
        return ("instagram", "highlight", parts[2])
    if len(parts) == 3 and parts[0] == "stories" and INSTAGRAM_NAME.match(parts[1]) and NUMERIC_ID.match(parts[2]):
        return ("instagram", "story", parts[2])
    if len(parts) == 1 and INSTAGRAM_NAME.match(parts[0]) and parts[0].lower() not in INSTAGRAM_RESERVED:
        return ("instagram", "profile", f"@{parts[0]}")
    raise OpenHandleReferenceError("Unsupported Instagram URL.")


def resolve_tiktok_url(parts: list[str]) -> tuple[str, str, str]:
    first = parts[0] if parts else ""
    username = first[1:] if first.startswith("@") else ""
    if not TIKTOK_NAME.match(username):
        raise OpenHandleReferenceError("Unsupported TikTok URL.")
    if len(parts) == 3 and parts[1] == "video" and NUMERIC_ID.match(parts[2]):
        return ("tiktok", "post", parts[2])
    if len(parts) == 1:
        return ("tiktok", "profile", f"@{username}")
    raise OpenHandleReferenceError("Unsupported TikTok URL.")


def resolve_twitter_url(parts: list[str]) -> tuple[str, str, str]:
    if len(parts) >= 3 and parts[1].lower() == "status" and TWITTER_NAME.match(parts[0]) and NUMERIC_ID.match(parts[2]):
        return ("twitter", "post", parts[2])
    if (
        len(parts) == 4
        and parts[0] == "i"
        and parts[1] == "web"
        and parts[2] == "status"
        and NUMERIC_ID.match(parts[3])
    ):
        return ("twitter", "post", parts[3])
    if len(parts) == 1 and TWITTER_NAME.match(parts[0]) and parts[0].lower() not in TWITTER_RESERVED:
        return ("twitter", "profile", f"@{parts[0]}")
    raise OpenHandleReferenceError("Unsupported Twitter URL.")
