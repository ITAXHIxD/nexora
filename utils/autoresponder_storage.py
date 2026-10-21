"""
utils/autoresponder_storage.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Storage and persistence layer for Nexora Autoresponder system.
Supports dual persistence:
  • Primary: MongoDB Atlas collection `autoresponders`
  • Secondary: Local fallback JSON in `data/private/autoresponders.json`
  • Legacy auto-migration from `custom_replies` in `data/private/premium.json`
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from utils.autoresponder_engine import (
    AutoResponderItem,
    GuildAutoResponderSettings,
)
from utils.premium_storage import load_premium_data

logger = logging.getLogger(__name__)

AUTORESPONDER_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data",
    "private",
    "autoresponders.json",
)


def default_autoresponder_data() -> Dict[str, Any]:
    return {
        "version": 1,
        "guilds": {},
    }


def load_local_autoresponder_data() -> Dict[str, Any]:
    if not os.path.exists(AUTORESPONDER_FILE):
        return default_autoresponder_data()
    try:
        with open(AUTORESPONDER_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if not isinstance(data, dict):
                return default_autoresponder_data()
            if "guilds" not in data:
                data["guilds"] = {}
            return data
    except Exception as exc:
        logger.error("Failed to read %s: %s", AUTORESPONDER_FILE, exc)
        return default_autoresponder_data()


def save_local_autoresponder_data(data: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(AUTORESPONDER_FILE), exist_ok=True)
    temp_file = f"{AUTORESPONDER_FILE}.tmp"
    try:
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(temp_file, AUTORESPONDER_FILE)
    except Exception as exc:
        logger.error("Failed to write %s: %s", AUTORESPONDER_FILE, exc)
        if os.path.exists(temp_file):
            try:
                os.remove(temp_file)
            except OSError:
                pass
        raise


class AutoResponderStorage:
    """Manages persistence for autoresponder settings and items with Mongo and local JSON fallback."""

    def __init__(self, bot):
        self.bot = bot

    def _get_col(self):
        db = getattr(self.bot, "mongo_db", None)
        return db["autoresponders"] if db is not None else None

    async def get_guild_data(
        self, guild_id: int
    ) -> Tuple[GuildAutoResponderSettings, List[AutoResponderItem]]:
        """
        Fetch settings and responders for a guild.
        First checks Mongo, falls back to local JSON, and handles legacy migration if empty.
        """
        col = self._get_col()
        if col is not None:
            try:
                doc = await col.find_one({"_id": int(guild_id)})
                if isinstance(doc, dict):
                    settings = GuildAutoResponderSettings.from_dict(doc.get("settings", {}))
                    raw_items = doc.get("responders", [])
                    items = [AutoResponderItem.from_dict(r) for r in raw_items if isinstance(r, dict)]
                    return settings, items
            except Exception as exc:
                logger.warning("Autoresponder Mongo read failed for guild %s: %s", guild_id, exc)

        # Local storage fallback
        local_data = load_local_autoresponder_data()
        guild_entry = local_data.get("guilds", {}).get(str(guild_id))
        if isinstance(guild_entry, dict):
            settings = GuildAutoResponderSettings.from_dict(guild_entry.get("settings", {}))
            raw_items = guild_entry.get("responders", [])
            items = [AutoResponderItem.from_dict(r) for r in raw_items if isinstance(r, dict)]
            return settings, items

        # Check for legacy migration from premium.json / mongo premium collection
        migrated_items = await self._check_legacy_migration(guild_id)
        settings = GuildAutoResponderSettings()
        if migrated_items:
            # Save migrated data immediately
            await self.save_guild_data(guild_id, settings, migrated_items)
            return settings, migrated_items

        return settings, []

    async def _check_legacy_migration(self, guild_id: int) -> List[AutoResponderItem]:
        """Convert any existing custom_replies to AutoResponderItem."""
        items: List[AutoResponderItem] = []
        try:
            prem_data = load_premium_data()
            sub = prem_data.get("subscriptions", {}).get(str(guild_id), {})
            legacy_replies = sub.get("custom_replies", [])
            if isinstance(legacy_replies, list) and legacy_replies:
                for rep in legacy_replies:
                    if isinstance(rep, dict) and rep.get("trigger"):
                        item = AutoResponderItem(
                            id=str(rep.get("id") or "")[:8] or AutoResponderItem().id,
                            name=str(rep.get("trigger", ""))[:30],
                            triggers=[str(rep.get("trigger", "")).strip()],
                            match_mode=str(rep.get("match_mode", "contains")).lower(),
                            replies=[str(rep.get("reply", "")).strip()] if rep.get("reply") else [],
                            hits=int(rep.get("hits", 0)),
                            created_by=int(rep.get("created_by", 0)),
                            created_at=str(rep.get("created_at") or datetime.now(timezone.utc).isoformat()),
                        )
                        items.append(item)
                logger.info("Migrated %d legacy autoresponders for guild %s", len(items), guild_id)
        except Exception as exc:
            logger.debug("Legacy migration check failed for guild %s: %s", guild_id, exc)
        return items

    async def save_guild_data(
        self,
        guild_id: int,
        settings: GuildAutoResponderSettings,
        responders: List[AutoResponderItem],
    ) -> None:
        """Save settings and responders to MongoDB and mirror locally."""
        payload = {
            "settings": settings.to_dict(),
            "responders": [r.to_dict() for r in responders],
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        col = self._get_col()
        if col is not None:
            try:
                await col.update_one(
                    {"_id": int(guild_id)},
                    {"$set": payload},
                    upsert=True,
                )
            except Exception as exc:
                logger.error("Autoresponder Mongo save failed for guild %s: %s", guild_id, exc)

        # Mirror to local JSON
        try:
            local_data = load_local_autoresponder_data()
            guilds = local_data.setdefault("guilds", {})
            guilds[str(guild_id)] = payload
            save_local_autoresponder_data(local_data)
        except Exception as exc:
            logger.error("Autoresponder local save failed for guild %s: %s", guild_id, exc)

    async def record_hit(self, guild_id: int, responder_id: str) -> None:
        """Increment hit count and update last_triggered_at."""
        now_iso = datetime.now(timezone.utc).isoformat()
        col = self._get_col()
        if col is not None:
            try:
                await col.update_one(
                    {"_id": int(guild_id), "responders.id": responder_id},
                    {
                        "$inc": {"responders.$.hits": 1},
                        "$set": {"responders.$.last_triggered_at": now_iso},
                    },
                )
            except Exception as exc:
                logger.debug("Mongo record_hit failed for %s: %s", responder_id, exc)

        # Update local storage
        try:
            local_data = load_local_autoresponder_data()
            guild_entry = local_data.get("guilds", {}).get(str(guild_id))
            if isinstance(guild_entry, dict):
                for item in guild_entry.get("responders", []):
                    if item.get("id") == responder_id:
                        item["hits"] = int(item.get("hits", 0)) + 1
                        item["last_triggered_at"] = now_iso
                        break
                save_local_autoresponder_data(local_data)
        except Exception as exc:
            logger.debug("Local record_hit failed for %s: %s", responder_id, exc)
