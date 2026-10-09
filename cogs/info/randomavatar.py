"""
cogs/info/randomavatar.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Interactive Random Server Member Avatar & Profile Showcase
Features:
  • 🖼️ Full-width high-resolution avatar display
  • 🎲 Instant re-roll for another random member
  • 👤 Detailed profile dossier view
  • 🗑️ Dismiss button
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import logging
import random
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

logger = logging.getLogger(__name__)

BRAND_COLOR = 0x5865F2
PURPLE_COLOR = 0x9B59B6


class RandomAvatarView(discord.ui.View):
    """Interactive media switcher for discovering random guild members."""

    def __init__(
        self,
        bot: commands.Bot,
        guild: discord.Guild,
        target: discord.Member,
        requester: discord.abc.User,
        current_tab: str = "avatar",
        timeout: float = 120,
    ):
        super().__init__(timeout=timeout)
        self.bot = bot
        self.guild = guild
        self.target = target
        self.requester = requester
        self.current_tab = current_tab
        self.message: Optional[discord.Message] = None

        self._setup_buttons()

    def _setup_buttons(self):
        self.clear_items()

        # 1. Reroll
        self.btn_reroll = discord.ui.Button(
            label="Another Member",
            emoji="🎲",
            style=discord.ButtonStyle.primary,
            custom_id="rav_reroll",
        )
        self.btn_reroll.callback = self._on_reroll
        self.add_item(self.btn_reroll)

        # 2. Avatar
        self.btn_avatar = discord.ui.Button(
            label="Avatar",
            emoji="🖼️",
            style=discord.ButtonStyle.success if self.current_tab == "avatar" else discord.ButtonStyle.secondary,
            custom_id="rav_tab_avatar",
        )
        self.btn_avatar.callback = self._on_avatar_click
        self.add_item(self.btn_avatar)

        # 3. Profile
        self.btn_profile = discord.ui.Button(
            label="Profile",
            emoji="👤",
            style=discord.ButtonStyle.success if self.current_tab == "profile" else discord.ButtonStyle.secondary,
            custom_id="rav_tab_profile",
        )
        self.btn_profile.callback = self._on_profile_click
        self.add_item(self.btn_profile)

        # 4. Dismiss
        self.btn_dismiss = discord.ui.Button(
            label="Dismiss",
            emoji="🗑️",
            style=discord.ButtonStyle.danger,
            custom_id="rav_dismiss",
        )
        self.btn_dismiss.callback = self._on_dismiss_click
        self.add_item(self.btn_dismiss)

    def _update_button_styles(self):
        self.btn_avatar.style = discord.ButtonStyle.success if self.current_tab == "avatar" else discord.ButtonStyle.secondary
        self.btn_profile.style = discord.ButtonStyle.success if self.current_tab == "profile" else discord.ButtonStyle.secondary

    def generate_embed(self) -> discord.Embed:
        u = self.target
        color = u.color if u.color.value else discord.Color(BRAND_COLOR)

        if self.current_tab == "avatar":
            embed = discord.Embed(
                title=f"🎲 Random Member: {u.display_name}",
                description=f"> Randomly selected from **{self.guild.name}**",
                color=color,
            )
            embed.set_image(url=str(u.display_avatar.with_size(1024).url))

            is_animated = u.display_avatar.is_animated()
            formats = [
                f"[PNG]({u.display_avatar.with_format('png').with_size(1024).url})",
                f"[WebP]({u.display_avatar.with_format('webp').with_size(1024).url})",
                f"[JPG]({u.display_avatar.with_format('jpeg').with_size(1024).url})",
            ]
            if is_animated:
                formats.insert(0, f"[GIF]({u.display_avatar.with_format('gif').with_size(1024).url})")

            embed.add_field(name="High-Res Downloads (1024px)", value="  •  ".join(formats), inline=False)
            embed.set_footer(
                text=f"Requested by {self.requester.display_name}  •  Member ID: {u.id}",
                icon_url=self.requester.display_avatar.url,
            )
            return embed

        elif self.current_tab == "profile":
            created_ts = int(u.created_at.timestamp())
            joined_ts = int(u.joined_at.timestamp()) if u.joined_at else created_ts

            embed = discord.Embed(
                title=f"👤 {u.display_name}'s Profile Dossier",
                description=f"> Exploring members in **{self.guild.name}**",
                color=color,
            )
            embed.set_thumbnail(url=u.display_avatar.url)

            handle = f"@{u.name}" if getattr(u, "discriminator", "0") in ("0", None) else f"{u.name}#{u.discriminator}"
            embed.add_field(name="Username", value=f"`{handle}`", inline=True)
            embed.add_field(name="User ID", value=f"`{u.id}`", inline=True)
            top_role = u.top_role.mention if u.top_role.name != "@everyone" else "`None`"
            embed.add_field(name="Top Role", value=top_role, inline=True)
            embed.add_field(
                name="Account Created",
                value=f"<t:{created_ts}:F> (<t:{created_ts}:R>)",
                inline=False,
            )
            embed.add_field(
                name="Joined Server",
                value=f"<t:{joined_ts}:F> (<t:{joined_ts}:R>)",
                inline=False,
            )
            embed.set_footer(
                text=f"Requested by {self.requester.display_name}",
                icon_url=self.requester.display_avatar.url,
            )
            return embed

        return self.generate_embed()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.data.get("custom_id") == "rav_dismiss":
            if interaction.user.id != self.requester.id:
                await interaction.response.send_message(
                    "❌ Only the person who requested this can dismiss it.",
                    ephemeral=True,
                )
                return False
        return True

    async def _on_avatar_click(self, interaction: discord.Interaction):
        self.current_tab = "avatar"
        self._update_button_styles()
        await interaction.response.edit_message(embed=self.generate_embed(), view=self)

    async def _on_profile_click(self, interaction: discord.Interaction):
        self.current_tab = "profile"
        self._update_button_styles()
        await interaction.response.edit_message(embed=self.generate_embed(), view=self)

    async def _on_reroll(self, interaction: discord.Interaction):
        members = [m for m in self.guild.members if not m.bot and m.id != self.target.id]
        if not members:
            members = [m for m in self.guild.members if not m.bot]
        if not members:
            await interaction.response.send_message("❌ No eligible members found to re-roll.", ephemeral=True)
            return

        self.target = random.choice(members)
        embed = self.generate_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    async def _on_dismiss_click(self, interaction: discord.Interaction):
        try:
            await interaction.message.delete()
        except Exception:
            try:
                await interaction.response.edit_message(content="*Dismissed.*", embed=None, view=None)
            except Exception:
                pass


class RandomAvatar(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(
        name="randomavatar",
        description="🎲 Inspect a random member's avatar and profile with live re-roll",
        aliases=["rav"],
    )
    async def randomavatar(self, ctx: commands.Context):
        if not ctx.guild:
            await ctx.send("❌ This command must be used within a server.", ephemeral=True)
            return

        members = [m for m in ctx.guild.members if not m.bot]
        if not members:
            await ctx.send("❌ Could not find any eligible server members.", ephemeral=True)
            return

        user = random.choice(members)
        view = RandomAvatarView(self.bot, ctx.guild, user, ctx.author)
        embed = view.generate_embed()

        if ctx.interaction:
            msg = await ctx.interaction.response.send_message(embed=embed, view=view)
        else:
            msg = await ctx.send(embed=embed, view=view)

        view.message = msg


async def setup(bot):
    await bot.add_cog(RandomAvatar(bot))