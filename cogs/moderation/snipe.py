import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime
import typing
import logging
from collections import deque

logger = logging.getLogger(__name__)


class SnipeView(discord.ui.View):
    """Pagination view for snipe history"""
    def __init__(self, snipes, channel_name, snipe_type="deleted"):
        super().__init__(timeout=60)
        self.snipes = snipes
        self.channel_name = channel_name
        self.snipe_type = snipe_type
        self.current_page = 0
        self.max_pages = len(snipes)
        
    def create_embed(self):
        """Create embed for current page"""
        snipe = self.snipes[self.current_page]
        
        if self.snipe_type == "deleted":
            embed = discord.Embed(
                description=snipe["content"] or "*No text content*",
                color=discord.Color.red(),
                timestamp=snipe["timestamp"]
            )
            embed.set_author(name=f"{snipe['author']}", icon_url=snipe["avatar_url"])
            embed.set_footer(text=f"Deleted in #{self.channel_name} • Message {self.current_page + 1}/{self.max_pages}")
            
            if snipe["attachments"]:
                embed.add_field(name="📎 Attachments", value="\n".join(snipe["attachments"]), inline=False)
                # Set image if first attachment is an image
                if snipe["attachments"] and any(snipe["attachments"][0].lower().endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.gif', '.webp']):
                    embed.set_image(url=snipe["attachments"][0])
        else:  # edited
            embed = discord.Embed(color=discord.Color.orange(), timestamp=snipe["timestamp"])
            embed.set_author(name=f"{snipe['author']}", icon_url=snipe["avatar_url"])
            embed.add_field(name="📝 Before", value=snipe["before"] or "*No text content*", inline=False)
            embed.add_field(name="✏️ After", value=snipe["after"] or "*No text content*", inline=False)
            embed.set_footer(text=f"Edited in #{self.channel_name} • Edit {self.current_page + 1}/{self.max_pages}")
        
        return embed
    
    @discord.ui.button(label="◀️ Previous", style=discord.ButtonStyle.blurple, disabled=True)
    async def previous_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page -= 1
        self.update_buttons()
        await interaction.response.edit_message(embed=self.create_embed(), view=self)
    
    @discord.ui.button(label="Next ▶️", style=discord.ButtonStyle.blurple)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page += 1
        self.update_buttons()
        await interaction.response.edit_message(embed=self.create_embed(), view=self)
    
    @discord.ui.button(label="🗑️ Clear History", style=discord.ButtonStyle.danger)
    async def clear_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Check if user has manage messages permission
        if not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message("❌ You need `Manage Messages` permission to clear snipe history!", ephemeral=True)
            return
        
        await interaction.response.send_message("✅ Snipe history cleared for this channel!", ephemeral=True)
        self.stop()
    
    def update_buttons(self):
        """Update button states based on current page"""
        self.previous_button.disabled = (self.current_page == 0)
        self.next_button.disabled = (self.current_page >= self.max_pages - 1)
    
    async def on_timeout(self):
        """Disable all buttons when view times out"""
        for item in self.children:
            item.disabled = True


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
        
        # Initialize deque for channel if not exists
        if message.channel.id not in self.snipes:
            self.snipes[message.channel.id] = deque(maxlen=self.max_snipes)
        
        snipe_data = {
            "content": message.content,
            "author": message.author,
            "avatar_url": message.author.avatar.url if message.author.avatar else message.author.default_avatar.url,
            "timestamp": datetime.now(),
            "attachments": [attachment.url for attachment in message.attachments],
            "stickers": [sticker.url for sticker in message.stickers] if message.stickers else [],
            "message_id": message.id
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
                    "avatar_url": message.author.avatar.url if message.author.avatar else message.author.default_avatar.url,
                    "timestamp": datetime.now(),
                    "attachments": [attachment.url for attachment in message.attachments],
                    "stickers": [sticker.url for sticker in message.stickers] if message.stickers else [],
                    "message_id": message.id
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
            "avatar_url": before.author.avatar.url if before.author.avatar else before.author.default_avatar.url,
            "timestamp": datetime.now(),
            "message_id": before.id,
            "jump_url": after.jump_url
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
            "message_content": reaction.message.content[:100] if reaction.message.content else "*No content*",
            "message_author": reaction.message.author,
            "timestamp": datetime.now()
        }
        
        self.reaction_snipes[reaction.message.channel.id].appendleft(reaction_data)

    @commands.hybrid_command(name="snipe", description="Shows recently deleted messages in a channel")
    @app_commands.describe(
        channel="The channel to snipe from (optional)",
        index="Which deleted message to show (1 = most recent)"
    )
    @commands.guild_only()
    async def snipe(
        self, 
        ctx: commands.Context, 
        channel: typing.Optional[discord.TextChannel] = None,
        index: typing.Optional[int] = 1
    ):
        """Shows the last deleted message(s) in the channel"""
        channel = channel or ctx.channel
        
        # Check permissions
        if channel != ctx.channel and not ctx.author.guild_permissions.manage_messages:
            return await ctx.send("❌ You need `Manage Messages` permission to snipe other channels!", ephemeral=True)
        
        if channel.id not in self.snipes or len(self.snipes[channel.id]) == 0:
            return await ctx.send(f"📭 There are no deleted messages to snipe in {channel.mention}!", ephemeral=True)
        
        snipes_list = list(self.snipes[channel.id])
        
        # Validate index
        if index < 1 or index > len(snipes_list):
            return await ctx.send(f"❌ Invalid index! Use a number between 1 and {len(snipes_list)}.", ephemeral=True)
        
        # Show single snipe or use pagination
        if index == 1 and len(snipes_list) > 1:
            view = SnipeView(snipes_list, channel.name, "deleted")
            embed = view.create_embed()
            await ctx.send(embed=embed, view=view)
        else:
            snipe = snipes_list[index - 1]
            embed = discord.Embed(
                description=snipe["content"] or "*No text content*",
                color=discord.Color.red(),
                timestamp=snipe["timestamp"]
            )
            embed.set_author(name=f"{snipe['author']}", icon_url=snipe["avatar_url"])
            embed.set_footer(text=f"Deleted in #{channel.name} • Message {index}/{len(snipes_list)}")
            
            if snipe["attachments"]:
                embed.add_field(name="📎 Attachments", value="\n".join(snipe["attachments"]), inline=False)
                if any(snipe["attachments"][0].lower().endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.gif', '.webp']):
                    embed.set_image(url=snipe["attachments"][0])
            
            if snipe["stickers"]:
                embed.add_field(name="🎴 Stickers", value=f"{len(snipe['stickers'])} sticker(s)", inline=False)
            
            await ctx.send(embed=embed)

    @commands.hybrid_command(name="editsnipe", aliases=["esnipe"], description="Shows recently edited messages in a channel")
    @app_commands.describe(
        channel="The channel to snipe from (optional)",
        index="Which edited message to show (1 = most recent)"
    )
    @commands.guild_only()
    async def editsnipe(
        self, 
        ctx: commands.Context, 
        channel: typing.Optional[discord.TextChannel] = None,
        index: typing.Optional[int] = 1
    ):
        """Shows the last edited message(s) in the channel"""
        channel = channel or ctx.channel
        
        if channel != ctx.channel and not ctx.author.guild_permissions.manage_messages:
            return await ctx.send("❌ You need `Manage Messages` permission to snipe other channels!", ephemeral=True)
        
        if channel.id not in self.edit_snipes or len(self.edit_snipes[channel.id]) == 0:
            return await ctx.send(f"📭 There are no edited messages to snipe in {channel.mention}!", ephemeral=True)
        
        snipes_list = list(self.edit_snipes[channel.id])
        
        if index < 1 or index > len(snipes_list):
            return await ctx.send(f"❌ Invalid index! Use a number between 1 and {len(snipes_list)}.", ephemeral=True)
        
        if index == 1 and len(snipes_list) > 1:
            view = SnipeView(snipes_list, channel.name, "edited")
            embed = view.create_embed()
            await ctx.send(embed=embed, view=view)
        else:
            snipe = snipes_list[index - 1]
            embed = discord.Embed(color=discord.Color.orange(), timestamp=snipe["timestamp"])
            embed.set_author(name=f"{snipe['author']}", icon_url=snipe["avatar_url"])
            embed.add_field(name="📝 Before", value=snipe["before"] or "*No text content*", inline=False)
            embed.add_field(name="✏️ After", value=snipe["after"] or "*No text content*", inline=False)
            embed.set_footer(text=f"Edited in #{channel.name} • Edit {index}/{len(snipes_list)}")
            
            if "jump_url" in snipe:
                embed.add_field(name="🔗 Jump to Message", value=f"[Click here]({snipe['jump_url']})", inline=False)
            
            await ctx.send(embed=embed)

    @commands.hybrid_command(name="reactionsnipe", aliases=["rsnipe"], description="Shows recently removed reactions")
    @app_commands.describe(channel="The channel to snipe from (optional)")
    @commands.guild_only()
    async def reactionsnipe(self, ctx: commands.Context, channel: typing.Optional[discord.TextChannel] = None):
        """Shows the last removed reaction in the channel"""
        channel = channel or ctx.channel
        
        if channel.id not in self.reaction_snipes or len(self.reaction_snipes[channel.id]) == 0:
            return await ctx.send(f"📭 There are no removed reactions to snipe in {channel.mention}!", ephemeral=True)
        
        snipe = list(self.reaction_snipes[channel.id])[0]
        embed = discord.Embed(
            description=f"**Reaction:** {snipe['emoji']}\n**On message by:** {snipe['message_author']}\n**Message:** {snipe['message_content']}",
            color=discord.Color.purple(),
            timestamp=snipe["timestamp"]
        )
        embed.set_author(name=f"Removed by {snipe['user']}", icon_url=snipe["avatar_url"])
        embed.set_footer(text=f"Reaction removed in #{channel.name}")
        
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="clearsnipes", description="Clear snipe history for a channel")
    @app_commands.describe(channel="The channel to clear (optional - clears current channel)")
    @commands.guild_only()
    @commands.has_permissions(manage_messages=True)
    async def clearsnipes(self, ctx: commands.Context, channel: typing.Optional[discord.TextChannel] = None):
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
        
        embed = discord.Embed(
            description=f"✅ Cleared **{cleared_count}** sniped message(s) from {channel.mention}",
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="snipestats", description="View snipe statistics for the server")
    @commands.guild_only()
    async def snipestats(self, ctx: commands.Context):
        """Display snipe statistics"""
        total_deleted = sum(len(snipes) for channel_id, snipes in self.snipes.items() if ctx.guild.get_channel(channel_id))
        total_edited = sum(len(snipes) for channel_id, snipes in self.edit_snipes.items() if ctx.guild.get_channel(channel_id))
        total_reactions = sum(len(snipes) for channel_id, snipes in self.reaction_snipes.items() if ctx.guild.get_channel(channel_id))
        
        embed = discord.Embed(
            title=f"📊 Snipe Statistics for {ctx.guild.name}",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        embed.add_field(name="🗑️ Deleted Messages", value=f"``````", inline=True)
        embed.add_field(name="✏️ Edited Messages", value=f"``````", inline=True)
        embed.add_field(name="😮 Removed Reactions", value=f"``````", inline=True)
        embed.add_field(name="⚙️ Max Per Channel", value=f"``````", inline=True)
        embed.set_footer(text=f"Requested by {ctx.author.display_name}", icon_url=ctx.author.display_avatar.url)
        
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Snipe(bot))
