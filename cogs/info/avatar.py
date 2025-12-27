import discord
from discord.ext import commands
from discord import app_commands
import random
import asyncio

class AvatarView(discord.ui.View):
    def __init__(self, user: discord.User, bot):
        super().__init__(timeout=60)
        self.user = user
        self.bot = bot

    # The button functions are correct as they use interaction.response.defer()
    @discord.ui.button(label="Avatar", style=discord.ButtonStyle.primary, emoji="🖼️")
    async def avatar_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        embed = discord.Embed(
            title=f"🖼️ {self.user.display_name}'s Avatar", 
            color=discord.Color.blue()
        )
        embed.set_image(url=self.user.display_avatar.url)
        embed.set_footer(text=f"Requested by {interaction.user.display_name}", icon_url=interaction.user.display_avatar.url)
        await interaction.followup.edit_message(interaction.message.id, embed=embed, view=self)

    @discord.ui.button(label="Banner", style=discord.ButtonStyle.secondary, emoji="🌆")
    async def banner_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            user = await self.bot.fetch_user(self.user.id)
            if not hasattr(user, 'banner') or user.banner is None:
                await interaction.response.send_message(
                    f"❌ {self.user.display_name} doesn't have a banner set!", 
                    ephemeral=True
                )
                return
        except:
            if not hasattr(self.user, 'banner') or self.user.banner is None:
                await interaction.response.send_message(
                    f"❌ {self.user.display_name} doesn't have a banner set!", 
                    ephemeral=True
                )
                return
            user = self.user
        await interaction.response.defer()
        embed = discord.Embed(
            title=f"🌆 {user.display_name}'s Banner", 
            color=discord.Color.purple()
        )
        embed.set_image(url=user.banner.url)
        embed.set_footer(text=f"Requested by {interaction.user.display_name}", icon_url=interaction.user.display_avatar.url)
        await interaction.followup.edit_message(interaction.message.id, embed=embed, view=self)

    @discord.ui.button(label="Profile", style=discord.ButtonStyle.success, emoji="👤")
    async def profile_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        embed = discord.Embed(
            title=f"👤 {self.user.display_name}'s Profile", 
            color=discord.Color.green()
        )
        embed.add_field(name="Username", value=f"{self.user.name}#{self.user.discriminator}", inline=True)
        embed.add_field(name="User ID", value=f"`{self.user.id}`", inline=True)
        embed.add_field(name="Account Created", value=f"<t:{int(self.user.created_at.timestamp())}:R>", inline=True)
        embed.set_thumbnail(url=self.user.display_avatar.url)
        try:
            user = await self.bot.fetch_user(self.user.id)
            if hasattr(user, 'banner') and user.banner is not None:
                embed.set_image(url=user.banner.url)
        except:
            if hasattr(self.user, 'banner') and self.user.banner is not None:
                embed.set_image(url=self.user.banner.url)
        embed.set_footer(text=f"Requested by {interaction.user.display_name}", icon_url=interaction.user.display_avatar.url)
        await interaction.followup.edit_message(interaction.message.id, embed=embed, view=self)

    @discord.ui.button(label="Download", style=discord.ButtonStyle.gray, emoji="💾")
    async def download_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title=f"💾 Download {self.user.display_name}'s Images", 
            color=discord.Color.dark_gray(),
            description="Click the links below to download:"
        )
        embed.add_field(
            name="🖼️ Avatar", 
            value=f"[Download Avatar]({self.user.display_avatar.url})", 
            inline=False
        )
        banner_available = False
        try:
            user = await self.bot.fetch_user(self.user.id)
            if hasattr(user, 'banner') and user.banner is not None:
                embed.add_field(
                    name="🌆 Banner", 
                    value=f"[Download Banner]({user.banner.url})", 
                    inline=False
                )
                banner_available = True
        except:
            if hasattr(self.user, 'banner') and self.user.banner is not None:
                embed.add_field(
                    name="🌆 Banner", 
                    value=f"[Download Banner]({self.user.banner.url})", 
                    inline=False
                )
                banner_available = True
        if not banner_available:
            embed.add_field(
                name="🌆 Banner", 
                value="❌ No banner available", 
                inline=False
            )
        embed.set_thumbnail(url=self.user.display_avatar.url)
        embed.set_footer(text=f"Requested by {interaction.user.display_name}", icon_url=interaction.user.display_avatar.url)
        await interaction.response.edit_message(embed=embed, view=self)

class Avatar(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name="avatar", description="Display a user's avatar or banner.",aliases=['av'])
    @app_commands.describe(user="The user whose avatar/banner you want to see (defaults to yourself)")
    async def avatar(self, ctx: commands.Context, user: discord.User = None):
        # The key change is here: REMOVE ctx.defer()
        # The ctx.send() will handle the initial response for a slash command
        # and a regular message for a prefix command.
        
        target_user = user or ctx.author
        
        try:
            fresh_user = await self.bot.fetch_user(target_user.id)
            target_user = fresh_user
        except:
            pass
        
        view = AvatarView(target_user, self.bot)
        
        embed = discord.Embed(
            title=f"🖼️ {target_user.display_name}'s Avatar",
            color=discord.Color.blue(),
        )
        embed.add_field(
            name="💡 Interactive Buttons", 
            value="Use the buttons below to view avatar, banner, profile info, or download links!", 
            inline=False
        )
        embed.set_image(url=target_user.display_avatar.url)
        embed.set_footer(
            text=f"Requested by {ctx.author.display_name}", 
            icon_url=ctx.author.display_avatar.url
        )
        
        # This single line handles both command types correctly now.
        await ctx.send(embed=embed, view=view)



async def setup(bot):
    await bot.add_cog(Avatar(bot))