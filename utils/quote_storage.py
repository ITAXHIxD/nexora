"""
utils/quote_storage.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Storage and persistence layer for the Nexora Quote System.
Manages server configuration (destination channel, toggles, exclusions)
with dual persistence:
  • Primary: MongoDB Atlas collection `quote_settings`
  • Secondary: Local fallback JSON in `data/private/quotes.json`

Stateless Quote Cards:
Quote messages are stateless — quoter ownership is embedded directly
into Discord's button `custom_id` (`quote:delete:{user_id}`).
No message content or quote records are stored, ensuring complete privacy
and zero database bloat.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import json
import logging
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

QUOTES_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data",
    "private",
    "quotes.json",
)


@dataclass
class GuildQuoteSettings:
    """Per-guild configuration settings for the quote system."""
    guild_id: int = 0
    destination_channel_id: Optional[int] = None
    enabled: bool = True
    allowed_roles: List[int] = field(default_factory=list)
    excluded_channels: List[int] = field(default_factory=list)
    log_channel_id: Optional[int] = None
    render_style: str = "card"  # "card" (PIL image + embed) or "embed"
    allow_cross_channel: bool = True
    quotes_count: int = 0  # Lightweight counter of quotes generated

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any], guild_id: int = 0) -> "GuildQuoteSettings":
        if not isinstance(data, dict):
            return cls(guild_id=guild_id)
        return cls(
            guild_id=int(data.get("guild_id", guild_id) or guild_id),
            destination_channel_id=(
                int(data["destination_channel_id"])
                if data.get("destination_channel_id")
                else None
            ),
            enabled=bool(data.get("enabled", True)),
            allowed_roles=[int(r) for r in data.get("allowed_roles", []) if str(r).isdigit()],
            excluded_channels=[int(c) for c in data.get("excluded_channels", []) if str(c).isdigit()],
            log_channel_id=int(data["log_channel_id"]) if data.get("log_channel_id") else None,
            render_style=str(data.get("render_style", "card")).lower(),
            allow_cross_channel=bool(data.get("allow_cross_channel", True)),
            quotes_count=int(data.get("quotes_count", 0)),
        )


def default_quotes_storage() -> Dict[str, Any]:
    return {
        "version": 2,
        "guild_settings": {},
    }


def load_local_quotes_data() -> Dict[str, Any]:
    if not os.path.exists(QUOTES_FILE):
        return default_quotes_storage()
    try:
        with open(QUOTES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if not isinstance(data, dict):
                return default_quotes_storage()
            data.setdefault("guild_settings", {})
            return data
    except Exception as exc:
        logger.error("Failed to read %s: %s", QUOTES_FILE, exc)
        return default_quotes_storage()


def save_local_quotes_data(data: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(QUOTES_FILE), exist_ok=True)
    temp_file = f"{QUOTES_FILE}.tmp"
    try:
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(temp_file, QUOTES_FILE)
    except Exception as exc:
        logger.error("Failed to write %s: %s", QUOTES_FILE, exc)
        if os.path.exists(temp_file):
            try:
                os.remove(temp_file)
            except OSError:
                pass
        raise


class QuoteStorage:
    """Manages persistence for quote server settings with an in-memory cache."""

    def __init__(self, bot):
        self.bot = bot
        self._settings_cache: Dict[int, GuildQuoteSettings] = {}

    def _get_settings_col(self):
        db = getattr(self.bot, "mongo_db", None)
        return db["quote_settings"] if db is not None else None

    async def get_settings(self, guild_id: int) -> GuildQuoteSettings:
        """Fetch guild settings with RAM cache first, Mongo second, falling back to local JSON."""
        gid = int(guild_id)
        if gid in self._settings_cache:
            return self._settings_cache[gid]

        col = self._get_settings_col()
        if col is not None:
            try:
                doc = await col.find_one({"_id": gid})
                if isinstance(doc, dict):
                    settings = GuildQuoteSettings.from_dict(doc.get("settings", {}), guild_id=gid)
                    self._settings_cache[gid] = settings
                    return settings
            except Exception as exc:
                logger.warning("Quote Mongo settings read failed for guild %s: %s", gid, exc)

        local_data = load_local_quotes_data()
        raw_settings = local_data.get("guild_settings", {}).get(str(gid))
        if isinstance(raw_settings, dict):
            settings = GuildQuoteSettings.from_dict(raw_settings, guild_id=gid)
            self._settings_cache[gid] = settings
            return settings

        settings = GuildQuoteSettings(guild_id=gid)
        self._settings_cache[gid] = settings
        return settings

    async def save_settings(self, guild_id: int, settings: GuildQuoteSettings) -> None:
        """Save guild quote settings to RAM cache, Mongo, and mirror locally."""
        gid = int(guild_id)
        self._settings_cache[gid] = settings
        payload = settings.to_dict()
        col = self._get_settings_col()
        if col is not None:
            try:
                await col.update_one(
                    {"_id": gid},
                    {"$set": {"settings": payload, "updated_at": datetime.now(timezone.utc).isoformat()}},
                    upsert=True,
                )
            except Exception as exc:
                logger.error("Quote Mongo settings save failed for guild %s: %s", gid, exc)

        try:
            local_data = load_local_quotes_data()
            local_data.setdefault("guild_settings", {})[str(gid)] = payload
            save_local_quotes_data(local_data)
        except Exception as exc:
            logger.error("Quote local settings save failed for guild %s: %s", gid, exc)

    async def increment_quote_count(self, guild_id: int) -> None:
        """Atomically increment the quote usage counter for a guild."""
        gid = int(guild_id)
        if gid in self._settings_cache:
            self._settings_cache[gid].quotes_count += 1

        col = self._get_settings_col()
        if col is not None:
            try:
                await col.update_one(
                    {"_id": gid},
                    {"$inc": {"settings.quotes_count": 1}},
                    upsert=True,
                )
            except Exception as exc:
                logger.debug("Mongo increment quote count failed: %s", exc)

        try:
            local_data = load_local_quotes_data()
            g_entry = local_data.setdefault("guild_settings", {}).setdefault(str(gid), {})
            g_entry["quotes_count"] = int(g_entry.get("quotes_count", 0)) + 1
            save_local_quotes_data(local_data)
        except Exception as exc:
            logger.debug("Local increment quote count failed: %s", exc)
