"""
cogs/fun/meme.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Interactive Components V2 Reddit Meme Stream Engine
Fetches fresh, high-upvote memes from top subreddits with instant 'Next Meme' navigation.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import asyncio
import logging
import random
import time
from typing import Optional

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

from utils.ui import (
    BRAND_COLOR,
    ERROR_COLOR,
    SUCCESS_COLOR,
    WARNING_COLOR,
    DismissButton,
    NexoraView,
    send_view,
)

logger = logging.getLogger(__name__)

SUBREDDITS = {
    "dank": "dankmemes",
    "memes": "memes",
    "wholesome": "wholesomememes",
    "me_irl": "me_irl",
    "programmer": "ProgrammerHumor",
}

# ── Fallback memes in case all APIs are temporarily blocked ───────────────────
FALLBACK_MEMES = [
    {
        "title": "When the code compiles on the first try",
        "url": "https://images.unsplash.com/photo-1534972195531-a756b1129f63?auto=format&fit=crop&w=800&q=80",
        "author": "dev_legend",
        "subreddit": "ProgrammerHumor",
        "ups": 15420,
        "comments": 312,
        "permalink": "https://reddit.com/r/ProgrammerHumor",
    },
    {
        "title": "It's not a bug, it's an undocumented feature",
        "url": "https://images.unsplash.com/photo-1555066931-4365d14bab8c?auto=format&fit=crop&w=800&q=80",
        "author": "bug_hunter",
        "subreddit": "ProgrammerHumor",
        "ups": 21890,
        "comments": 420,
        "permalink": "https://reddit.com/r/ProgrammerHumor",
    },
    {
        "title": "Me explaining why the bot restarted",
        "url": "https://images.unsplash.com/photo-1518770660439-4636190af475?auto=format&fit=crop&w=800&q=80",
        "author": "sysadmin_cat",
        "subreddit": "memes",
        "ups": 18320,
        "comments": 245,
        "permalink": "https://reddit.com/r/memes",
    },
]


class MemeCardView(NexoraView):
    """Components V2 Interactive Meme Card View."""

    def __init__(
        self,
        cog: "Meme",
        meme_data: dict,
        requester: discord.abc.User,
        category: str = "memes",
        timeout: float = 180.0,
    ):
        super().__init__(bot=cog.bot, user_id=requester.id, color=BRAND_COLOR, timeout=timeout)
        self.cog = cog
        self.meme_data = meme_data
        self.requester = requester
        self.category = category
        self._build_meme()

    def _build_meme(self):
        self.clear_container()

        title = self.meme_data.get("title", "Untitled Meme")
        sub = self.meme_data.get("subreddit", "memes")
        author = self.meme_data.get("author", "anonymous")
        ups = self.meme_data.get("ups", 0)
        comments = self.meme_data.get("comments", 0)
        img_url = self.meme_data.get("url", "")
        post_url = self.meme_data.get("permalink", f"https://reddit.com/r/{sub}")

        header = (
            f"# 🐸 {title}\n"
            f"> Posted by `u/{author}` in **r/{sub}** · 👍 **{ups:,}** · 💬 **{comments:,}**"
        )
        self.add_section(header)
        self.add_separator(discord.SeparatorSpacing.small)

        if img_url:
            try:
                gallery = discord.ui.MediaGallery(discord.MediaGalleryItem(img_url))
                self.container.add_item(gallery)
            except Exception:
                # Fallback: display image link
                self.add_text(f"[🖼️ Click to view high-res image]({img_url})")

        btn_next = discord.ui.Button(label="Next Meme", emoji="🔄", style=discord.ButtonStyle.primary)
        btn_link = discord.ui.Button(label="Reddit Post", url=post_url, style=discord.ButtonStyle.link, emoji="🔗")

        btn_next.callback = self._on_next

        self.add_row(btn_next, btn_link, DismissButton(user_id=self.requester.id))
        self.add_footer(f"Nexora Meme Engine · r/{sub} · Click 'Next Meme' for another")

    async def _on_next(self, interaction: discord.Interaction):
        await interaction.response.defer()
        new_meme = await self.cog.fetch_meme(self.category)
        if new_meme:
            self.meme_data = new_meme
            self._build_meme()
            await interaction.followup.edit_message(message_id=interaction.message.id, view=self)
        else:
            await interaction.followup.send("⚠️ Could not load another meme right now. Try again shortly!", ephemeral=True)


class Meme(commands.Cog):
    """Reddit Meme Stream Engine."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.cache: dict[str, list[dict]] = {}  # category -> list of posts
        self.last_fetch: dict[str, float] = {}  # category -> timestamp

    async def fetch_memes_from_api(self, subreddit: str) -> list[dict]:
        """Fetch fresh memes via meme-api.com (dedicated Reddit proxy for Discord bots)."""
        url = f"https://meme-api.com/gimme/{subreddit}/50"
        headers = {"User-Agent": "NexoraDiscordBot/2.0"}

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                    if resp.status != 200:
                        logger.warning("Meme API returned status %d for r/%s", resp.status, subreddit)
                        return []
                    data = await resp.json()
                    raw_memes = data.get("memes", [])

                    memes = []
                    for post in raw_memes:
                        if post.get("nsfw") or post.get("spoiler"):
                            continue
                        p_url = post.get("url", "")
                        if not any(p_url.lower().endswith(ext) for ext in (".png", ".jpg", ".jpeg", ".gif", ".webp")):
                            continue

                        memes.append({
                            "title": post.get("title", "Untitled Meme"),
                            "url": p_url,
                            "author": post.get("author", "anonymous"),
                            "subreddit": post.get("subreddit", subreddit),
                            "ups": post.get("ups", 0),
                            "comments": 0,
                            "permalink": post.get("postLink", f"https://reddit.com/r/{subreddit}"),
                        })

                    random.shuffle(memes)
                    return memes
        except Exception as e:
            logger.error("Error fetching memes from Meme API for r/%s: %s", subreddit, e)
            return []

    async def fetch_memes_from_reddit(self, subreddit: str) -> list[dict]:
        """Secondary fallback: Direct request to Reddit."""
        url = f"https://www.reddit.com/r/{subreddit}/hot.json?limit=50"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "application/json",
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                    if resp.status != 200:
                        logger.debug("Reddit direct API returned status %d for r/%s", resp.status, subreddit)
                        return []
                    data = await resp.json()
                    children = data.get("data", {}).get("children", [])

                    memes = []
                    for child in children:
                        post = child.get("data", {})
                        if post.get("over_18") or post.get("is_video") or post.get("stickied"):
                            continue
                        p_url = post.get("url", "")
                        if not any(p_url.lower().endswith(ext) for ext in (".png", ".jpg", ".jpeg", ".gif", ".webp")):
                            continue

                        memes.append({
                            "title": post.get("title"),
                            "url": p_url,
                            "author": post.get("author"),
                            "subreddit": post.get("subreddit"),
                            "ups": post.get("ups", 0),
                            "comments": post.get("num_comments", 0),
                            "permalink": f"https://reddit.com{post.get('permalink')}",
                        })

                    random.shuffle(memes)
                    return memes
        except Exception as e:
            logger.debug("Direct Reddit fetch failed for r/%s: %s", subreddit, e)
            return []

    async def fetch_meme(self, category: str = "memes") -> dict:
        sub = SUBREDDITS.get(category.lower(), "memes")
        now = time.time()

        # Cache for 10 minutes
        if sub not in self.cache or len(self.cache[sub]) == 0 or (now - self.last_fetch.get(sub, 0) > 600):
            # 1. Primary: Meme API (reliable Reddit aggregator)
            fresh = await self.fetch_memes_from_api(sub)

            # 2. Secondary fallback: Direct Reddit
            if not fresh:
                fresh = await self.fetch_memes_from_reddit(sub)

            if fresh:
                self.cache[sub] = fresh
                self.last_fetch[sub] = now

        if sub in self.cache and len(self.cache[sub]) > 0:
            return self.cache[sub].pop()

        return random.choice(FALLBACK_MEMES)

    @commands.hybrid_command(
        name="meme",
        description="🐸 Browse fresh, top-upvoted trending memes from Reddit",
    )
    @app_commands.describe(
        category="Meme category: dank, memes, wholesome, me_irl, or programmer",
    )
    @app_commands.choices(
        category=[
            app_commands.Choice(name="🔥 Dank Memes (r/dankmemes)", value="dank"),
            app_commands.Choice(name="🐸 General Memes (r/memes)", value="memes"),
            app_commands.Choice(name="💖 Wholesome Memes (r/wholesomememes)", value="wholesome"),
            app_commands.Choice(name="🛋️ Relatable / Real Life (r/me_irl)", value="me_irl"),
            app_commands.Choice(name="💻 Programmer & Tech (r/ProgrammerHumor)", value="programmer"),
        ]
    )
    @commands.guild_only()
    async def meme(self, ctx: commands.Context, category: Optional[str] = "memes"):
        selected_cat = (category or "memes").lower()
        if selected_cat not in SUBREDDITS:
            selected_cat = "memes"

        if ctx.interaction:
            await ctx.interaction.response.defer()

        meme_data = await self.fetch_meme(selected_cat)
        view = MemeCardView(self, meme_data, ctx.author, selected_cat)
        await send_view(ctx, view)
        logger.info("Meme: %s viewed meme in r/%s", ctx.author, selected_cat)


async def setup(bot: commands.Bot):
    await bot.add_cog(Meme(bot))
    logger.debug("Loaded Meme")
