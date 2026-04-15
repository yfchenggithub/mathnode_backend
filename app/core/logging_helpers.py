from __future__ import annotations

from collections.abc import Mapping

_SENSITIVE_KEYWORDS = {
    "authorization",
    "token",
    "password",
    "secret",
    "session_key",
    "cookie",
    "set-cookie",
    "x-token",
}


def summarize_text(value: object, max_length: int = 120) -> str:
    text = str(value).strip()
    if len(text) <= max_length:
        return text
    if max_length <= 3:
        return text[:max_length]
    return f"{text[: max_length - 3]}..."


def mask_sensitive(value: str | None, left: int = 3, right: int = 2) -> str:
    if value is None:
        return ""

    raw = value.strip()
    if not raw:
        return ""

    if len(raw) <= left + right:
        return "***"
    return f"{raw[:left]}***{raw[-right:]}"


def is_sensitive_key(key: str) -> bool:
    key_lower = key.strip().lower()
    return any(part in key_lower for part in _SENSITIVE_KEYWORDS)


def summarize_query_params(
    params: Mapping[str, object],
    *,
    max_items: int = 8,
    max_value_length: int = 100,
) -> str:
    if not params:
        return "{}"

    parts: list[str] = []
    for idx, (key, value) in enumerate(params.items()):
        if idx >= max_items:
            parts.append(f"...(+{len(params) - max_items} more)")
            break

        if is_sensitive_key(key):
            value_text = "[REDACTED]"
        else:
            value_text = summarize_text(value, max_length=max_value_length)
        parts.append(f"{key}={value_text!r}")

    return "{" + ", ".join(parts) + "}"


def summarize_validation_errors(errors: list[dict], *, limit: int = 5) -> str:
    if not errors:
        return ""

    parts: list[str] = []
    for err in errors[:limit]:
        loc_value = err.get("loc", ())
        if isinstance(loc_value, (list, tuple)):
            loc = ".".join(str(item) for item in loc_value)
        else:
            loc = str(loc_value)

        msg = summarize_text(err.get("msg", ""), max_length=100)
        parts.append(f"{loc}: {msg}")

    if len(errors) > limit:
        parts.append(f"...(+{len(errors) - limit} more)")

    return "; ".join(parts)
