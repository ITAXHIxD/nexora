"""
cogs/utility/giveaway.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Nexora Interactive Giveaway Engine
• Persistent across bot restarts & reloads (RAM cache + MongoDB + JSON)
• Interactive Giveaway Setup Studio (/giveaway, n!giveaway) with Modal,
  Channel Selector, and Optional Required Role Selector
• Quick 1-line launcher (/giveaway start, n!gstart <duration> [winners] <prize>)
• 1-Click persistent buttons:
  - 🎉 Enter Giveaway (live counter + toggle entry)
  - 👥 Participants (ephemeral participant viewer)
  - 🛑 End Now (host/admin instant finish)
  - 🎲 Reroll Winner (1-click reroll after giveaway ends)
• Replies directly to the giveaway card when announcing winners
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import asyncio
import json
import logging
import os
import random
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import discord
from discord import app_commands
from discord.ext import commands, tasks

from cogs.moderation.mod_utils import parse_duration
from utils.ui import (
    BRAND_COLOR,
    ERROR_COLOR,
    PREMIUM_COLOR,
    SUCCESS_COLOR,
    WARNING_COLOR,
)

logger = logging.getLogger(__name__)

GIVEAWAYS_FILE = "data/giveaways.json"


def _can_manage_giveaways(member: discord.abc.Snowflake, guild: Optional[discord.Guild], host_id: Optional[int] = None) -> bool:
    if guild is None:
        return False
    if host_id and getattr(member, "id", None) == host_id:
        return True
    perms = getattr(member, "guild_permissions", None)
    if perms and (perms.manage_guild or perms.manage_messages or perms.administrator):
        return True
    return False


def build_giveaway_embed(gw: Dict[str, Any]) -> discord.Embed:
    """Build the live or ended giveaway embed."""
    prize = gw.get("prize", "Mystery Prize")
    host_id = gw.get("host_id")
    winners_count = int(gw.get("winners_count", 1))
    end_ts = int(gw.get("end_ts", 0))
    entrants: List[int] = gw.get("entrants", [])
    req_role_id = gw.get("required_role_id")
    description = (gw.get("description") or "").strip()
    ended = bool(gw.get("ended", False))
    winner_ids: List[int] = gw.get("winners", [])

    if not ended:
        lines = []
        if description:
            lines.append(f"> {description}\n")
        lines.extend([
            f"🎁 **Prize:** **{prize}**",
            f"⏰ **Ends:** <t:{end_ts}:R> (<t:{end_ts}:f>)",
            f"👑 **Hosted by:** <@{host_id}>",
            f"🏆 **Winners:** **{winners_count}**",
            f"🎟️ **Entries:** **{len(entrants)}** participant{'s' if len(entrants) != 1 else ''}",
        ])
        if req_role_id:
            lines.append(f"🎭 **Required Role:** <@&{req_role_id}>")
        lines.append("\n*Click **🎉 Enter Giveaway** below to join!*")

        embed = discord.Embed(
            title=f"🎉 GIVEAWAY · {prize}",
            description="\n".join(lines),
            color=PREMIUM_COLOR,
            timestamp=datetime.fromtimestamp(end_ts, tz=timezone.utc),
        )
        embed.set_footer(text=f"Giveaway ID: {gw.get('id')} • Ends at")
    else:
        if winner_ids:
            win_mentions = ", ".join(f"<@{uid}>" for uid in winner_ids)
        else:
            win_mentions = "*No valid entries*"

        lines = []
        if description:
            lines.append(f"> {description}\n")
        lines.extend([
            f"🎁 **Prize:** **{prize}**",
            f"🏆 **Winner{'s' if len(winner_ids) != 1 else ''}:** {win_mentions}",
            f"👑 **Hosted by:** <@{host_id}>",
            f"🎟️ **Total Entries:** **{len(entrants)}** participant{'s' if len(entrants) != 1 else ''}",
            f"🏁 **Ended:** <t:{end_ts}:R>",
        ])
        embed = discord.Embed(
            title=f"🎊 GIVEAWAY ENDED · {prize}",
            description="\n".join(lines),
            color=SUCCESS_COLOR if winner_ids else WARNING_COLOR,
            timestamp=datetime.now(timezone.utc),
        )
        embed.set_footer(text=f"Giveaway ID: {gw.get('id')} • Ended")

    return embed


def build_giveaway_buttons(gw: Dict[str, Any]) -> discord.ui.View:
    """Build persistent custom_id buttons for an active or ended giveaway."""
    gw_id = gw["id"]
    entrants = gw.get("entrants", [])
    ended = bool(gw.get("ended", False))

    view = discord.ui.View(timeout=None)
    if not ended:
        view.add_item(
            discord.ui.Button(
                label=f"Enter Giveaway ({len(entrants)})",
                emoji="🎉",
                style=discord.ButtonStyle.primary,
                custom_id=f"gw_enter:{gw_id}",
            )
        )
        view.add_item(
            discord.ui.Button(
                label="Participants",
                emoji="👥",
                style=discord.ButtonStyle.secondary,
                custom_id=f"gw_list:{gw_id}",
            )
        )
        view.add_item(
            discord.ui.Button(
                label="End Early",
                emoji="🛑",
                style=discord.ButtonStyle.danger,
                custom_id=f"gw_end:{gw_id}",
            )
        )
    else:
        view.add_item(
            discord.ui.Button(
                label="Giveaway Ended",
                emoji="🏁",
                style=discord.ButtonStyle.secondary,
                disabled=True,
                custom_id=f"gw_done:{gw_id}",
            )
        )
        view.add_item(
            discord.ui.Button(
                label=f"Participants ({len(entrants)})",
                emoji="👥",
                style=discord.ButtonStyle.secondary,
                custom_id=f"gw_list:{gw_id}",
            )
        )
        view.add_item(
            discord.ui.Button(
                label="Reroll Winner",
                emoji="🎲",
                style=discord.ButtonStyle.success,
                custom_id=f"gw_reroll:{gw_id}",
            )
        )
    return view


class GiveawayCreateModal(discord.ui.Modal, title="🎁 Launch New Giveaway"):
    prize_input = discord.ui.TextInput(
        label="Prize Name",
        placeholder="e.g. Discord Nitro (1 Month) or $25 Gift Card",
        max_length=150,
        required=True,
    )
    duration_input = discord.ui.TextInput(
        label="Duration (e.g. 10m, 2h, 1d, 7d)",
        placeholder="1h",
        default="1h",
        max_length=20,
        required=True,
    )
    winners_input = discord.ui.TextInput(
        label="Number of Winners (1 - 20)",
        placeholder="1",
        default="1",
        max_length=2,
        required=True,
    )
    desc_input = discord.ui.TextInput(
        label="Bonus Note / Requirements (Optional)",
        style=discord.TextStyle.paragraph,
        placeholder="Optional message shown at the top of the giveaway card...",
        max_length=400,
        required=False,
    )

    def __init__(self, studio_view: "GiveawayStudioView"):
        super().__init__()
        self.studio = studio_view

    async def on_submit(self, interaction: discord.Interaction):
        dur_td = parse_duration(self.duration_input.value.strip())
        seconds = int(dur_td.total_seconds()) if dur_td else 0
        if not seconds or seconds < 10 or seconds > 86400 * 60:
            return await interaction.response.send_message(
                "❌ Invalid duration! Use formats like `10m`, `1h`, `12h`, `1d`, `7d` (min 10s, max 60d).",
                ephemeral=True,
            )

        try:
            winners = int(self.winners_input.value.strip())
            if winners < 1 or winners > 20:
                raise ValueError()
        except ValueError:
            return await interaction.response.send_message(
                "❌ Number of winners must be a number between **1** and **20**.",
                ephemeral=True,
            )

        target_channel = self.studio.selected_channel or interaction.channel
        if not isinstance(target_channel, discord.TextChannel):
            return await interaction.response.send_message(
                "❌ Please select a valid text channel to post the giveaway.",
                ephemeral=True,
            )

        await interaction.response.defer(ephemeral=True)
        gw = await self.studio.cog.create_and_send_giveaway(
            guild=interaction.guild,
            channel=target_channel,
            host=interaction.user,
            prize=self.prize_input.value.strip(),
            duration_seconds=seconds,
            winners_count=winners,
            required_role=self.studio.selected_role,
            description=self.desc_input.value.strip() if self.desc_input.value else None,
        )
        if not gw:
            return await interaction.followup.send(
                f"❌ Failed to send giveaway in {target_channel.mention}. Check my **Send Messages** & **Embed Links** permissions!",
                ephemeral=True,
            )

        await interaction.followup.send(
            f"✅ **Giveaway Launched!** Posted **{gw['prize']}** in {target_channel.mention} (Ends <t:{gw['end_ts']}:R>).",
            ephemeral=True,
        )


class GiveawayStudioView(discord.ui.View):
    """Interactive admin studio to configure channel, role requirement, and launch giveaways."""

    def __init__(self, cog: "Giveaway", guild: discord.Guild, author: discord.Member, default_channel: discord.TextChannel):
        super().__init__(timeout=240)
        self.cog = cog
        self.guild = guild
        self.author = author
        self.selected_channel: discord.TextChannel = default_channel
        self.selected_role: Optional[discord.Role] = None

        # Row 0: Channel Select
        ch_select = discord.ui.ChannelSelect(
            placeholder="📢 Select Announcement Channel (optional)...",
            channel_types=[discord.ChannelType.text, discord.ChannelType.news],
            min_values=1,
            max_values=1,
            row=0,
        )
        ch_select.callback = self._on_channel
        self.add_item(ch_select)

        # Row 1: Required Role Select
        role_select = discord.ui.RoleSelect(
            placeholder="🎭 Select Required Role to Enter (optional)...",
            min_values=0,
            max_values=1,
            row=1,
        )
        role_select.callback = self._on_role
        self.add_item(role_select)

        # Row 2: Action Buttons
        btn_launch = discord.ui.Button(
            label="Launch Giveaway (Modal)",
            emoji="🎁",
            style=discord.ButtonStyle.success,
            row=2,
        )
        btn_launch.callback = self._on_launch
        self.add_item(btn_launch)

        btn_clear_role = discord.ui.Button(
            label="Clear Role Req",
            emoji="🔓",
            style=discord.ButtonStyle.secondary,
            row=2,
        )
        btn_clear_role.callback = self._on_clear_role
        self.add_item(btn_clear_role)

        btn_active = discord.ui.Button(
            label="Active Giveaways",
            emoji="📋",
            style=discord.ButtonStyle.primary,
            row=2,
        )
        btn_active.callback = self._on_active_list
        self.add_item(btn_active)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author.id:
            await interaction.response.send_message(
                "❌ Only the person who opened this Giveaway Studio can use these controls.",
                ephemeral=True,
            )
            return False
        return True

    def build_embed(self) -> discord.Embed:
        active_cnt = sum(
            1 for g in self.cog.giveaways.values()
            if g.get("guild_id") == self.guild.id and not g.get("ended")
        )
        role_str = self.selected_role.mention if self.selected_role else "`None (Everyone can enter)`"
        embed = discord.Embed(
            title="🎁 Nexora Giveaway Studio",
            description=(
                "Configure your giveaway settings below and click **🎁 Launch Giveaway (Modal)** to start!\n\n"
                f"• **📢 Target Channel:** {self.selected_channel.mention}\n"
                f"• **🎭 Required Role:** {role_str}\n"
                f"• **🎉 Active Server Giveaways:** `{active_cnt}` running\n\n"
                "**⚡ Quick Command Alternative:**\n"
                "`/giveaway start duration:1h prize:Discord Nitro winners:1`\n"
                "`n!gstart 1h 1 Discord Nitro`"
            ),
            color=BRAND_COLOR,
            timestamp=datetime.now(timezone.utc),
        )
        embed.set_footer(text="Nexora Giveaways • Persistent across restarts")
        return embed

    async def _on_channel(self, interaction: discord.Interaction):
        ch = interaction.guild.get_channel(int(interaction.data["values"][0]))
        if isinstance(ch, discord.TextChannel):
            self.selected_channel = ch
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    async def _on_role(self, interaction: discord.Interaction):
        vals = interaction.data.get("values") or []
        self.selected_role = interaction.guild.get_role(int(vals[0])) if vals else None
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    async def _on_clear_role(self, interaction: discord.Interaction):
        self.selected_role = None
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    async def _on_launch(self, interaction: discord.Interaction):
        await interaction.response.send_modal(GiveawayCreateModal(self))

    async def _on_active_list(self, interaction: discord.Interaction):
        embed = self.cog.build_active_list_embed(self.guild)
        await interaction.response.send_message(embed=embed, ephemeral=True)


class Giveaway(commands.Cog):
    """Persistent Giveaway System with interactive studio, live entry counters, and 1-click rerolls."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.giveaways: Dict[str, Dict[str, Any]] = {}
        self._load_local()
        self.check_giveaways_task.start()

    def cog_unload(self):
        self.check_giveaways_task.cancel()

    def _load_local(self):
        try:
            if os.path.exists(GIVEAWAYS_FILE):
                with open(GIVEAWAYS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        self.giveaways = data
                        logger.info("Giveaway: Loaded %d giveaways from local cache", len(self.giveaways))
        except Exception as e:
            logger.warning("Giveaway: Failed to read %s: %s", GIVEAWAYS_FILE, e)

    def _save_local(self):
        try:
            os.makedirs("data", exist_ok=True)
            with open(GIVEAWAYS_FILE, "w", encoding="utf-8") as f:
                json.dump(self.giveaways, f, indent=2)
        except Exception as e:
            logger.warning("Giveaway: Failed to save %s: %s", GIVEAWAYS_FILE, e)

    async def _save_giveaway(self, gw: Dict[str, Any]):
        self.giveaways[gw["id"]] = gw
        self._save_local()
        mongo = getattr(self.bot, "mongo_db", None)
        if mongo is not None:
            try:
                await mongo["giveaways"].update_one(
                    {"_id": gw["id"]},
                    {"$set": gw},
                    upsert=True,
                )
            except Exception as e:
                logger.debug("Giveaway MongoDB save error: %s", e)

    def _find_giveaway(self, identifier: str, guild_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
        ident = str(identifier).strip()
        # Direct ID match
        if ident in self.giveaways:
            gw = self.giveaways[ident]
            if guild_id is None or gw.get("guild_id") == guild_id:
                return gw
        # Message ID match
        for gw in self.giveaways.values():
            if guild_id is not None and gw.get("guild_id") != guild_id:
                continue
            if str(gw.get("message_id")) == ident or gw.get("id", "").lower() == ident.lower():
                return gw
        return None

    async def create_and_send_giveaway(
        self,
        *,
        guild: discord.Guild,
        channel: discord.TextChannel,
        host: discord.abc.User,
        prize: str,
        duration_seconds: int,
        winners_count: int = 1,
        required_role: Optional[discord.Role] = None,
        description: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        gw_id = uuid.uuid4().hex[:8].upper()
        now_ts = int(datetime.now(timezone.utc).timestamp())
        end_ts = now_ts + int(duration_seconds)

        gw: Dict[str, Any] = {
            "id": gw_id,
            "guild_id": guild.id,
            "channel_id": channel.id,
            "message_id": None,
            "host_id": host.id,
            "prize": prize,
            "winners_count": max(1, min(20, int(winners_count))),
            "required_role_id": required_role.id if required_role else None,
            "description": description or "",
            "start_ts": now_ts,
            "end_ts": end_ts,
            "entrants": [],
            "winners": [],
            "ended": False,
        }

        embed = build_giveaway_embed(gw)
        view = build_giveaway_buttons(gw)

        try:
            msg = await channel.send(embed=embed, view=view)
        except Exception as e:
            logger.warning("Giveaway: Could not send message in %s: %s", channel.id, e)
            return None

        gw["message_id"] = msg.id
        await self._save_giveaway(gw)
        return gw

    async def finish_giveaway(self, gw: Dict[str, Any], ended_by: Optional[discord.abc.User] = None) -> List[int]:
        """Draw winners, update the giveaway card, and reply to announce the winners."""
        gw["ended"] = True
        gw["end_ts"] = int(datetime.now(timezone.utc).timestamp())

        entrants: List[int] = list(dict.fromkeys(gw.get("entrants", [])))
        winners_count = int(gw.get("winners_count", 1))

        guild = self.bot.get_guild(int(gw["guild_id"])) if gw.get("guild_id") else None
        # Filter out entrants who left the server if guild is cached
        if guild and guild.members:
            member_ids = {m.id for m in guild.members if not m.bot}
            valid_pool = [uid for uid in entrants if uid in member_ids] or entrants
        else:
            valid_pool = entrants

        if valid_pool:
            k = min(winners_count, len(valid_pool))
            winners = random.sample(valid_pool, k=k)
        else:
            winners = []

        gw["winners"] = winners
        await self._save_giveaway(gw)

        # Fetch channel & update original message
        channel = self.bot.get_channel(int(gw["channel_id"])) if gw.get("channel_id") else None
        if channel is None and gw.get("channel_id"):
            try:
                channel = await self.bot.fetch_channel(int(gw["channel_id"]))
            except Exception:
                channel = None

        if channel and gw.get("message_id"):
            embed = build_giveaway_embed(gw)
            view = build_giveaway_buttons(gw)
            orig_msg = None
            try:
                orig_msg = await channel.fetch_message(int(gw["message_id"]))
                await orig_msg.edit(embed=embed, view=view)
            except Exception as e:
                logger.debug("Giveaway: Could not edit original giveaway message %s: %s", gw.get("message_id"), e)

            # Announce winners by replying directly to the giveaway message
            if winners:
                win_mentions = ", ".join(f"<@{uid}>" for uid in winners)
                win_text = (
                    f"🎉 **GIVEAWAY WINNER{'S' if len(winners) > 1 else ''}!** 🎉\n"
                    f"Congratulations {win_mentions}! You won **{gw['prize']}** hosted by <@{gw['host_id']}>! 🥳"
                )
            else:
                win_text = (
                    f"😢 The giveaway for **{gw['prize']}** hosted by <@{gw['host_id']}> ended with **no valid entries**."
                )

            try:
                if orig_msg:
                    await orig_msg.reply(
                        content=win_text,
                        allowed_mentions=discord.AllowedMentions(users=True, roles=False, everyone=False),
                    )
                else:
                    await channel.send(
                        content=win_text,
                        allowed_mentions=discord.AllowedMentions(users=True, roles=False, everyone=False),
                    )
            except Exception as e:
                logger.debug("Giveaway: Could not send winner reply: %s", e)

        return winners

    def build_active_list_embed(self, guild: discord.Guild) -> discord.Embed:
        active = [
            g for g in self.giveaways.values()
            if g.get("guild_id") == guild.id and not g.get("ended")
        ]
        active.sort(key=lambda g: g.get("end_ts", 0))

        embed = discord.Embed(
            title=f"🎉 Active Giveaways in {guild.name}",
            color=BRAND_COLOR,
            timestamp=datetime.now(timezone.utc),
        )
        if not active:
            embed.description = "> *No active giveaways right now!*\n> Use `/giveaway start` or `n!gstart` to launch one."
        else:
            lines = []
            for g in active[:15]:
                jump_url = f"https://discord.com/channels/{g['guild_id']}/{g['channel_id']}/{g['message_id']}"
                lines.append(
                    f"• **[🎁 {g['prize']}]({jump_url})** (`ID: {g['id']}`)\n"
                    f"  └ ⏰ Ends <t:{g['end_ts']}:R> · 🏆 `{g['winners_count']}` winner(s) · 🎟️ `{len(g.get('entrants', []))}` entries · <#{(g['channel_id'])}>"
                )
            embed.description = "\n".join(lines)
        embed.set_footer(text=f"{len(active)} active giveaway(s)")
        return embed

    # ── Background Scheduler ──────────────────────────────────────────────────

    @tasks.loop(seconds=15)
    async def check_giveaways_task(self):
        now_ts = int(datetime.now(timezone.utc).timestamp())
        due = [
            gw for gw in list(self.giveaways.values())
            if not gw.get("ended") and int(gw.get("end_ts", 0)) <= now_ts
        ]
        for gw in due:
            try:
                await self.finish_giveaway(gw)
            except Exception as e:
                logger.error("Giveaway scheduler error for %s: %s", gw.get("id"), e)

    @check_giveaways_task.before_loop
    async def before_check_giveaways(self):
        await self.bot.wait_until_ready()
        # Sync from MongoDB on startup if available
        mongo = getattr(self.bot, "mongo_db", None)
        if mongo is not None:
            try:
                cursor = mongo["giveaways"].find({})
                async for doc in cursor:
                    gid = doc.get("id") or doc.get("_id")
                    if gid:
                        doc["id"] = str(gid)
                        self.giveaways[str(gid)] = doc
                self._save_local()
            except Exception as e:
                logger.debug("Giveaway MongoDB startup sync error: %s", e)

    # ── Persistent Button Listener ────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        if interaction.type != discord.InteractionType.component:
            return
        data = interaction.data or {}
        custom_id = str(data.get("custom_id") or "")
        if not custom_id.startswith(("gw_enter:", "gw_list:", "gw_end:", "gw_reroll:")):
            return

        action, _, gw_id = custom_id.partition(":")
        gw = self.giveaways.get(gw_id)
        if not gw:
            return await interaction.response.send_message(
                "❌ This giveaway record could not be found.",
                ephemeral=True,
            )

        # 1. ENTER / LEAVE GIVEAWAY
        if action == "gw_enter":
            if gw.get("ended"):
                return await interaction.response.send_message(
                    "🏁 This giveaway has already ended!",
                    ephemeral=True,
                )

            req_role_id = gw.get("required_role_id")
            if req_role_id and interaction.guild:
                member = interaction.user if isinstance(interaction.user, discord.Member) else interaction.guild.get_member(interaction.user.id)
                role_ids = {r.id for r in getattr(member, "roles", [])}
                if req_role_id not in role_ids:
                    return await interaction.response.send_message(
                        f"❌ You need the <@&{req_role_id}> role to enter this giveaway!",
                        ephemeral=True,
                    )

            entrants: List[int] = gw.setdefault("entrants", [])
            uid = interaction.user.id
            if uid in entrants:
                entrants.remove(uid)
                await self._save_giveaway(gw)
                await interaction.response.edit_message(
                    embed=build_giveaway_embed(gw),
                    view=build_giveaway_buttons(gw),
                )
                return await interaction.followup.send(
                    f"📤 You have withdrawn your entry from **{gw['prize']}**. (Click 🎉 again anytime to re-enter!)",
                    ephemeral=True,
                )
            else:
                entrants.append(uid)
                await self._save_giveaway(gw)
                await interaction.response.edit_message(
                    embed=build_giveaway_embed(gw),
                    view=build_giveaway_buttons(gw),
                )
                return await interaction.followup.send(
                    f"🎉 **You're in!** You entered the giveaway for **{gw['prize']}**! Good luck! 🍀",
                    ephemeral=True,
                )

        # 2. PARTICIPANTS LIST
        if action == "gw_list":
            entrants = gw.get("entrants", [])
            if not entrants:
                return await interaction.response.send_message(
                    "👥 No one has entered this giveaway yet! Be the first to click **🎉 Enter Giveaway**!",
                    ephemeral=True,
                )
            preview = ", ".join(f"<@{uid}>" for uid in entrants[:40])
            more = f"\n*...and {len(entrants) - 40} more*" if len(entrants) > 40 else ""
            embed = discord.Embed(
                title=f"👥 Giveaway Participants ({len(entrants)})",
                description=f"**Prize:** {gw.get('prize')}\n\n{preview}{more}",
                color=BRAND_COLOR,
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        # 3. END EARLY
        if action == "gw_end":
            if gw.get("ended"):
                return await interaction.response.send_message(
                    "🏁 This giveaway has already ended.",
                    ephemeral=True,
                )
            if not _can_manage_giveaways(interaction.user, interaction.guild, gw.get("host_id")):
                return await interaction.response.send_message(
                    "❌ Only the giveaway host or server staff (`Manage Server` / `Manage Messages`) can end this giveaway early.",
                    ephemeral=True,
                )
            await interaction.response.defer(ephemeral=True)
            winners = await self.finish_giveaway(gw, ended_by=interaction.user)
            return await interaction.followup.send(
                f"🛑 Ended giveaway **{gw['prize']}** early! ({len(winners)} winner(s) drawn)",
                ephemeral=True,
            )

        # 4. REROLL WINNER
        if action == "gw_reroll":
            if not _can_manage_giveaways(interaction.user, interaction.guild, gw.get("host_id")):
                return await interaction.response.send_message(
                    "❌ Only the giveaway host or server staff (`Manage Server` / `Manage Messages`) can reroll winners.",
                    ephemeral=True,
                )
            entrants: List[int] = list(dict.fromkeys(gw.get("entrants", [])))
            if not entrants:
                return await interaction.response.send_message(
                    "❌ Cannot reroll because there were no participants in this giveaway.",
                    ephemeral=True,
                )
            prev_winners = set(gw.get("winners", []))
            pool = [uid for uid in entrants if uid not in prev_winners] or entrants
            new_winner = random.choice(pool)
            if new_winner not in gw.setdefault("winners", []):
                gw["winners"].append(new_winner)
            await self._save_giveaway(gw)

            await interaction.response.edit_message(
                embed=build_giveaway_embed(gw),
                view=build_giveaway_buttons(gw),
            )
            if interaction.message:
                try:
                    await interaction.message.reply(
                        content=f"🎲 **GIVEAWAY REROLL!** Congratulations <@{new_winner}>! You are the new winner of **{gw['prize']}**! 🥳",
                        allowed_mentions=discord.AllowedMentions(users=True, roles=False, everyone=False),
                    )
                    return
                except Exception:
                    pass
            await interaction.followup.send(
                content=f"🎲 **GIVEAWAY REROLL!** Congratulations <@{new_winner}>! You are the new winner of **{gw['prize']}**! 🥳",
                allowed_mentions=discord.AllowedMentions(users=True, roles=False, everyone=False),
            )

    # ── Commands ──────────────────────────────────────────────────────────────

    @commands.hybrid_group(
        name="giveaway",
        aliases=["gw"],
        description="🎁 Create and manage interactive server giveaways",
        invoke_without_command=True,
    )
    @commands.guild_only()
    async def giveaway(self, ctx: commands.Context):
        """Open the interactive Giveaway Studio."""
        if not _can_manage_giveaways(ctx.author, ctx.guild):
            return await ctx.send(
                "❌ You need **Manage Server** or **Manage Messages** permission to manage giveaways.",
                ephemeral=True,
            )
        default_ch = ctx.channel if isinstance(ctx.channel, discord.TextChannel) else ctx.guild.text_channels[0]
        view = GiveawayStudioView(self, ctx.guild, ctx.author, default_ch)
        await ctx.send(embed=view.build_embed(), view=view)

    @giveaway.command(
        name="studio",
        description="🎨 Open the interactive Giveaway Setup Studio (channel, role req & modal)",
    )
    @commands.guild_only()
    async def giveaway_studio(self, ctx: commands.Context):
        if not _can_manage_giveaways(ctx.author, ctx.guild):
            return await ctx.send(
                "❌ You need **Manage Server** or **Manage Messages** permission to open the Giveaway Studio.",
                ephemeral=True,
            )
        default_ch = ctx.channel if isinstance(ctx.channel, discord.TextChannel) else ctx.guild.text_channels[0]
        view = GiveawayStudioView(self, ctx.guild, ctx.author, default_ch)
        await ctx.send(embed=view.build_embed(), view=view)

    @giveaway.command(
        name="start",
        description="🚀 Start a giveaway immediately (e.g. /giveaway start 1h Discord Nitro)",
    )
    @app_commands.describe(
        duration="Duration (e.g. 10m, 1h, 12h, 1d, 7d)",
        prize="What are you giving away?",
        winners="Number of winners (default: 1, max: 20)",
        channel="Channel to post the giveaway in (defaults to current channel)",
        required_role="Optional role required to enter the giveaway",
        description="Optional bonus note or entry requirement text",
    )
    @commands.guild_only()
    async def giveaway_start(
        self,
        ctx: commands.Context,
        duration: str,
        prize: str,
        winners: int = 1,
        channel: Optional[discord.TextChannel] = None,
        required_role: Optional[discord.Role] = None,
        description: Optional[str] = None,
    ):
        if not _can_manage_giveaways(ctx.author, ctx.guild):
            return await ctx.send(
                "❌ You need **Manage Server** or **Manage Messages** permission to start a giveaway.",
                ephemeral=True,
            )

        dur_td = parse_duration(duration)
        seconds = int(dur_td.total_seconds()) if dur_td else 0
        if not seconds or seconds < 10 or seconds > 86400 * 60:
            return await ctx.send(
                "❌ Invalid duration! Use formats like `10m`, `1h`, `12h`, `1d`, `7d` (min 10s, max 60d).",
                ephemeral=True,
            )

        target_channel = channel or (ctx.channel if isinstance(ctx.channel, discord.TextChannel) else None)
        if not target_channel:
            return await ctx.send("❌ Please run this in a text channel or specify a target channel.", ephemeral=True)

        gw = await self.create_and_send_giveaway(
            guild=ctx.guild,
            channel=target_channel,
            host=ctx.author,
            prize=prize.strip(),
            duration_seconds=seconds,
            winners_count=max(1, min(20, winners)),
            required_role=required_role,
            description=description,
        )
        if not gw:
            return await ctx.send(
                f"❌ Could not post giveaway in {target_channel.mention}. Check my channel permissions!",
                ephemeral=True,
            )

        if ctx.interaction:
            await ctx.send(
                f"✅ **Giveaway Started!** Posted **{gw['prize']}** in {target_channel.mention} (`ID: {gw['id']}`).",
                ephemeral=True,
            )
        elif target_channel.id != ctx.channel.id:
            await ctx.send(f"✅ **Giveaway Started!** Posted **{gw['prize']}** in {target_channel.mention} (`ID: {gw['id']}`).")

    @giveaway.command(
        name="end",
        description="🛑 End an active giveaway immediately and draw winners",
    )
    @app_commands.describe(identifier="Giveaway ID or Message ID (or reply to the giveaway message with n!gend)")
    @commands.guild_only()
    async def giveaway_end(self, ctx: commands.Context, identifier: Optional[str] = None):
        if not identifier and ctx.message and ctx.message.reference and ctx.message.reference.message_id:
            identifier = str(ctx.message.reference.message_id)
        if not identifier:
            return await ctx.send(
                "❌ Provide the **Giveaway ID** or **Message ID** (or reply to the giveaway message with `n!gend`).",
                ephemeral=True,
            )

        gw = self._find_giveaway(identifier, guild_id=ctx.guild.id)
        if not gw:
            return await ctx.send(f"❌ No giveaway found matching `{identifier}` in this server.", ephemeral=True)
        if gw.get("ended"):
            return await ctx.send("🏁 That giveaway has already ended! Use `/giveaway reroll` to draw a new winner.", ephemeral=True)
        if not _can_manage_giveaways(ctx.author, ctx.guild, gw.get("host_id")):
            return await ctx.send("❌ Only the giveaway host or server staff can end this giveaway.", ephemeral=True)

        winners = await self.finish_giveaway(gw, ended_by=ctx.author)
        await ctx.send(
            f"🛑 Ended giveaway **{gw['prize']}** (`{gw['id']}`) — **{len(winners)}** winner(s) announced!",
            ephemeral=True,
        )

    @giveaway.command(
        name="reroll",
        description="🎲 Reroll a new winner for an ended giveaway",
    )
    @app_commands.describe(
        identifier="Giveaway ID or Message ID (or reply to the giveaway message with n!greroll)",
        winners="How many new winners to draw (default: 1)",
    )
    @commands.guild_only()
    async def giveaway_reroll(self, ctx: commands.Context, identifier: Optional[str] = None, winners: int = 1):
        if not identifier and ctx.message and ctx.message.reference and ctx.message.reference.message_id:
            identifier = str(ctx.message.reference.message_id)
        if not identifier:
            return await ctx.send(
                "❌ Provide the **Giveaway ID** or **Message ID** (or reply to the giveaway message with `n!greroll`).",
                ephemeral=True,
            )

        gw = self._find_giveaway(identifier, guild_id=ctx.guild.id)
        if not gw:
            return await ctx.send(f"❌ No giveaway found matching `{identifier}` in this server.", ephemeral=True)
        if not gw.get("ended"):
            return await ctx.send("⏳ That giveaway is still running! End it first with `/giveaway end`.", ephemeral=True)
        if not _can_manage_giveaways(ctx.author, ctx.guild, gw.get("host_id")):
            return await ctx.send("❌ Only the giveaway host or server staff can reroll this giveaway.", ephemeral=True)

        entrants: List[int] = list(dict.fromkeys(gw.get("entrants", [])))
        if not entrants:
            return await ctx.send("❌ Cannot reroll because nobody entered this giveaway.", ephemeral=True)

        prev_winners = set(gw.get("winners", []))
        pool = [uid for uid in entrants if uid not in prev_winners] or entrants
        k = max(1, min(int(winners), len(pool)))
        new_winners = random.sample(pool, k=k)
        gw["winners"] = new_winners
        await self._save_giveaway(gw)

        win_mentions = ", ".join(f"<@{uid}>" for uid in new_winners)
        await ctx.send(
            content=f"🎲 **GIVEAWAY REROLL!** Congratulations {win_mentions}! You won **{gw['prize']}**! 🥳",
            allowed_mentions=discord.AllowedMentions(users=True, roles=False, everyone=False),
        )

    @giveaway.command(
        name="list",
        description="📋 List all active giveaways running in this server",
    )
    @commands.guild_only()
    async def giveaway_list(self, ctx: commands.Context):
        embed = self.build_active_list_embed(ctx.guild)
        await ctx.send(embed=embed)

    # ── Convenient Prefix Shortcuts (n!gstart, n!gend, n!greroll, n!glist) ────

    @commands.command(name="gstart", help="Quickly start a giveaway: n!gstart <duration> [winners] <prize>")
    @commands.guild_only()
    async def prefix_gstart(self, ctx: commands.Context, duration: str, *, rest: str):
        """
        Supports both:
          n!gstart 1h Discord Nitro
          n!gstart 1h 2 Discord Nitro
          n!gstart 30m 1w Discord Nitro
        """
        if not _can_manage_giveaways(ctx.author, ctx.guild):
            return await ctx.send("❌ You need **Manage Server** or **Manage Messages** permission to start a giveaway.")

        dur_td = parse_duration(duration)
        seconds = int(dur_td.total_seconds()) if dur_td else 0
        if not seconds or seconds < 10 or seconds > 86400 * 60:
            return await ctx.send("❌ Invalid duration! Example: `n!gstart 1h Discord Nitro` or `n!gstart 1d 2 Nitro`.")

        parts = rest.strip().split(None, 1)
        winners = 1
        prize = rest.strip()
        if len(parts) == 2:
            m = re.match(r"^(\d+)w?$", parts[0].lower())
            if m:
                winners = max(1, min(20, int(m.group(1))))
                prize = parts[1].strip()

        if not prize:
            return await ctx.send("❌ Please specify a prize! Example: `n!gstart 1h Discord Nitro`.")

        await self.create_and_send_giveaway(
            guild=ctx.guild,
            channel=ctx.channel,
            host=ctx.author,
            prize=prize,
            duration_seconds=seconds,
            winners_count=winners,
        )

    @commands.command(name="gend", help="End a giveaway early by ID/Message ID or by replying to it")
    @commands.guild_only()
    async def prefix_gend(self, ctx: commands.Context, identifier: Optional[str] = None):
        await self.giveaway_end(ctx, identifier=identifier)

    @commands.command(name="greroll", help="Reroll a giveaway winner by ID/Message ID or by replying to it")
    @commands.guild_only()
    async def prefix_greroll(self, ctx: commands.Context, identifier: Optional[str] = None, winners: int = 1):
        await self.giveaway_reroll(ctx, identifier=identifier, winners=winners)

    @commands.command(name="glist", help="List all active giveaways in this server")
    @commands.guild_only()
    async def prefix_glist(self, ctx: commands.Context):
        await self.giveaway_list(ctx)


async def setup(bot: commands.Bot):
    await bot.add_cog(Giveaway(bot))
