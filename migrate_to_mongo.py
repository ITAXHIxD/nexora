"""
migrate_to_mongo.py
────────────────────
Run this ONCE to upload your existing local JSON files into MongoDB Atlas.
After this your cogs will read/write directly to Atlas — no more JSON files.

Usage:
    python migrate_to_mongo.py

Make sure your .env file has MONGO_URI set before running.
"""

import asyncio
import json
import os
from pathlib import Path

# ── Install check ──────────────────────────────────────────────────────────────
try:
    import motor.motor_asyncio
    from dotenv import load_dotenv
except ImportError:
    print("❌  Missing packages. Run:  pip install motor python-dotenv")
    raise SystemExit(1)

load_dotenv()

# ── Map: JSON file path → MongoDB collection name ──────────────────────────────
# Add or remove entries here to match your actual data/  folder
FILE_TO_COLLECTION = {
    "data/afk_data.json":              "afk",
    "data/confessions.json":           "confessions",
    "data/confession_logs.json":       "confession_logs",
    "data/premium.json":               "premium",
    "data/bday_intro_data.json":       "birthday",
    "data/bday_intro_settings.json":   "birthday_settings",
    "data/economy_data.json":          "economy",
    "data/economy_settings.json":      "economy_settings",
}

# ── How each file's records are keyed ─────────────────────────────────────────
# "top"      = the JSON is a flat dict  { "user_or_guild_id": { ...data } }
# "nested"   = the JSON has a wrapper   { "subscriptions": { "id": {...} } }
# "list"     = the JSON is a list       [ {...}, {...} ]
FILE_STRUCTURE = {
    "data/afk_data.json":              "top",
    "data/confessions.json":           "top",
    "data/confession_logs.json":       "top",
    "data/premium.json":               "nested",   # has wrapper keys
    "data/bday_intro_data.json":       "top",
    "data/bday_intro_settings.json":   "top",
    "data/economy_data.json":          "top",
    "data/economy_settings.json":      "top",
}


async def migrate():
    uri = os.getenv("MONGO_URI")
    if not uri:
        print("❌  MONGO_URI not found in environment. Check your .env file.")
        return

    client = motor.motor_asyncio.AsyncIOMotorClient(uri)
    db     = client["botdb"]

    # Quick ping
    try:
        await client.admin.command("ping")
        print("✅  Connected to MongoDB Atlas\n")
    except Exception as e:
        print(f"❌  Connection failed: {e}")
        return

    total_imported = 0

    for file_path, collection_name in FILE_TO_COLLECTION.items():
        if not Path(file_path).exists():
            print(f"⏭️   Skipped  {file_path}  (file not found)")
            continue

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                raw = json.load(f)
        except json.JSONDecodeError as e:
            print(f"❌  {file_path} — invalid JSON: {e}")
            continue

        col       = db[collection_name]
        structure = FILE_STRUCTURE.get(file_path, "top")
        records   = []

        if structure == "top":
            # { "123456789": { ...data... }, ... }
            for key, value in raw.items():
                if not isinstance(value, dict):
                    # Simple value — wrap it
                    value = {"value": value}
                record = {"_id": _try_int(key), **value}
                records.append(record)

        elif structure == "nested":
            # { "subscriptions": { "id": {...} }, "other_key": {...} }
            # Store each top-level key as its own document
            for top_key, top_value in raw.items():
                if isinstance(top_value, dict):
                    for key, value in top_value.items():
                        if isinstance(value, dict):
                            record = {"_id": f"{top_key}:{_try_int(key)}", **value}
                        else:
                            record = {"_id": f"{top_key}:{_try_int(key)}", "value": value}
                        records.append(record)
                else:
                    records.append({"_id": top_key, "value": top_value})

        elif structure == "list":
            # [ { ...data... }, ... ]
            for i, item in enumerate(raw):
                if "_id" not in item:
                    item["_id"] = i
                records.append(item)

        if not records:
            print(f"📭  {file_path} — empty, skipped")
            continue

        # Upsert each record (safe to run multiple times — won't duplicate)
        imported = 0
        for record in records:
            try:
                _id = record.pop("_id")
                await col.update_one({"_id": _id}, {"$set": record}, upsert=True)
                imported += 1
            except Exception as e:
                print(f"   ⚠️  Skipped record {_id}: {e}")

        print(f"✅  {file_path:45s} → collection '{collection_name}' ({imported} records)")
        total_imported += imported

    print(f"\n🎉  Migration complete — {total_imported} total records imported into MongoDB Atlas.")
    print("    You can now delete your local JSON files or keep them as backup.")
    client.close()


def _try_int(value):
    """Convert string keys to int where possible (Discord IDs are ints)"""
    try:    return int(value)
    except: return value


if __name__ == "__main__":
    asyncio.run(migrate())