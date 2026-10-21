"""
utils/quote_storage.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Storage and persistence layer for the Nexora Quote System.
Supports dual persistence:
  • Primary: MongoDB Atlas collections `quote_settings` and `quotes`
  • Secondary: Local fallback JSON in `data/private/quotes.json`
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import json
import logging
import os
import uuid
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
        )


@dataclass
class QuoteRecord:
    """Metadata record for a saved quote."""
    quote_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    guild_id: int = 0
    source_channel_id: int = 0
    source_message_id: int = 0
    quote_channel_id: int = 0
    quote_message_id: int = 0
    quoter_id: int = 0
    author_id: int = 0
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    jump_url: str = ""
    content_preview: str = ""
    has_image: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "QuoteRecord":
        if not isinstance(data, dict):
            return cls()
        return cls(
            quote_id=str(data.get("quote_id") or uuid.uuid4().hex[:8]),
            guild_id=int(data.get("guild_id", 0) or 0),
            source_channel_id=int(data.get("source_channel_id", 0) or 0),
            source_message_id=int(data.get("source_message_id", 0) or 0),
            quote_channel_id=int(data.get("quote_channel_id", 0) or 0),
            quote_message_id=int(data.get("quote_message_id", 0) or 0),
            quoter_id=int(data.get("quoter_id", 0) or 0),
            author_id=int(data.get("author_id", 0) or 0),
            created_at=str(
                data.get("created_at")
                or datetime.now(timezone.utc).isoformat()
            ),
            jump_url=str(data.get("jump_url", "")),
            content_preview=str(data.get("content_preview", ""))[:200],
            has_image=bool(data.get("has_image", False)),
        )


def default_quotes_storage() -> Dict[str, Any]:
    return {
        "version": 1,
        "guild_settings": {},
        "quotes": {},
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
            data.setdefault("quotes", {})
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
    """Manages persistence for quote settings and quote records."""

    def __init__(self, bot):
        self.bot = bot

    def _get_settings_col(self):
        db = getattr(self.bot, "mongo_db", None)
        return db["quote_settings"] if db is not None else None

    def _get_quotes_col(self):
        db = getattr(self.bot, "mongo_db", None)
        return db["quotes"] if db is not None else None

    async def get_settings(self, guild_id: int) -> GuildQuoteSettings:
        """Fetch guild settings with Mongo first, falling back to local JSON."""
        col = self._get_settings_col()
        if col is not None:
            try:
                doc = await col.find_one({"_id": int(guild_id)})
                if isinstance(doc, dict):
                    return GuildQuoteSettings.from_dict(doc.get("settings", {}), guild_id=guild_id)
            except Exception as exc:
                logger.warning("Quote Mongo settings read failed for guild %s: %s", guild_id, exc)

        local_data = load_local_quotes_data()
        raw_settings = local_data.get("guild_settings", {}).get(str(guild_id))
        if isinstance(raw_settings, dict):
            return GuildQuoteSettings.from_dict(raw_settings, guild_id=guild_id)

        return GuildQuoteSettings(guild_id=guild_id)

    async def save_settings(self, guild_id: int, settings: GuildQuoteSettings) -> None:
        """Save guild quote settings to Mongo and mirror locally."""
        payload = settings.to_dict()
        col = self._get_settings_col()
        if col is not None:
            try:
                await col.update_one(
                    {"_id": int(guild_id)},
                    {"$set": {"settings": payload, "updated_at": datetime.now(timezone.utc).isoformat()}},
                    upsert=True,
                )
            except Exception as exc:
                logger.error("Quote Mongo settings save failed for guild %s: %s", guild_id, exc)

        try:
            local_data = load_local_quotes_data()
            local_data.setdefault("guild_settings", {})[str(guild_id)] = payload
            save_local_quotes_data(local_data)
        except Exception as exc:
            logger.error("Quote local settings save failed for guild %s: %s", guild_id, exc)

    async def add_quote(self, quote: QuoteRecord) -> None:
        """Store a new quote record in Mongo and local storage."""
        payload = quote.to_dict()
        col = self._get_quotes_col()
        if col is not None:
            try:
                await col.update_one(
                    {"_id": quote.quote_id},
                    {"$set": payload},
                    upsert=True,
                )
            except Exception as exc:
                logger.error("Quote Mongo record save failed for %s: %s", quote.quote_id, exc)

        try:
            local_data = load_local_quotes_data()
            local_data.setdefault("quotes", {})[quote.quote_id] = payload
            save_local_quotes_data(local_data)
        except Exception as exc:
            logger.error("Quote local record save failed for %s: %s", quote.quote_id, exc)

    async def get_quote(self, quote_id: str) -> Optional[QuoteRecord]:
        """Retrieve a quote record by quote_id."""
        if not quote_id:
            return None
        col = self._get_quotes_col()
        if col is not None:
            try:
                doc = await col.find_one({"_id": str(quote_id)})
                if isinstance(doc, dict):
                    return QuoteRecord.from_dict(doc)
            except Exception as exc:
                logger.warning("Quote Mongo get failed for %s: %s", quote_id, exc)

        local_data = load_local_quotes_data()
        raw_quote = local_data.get("quotes", {}).get(str(quote_id))
        if isinstance(raw_quote, dict):
            return QuoteRecord.from_dict(raw_quote)

        return None

    async def get_quote_by_message(self, guild_id: int, quote_message_id: int) -> Optional[QuoteRecord]:
        """Find a quote record by the posted quote message ID in a guild."""
        col = self._get_quotes_col()
        if col is not None:
            try:
                doc = await col.find_one({
                    "guild_id": int(guild_id),
                    "quote_message_id": int(quote_message_id),
                })
                if isinstance(doc, dict):
                    return QuoteRecord.from_dict(doc)
            except Exception as exc:
                logger.warning("Quote Mongo get by message failed: %s", exc)

        local_data = load_local_quotes_data()
        for q_data in local_data.get("quotes", {}).values():
            if isinstance(q_data, dict):
                if int(q_data.get("guild_id", 0)) == int(guild_id) and int(q_data.get("quote_message_id", 0)) == int(quote_message_id):
                    return QuoteRecord.from_dict(q_data)

        return None

    async def delete_quote(self, quote_id: str) -> bool:
        """Delete a quote record by quote_id."""
        if not quote_id:
            return False
        deleted = False
        col = self._get_quotes_col()
        if col is not None:
            try:
                res = await col.delete_one({"_id": str(quote_id)})
                if res.deleted_count > 0:
                    deleted = True
            except Exception as exc:
                logger.error("Quote Mongo delete failed for %s: %s", quote_id, exc)

        try:
            local_data = load_local_quotes_data()
            quotes_dict = local_data.get("quotes", {})
            if str(quote_id) in quotes_dict:
                del quotes_dict[str(quote_id)]
                save_local_quotes_data(local_data)
                deleted = True
        except Exception as exc:
            logger.error("Quote local delete failed for %s: %s", quote_id, exc)

        return deleted

    async def get_guild_quotes_count(self, guild_id: int) -> int:
        """Count total quotes saved for a guild."""
        col = self._get_quotes_col()
        if col is not None:
            try:
                return await col.count_documents({"guild_id": int(guild_id)})
            except Exception as exc:
                logger.warning("Quote Mongo count failed for %s: %s", guild_id, exc)

        local_data = load_local_quotes_data()
        count = 0
        for q in local_data.get("quotes", {}).values():
            if isinstance(q, dict) and int(q.get("guild_id", 0)) == int(guild_id):
                count += 1
        return count
