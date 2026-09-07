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


def load_premium_data() -> dict[str, Any]:
    source_path = None
    if os.path.exists(PREMIUM_DATA_PATH):
        source_path = PREMIUM_DATA_PATH
    elif os.path.exists(LEGACY_PREMIUM_DATA_PATH):
        source_path = LEGACY_PREMIUM_DATA_PATH

    if source_path is None:
        return default_premium_data()

    try:
        with open(source_path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return default_premium_data()

    sanitized, changed = sanitize_premium_data(data)
    if changed or source_path != PREMIUM_DATA_PATH:
        save_premium_data(sanitized)

    return sanitized


def save_premium_data(data: Any) -> None:
    sanitized, _ = sanitize_premium_data(data)
    os.makedirs(os.path.dirname(PREMIUM_DATA_PATH), exist_ok=True)
    with open(PREMIUM_DATA_PATH, "w", encoding="utf-8") as handle:
        json.dump(sanitized, handle, indent=2, ensure_ascii=False)
