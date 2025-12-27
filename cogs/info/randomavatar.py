import discord
from discord.ext import commands
from discord import app_commands
import random

class RandomAvatarView(discord.ui.View):
    def __init__(self, user: discord.User, bot):
        super().__init__(timeout=60)
        self.user = user
        self.bot = bot

    @discord.ui.button(label="Avatar", style=discord.ButtonStyle.primary, emoji="🖼️")
    async def avatar_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Use a color from your config, or keep it random.
        try:
            embed_color = int(self.bot.bot_config['ui_settings']['embed_color'], 16)
        except (KeyError, ValueError):
            embed_color = discord.Color.blue()
            
        embed = discord.Embed(
            title=f"🖼️ {self.user.display_name}'s Avatar",
            color=embed_color
        )
        embed.set_image(url=self.user.display_avatar.url)
        embed.set_footer(text=f"Requested by {interaction.user.display_name}", icon_url=interaction.user.display_avatar.url)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Profile", style=discord.ButtonStyle.success, emoji="👤")
    async def profile_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            embed_color = int(self.bot.bot_config['ui_settings']['success_color'], 16)
        except (KeyError, ValueError):
            embed_color = discord.Color.green()

        embed = discord.Embed(
            title=f"👤 {self.user.display_name}'s Profile",
            color=embed_color
        )
        embed.add_field(name="Username", value=f"{self.user.name}#{self.user.discriminator}", inline=True)
        embed.add_field(name="User ID", value=f"`{self.user.id}`", inline=True)
        embed.add_field(name="Account Created", value=f"<t:{int(self.user.created_at.timestamp())}:R>", inline=True)
        embed.set_thumbnail(url=self.user.display_avatar.url)
        embed.set_footer(text=f"Requested by {interaction.user.display_name}", icon_url=interaction.user.display_avatar.url)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Download", style=discord.ButtonStyle.gray, emoji="💾")
    async def download_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            embed_color = int(self.bot.bot_config['ui_settings']['embed_color'], 16)
        except (KeyError, ValueError):
            embed_color = discord.Color.dark_gray()
            
        embed = discord.Embed(
            title=f"💾 Download {self.user.display_name}'s Avatar",
            color=embed_color,
            description=f"[Click here to download 👆]({self.user.display_avatar.url})"
        )
        embed.set_thumbnail(url=self.user.display_avatar.url)
        embed.set_footer(text=f"Requested by {interaction.user.display_name}", icon_url=interaction.user.display_avatar.url)
        await interaction.response.edit_message(embed=embed, view=self)

    async def on_timeout(self):
        # Disable buttons and remove the view for a cleaner look
        for item in self.children:
            item.disabled = True
        try:
            await self.message.edit(view=None)
        except discord.NotFound:
            pass # Message might have been deleted

class RandomAvatar(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name="randomavatar", description="Shows a random server member's avatar with fun buttons!",aliases=['rav'])
    async def randomavatar(self, ctx: commands.Context):
        # Use ctx.defer() for hybrid commands
        await ctx.defer()
        
        # Get all non-bot members. Note: for larger servers, ctx.guild.members might not have all members cached.
        members = [m for m in ctx.guild.members if not m.bot]
        if not members:
            # ctx.reply() works for both slash and prefix commands
            await ctx.reply("❌ I couldn't find any eligible members!", ephemeral=True)
            return
            
        user = random.choice(members)
        
        # Pass the bot object to the view
        view = RandomAvatarView(user, self.bot)
        
        embed = discord.Embed(
            title=f"🖼️ Random Avatar: {user.display_name}",
            color=discord.Color.random() # Keeping this random is a nice touch for a random command!
        )
        embed.set_image(url=user.display_avatar.url)
        embed.add_field(name="Tip", value="Use the buttons below for profile info and download options!", inline=False)
        embed.set_footer(text=f"Requested by {ctx.author.display_name}", icon_url=ctx.author.display_avatar.url)
        
        # Use ctx.send() for hybrid commands
        message = await ctx.send(embed=embed, view=view)
        # Store the message object in the view to edit it on timeout
        view.message = message

async def setup(bot):
    await bot.add_cog(RandomAvatar(bot))