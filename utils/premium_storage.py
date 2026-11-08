import json
import os
import re
from copy import deepcopy
from typing import Any

LEGACY_PREMIUM_DATA_PATH = os.path.join("data", "premium.json")
PREMIUM_DATA_PATH = os.path.join("data", "private", "premium.json")

WEBHOOK_URL_RE = re.compile(
    r"^https://discord(?:app)?\.com/api/webhooks/\d+/[A-Za-z0-9._-]+$"
)
UNSAFE_WEBHOOK_KEYS = {
    "log_webhook",
    "webhook",
    "webhook_url",
    "discord_webhook",
    "discord_webhook_url",
}


def default_premium_data() -> dict[str, Any]:
    return {
        "subscriptions": {},
        "user_subscriptions": {},
        "vanity": {
            "roles": {},
            "settings": {},
        },
        "grandfathered": [],
    }


def sanitize_vanity_settings(settings: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    sanitized: dict[str, Any] = {}
    changed = False

    for key, value in settings.items():
        if key.lower() in UNSAFE_WEBHOOK_KEYS:
            changed = True
            continue
        if isinstance(value, str) and WEBHOOK_URL_RE.match(value):
            changed = True
            continue
        sanitized[key] = value

    return sanitized, changed


def sanitize_premium_data(data: Any) -> tuple[dict[str, Any], bool]:
    if not isinstance(data, dict):
        return default_premium_data(), True

    sanitized = deepcopy(data)
    changed = False

    subscriptions = sanitized.get("subscriptions")
    if not isinstance(subscriptions, dict):
        sanitized["subscriptions"] = {}
        changed = True

    user_subscriptions = sanitized.get("user_subscriptions")
    if not isinstance(user_subscriptions, dict):
        sanitized["user_subscriptions"] = {}
        changed = True

    vanity = sanitized.get("vanity")
    if not isinstance(vanity, dict):
        sanitized["vanity"] = {"roles": {}, "settings": {}}
        vanity = sanitized["vanity"]
        changed = True

    roles = vanity.get("roles")
    if not isinstance(roles, dict):
        vanity["roles"] = {}
        changed = True

    settings_map = vanity.get("settings")
    if not isinstance(settings_map, dict):
        vanity["settings"] = {}
        settings_map = vanity["settings"]
        changed = True

    for guild_id, settings in list(settings_map.items()):
        if not isinstance(settings, dict):
            settings_map[guild_id] = {}
            changed = True
            continue

        clean_settings, settings_changed = sanitize_vanity_settings(settings)
        if settings_changed:
            settings_map[guild_id] = clean_settings
            changed = True

    grandfathered = sanitized.get("grandfathered")
    if not isinstance(grandfathered, list):
        sanitized["grandfathered"] = []
        changed = True

    return sanitized, changed


_PREMIUM_CACHE: dict[str, Any] | None = None
_PREMIUM_CACHE_MTIME: float = -1.0
_PREMIUM_CACHE_PATH: str | None = None


def load_premium_data() -> dict[str, Any]:
    global _PREMIUM_CACHE, _PREMIUM_CACHE_MTIME, _PREMIUM_CACHE_PATH

    source_path = None
    if os.path.exists(PREMIUM_DATA_PATH):
        source_path = PREMIUM_DATA_PATH
    elif os.path.exists(LEGACY_PREMIUM_DATA_PATH):
        source_path = LEGACY_PREMIUM_DATA_PATH

    if source_path is None:
        return default_premium_data()

    try:
        mtime = os.path.getmtime(source_path)
    except OSError:
        mtime = -1.0

    if (
        _PREMIUM_CACHE is not None
        and _PREMIUM_CACHE_PATH == source_path
        and mtime == _PREMIUM_CACHE_MTIME
        and mtime >= 0
    ):
        return _PREMIUM_CACHE

    try:
        with open(source_path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return default_premium_data()

    sanitized, changed = sanitize_premium_data(data)
    if changed or source_path != PREMIUM_DATA_PATH:
        save_premium_data(sanitized)
        return sanitized

    _PREMIUM_CACHE = sanitized
    _PREMIUM_CACHE_MTIME = mtime
    _PREMIUM_CACHE_PATH = source_path
    return sanitized


def save_premium_data(data: Any) -> None:
    global _PREMIUM_CACHE, _PREMIUM_CACHE_MTIME, _PREMIUM_CACHE_PATH
    sanitized, _ = sanitize_premium_data(data)
    os.makedirs(os.path.dirname(PREMIUM_DATA_PATH), exist_ok=True)
    with open(PREMIUM_DATA_PATH, "w", encoding="utf-8") as handle:
        json.dump(sanitized, handle, indent=2, ensure_ascii=False)
    try:
        _PREMIUM_CACHE = sanitized
        _PREMIUM_CACHE_PATH = PREMIUM_DATA_PATH
        _PREMIUM_CACHE_MTIME = os.path.getmtime(PREMIUM_DATA_PATH)
    except OSError:
        _PREMIUM_CACHE = None
        _PREMIUM_CACHE_MTIME = -1.0
