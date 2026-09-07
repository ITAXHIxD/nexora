"""
migrate_premium.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
One-time script to migrate premium.json → MongoDB.

Run ONCE on Wisp:
  python migrate_premium.py

Then delete this file.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import asyncio
import os
from datetime import datetime, timezone

import motor.motor_asyncio
from dotenv import load_dotenv

from utils.premium_storage import (
    LEGACY_PREMIUM_DATA_PATH,
    PREMIUM_DATA_PATH,
    load_premium_data,
)

load_dotenv()

MONGO_URI   = os.getenv("MONGO_URI")
DB_NAME     = os.getenv("MONGO_DB", "botdb")

# Tier name remapping — your old file used ULTRA/CUSTOM, new uses ENTERPRISE/CUSTOM
TIER_REMAP = {
    "ULTRA": "ENTERPRISE",  # map old ULTRA → ENTERPRISE
}

def _aware(dt):
    if dt is None: return None
    if dt.tzinfo is None: return dt.replace(tzinfo=timezone.utc)
    return dt

def _parse(val):
    if not val or val == "null": return None
    try: return _aware(datetime.fromisoformat(val))
    except: return None

async def migrate():
    if not (os.path.exists(PREMIUM_DATA_PATH) or os.path.exists(LEGACY_PREMIUM_DATA_PATH)):
        print(f"❌ Premium data not found at {PREMIUM_DATA_PATH} or {LEGACY_PREMIUM_DATA_PATH}.")
        return

    data = load_premium_data()

    client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URI)
    db     = client[DB_NAME]
    col    = db["premium"]

    subs         = data.get("subscriptions", {})
    vanity_roles = data.get("vanity", {}).get("roles", {})
    vanity_settings = data.get("vanity", {}).get("settings", {})
    grandfathered   = [str(g) for g in data.get("grandfathered", [])]

    migrated = 0
    skipped  = 0

    for guild_id_str, sub in subs.items():
        gid  = int(guild_id_str)
        tier = (sub.get("tier") or "FREE").upper()
        tier = TIER_REMAP.get(tier, tier)

        # Grandfathered override
        if guild_id_str in grandfathered:
            tier = "GRANDFATHERED"

        existing = await col.find_one({"_id": gid})
        if existing:
            print(f"  ⏭  Skipping {gid} — already in MongoDB (tier={existing.get('tier')})")
            skipped += 1
            continue

        doc = {
            "_id":            gid,
            "tier":           tier,
            "expires_at":     _parse(sub.get("expires_at")),
            "purchased_by":   int(sub["purchased_by"]) if sub.get("purchased_by") else None,
            "purchased_at":   _aware(datetime.now(timezone.utc)),
            "payment_method": "Migrated from JSON",
            "amount_paid":    0,
            "notes":          "Migrated from premium.json",
            "vanity_roles":   vanity_roles.get(guild_id_str, {}),
            "vanity_settings":vanity_settings.get(guild_id_str, {}),
        }

        await col.insert_one(doc)
        exp_str = str(doc["expires_at"])[:19] if doc["expires_at"] else "permanent"
        print(f"  ✅ Migrated guild {gid}  tier={tier}  expires={exp_str}")
        migrated += 1

    # Handle grandfathered guilds not in subscriptions
    for gid_str in grandfathered:
        gid = int(gid_str)
        if not any(int(k) == gid for k in subs):
            existing = await col.find_one({"_id": gid})
            if existing:
                skipped += 1
                continue
            doc = {
                "_id":            gid,
                "tier":           "GRANDFATHERED",
                "expires_at":     None,
                "purchased_by":   None,
                "purchased_at":   _aware(datetime.now(timezone.utc)),
                "payment_method": "Grandfathered",
                "amount_paid":    0,
                "notes":          "Grandfathered — migrated from JSON",
                "vanity_roles":   vanity_roles.get(gid_str, {}),
                "vanity_settings":vanity_settings.get(gid_str, {}),
            }
            await col.insert_one(doc)
            print(f"  ✅ Migrated grandfathered guild {gid}")
            migrated += 1

    client.close()
    print(f"\n━━━ Done: {migrated} migrated, {skipped} skipped ━━━")
    print("You can now delete this script and the legacy tracked premium.json copy.")

asyncio.run(migrate())
