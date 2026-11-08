"""
utils/game_stats.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Persistent Game Statistics Engine for Nexora Mini-Games.
Provides dual-layer persistence:
  1. MongoDB Atlas (collection: 'game_stats')
  2. Local JSON fallback ('data/game_stats.json')
Ensures wins, losses, and draws are permanently recorded across sessions,
never lost on restart, and provides admin reset and customization controls.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import json
import logging
import os
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

STATS_FILE = "data/game_stats.json"

DEFAULT_GAME_DATA = {
    "played": 0,
    "wins": 0,
    "losses": 0,
    "draws": 0,
}

DEFAULT_USER_STATS = {
    "rps": dict(DEFAULT_GAME_DATA),
    "tictactoe": dict(DEFAULT_GAME_DATA),
    "connect4": dict(DEFAULT_GAME_DATA),
    "guess": dict(DEFAULT_GAME_DATA),
}


_LOCAL_STATS_CACHE: Optional[Dict[str, Any]] = None


def _load_local_stats() -> Dict[str, Any]:
    """Load local JSON stats file with in-memory caching."""
    global _LOCAL_STATS_CACHE
    if _LOCAL_STATS_CACHE is not None:
        return _LOCAL_STATS_CACHE
    try:
        if os.path.exists(STATS_FILE):
            with open(STATS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    _LOCAL_STATS_CACHE = data
                    return _LOCAL_STATS_CACHE
    except Exception as e:
        logger.warning("GameStats: Error reading %s: %s", STATS_FILE, e)
    _LOCAL_STATS_CACHE = {}
    return _LOCAL_STATS_CACHE


def _save_local_stats(data: Dict[str, Any]):
    """Persist stats to local JSON file safely and update RAM cache."""
    global _LOCAL_STATS_CACHE
    _LOCAL_STATS_CACHE = data
    try:
        os.makedirs("data", exist_ok=True)
        with open(STATS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        logger.warning("GameStats: Error saving %s: %s", STATS_FILE, e)


async def record_game(
    bot,
    user_id: int,
    game: str,
    outcome: str,  # 'win', 'loss', 'draw'
) -> Dict[str, Any]:
    """
    Record a finished game result for a user immediately and permanently.
    Saves to both MongoDB Atlas (if connected) and local JSON storage.
    """
    uid_str = str(user_id)
    game_key = game.lower()

    # 1. Update local cache / file
    local_data = _load_local_stats()
    user_entry = local_data.setdefault(uid_str, {
        "rps": dict(DEFAULT_GAME_DATA),
        "tictactoe": dict(DEFAULT_GAME_DATA),
        "connect4": dict(DEFAULT_GAME_DATA),
        "guess": dict(DEFAULT_GAME_DATA),
    })

    if game_key not in user_entry:
        user_entry[game_key] = dict(DEFAULT_GAME_DATA)

    user_entry[game_key]["played"] = user_entry[game_key].get("played", 0) + 1
    if outcome == "win":
        user_entry[game_key]["wins"] = user_entry[game_key].get("wins", 0) + 1
    elif outcome == "loss":
        user_entry[game_key]["losses"] = user_entry[game_key].get("losses", 0) + 1
    elif outcome == "draw":
        user_entry[game_key]["draws"] = user_entry[game_key].get("draws", 0) + 1

    _save_local_stats(local_data)

    # 2. Update MongoDB Atlas if available
    mongo = getattr(bot, "mongo_db", None)
    if mongo is not None:
        try:
            col = mongo["game_stats"]
            inc_field = f"{game_key}.{outcome}s" if outcome in ("win", "loss", "draw") else None
            inc_dict = {
                f"{game_key}.played": 1,
            }
            if outcome == "win":
                inc_dict[f"{game_key}.wins"] = 1
            elif outcome == "loss":
                inc_dict[f"{game_key}.losses"] = 1
            elif outcome == "draw":
                inc_dict[f"{game_key}.draws"] = 1

            await col.update_one(
                {"_id": user_id},
                {"$inc": inc_dict},
                upsert=True,
            )
        except Exception as e:
            logger.warning("GameStats: MongoDB record error: %s", e)

    return user_entry.get(game_key, dict(DEFAULT_GAME_DATA))


async def get_user_stats(bot, user_id: int) -> Dict[str, Any]:
    """Retrieve lifetime mini-game stats for a user."""
    # Check Mongo first
    mongo = getattr(bot, "mongo_db", None)
    if mongo is not None:
        try:
            col = mongo["game_stats"]
            doc = await col.find_one({"_id": user_id})
            if doc:
                return doc
        except Exception as e:
            logger.warning("GameStats: MongoDB fetch error: %s", e)

    # Fallback to local file
    local_data = _load_local_stats()
    return local_data.get(str(user_id), dict(DEFAULT_USER_STATS))


async def reset_user_stats(bot, user_id: int, game: Optional[str] = None):
    """Reset game statistics for a single user (all games or specific game)."""
    uid_str = str(user_id)
    local_data = _load_local_stats()

    if game:
        g = game.lower()
        if uid_str in local_data and g in local_data[uid_str]:
            local_data[uid_str][g] = dict(DEFAULT_GAME_DATA)
            _save_local_stats(local_data)
    else:
        if uid_str in local_data:
            local_data[uid_str] = {
                "rps": dict(DEFAULT_GAME_DATA),
                "tictactoe": dict(DEFAULT_GAME_DATA),
                "connect4": dict(DEFAULT_GAME_DATA),
                "guess": dict(DEFAULT_GAME_DATA),
            }
            _save_local_stats(local_data)

    mongo = getattr(bot, "mongo_db", None)
    if mongo is not None:
        try:
            col = mongo["game_stats"]
            if game:
                g = game.lower()
                await col.update_one({"_id": user_id}, {"$set": {g: dict(DEFAULT_GAME_DATA)}})
            else:
                await col.delete_one({"_id": user_id})
        except Exception as e:
            logger.warning("GameStats: MongoDB reset error: %s", e)


async def reset_server_stats(bot, member_ids: list[int], game: Optional[str] = None):
    """Reset game statistics for all members in a guild."""
    local_data = _load_local_stats()
    str_ids = {str(mid) for mid in member_ids}

    for mid_str in str_ids:
        if mid_str in local_data:
            if game:
                g = game.lower()
                if g in local_data[mid_str]:
                    local_data[mid_str][g] = dict(DEFAULT_GAME_DATA)
            else:
                local_data[mid_str] = {
                    "rps": dict(DEFAULT_GAME_DATA),
                    "tictactoe": dict(DEFAULT_GAME_DATA),
                    "connect4": dict(DEFAULT_GAME_DATA),
                    "guess": dict(DEFAULT_GAME_DATA),
                }

    _save_local_stats(local_data)

    mongo = getattr(bot, "mongo_db", None)
    if mongo is not None:
        try:
            col = mongo["game_stats"]
            if game:
                g = game.lower()
                await col.update_many(
                    {"_id": {"$in": member_ids}},
                    {"$set": {g: dict(DEFAULT_GAME_DATA)}},
                )
            else:
                await col.delete_many({"_id": {"$in": member_ids}})
        except Exception as e:
            logger.warning("GameStats: MongoDB server reset error: %s", e)


async def set_user_stats(
    bot,
    user_id: int,
    game: str,
    wins: int,
    losses: int = 0,
    draws: int = 0,
):
    """Customize/set statistics for a particular user."""
    g = game.lower()
    played = wins + losses + draws
    stats_dict = {
        "played": played,
        "wins": wins,
        "losses": losses,
        "draws": draws,
    }

    uid_str = str(user_id)
    local_data = _load_local_stats()
    user_entry = local_data.setdefault(uid_str, {
        "rps": dict(DEFAULT_GAME_DATA),
        "tictactoe": dict(DEFAULT_GAME_DATA),
        "connect4": dict(DEFAULT_GAME_DATA),
        "guess": dict(DEFAULT_GAME_DATA),
    })
    user_entry[g] = stats_dict
    _save_local_stats(local_data)

    mongo = getattr(bot, "mongo_db", None)
    if mongo is not None:
        try:
            col = mongo["game_stats"]
            await col.update_one(
                {"_id": user_id},
                {"$set": {g: stats_dict}},
                upsert=True,
            )
        except Exception as e:
            logger.warning("GameStats: MongoDB set error: %s", e)

    return stats_dict


async def get_leaderboard(
    bot,
    game: str = "all",
    member_ids: Optional[set[int]] = None,
    limit: int = 10,
) -> list[Dict[str, Any]]:
    """
    Return top players sorted by total wins (then win rate, then games played).
    game can be 'all', 'tictactoe', 'connect4', 'rps', or 'guess'.
    """
    records: Dict[int, Dict[str, Any]] = {}

    local_data = _load_local_stats()
    for uid_str, doc in local_data.items():
        if str(uid_str).isdigit() and isinstance(doc, dict):
            records[int(uid_str)] = doc

    mongo = getattr(bot, "mongo_db", None)
    if mongo is not None:
        try:
            col = mongo["game_stats"]
            cursor = col.find({})
            async for doc in cursor:
                uid = doc.get("_id")
                if isinstance(uid, int) or (isinstance(uid, str) and uid.isdigit()):
                    records[int(uid)] = doc
        except Exception as e:
            logger.warning("GameStats: MongoDB leaderboard fetch error: %s", e)

    games_to_sum = ("tictactoe", "connect4", "rps", "guess") if game == "all" else (game.lower(),)
    entries = []

    for uid, doc in records.items():
        if member_ids is not None and uid not in member_ids:
            continue
        wins = 0
        played = 0
        losses = 0
        draws = 0
        for g in games_to_sum:
            g_doc = doc.get(g) or {}
            if isinstance(g_doc, dict):
                wins += int(g_doc.get("wins", 0))
                played += int(g_doc.get("played", 0))
                losses += int(g_doc.get("losses", 0))
                draws += int(g_doc.get("draws", 0))
        if played <= 0 and wins <= 0:
            continue
        wr = (wins / played * 100.0) if played > 0 else 0.0
        entries.append({
            "user_id": uid,
            "wins": wins,
            "played": played,
            "losses": losses,
            "draws": draws,
            "win_rate": wr,
        })

    entries.sort(key=lambda x: (x["wins"], x["win_rate"], x["played"]), reverse=True)
    return entries[:limit]

