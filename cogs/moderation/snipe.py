"""
cogs/moderation/snipe.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Nexora Snipe Engine · Powered by Discord Components V2
Captures deleted messages, edited messages, and removed reactions.
Provides interactive pagination views with media previews and dismiss buttons.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timezone
import typing
import logging
from collections import deque

from utils.ui import (
    NexoraView,
    NexoraCardView,
    DismissButton,
    send_view,
    ts_format,
    BRAND_COLOR,
    ERROR_COLOR,
    WARNING_COLOR,
    SUCCESS_COLOR,
    CYAN_COLOR,
    PURPLE_COLOR,
)

logger = logging.getLogger(__name__)


class SnipeLayoutView(NexoraView):
    """Modern Components V2 Pagination view for snipe history."""

    def __init__(
        self,
        bot: commands.Bot,
        snipes: list,
        channel: discord.TextChannel,
        requester: typing.Union[discord.Member, discord.User],
        snipe_type: str = "deleted",
        initial_index: int = 0,
        cog_ref: typing.Optional[commands.Cog] = None,
    ):
        color = ERROR_COLOR if snipe_type == "deleted" else WARNING_COLOR
        super().__init__(bot=bot, user_id=requester.id, color=color, timeout=120)
        self.snipes = snipes
        self.channel = channel
        self.requester = requester
        self.snipe_type = snipe_type
        self.current_page = max(0, min(initial_index, len(snipes) - 1))
        self.max_pages = len(snipes)
        self.cog_ref = cog_ref
        self._build()

    def _build(self):
        self.clear_container()

        if not self.snipes:
            self.add_section(
                f"# 📭 No Snipe History\n"
                f"> All cached records for {self.channel.mention} have been cleared."
            )
            self.add_row(DismissButton(user_id=self.requester.id))
            return

        snipe = self.snipes[self.current_page]
        author = snipe.get("author")
        avatar_url = snipe.get("avatar_url")
        ts_str = ts_format(snipe.get("timestamp"), "R")

        if self.snipe_type == "deleted":
            author_mention = author.mention if hasattr(author, "mention") else f"**{author}**"
            header = (
                f"# 🗑️ Sniped Message · #{self.channel.name}\n"
                f"> Author: {author_mention} · Deleted {ts_str}"
            )
            self.add_section(header, thumbnail_url=avatar_url)
            self.add_separator(discord.SeparatorSpacing.small)

            content = snipe.get("content") or "*[No text content]*"
            self.add_text(f"### Message Content\n{content}")

            attachments = snipe.get("attachments", [])
            if attachments:
                img_url = next(
                    (
                        url
                        for url in attachments
                        if any(
                            url.lower().endswith(ext)
                            for ext in [".png", ".jpg", ".jpeg", ".gif", ".webp"]
                        )
                    ),
                    None,
                )
                if img_url:
                    try:
                        self.container.add_item(
                            discord.ui.MediaGallery(discord.MediaGalleryItem(img_url))
                        )
                    except Exception:
                        pass
                att_links = "\n".join(
                    f"• [Attachment {i+1}]({url})" for i, url in enumerate(attachments)
                )
                self.add_text(f"### 📎 Attachments ({len(attachments)})\n{att_links}")

            stickers = snipe.get("stickers", [])
            if stickers:
                self.add_text(f"### 🎴 Stickers\n• {len(stickers)} custom sticker(s) attached")

            self.add_footer(
                f"Page {self.current_page + 1} of {self.max_pages} · "
                f"#{self.channel.name} · Requested by {self.requester.display_name}"
            )
        else:  # edited
            author_mention = author.mention if hasattr(author, "mention") else f"**{author}**"
            header = (
                f"# ✏️ Sniped Edit · #{self.channel.name}\n"
                f"> Author: {author_mention} · Edited {ts_str}"
            )
            self.add_section(header, thumbnail_url=avatar_url)
            self.add_separator(discord.SeparatorSpacing.small)

            before_content = snipe.get("before") or "*[No text content]*"
            after_content = snipe.get("after") or "*[No text content]*"

            self.add_text(f"### 📝 Before Edit\n{before_content}")
            self.add_separator(discord.SeparatorSpacing.small)
            self.add_text(f"### ✏️ After Edit\n{after_content}")

            if "jump_url" in snipe:
                self.add_text(f"[🔗 Jump to current message]({snipe['jump_url']})")

            self.add_footer(
                f"Edit {self.current_page + 1} of {self.max_pages} · "
                f"#{self.channel.name} · Requested by {self.requester.display_name}"
            )

        # Pagination & Action Buttons
        prev_btn = discord.ui.Button(
            label="Previous",
            emoji="◀️",
            style=discord.ButtonStyle.secondary,
            disabled=(self.current_page == 0),
        )
        prev_btn.callback = self._on_prev

        next_btn = discord.ui.Button(
            label="Next",
            emoji="▶️",
            style=discord.ButtonStyle.secondary,
            disabled=(self.current_page >= self.max_pages - 1),
        )
        next_btn.callback = self._on_next

        clear_btn = discord.ui.Button(
            label="Clear History",
            emoji="🗑️",
            style=discord.ButtonStyle.danger,
        )
        clear_btn.callback = self._on_clear

        dismiss_btn = DismissButton(user_id=self.requester.id)

        if self.max_pages > 1:
            self.add_row(prev_btn, next_btn, clear_btn, dismiss_btn)
        else:
            self.add_row(clear_btn, dismiss_btn)

    async def _on_prev(self, interaction: discord.Interaction):
        if interaction.user.id != self.requester.id:
            await interaction.response.send_message(
                "❌ This snipe card belongs to someone else.",
                ephemeral=True,
            )
            return
        if self.current_page > 0:
            self.current_page -= 1
            self._build()
            await interaction.response.edit_message(view=self)

    async def _on_next(self, interaction: discord.Interaction):
        if interaction.user.id != self.requester.id:
            await interaction.response.send_message(
                "❌ This snipe card belongs to someone else.",
                ephemeral=True,
            )
            return
        if self.current_page < self.max_pages - 1:
            self.current_page += 1
            self._build()
            await interaction.response.edit_message(view=self)

    async def _on_clear(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message(
                "❌ You need `Manage Messages` permission to clear snipe history!",
                ephemeral=True,
            )
            return
        if self.cog_ref:
            if self.snipe_type == "deleted" and self.channel.id in getattr(self.cog_ref, "snipes", {}):
                self.cog_ref.snipes[self.channel.id].clear()
            elif self.snipe_type == "edited" and self.channel.id in getattr(self.cog_ref, "edit_snipes", {}):
                self.cog_ref.edit_snipes[self.channel.id].clear()
        self.snipes = []
        self._build()
        await interaction.response.edit_message(view=self)


class ReactionSnipeLayoutView(NexoraView):
    """Components V2 LayoutView for removed reaction records with interactive pagination."""

    def __init__(
        self,
        bot: commands.Bot,
        snipes: list,
        channel: discord.TextChannel,
        requester: typing.Union[discord.Member, discord.User],
        initial_index: int = 0,
        cog_ref: typing.Optional[commands.Cog] = None,
    ):
        super().__init__(bot=bot, user_id=requester.id, color=PURPLE_COLOR, timeout=120)
        self.snipes = snipes
        self.channel = channel
        self.requester = requester
        self.current_page = max(0, min(initial_index, len(snipes) - 1))
        self.max_pages = len(snipes)
        self.cog_ref = cog_ref
        self._build()

    def _build(self):
        self.clear_container()

        if not self.snipes:
            self.add_section(
                f"# 📭 No Reaction History\n"
                f"> All cached removed reactions for {self.channel.mention} have been cleared."
            )
            self.add_row(DismissButton(user_id=self.requester.id))
            return

        snipe = self.snipes[self.current_page]
        user = snipe.get("user")
        user_mention = user.mention if hasattr(user, "mention") else f"**{user}**"
        ts_str = ts_format(snipe.get("timestamp"), "R")

        header = (
            f"# 😮 Sniped Reaction · #{self.channel.name}\n"
            f"> Removed by {user_mention} · {ts_str}"
        )
        self.add_section(header, thumbnail_url=snipe.get("avatar_url"))
        self.add_separator(discord.SeparatorSpacing.small)

        author = snipe.get("message_author")
        author_name = author.display_name if hasattr(author, "display_name") else str(author)
        content = (
            f"• **Reaction Emoji:** {snipe.get('emoji')}\n"
            f"• **Message Author:** **{author_name}**\n"
            f"• **Message Snippet:** {snipe.get('message_content')}"
        )
        self.add_text(content)
        self.add_footer(
            f"Reaction {self.current_page + 1} of {self.max_pages} · "
            f"#{self.channel.name} · Requested by {self.requester.display_name}"
        )

        prev_btn = discord.ui.Button(
            label="Previous",
            emoji="◀️",
            style=discord.ButtonStyle.secondary,
            disabled=(self.current_page == 0),
        )
        prev_btn.callback = self._on_prev

        next_btn = discord.ui.Button(
            label="Next",
            emoji="▶️",
            style=discord.ButtonStyle.secondary,
            disabled=(self.current_page >= self.max_pages - 1),
        )
        next_btn.callback = self._on_next

        clear_btn = discord.ui.Button(
            label="Clear History",
            emoji="🗑️",
            style=discord.ButtonStyle.danger,
        )
        clear_btn.callback = self._on_clear

        dismiss_btn = DismissButton(user_id=self.requester.id)

        if self.max_pages > 1:
            self.add_row(prev_btn, next_btn, clear_btn, dismiss_btn)
        else:
            self.add_row(clear_btn, dismiss_btn)

    async def _on_prev(self, interaction: discord.Interaction):
        if self.current_page > 0:
            self.current_page -= 1
            self._build()
            await interaction.response.edit_message(view=self)

    async def _on_next(self, interaction: discord.Interaction):
        if self.current_page < self.max_pages - 1:
            self.current_page += 1
            self._build()
            await interaction.response.edit_message(view=self)

    async def _on_clear(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message(
                "❌ You need `Manage Messages` permission to clear reaction snipe history!",
                ephemeral=True,
            )
            return
        if self.cog_ref and self.channel.id in getattr(self.cog_ref, "reaction_snipes", {}):
            self.cog_ref.reaction_snipes[self.channel.id].clear()
        self.snipes = []
        self._build()
        await interaction.response.edit_message(view=self)


class SnipeStatsView(NexoraView):
    """Components V2 LayoutView for guild snipe cache diagnostics."""

    def __init__(
        self,
        bot: commands.Bot,
        guild: discord.Guild,
        total_deleted: int,
        total_edited: int,
        total_reactions: int,
        max_per_channel: int,
        requester: typing.Union[discord.Member, discord.User],
    ):
        super().__init__(bot=bot, user_id=requester.id, color=CYAN_COLOR, timeout=120)
        header = (
            f"# 📊 Snipe Telemetry · {guild.name}\n"
            f"> Active message trace caches across all guild channels"
        )
        guild_icon = str(guild.icon.url) if guild.icon else None
        self.add_section(header, thumbnail_url=guild_icon)
        self.add_separator(discord.SeparatorSpacing.small)

        stats_text = (
            "### 📈 Cached Records\n"
            f"• **Deleted Messages:** `{total_deleted:,}` entries\n"
            f"• **Edited Messages:** `{total_edited:,}` entries\n"
            f"• **Removed Reactions:** `{total_reactions:,}` entries\n"
            f"• **Channel Buffer Size:** `{max_per_channel}` max records / channel"
        )
        self.add_text(stats_text)
        self.add_footer(f"Requested by {requester.display_name} · Real-time guild cache")
        self.add_row(DismissButton(user_id=requester.id))


class Snipe(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.max_snipes = 10  # Maximum messages to store per channel
        self.snipes = {}  # Store deleted messages per channel
        self.edit_snipes = {}  # Store edited messages per channel
        self.reaction_snipes = {}  # Store removed reactions per channel

    @commands.Cog.listener()
    async def on_message_delete(self, message):
        """Track deleted messages"""
        if message.author.bot:
            return

        if message.channel.id not in self.snipes:
            self.snipes[message.channel.id] = deque(maxlen=self.max_snipes)

        snipe_data = {
            "content": message.content,
            "author": message.author,
            "avatar_url": (
                message.author.avatar.url
                if message.author.avatar
                else message.author.default_avatar.url
            ),
            "timestamp": datetime.now(timezone.utc),
            "attachments": [attachment.url for attachment in message.attachments],
            "stickers": [sticker.url for sticker in message.stickers] if message.stickers else [],
            "message_id": message.id,
        }

        self.snipes[message.channel.id].appendleft(snipe_data)

    @commands.Cog.listener()
    async def on_bulk_message_delete(self, messages):
        """Track bulk deleted messages"""
        for message in messages:
            if not message.author.bot:
                if message.channel.id not in self.snipes:
                    self.snipes[message.channel.id] = deque(maxlen=self.max_snipes)

                snipe_data = {
                    "content": message.content,
                    "author": message.author,
                    "avatar_url": (
                        message.author.avatar.url
                        if message.author.avatar
                        else message.author.default_avatar.url
                    ),
                    "timestamp": datetime.now(timezone.utc),
                    "attachments": [attachment.url for attachment in message.attachments],
                    "stickers": [sticker.url for sticker in message.stickers] if message.stickers else [],
                    "message_id": message.id,
                }

                self.snipes[message.channel.id].appendleft(snipe_data)

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        """Track edited messages"""
        if before.author.bot or before.content == after.content:
            return

        if before.channel.id not in self.edit_snipes:
            self.edit_snipes[before.channel.id] = deque(maxlen=self.max_snipes)

        snipe_data = {
            "before": before.content,
            "after": after.content,
            "author": before.author,
            "avatar_url": (
                before.author.avatar.url
                if before.author.avatar
                else before.author.default_avatar.url
            ),
            "timestamp": datetime.now(timezone.utc),
            "message_id": before.id,
            "jump_url": after.jump_url,
        }

        self.edit_snipes[before.channel.id].appendleft(snipe_data)

    @commands.Cog.listener()
    async def on_reaction_remove(self, reaction, user):
        """Track removed reactions"""
        if user.bot:
            return

        if reaction.message.channel.id not in self.reaction_snipes:
            self.reaction_snipes[reaction.message.channel.id] = deque(maxlen=self.max_snipes)

        reaction_data = {
            "emoji": str(reaction.emoji),
            "user": user,
            "avatar_url": user.avatar.url if user.avatar else user.default_avatar.url,
            "message_content": (
                reaction.message.content[:100]
                if reaction.message.content
                else "*No content*"
            ),
            "message_author": reaction.message.author,
            "timestamp": datetime.now(timezone.utc),
        }

        self.reaction_snipes[reaction.message.channel.id].appendleft(reaction_data)

    @commands.hybrid_command(name="snipe", description="Shows recently deleted messages in a channel")
    @app_commands.describe(
        channel="The channel to snipe from (optional)",
        member="Filter by specific member who sent the deleted message (optional)",
        index="Which deleted message to show (1 = most recent)",
    )
    @commands.guild_only()
    async def snipe(
        self,
        ctx: commands.Context,
        channel: typing.Optional[discord.TextChannel] = None,
        member: typing.Optional[discord.Member] = None,
        index: typing.Optional[int] = 1,
    ):
        """Shows the last deleted message(s) in the channel"""
        channel = channel or ctx.channel

        if channel != ctx.channel and not ctx.author.guild_permissions.manage_messages:
            view = NexoraCardView(
                title="Permission Denied",
                description="❌ You need `Manage Messages` permission to snipe other channels.",
                color=ERROR_COLOR,
                user_id=ctx.author.id,
            )
            return await send_view(ctx, view, ephemeral=True)

        if channel.id not in self.snipes or len(self.snipes[channel.id]) == 0:
            view = NexoraCardView(
                title="No Deleted Messages",
                description=f"📭 There are no deleted messages to snipe in {channel.mention}.",
                color=CYAN_COLOR,
                user_id=ctx.author.id,
            )
            return await send_view(ctx, view, ephemeral=True)

        snipes_list = list(self.snipes[channel.id])

        # Filter by member if specified
        if member:
            snipes_list = [
                s for s in snipes_list
                if getattr(s.get("author"), "id", None) == member.id
            ]
            if not snipes_list:
                view = NexoraCardView(
                    title="No Matching Snipes",
                    description=f"📭 No deleted messages found from {member.mention} in {channel.mention}.",
                    color=CYAN_COLOR,
                    user_id=ctx.author.id,
                )
                return await send_view(ctx, view, ephemeral=True)

        idx = index or 1
        if idx < 1 or idx > len(snipes_list):
            view = NexoraCardView(
                title="Invalid Index",
                description=f"❌ Invalid index. Please choose a number between **1** and **{len(snipes_list)}**.",
                color=WARNING_COLOR,
                user_id=ctx.author.id,
            )
            return await send_view(ctx, view, ephemeral=True)

        view = SnipeLayoutView(
            bot=self.bot,
            snipes=snipes_list,
            channel=channel,
            requester=ctx.author,
            snipe_type="deleted",
            initial_index=idx - 1,
            cog_ref=self,
        )
        await send_view(ctx, view)

    @commands.hybrid_command(
        name="editsnipe",
        aliases=["esnipe"],
        description="Shows recently edited messages in a channel",
    )
    @app_commands.describe(
        channel="The channel to snipe from (optional)",
        index="Which edited message to show (1 = most recent)",
    )
    @commands.guild_only()
    async def editsnipe(
        self,
        ctx: commands.Context,
        channel: typing.Optional[discord.TextChannel] = None,
        index: typing.Optional[int] = 1,
    ):
        """Shows the last edited message(s) in the channel"""
        channel = channel or ctx.channel

        if channel != ctx.channel and not ctx.author.guild_permissions.manage_messages:
            view = NexoraCardView(
                title="Permission Denied",
                description="❌ You need `Manage Messages` permission to snipe other channels.",
                color=ERROR_COLOR,
                user_id=ctx.author.id,
            )
            return await send_view(ctx, view, ephemeral=True)

        if channel.id not in self.edit_snipes or len(self.edit_snipes[channel.id]) == 0:
            view = NexoraCardView(
                title="No Edited Messages",
                description=f"📭 There are no edited messages to snipe in {channel.mention}.",
                color=CYAN_COLOR,
                user_id=ctx.author.id,
            )
            return await send_view(ctx, view, ephemeral=True)

        snipes_list = list(self.edit_snipes[channel.id])

        idx = index or 1
        if idx < 1 or idx > len(snipes_list):
            view = NexoraCardView(
                title="Invalid Index",
                description=f"❌ Invalid index. Please choose a number between **1** and **{len(snipes_list)}**.",
                color=WARNING_COLOR,
                user_id=ctx.author.id,
            )
            return await send_view(ctx, view, ephemeral=True)

        view = SnipeLayoutView(
            bot=self.bot,
            snipes=snipes_list,
            channel=channel,
            requester=ctx.author,
            snipe_type="edited",
            initial_index=idx - 1,
            cog_ref=self,
        )
        await send_view(ctx, view)

    @commands.hybrid_command(
        name="reactionsnipe",
        aliases=["rsnipe"],
        description="Shows recently removed reactions in a channel",
    )
    @app_commands.describe(
        channel="The channel to snipe from (optional)",
        index="Which removed reaction to show (1 = most recent)",
    )
    @commands.guild_only()
    async def reactionsnipe(
        self,
        ctx: commands.Context,
        channel: typing.Optional[discord.TextChannel] = None,
        index: typing.Optional[int] = 1,
    ):
        """Shows recently removed reaction(s) in the channel"""
        channel = channel or ctx.channel

        if channel.id not in self.reaction_snipes or len(self.reaction_snipes[channel.id]) == 0:
            view = NexoraCardView(
                title="No Removed Reactions",
                description=f"📭 There are no removed reactions to snipe in {channel.mention}.",
                color=CYAN_COLOR,
                user_id=ctx.author.id,
            )
            return await send_view(ctx, view, ephemeral=True)

        snipes_list = list(self.reaction_snipes[channel.id])
        idx = index or 1
        if idx < 1 or idx > len(snipes_list):
            view = NexoraCardView(
                title="Invalid Index",
                description=f"❌ Invalid index. Please choose a number between **1** and **{len(snipes_list)}**.",
                color=WARNING_COLOR,
                user_id=ctx.author.id,
            )
            return await send_view(ctx, view, ephemeral=True)

        view = ReactionSnipeLayoutView(
            bot=self.bot,
            snipes=snipes_list,
            channel=channel,
            requester=ctx.author,
            initial_index=idx - 1,
            cog_ref=self,
        )
        await send_view(ctx, view)

    @commands.command(name="clearsnipes")
    @commands.guild_only()
    @commands.has_permissions(manage_messages=True)
    async def clearsnipes(
        self,
        ctx: commands.Context,
        channel: typing.Optional[discord.TextChannel] = None,
    ):
        """Clear snipe history for a channel (requires Manage Messages)"""
        channel = channel or ctx.channel

        cleared_count = 0
        if channel.id in self.snipes:
            cleared_count += len(self.snipes[channel.id])
            self.snipes[channel.id].clear()

        if channel.id in self.edit_snipes:
            cleared_count += len(self.edit_snipes[channel.id])
            self.edit_snipes[channel.id].clear()

        if channel.id in self.reaction_snipes:
            cleared_count += len(self.reaction_snipes[channel.id])
            self.reaction_snipes[channel.id].clear()

        view = NexoraCardView(
            title="Snipe Cache Purged",
            description=f"✅ Cleared **{cleared_count}** sniped message(s) from {channel.mention}.",
            color=SUCCESS_COLOR,
            user_id=ctx.author.id,
        )
        await send_view(ctx, view)

    @commands.command(name="snipestats")
    @commands.guild_only()
    async def snipestats(self, ctx: commands.Context):
        """Display snipe statistics"""
        total_deleted = sum(
            len(snipes)
            for channel_id, snipes in self.snipes.items()
            if ctx.guild.get_channel(channel_id)
        )
        total_edited = sum(
            len(snipes)
            for channel_id, snipes in self.edit_snipes.items()
            if ctx.guild.get_channel(channel_id)
        )
        total_reactions = sum(
            len(snipes)
            for channel_id, snipes in self.reaction_snipes.items()
            if ctx.guild.get_channel(channel_id)
        )

        view = SnipeStatsView(
            bot=self.bot,
            guild=ctx.guild,
            total_deleted=total_deleted,
            total_edited=total_edited,
            total_reactions=total_reactions,
            max_per_channel=self.max_snipes,
            requester=ctx.author,
        )
        await send_view(ctx, view)


async def setup(bot):
    await bot.add_cog(Snipe(bot))
