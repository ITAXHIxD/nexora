import discord
from discord.ext import commands
from datetime import datetime, timezone
import logging
import json
import io
from typing import Optional

from utils.config import OWNER_ID as CONFIG_OWNER_ID
from utils.premium_storage import load_premium_data, save_premium_data

logger = logging.getLogger(__name__)


def is_owner():
    async def predicate(ctx: commands.Context) -> bool:
        if ctx.author.id == CONFIG_OWNER_ID:
            return True
        if getattr(ctx.bot, "owner_id", None) and ctx.author.id == ctx.bot.owner_id:
            return True
        if getattr(ctx.bot, "owner_ids", None) and ctx.author.id in ctx.bot.owner_ids:
            return True
        return await ctx.bot.is_owner(ctx.author)

    return commands.check(predicate)


class OwnerControlPanelView(discord.ui.View):
    """Interactive Owner Control Panel for 1-click bot management."""

    def __init__(self, cog: "Owner", owner_id: int, timeout: float = 180):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.bot = cog.bot
        self.owner_id = owner_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id in (self.owner_id, CONFIG_OWNER_ID, getattr(self.bot, "owner_id", 0)):
            return True
        await interaction.response.send_message("❌ Only the Bot Owner can use this control panel.", ephemeral=True)
        return False

    def build_embed(self) -> discord.Embed:
        ping_ms = round(self.bot.latency * 1000) if self.bot.latency and str(self.bot.latency) != "inf" else 0
        total_guilds = len(self.bot.guilds)
        total_users = sum(g.member_count or 0 for g in self.bot.guilds)
        loaded_count = len(getattr(self.bot, "loaded_extensions", []))
        stats = getattr(self.bot, "bot_stats", {})

        embed = discord.Embed(
            title="👑 Nexora Owner Control Panel",
            description="Quick-action operational dashboard for the bot owner.",
            color=0x5865F2,
            timestamp=datetime.now(timezone.utc),
        )
        embed.add_field(name="⚡ Latency", value=f"`{ping_ms}ms`", inline=True)
        embed.add_field(name="🌐 Servers", value=f"`{total_guilds:,}`", inline=True)
        embed.add_field(name="👥 Users", value=f"`{total_users:,}`", inline=True)
        embed.add_field(name="📦 Loaded Cogs", value=f"`{loaded_count}`", inline=True)
        embed.add_field(name="💬 Msgs Processed", value=f"`{stats.get('messages_processed', 0):,}`", inline=True)
        embed.add_field(name="⌨️ Commands Used", value=f"`{stats.get('commands_used', 0):,}`", inline=True)
        embed.set_footer(text="Tip: Use n!reload <cog_name|all> to hot-reload any module by short name")
        return embed

    @discord.ui.button(label="Sync Guild", emoji="🏠", style=discord.ButtonStyle.primary, row=0)
    async def btn_sync_guild(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.guild:
            return await interaction.response.send_message("❌ Run this inside a server to sync guild commands.", ephemeral=True)
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            synced = await self.bot.tree.sync(guild=interaction.guild)
            await interaction.followup.send(f"✅ Synced **{len(synced)}** slash commands to **{interaction.guild.name}**.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Guild sync failed: `{e}`", ephemeral=True)

    @discord.ui.button(label="Sync Global", emoji="🌐", style=discord.ButtonStyle.secondary, row=0)
    async def btn_sync_global(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            if hasattr(self.bot, "configure_user_app_contexts"):
                self.bot.configure_user_app_contexts()
            synced = await self.bot.tree.sync()
            await interaction.followup.send(f"✅ Synced **{len(synced)}** slash commands globally.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Global sync failed: `{e}`", ephemeral=True)

    @discord.ui.button(label="Reload All Cogs", emoji="🔄", style=discord.ButtonStyle.success, row=0)
    async def btn_reload_all(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True, thinking=True)
        ok, failed = await self.cog._reload_all_extensions()
        msg = f"🔄 Reloaded **{ok}** extensions successfully."
        if failed:
            msg += f"\n⚠️ **{len(failed)} failed:** " + ", ".join(f"`{ext}`" for ext, _ in failed[:5])
        await interaction.followup.send(msg, ephemeral=True)

    @discord.ui.button(label="Download Backup", emoji="💾", style=discord.ButtonStyle.secondary, row=1)
    async def btn_backup(self, interaction: discord.Interaction, button: discord.ui.Button):
        file = self.cog._build_backup_file()
        await interaction.response.send_message("✅ **Backup generated!**", file=file, ephemeral=True)

    @discord.ui.button(label="Refresh Stats", emoji="📊", style=discord.ButtonStyle.secondary, row=1)
    async def btn_refresh(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(embed=self.build_embed(), view=self)


class Owner(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def _resolve_extension_name(self, name: str) -> str:
        """Resolve a short cog name (e.g. 'afk', 'birthday', 'quote') to its full extension path."""
        clean = name.strip().lower().removesuffix(".py")
        loaded = list(getattr(self.bot, "extensions", {}).keys()) or list(getattr(self.bot, "loaded_extensions", []))
        if clean in loaded:
            return clean
        for ext in loaded:
            if ext.lower() == clean or ext.lower().endswith(f".{clean}") or clean in ext.lower().split(".")[-1]:
                return ext
        return name.strip()

    async def _reload_all_extensions(self):
        exts = list(getattr(self.bot, "loaded_extensions", [])) or list(self.bot.extensions.keys())
        ok = 0
        failed = []
        for ext in exts:
            try:
                await self.bot.reload_extension(ext)
                ok += 1
            except Exception as e:
                failed.append((ext, str(e)))
        if hasattr(self.bot, "configure_user_app_contexts"):
            self.bot.configure_user_app_contexts()
        logger.info("[CHANGE] 🔄 Reloaded %d/%d extensions", ok, len(exts))
        return ok, failed

    def _build_backup_file(self) -> discord.File:
        backup_data = {
            "stats": getattr(self.bot, "bot_stats", {}),
            "guilds_count": len(self.bot.guilds),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        filename = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        data_bytes = json.dumps(backup_data, indent=2, ensure_ascii=False, default=str).encode("utf-8")
        return discord.File(io.BytesIO(data_bytes), filename=filename)

    @commands.command(name="owner", aliases=["panel", "adminpanel"])
    @is_owner()
    async def owner_panel(self, ctx: commands.Context):
        """Open the interactive Bot Owner Control Panel."""
        view = OwnerControlPanelView(self, ctx.author.id)
        await ctx.send(embed=view.build_embed(), view=view)

    @commands.command(name="debug_commands", aliases=["debug"])
    @is_owner()
    async def debug_commands(self, ctx: commands.Context):
        commands_list = sorted(cmd.name for cmd in self.bot.tree.get_commands())

        try:
            embed_color = int(self.bot.bot_config["ui_settings"]["embed_color"], 16)
        except (KeyError, ValueError, AttributeError):
            embed_color = 0x5865F2

        embed = discord.Embed(
            title=f"⚡ Registered Global Slash Commands ({len(commands_list)}/100)",
            description=", ".join(f"`/{c}`" for c in commands_list) or "No slash commands registered.",
            color=embed_color,
        )
        await ctx.send(embed=embed)

    @commands.command(name="activate")
    @is_owner()
    async def activate(self, ctx: commands.Context, guild_id: str, tier: str = "PRO"):
        """Activate a server premium tier (e.g. n!activate 123456789 PRO)."""
        tier_upper = tier.strip().upper()
        gid_clean = guild_id.strip()
        now_iso = datetime.now(timezone.utc).isoformat()

        data = load_premium_data()
        data.setdefault("subscriptions", {})[gid_clean] = {
            "tier": tier_upper,
            "activated_by": ctx.author.id,
            "activated_at": now_iso,
            "expires_at": None,
        }
        save_premium_data(data)

        if hasattr(self.bot, "load_premium_guilds"):
            self.bot.load_premium_guilds()

        mongo = getattr(self.bot, "mongo_db", None)
        if mongo is not None and gid_clean.isdigit():
            try:
                await mongo["premium"].update_one(
                    {"_id": int(gid_clean)},
                    {
                        "$set": {
                            "tier": tier_upper,
                            "activated_by": ctx.author.id,
                            "activated_at": now_iso,
                            "expires_at": None,
                        }
                    },
                    upsert=True,
                )
            except Exception as e:
                logger.warning("Failed to sync activate to MongoDB: %s", e)

        logger.info("[CHANGE] 💎 Activated %s tier for guild %s (by %s)", tier_upper, gid_clean, ctx.author)
        await ctx.send(f"✅ **{tier_upper}** tier activated for server `{gid_clean}`!")

    @commands.command(name="force_resync")
    @is_owner()
    async def force_resync(self, ctx: commands.Context):
        try:
            if hasattr(self.bot, "configure_user_app_contexts"):
                self.bot.configure_user_app_contexts()
            guild_synced = await self.bot.tree.sync(guild=ctx.guild) if ctx.guild else []
            global_synced = await self.bot.tree.sync()

            await ctx.send(
                f"✅ **Resynced!**\n• Guild: `{len(guild_synced)}` commands\n• Global: `{len(global_synced)}` commands"
            )
        except Exception as e:
            await ctx.send(f"❌ Resync failed: `{e}`")

    @commands.command(name="backup")
    @is_owner()
    async def backup(self, ctx: commands.Context):
        file = self._build_backup_file()
        await ctx.send("✅ **Backup Created!**", file=file)

    @commands.command(name="resetstats")
    @is_owner()
    async def resetstats(self, ctx: commands.Context):
        self.bot.bot_stats = {
            "messages_processed": 0,
            "conversations_today": 0,
            "commands_used": 0,
            "errors_encountered": 0,
            "api_calls_made": 0,
            "start_time": datetime.now(),
        }
        try:
            embed_color = int(self.bot.bot_config["ui_settings"]["success_color"], 16)
        except (KeyError, ValueError, AttributeError):
            embed_color = 0x57F287

        embed = discord.Embed(
            title="✅ Statistics Reset",
            description="Bot runtime statistics have been reset.",
            color=embed_color,
        )
        await ctx.send(embed=embed)

    @commands.command(name="sync")
    @is_owner()
    async def sync(self, ctx: commands.Context, guild_id: Optional[str] = None):
        try:
            if hasattr(self.bot, "configure_user_app_contexts"):
                self.bot.configure_user_app_contexts()
            if guild_id:
                gid = int(ctx.guild.id) if guild_id.lower() in ("here", "guild", ".") and ctx.guild else int(guild_id)
                guild_obj = discord.Object(id=gid)
                synced = await self.bot.tree.sync(guild=guild_obj)
                message = f"✅ Synced **{len(synced)}** commands to guild `{gid}`."
            else:
                synced = await self.bot.tree.sync()
                message = f"✅ Synced **{len(synced)}** commands globally."

            await ctx.send(message)
        except Exception as e:
            await ctx.send(f"❌ Sync failed: `{e}`")

    @commands.command(name="unsync")
    @is_owner()
    async def unsync(self, ctx: commands.Context):
        try:
            self.bot.tree.clear_commands(guild=None)
            await self.bot.tree.sync()
            logger.info("[CHANGE] Global slash commands cleared by owner %s", ctx.author)
            await ctx.send("✅ All global slash commands have been cleared.")
        except Exception as e:
            logger.error("Unsync failed: %s", e)
            await ctx.send(f"❌ Unsync failed: `{e}`")

    @commands.command(name="reload", aliases=["rl"])
    @is_owner()
    async def reload_ext(self, ctx: commands.Context, extension: str = "all"):
        """Reload a cog by short name (e.g. n!reload afk) or reload all cogs (n!reload all)."""
        if extension.strip().lower() in ("all", "*"):
            ok, failed = await self._reload_all_extensions()
            msg = f"🔄 Reloaded **{ok}** extensions successfully!"
            if failed:
                msg += "\n❌ Failed: " + ", ".join(f"`{ext}` ({err})" for ext, err in failed[:5])
            return await ctx.send(msg)

        resolved = self._resolve_extension_name(extension)
        try:
            await self.bot.reload_extension(resolved)
            if hasattr(self.bot, "configure_user_app_contexts"):
                self.bot.configure_user_app_contexts()
            logger.info("[CHANGE] 🔄 Reloaded extension '%s' (by %s)", resolved, ctx.author)
            await ctx.send(f"🔄 Reloaded `{resolved}` successfully.")
        except Exception as e:
            logger.error("Failed to reload extension '%s': %s", resolved, e)
            await ctx.send(f"❌ Failed to reload `{resolved}`: `{e}`")


async def setup(bot):
    raw_owner = getattr(bot, "bot_config", {}).get("owner_id") or CONFIG_OWNER_ID
    try:
        if isinstance(raw_owner, (int, str)) and str(raw_owner).strip().isdigit():
            bot.owner_id = int(str(raw_owner).strip())
        elif not getattr(bot, "owner_id", None):
            bot.owner_id = CONFIG_OWNER_ID
    except (ValueError, TypeError):
        bot.owner_id = CONFIG_OWNER_ID

    await bot.add_cog(Owner(bot))
