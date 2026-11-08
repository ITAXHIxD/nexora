"""
cogs/info/avatar.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Nexora Avatar, Banner & Profile Showcase System
Provides interactive, high-resolution media inspection with tabs:
  • 🖼️ Avatar: Full-size high-res avatar with dynamic compliments & specs
  • 🏰 Server PFP: Server-specific avatar (if distinct from global)
  • 🌆 Banner: Full-resolution custom banner & accent color showcase
  • 👤 Profile: Detailed user dossier, timestamps, badges & thumbnails
  • 💾 Download: Quick-access links for 1024px, 2048px, 4096px assets
  • 🗑️ Dismiss: Invoker-only clean dismissal
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import logging
import random
from typing import Optional, Union

import discord
from discord import app_commands
from discord.ext import commands

logger = logging.getLogger(__name__)

# ── Aesthetic Compliments Pool ────────────────────────────────────────────────
COMPLIMENTS = {
    "avatar": [
        "✨ Looking absolutely stunning today!",
        "🔥 Certified 10/10 visual aesthetic.",
        "💎 Iconic look. Absolutely unmatched style.",
        "🌟 Radiating unstoppable main character energy.",
        "📸 Clean, crisp, and pure visual perfection.",
        "🎨 A masterpiece of a profile picture!",
        "⚡ Unrivaled presence and immaculate vibes.",
        "👑 Peak elegance right here.",
        "🌌 Out of this world aesthetic appeal.",
        "💫 Pure class and effortless style.",
    ],
    "server_avatar": [
        "🏰 Server-exclusive style hitting different!",
        "🎭 Tailored to absolute perfection for this community.",
        "✨ Local aesthetic operating at peak performance.",
        "💎 Serving server royalty with distinction.",
    ],
    "banner": [
        "🌆 Elite profile banner aesthetic!",
        "🌌 Atmospheric backdrop vibes are immaculate.",
        "✨ Setting the mood with supreme visual taste.",
        "🎨 High taste detected in this banner composition.",
        "🌃 Absolutely breathtaking visual backdrop.",
        "💎 High-definition luxury aesthetic.",
    ],
    "profile": [
        "👑 A legendary presence on Discord.",
        "💫 A top-tier profile in every single aspect.",
        "🌟 Certified OG credentials with immaculate aura.",
        "📜 A high-ranking dossier of prestige and style.",
    ],
    "download": [
        "💾 High-resolution assets ready for collection.",
        "📦 Direct CDN master links packaged for you.",
    ],
}


class AvatarView(discord.ui.View):
    """
    Interactive media switcher for Avatar, Server Avatar, Banner,
    Profile Overview, and High-Resolution Downloads.
    """

    def __init__(
        self,
        bot: commands.Bot,
        target: Union[discord.Member, discord.User],
        requester: Union[discord.Member, discord.User],
        fetched_user: Optional[discord.User] = None,
        timeout: float = 180,
    ):
        super().__init__(timeout=timeout)
        self.bot = bot
        self.target = target
        self.requester = requester
        self.fetched_user = fetched_user or target
        self.current_tab = "avatar"
        self.message: Optional[discord.Message] = None

        # Check if user has a distinct server avatar
        self.has_guild_avatar = (
            isinstance(self.target, discord.Member)
            and self.target.guild_avatar is not None
        )

        self._setup_buttons()

    def get_fallback_compliment(self, category: str) -> str:
        """Retrieve a random, aesthetic compliment for the specified category."""
        pool = COMPLIMENTS.get(category, COMPLIMENTS["avatar"])
        return random.choice(pool)

    def _setup_buttons(self):
        """Initialize all interactive tab buttons once for stable ViewStore dispatching."""
        self.clear_items()

        # 1. Global Avatar
        self.btn_avatar = discord.ui.Button(
            label="Avatar",
            emoji="🖼️",
            style=discord.ButtonStyle.primary if self.current_tab == "avatar" else discord.ButtonStyle.secondary,
            custom_id="av_tab_avatar",
            row=0,
        )
        self.btn_avatar.callback = self._on_avatar_click
        self.add_item(self.btn_avatar)

        # 2. Server Avatar (conditional)
        if self.has_guild_avatar:
            self.btn_server_avatar = discord.ui.Button(
                label="Server PFP",
                emoji="🏰",
                style=discord.ButtonStyle.primary if self.current_tab == "server_avatar" else discord.ButtonStyle.secondary,
                custom_id="av_tab_server_avatar",
                row=0,
            )
            self.btn_server_avatar.callback = self._on_server_avatar_click
            self.add_item(self.btn_server_avatar)

        # 3. Banner
        self.btn_banner = discord.ui.Button(
            label="Banner",
            emoji="🌆",
            style=discord.ButtonStyle.primary if self.current_tab == "banner" else discord.ButtonStyle.secondary,
            custom_id="av_tab_banner",
            row=0,
        )
        self.btn_banner.callback = self._on_banner_click
        self.add_item(self.btn_banner)

        # 4. Profile
        self.btn_profile = discord.ui.Button(
            label="Profile",
            emoji="👤",
            style=discord.ButtonStyle.primary if self.current_tab == "profile" else discord.ButtonStyle.secondary,
            custom_id="av_tab_profile",
            row=0,
        )
        self.btn_profile.callback = self._on_profile_click
        self.add_item(self.btn_profile)

        # 5. Download Links
        self.btn_download = discord.ui.Button(
            label="Download",
            emoji="💾",
            style=discord.ButtonStyle.primary if self.current_tab == "download" else discord.ButtonStyle.secondary,
            custom_id="av_tab_download",
            row=1,
        )
        self.btn_download.callback = self._on_download_click
        self.add_item(self.btn_download)

        # 6. Dismiss Button
        self.btn_dismiss = discord.ui.Button(
            label="Dismiss",
            emoji="🗑️",
            style=discord.ButtonStyle.danger,
            custom_id="av_tab_dismiss",
            row=1,
        )
        self.btn_dismiss.callback = self._on_dismiss_click
        self.add_item(self.btn_dismiss)

    def _update_button_styles(self):
        """Update button styles based on current_tab without rebuilding items."""
        self.btn_avatar.style = discord.ButtonStyle.primary if self.current_tab == "avatar" else discord.ButtonStyle.secondary
        if self.has_guild_avatar and hasattr(self, "btn_server_avatar"):
            self.btn_server_avatar.style = discord.ButtonStyle.primary if self.current_tab == "server_avatar" else discord.ButtonStyle.secondary
        self.btn_banner.style = discord.ButtonStyle.primary if self.current_tab == "banner" else discord.ButtonStyle.secondary
        self.btn_profile.style = discord.ButtonStyle.primary if self.current_tab == "profile" else discord.ButtonStyle.secondary
        self.btn_download.style = discord.ButtonStyle.primary if self.current_tab == "download" else discord.ButtonStyle.secondary

    async def _ensure_banner_loaded(self):
        """Ensure banner data is fetched from the Discord REST API if not already present."""
        if not hasattr(self.fetched_user, "banner") or self.fetched_user.banner is None:
            try:
                self.fetched_user = await self.bot.fetch_user(self.target.id)
            except Exception as e:
                logger.debug("Failed to fetch fresh user for banner: %s", e)

    def _get_base_color(self) -> discord.Color:
        """Resolve theme color from VIP custom color, accent, member role color, or default blurple."""
        color_getter = getattr(self.bot, "get_user_custom_color", None)
        if color_getter:
            custom_val = color_getter(self.target.id)
            if custom_val:
                return discord.Color(custom_val)
        if isinstance(self.target, discord.Member) and self.target.color.value:
            return self.target.color
        if getattr(self.fetched_user, "accent_color", None):
            return self.fetched_user.accent_color
        return discord.Color.blurple()

    def generate_embed(self) -> discord.Embed:
        """Construct the full-resolution rich embed for the active tab."""
        u = self.fetched_user or self.target
        color = self._get_base_color()

        if self.current_tab == "avatar":
            compliment = self.get_fallback_compliment("avatar")
            embed = discord.Embed(
                title=f"🖼️ {self.target.display_name}'s Avatar",
                description=f"> {compliment}",
                color=color,
            )
            # Use target's global avatar (or display avatar if not distinct)
            avatar = getattr(self.target, "avatar", None) or self.target.display_avatar
            avatar_url = str(avatar.with_size(1024).url)
            embed.set_image(url=avatar_url)

            is_animated = avatar.is_animated()
            formats = [
                f"[PNG]({avatar.with_format('png').with_size(1024).url})",
                f"[WebP]({avatar.with_format('webp').with_size(1024).url})",
                f"[JPG]({avatar.with_format('jpeg').with_size(1024).url})",
            ]
            if is_animated:
                formats.insert(0, f"[GIF]({avatar.with_format('gif').with_size(1024).url})")

            embed.add_field(
                name="Direct High-Res Formats",
                value="  •  ".join(formats),
                inline=False,
            )
            embed.set_footer(
                text=f"Requested by {self.requester.display_name}  •  Global Avatar (1024px)",
                icon_url=self.requester.display_avatar.url,
            )
            return embed

        elif self.current_tab == "server_avatar":
            compliment = self.get_fallback_compliment("server_avatar")
            embed = discord.Embed(
                title=f"🏰 {self.target.display_name}'s Server Avatar",
                description=f"> {compliment}\n> *Exclusive to **{self.target.guild.name}***",
                color=color,
            )
            server_pfp = self.target.guild_avatar
            if server_pfp:
                embed.set_image(url=str(server_pfp.with_size(1024).url))
                formats = [
                    f"[PNG]({server_pfp.with_format('png').with_size(1024).url})",
                    f"[WebP]({server_pfp.with_format('webp').with_size(1024).url})",
                    f"[JPG]({server_pfp.with_format('jpeg').with_size(1024).url})",
                ]
                if server_pfp.is_animated():
                    formats.insert(0, f"[GIF]({server_pfp.with_format('gif').with_size(1024).url})")
                embed.add_field(
                    name="Direct Server PFP Formats",
                    value="  •  ".join(formats),
                    inline=False,
                )
            else:
                embed.description += "\n\n❌ No custom server avatar set."

            embed.set_footer(
                text=f"Requested by {self.requester.display_name}  •  Guild Profile Picture",
                icon_url=self.requester.display_avatar.url,
            )
            return embed

        elif self.current_tab == "banner":
            banner = getattr(self.fetched_user, "banner", None)
            if banner:
                compliment = self.get_fallback_compliment("banner")
                embed = discord.Embed(
                    title=f"🌆 {self.target.display_name}'s Banner",
                    description=f"> {compliment}",
                    color=color,
                )
                embed.set_image(url=str(banner.with_size(1024).url))
                formats = [
                    f"[PNG]({banner.with_format('png').with_size(1024).url})",
                    f"[WebP]({banner.with_format('webp').with_size(1024).url})",
                    f"[JPG]({banner.with_format('jpeg').with_size(1024).url})",
                ]
                if banner.is_animated():
                    formats.insert(0, f"[GIF]({banner.with_format('gif').with_size(1024).url})")
                embed.add_field(
                    name="Direct Banner Formats",
                    value="  •  ".join(formats),
                    inline=False,
                )
            else:
                accent = getattr(self.fetched_user, "accent_color", None)
                accent_hex = f"#{accent.value:06x}" if accent else "None"
                embed = discord.Embed(
                    title=f"🌆 {self.target.display_name}'s Banner",
                    description=(
                        f"❌ **{self.target.display_name}** does not have a custom profile banner set.\n\n"
                        f"• **Accent Color:** `{accent_hex}`\n"
                        f"• Members with Discord Nitro can set animated or static banners."
                    ),
                    color=accent or color,
                )
                embed.set_thumbnail(url=self.target.display_avatar.url)

            embed.set_footer(
                text=f"Requested by {self.requester.display_name}",
                icon_url=self.requester.display_avatar.url,
            )
            return embed

        elif self.current_tab == "profile":
            compliment = self.get_fallback_compliment("profile")
            embed = discord.Embed(
                title=f"👤 {self.target.display_name}'s Profile Dossier",
                description=f"> {compliment}",
                color=color,
            )
            embed.set_thumbnail(url=self.target.display_avatar.url)

            banner = getattr(self.fetched_user, "banner", None)
            if banner:
                embed.set_image(url=str(banner.with_size(1024).url))

            handle = (
                f"@{self.target.name}"
                if getattr(self.target, "discriminator", "0") in ("0", None)
                else f"{self.target.name}#{self.target.discriminator}"
            )
            created_ts = int(self.target.created_at.timestamp())
            embed.add_field(name="Username", value=f"`{handle}`", inline=True)
            embed.add_field(name="User ID", value=f"`{self.target.id}`", inline=True)
            embed.add_field(
                name="Account Created",
                value=f"<t:{created_ts}:F>\n(<t:{created_ts}:R>)",
                inline=False,
            )

            if isinstance(self.target, discord.Member) and self.target.joined_at:
                joined_ts = int(self.target.joined_at.timestamp())
                embed.add_field(
                    name="Joined Server",
                    value=f"<t:{joined_ts}:F>\n(<t:{joined_ts}:R>)",
                    inline=True,
                )
                top_role = self.target.top_role.mention if self.target.top_role.name != "@everyone" else "`None`"
                embed.add_field(name="Top Role", value=top_role, inline=True)

            avatar_type = "🎞️ Animated GIF" if self.target.display_avatar.is_animated() else "🖼️ Static Image"
            has_banner_str = "✅ Active" if banner else "❌ None"
            is_vip = self.target.id in getattr(self.bot, "premium_user_ids", set())
            vip_str = " · 👑 **Nexora VIP**" if is_vip else ""
            embed.add_field(
                name="Profile Features",
                value=f"• **Avatar Type:** {avatar_type}\n• **Custom Banner:** {has_banner_str}{vip_str}",
                inline=False,
            )
            embed.set_footer(
                text=f"Requested by {self.requester.display_name}",
                icon_url=self.requester.display_avatar.url,
            )
            return embed

        elif self.current_tab == "download":
            embed = discord.Embed(
                title=f"💾 Download {self.target.display_name}'s Assets",
                description="Click any resolution below for high-definition direct downloads:",
                color=color,
            )
            embed.set_thumbnail(url=self.target.display_avatar.url)

            # Global Avatar Links
            av = getattr(self.target, "avatar", None) or self.target.display_avatar
            av_links = []
            if av.is_animated():
                av_links.append(f"**GIF:** [1024px]({av.with_format('gif').with_size(1024).url}) · [2048px]({av.with_format('gif').with_size(2048).url}) · [4096px]({av.with_format('gif').with_size(4096).url})")
            av_links.append(f"**PNG:** [1024px]({av.with_format('png').with_size(1024).url}) · [2048px]({av.with_format('png').with_size(2048).url}) · [4096px]({av.with_format('png').with_size(4096).url})")
            av_links.append(f"**JPG:** [1024px]({av.with_format('jpeg').with_size(1024).url}) · [2048px]({av.with_format('jpeg').with_size(2048).url}) · [4096px]({av.with_format('jpeg').with_size(4096).url})")
            av_links.append(f"**WebP:** [1024px]({av.with_format('webp').with_size(1024).url}) · [2048px]({av.with_format('webp').with_size(2048).url}) · [4096px]({av.with_format('webp').with_size(4096).url})")
            embed.add_field(name="🖼️ Avatar Downloads", value="\n".join(av_links), inline=False)

            # Server Avatar Links (if any)
            if self.has_guild_avatar and self.target.guild_avatar:
                sav = self.target.guild_avatar
                sav_links = []
                if sav.is_animated():
                    sav_links.append(f"**GIF:** [1024px]({sav.with_format('gif').with_size(1024).url}) · [2048px]({sav.with_format('gif').with_size(2048).url}) · [4096px]({sav.with_format('gif').with_size(4096).url})")
                sav_links.append(f"**PNG:** [1024px]({sav.with_format('png').with_size(1024).url}) · [2048px]({sav.with_format('png').with_size(2048).url}) · [4096px]({sav.with_format('png').with_size(4096).url})")
                sav_links.append(f"**JPG:** [1024px]({sav.with_format('jpeg').with_size(1024).url}) · [2048px]({sav.with_format('jpeg').with_size(2048).url}) · [4096px]({sav.with_format('jpeg').with_size(4096).url})")
                sav_links.append(f"**WebP:** [1024px]({sav.with_format('webp').with_size(1024).url}) · [2048px]({sav.with_format('webp').with_size(2048).url}) · [4096px]({sav.with_format('webp').with_size(4096).url})")
                embed.add_field(name="🏰 Server Avatar Downloads", value="\n".join(sav_links), inline=False)

            # Banner Links
            banner = getattr(self.fetched_user, "banner", None)
            if banner:
                banner_links = []
                if banner.is_animated():
                    banner_links.append(f"**GIF:** [1024px]({banner.with_format('gif').with_size(1024).url}) · [2048px]({banner.with_format('gif').with_size(2048).url})")
                banner_links.append(f"**PNG:** [1024px]({banner.with_format('png').with_size(1024).url}) · [2048px]({banner.with_format('png').with_size(2048).url})")
                banner_links.append(f"**JPG:** [1024px]({banner.with_format('jpeg').with_size(1024).url}) · [2048px]({banner.with_format('jpeg').with_size(2048).url})")
                banner_links.append(f"**WebP:** [1024px]({banner.with_format('webp').with_size(1024).url}) · [2048px]({banner.with_format('webp').with_size(2048).url})")
                embed.add_field(name="🌆 Banner Downloads", value="\n".join(banner_links), inline=False)
            else:
                embed.add_field(name="🌆 Banner Downloads", value="❌ No custom banner available to download.", inline=False)

            embed.set_footer(
                text=f"Requested by {self.requester.display_name}",
                icon_url=self.requester.display_avatar.url,
            )
            return embed

        # Fallback to avatar embed
        return self.generate_embed()

    # ── Interaction & Button Callbacks ─────────────────────────────────────────

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Allow anyone to switch tabs; restrict message dismissal to the invoker."""
        if interaction.data.get("custom_id") == "av_tab_dismiss":
            if interaction.user.id != self.requester.id:
                await interaction.response.send_message(
                    "❌ Only the person who requested this can dismiss it.",
                    ephemeral=True,
                )
                return False
        return True

    async def _switch_tab(self, interaction: discord.Interaction, tab: str):
        self.current_tab = tab
        self._update_button_styles()
        embed = self.generate_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    async def _on_avatar_click(self, interaction: discord.Interaction):
        await self._switch_tab(interaction, "avatar")

    async def _on_server_avatar_click(self, interaction: discord.Interaction):
        await self._switch_tab(interaction, "server_avatar")

    async def _on_banner_click(self, interaction: discord.Interaction):
        await self._ensure_banner_loaded()
        await self._switch_tab(interaction, "banner")

    async def _on_profile_click(self, interaction: discord.Interaction):
        await self._ensure_banner_loaded()
        await self._switch_tab(interaction, "profile")

    async def _on_download_click(self, interaction: discord.Interaction):
        await self._ensure_banner_loaded()
        await self._switch_tab(interaction, "download")

    async def _on_dismiss_click(self, interaction: discord.Interaction):
        try:
            await interaction.message.delete()
        except Exception:
            try:
                await interaction.response.edit_message(content="*Dismissed.*", embed=None, view=None)
            except Exception:
                pass

    async def on_timeout(self):
        """Disable all interactive buttons when the view expires."""
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True
        try:
            if self.message:
                await self.message.edit(view=self)
        except Exception:
            pass


class Avatar(commands.Cog):
    """Commands for viewing and downloading user avatars, banners, and profile dossiers."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.ctx_menu_avatar = app_commands.ContextMenu(
            name="View Avatar & Banner",
            callback=self._context_menu_avatar,
        )
        self.bot.tree.add_command(self.ctx_menu_avatar)

    async def cog_unload(self):
        self.bot.tree.remove_command(self.ctx_menu_avatar.name, type=self.ctx_menu_avatar.type)

    async def _context_menu_avatar(
        self,
        interaction: discord.Interaction,
        user: Union[discord.Member, discord.User],
    ):
        await interaction.response.defer()
        fetched_user = None
        try:
            fetched_user = await self.bot.fetch_user(user.id)
        except Exception:
            pass
        view = AvatarView(
            bot=self.bot,
            target=user,
            requester=interaction.user,
            fetched_user=fetched_user,
        )
        embed = view.generate_embed()
        msg = await interaction.followup.send(embed=embed, view=view)
        view.message = msg

    @commands.hybrid_command(
        name="avatar",
        description="🖼️ Inspect and download a user's high-resolution avatar or banner",
        aliases=["av", "pfp"],
    )
    @app_commands.describe(user="The user whose avatar/banner you want to view (defaults to yourself)")
    async def avatar(
        self,
        ctx: commands.Context,
        user: Optional[Union[discord.Member, discord.User]] = None,
    ):
        """
        Display a user's avatar, server avatar, profile banner, and downloads.
        Works via prefix (n!avatar, n!av, n!pfp) or slash command (/avatar, /pfp).
        """
        # Defer if slash command to ensure safe network fetching
        if ctx.interaction:
            await ctx.interaction.response.defer()

        # Prioritize member in current guild if available, otherwise user
        target = user or ctx.author
        fetched_user = None

        try:
            fetched_user = await self.bot.fetch_user(target.id)
        except Exception as e:
            logger.debug("Could not fetch user %s from REST API: %s", target.id, e)

        view = AvatarView(
            bot=self.bot,
            target=target,
            requester=ctx.author,
            fetched_user=fetched_user,
        )
        embed = view.generate_embed()

        if ctx.interaction:
            msg = await ctx.interaction.followup.send(embed=embed, view=view)
        else:
            msg = await ctx.send(embed=embed, view=view)

        view.message = msg

    @commands.hybrid_command(
        name="banner",
        description="🌆 Quick shortcut to inspect and download a user's profile banner",
    )
    @app_commands.describe(user="The user whose banner you want to view (defaults to yourself)")
    async def banner(
        self,
        ctx: commands.Context,
        user: Optional[Union[discord.Member, discord.User]] = None,
    ):
        """Direct shortcut command to inspect a user's profile banner."""
        if ctx.interaction:
            await ctx.interaction.response.defer()

        target = user or ctx.author
        fetched_user = None

        try:
            fetched_user = await self.bot.fetch_user(target.id)
        except Exception as e:
            logger.debug("Could not fetch user %s from REST API: %s", target.id, e)

        view = AvatarView(
            bot=self.bot,
            target=target,
            requester=ctx.author,
            fetched_user=fetched_user,
        )
        view.current_tab = "banner"
        view._update_button_styles()
        embed = view.generate_embed()

        if ctx.interaction:
            msg = await ctx.interaction.followup.send(embed=embed, view=view)
        else:
            msg = await ctx.send(embed=embed, view=view)

        view.message = msg


async def setup(bot: commands.Bot):
    await bot.add_cog(Avatar(bot))
    logger.debug("Loaded Avatar Cog")