"""
cogs/fun/meme.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Interactive Components V2 Reddit & Meme Stream Engine
Fetches fresh, high-upvote posts from any subreddit with image & text rendering,
sort filtering (Hot/Top/New), random sub hopping, and instant post queue caching.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import asyncio
import html
import logging
import random
import re
import time
from typing import Optional

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

from utils.ui import (
    BRAND_COLOR,
    ERROR_COLOR,
    PURPLE_COLOR,
    SUCCESS_COLOR,
    WARNING_COLOR,
    DismissButton,
    NexoraView,
    send_view,
)

logger = logging.getLogger(__name__)

# Curated popular, fun, safe subreddits
CURATED_SUBREDDITS = [
    "memes",
    "dankmemes",
    "wholesomememes",
    "me_irl",
    "ProgrammerHumor",
    "aww",
    "gaming",
    "showerthoughts",
    "mildlyinteresting",
    "facepalm",
    "rareinsults",
    "technicallythetruth",
    "todayilearned",
    "dadjokes",
    "funny",
    "BikiniBottomTwitter",
    "anime_irl",
    "Eyebleach",
    "AnimalsBeingDerps",
    "natureismetal",
    "CozyPlaces",
    "CrappyDesign",
    "softwaregore",
    "pcmasterrace",
    "Catmemes",
    "dogmemes",
    "HistoryMemes",
]

SUBREDDIT_CATEGORIES = {
    "dank": "dankmemes",
    "memes": "memes",
    "wholesome": "wholesomememes",
    "me_irl": "me_irl",
    "programmer": "ProgrammerHumor",
    "gaming": "gaming",
    "aww": "aww",
    "showerthoughts": "showerthoughts",
    "interesting": "mildlyinteresting",
    "dadjokes": "dadjokes",
}

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "NexoraDiscordBot/3.0 (by /u/nexoradev)",
]

FALLBACK_POSTS = [
    {
        "title": "When the code compiles on the first try with zero warnings",
        "url": "https://images.unsplash.com/photo-1534972195531-a756b1129f63?auto=format&fit=crop&w=800&q=80",
        "author": "dev_legend",
        "subreddit": "ProgrammerHumor",
        "ups": 18420,
        "comments": 412,
        "permalink": "https://reddit.com/r/ProgrammerHumor",
        "is_text": False,
        "selftext": "",
    },
    {
        "title": "Showerthought: Your alarm clock is the only song you despise hearing in the morning",
        "url": "",
        "author": "deep_thinker",
        "subreddit": "showerthoughts",
        "ups": 25190,
        "comments": 780,
        "permalink": "https://reddit.com/r/showerthoughts",
        "is_text": True,
        "selftext": "No matter how much you love a song, set it as your alarm for one week and it becomes psychological warfare.",
    },
    {
        "title": "Why do programmers prefer dark mode? Because light attracts bugs.",
        "url": "",
        "author": "pun_master",
        "subreddit": "dadjokes",
        "ups": 14200,
        "comments": 310,
        "permalink": "https://reddit.com/r/dadjokes",
        "is_text": True,
        "selftext": "And darkness hides the messy spaghetti code.",
    },
    {
        "title": "Me explaining to the server why the bot has 99.9% uptime now",
        "url": "https://images.unsplash.com/photo-1518770660439-4636190af475?auto=format&fit=crop&w=800&q=80",
        "author": "sysadmin_cat",
        "subreddit": "memes",
        "ups": 21320,
        "comments": 545,
        "permalink": "https://reddit.com/r/memes",
        "is_text": False,
        "selftext": "",
    },
]


class RedditCardView(NexoraView):
    """Components V2 Interactive Reddit & Meme Browser Card."""

    def __init__(
        self,
        cog: "Meme",
        post_data: dict,
        requester: discord.abc.User,
        subreddit: str,
        sort: str = "hot",
        timeout: float = 240.0,
    ):
        super().__init__(bot=cog.bot, user_id=requester.id, color=BRAND_COLOR, timeout=timeout)
        self.cog = cog
        self.post_data = post_data
        self.requester = requester
        self.subreddit = subreddit
        self.sort = sort
        self._build_card()

    def _build_card(self):
        self.clear_container()

        title = self.post_data.get("title", "Untitled Post")
        sub = self.post_data.get("subreddit", self.subreddit)
        author = self.post_data.get("author", "anonymous")
        ups = self.post_data.get("ups", 0)
        comments = self.post_data.get("comments", 0)
        img_url = self.post_data.get("url", "")
        post_url = self.post_data.get("permalink", f"https://reddit.com/r/{sub}")
        is_text = self.post_data.get("is_text", False)
        selftext = self.post_data.get("selftext", "").strip()

        sort_emojis = {"hot": "🔥", "top": "⭐", "new": "✨", "rising": "📈"}
        sort_badge = f"{sort_emojis.get(self.sort, '🔥')} {self.sort.upper()}"

        header = (
            f"# 🌐 r/{sub}\n"
            f"> Posted by `u/{author}` · 👍 **{ups:,}** · 💬 **{comments:,}** · [{sort_badge}]\n\n"
            f"### **{title}**"
        )
        self.add_section(header)
        self.add_separator(discord.SeparatorSpacing.small)

        # Content Rendering: Image vs Text
        if is_text and selftext:
            cleaned_text = html.unescape(selftext)
            if len(cleaned_text) > 1200:
                cleaned_text = cleaned_text[:1197] + "..."
            self.add_text(f">>> {cleaned_text}")
            self.add_separator(discord.SeparatorSpacing.small)
        elif img_url:
            try:
                gallery = discord.ui.MediaGallery(discord.MediaGalleryItem(img_url))
                self.container.add_item(gallery)
            except Exception:
                self.add_text(f"[🖼️ Click to view high-res image]({img_url})")
                self.add_separator(discord.SeparatorSpacing.small)

        # Control Row 1: Actions
        btn_next = discord.ui.Button(label="Next Post", emoji="🔄", style=discord.ButtonStyle.primary)
        btn_random = discord.ui.Button(label="Random Sub", emoji="🎲", style=discord.ButtonStyle.secondary)
        btn_sort = discord.ui.Button(
            label=f"Sort: {self.sort.capitalize()}",
            emoji="⚡",
            style=discord.ButtonStyle.secondary,
        )
        btn_link = discord.ui.Button(label="Reddit Post", url=post_url, style=discord.ButtonStyle.link, emoji="🔗")

        btn_next.callback = self._on_next
        btn_random.callback = self._on_random_sub
        btn_sort.callback = self._on_cycle_sort

        self.add_row(btn_next, btn_random, btn_sort, btn_link, DismissButton(user_id=self.requester.id))
        self.add_footer(f"Nexora Reddit Stream · Browsing r/{sub} ({self.sort}) · Requested by {self.requester.display_name}")

    async def _on_next(self, interaction: discord.Interaction):
        if interaction.user.id != self.requester.id:
            return await interaction.response.send_message("❌ This browser session belongs to someone else.", ephemeral=True)

        await interaction.response.defer()
        new_post = await self.cog.fetch_post(self.subreddit, self.sort)
        if new_post:
            self.post_data = new_post
            self._build_card()
            await interaction.followup.edit_message(message_id=interaction.message.id, view=self)
        else:
            await interaction.followup.send("⚠️ Could not load another post right now. Try switching sort or subreddit!", ephemeral=True)

    async def _on_random_sub(self, interaction: discord.Interaction):
        if interaction.user.id != self.requester.id:
            return await interaction.response.send_message("❌ This browser session belongs to someone else.", ephemeral=True)

        await interaction.response.defer()
        new_sub = random.choice([s for s in CURATED_SUBREDDITS if s.lower() != self.subreddit.lower()])
        self.subreddit = new_sub
        new_post = await self.cog.fetch_post(new_sub, self.sort)
        if new_post:
            self.post_data = new_post
            self._build_card()
            await interaction.followup.edit_message(message_id=interaction.message.id, view=self)
        else:
            await interaction.followup.send(f"⚠️ Could not load posts from r/{new_sub}.", ephemeral=True)

    async def _on_cycle_sort(self, interaction: discord.Interaction):
        if interaction.user.id != self.requester.id:
            return await interaction.response.send_message("❌ This browser session belongs to someone else.", ephemeral=True)

        await interaction.response.defer()
        sort_order = ["hot", "top", "new"]
        idx = (sort_order.index(self.sort) + 1) % len(sort_order) if self.sort in sort_order else 0
        self.sort = sort_order[idx]

        new_post = await self.cog.fetch_post(self.subreddit, self.sort)
        if new_post:
            self.post_data = new_post
            self._build_card()
            await interaction.followup.edit_message(message_id=interaction.message.id, view=self)
        else:
            await interaction.followup.send(f"⚠️ Could not load posts for {self.sort} in r/{self.subreddit}.", ephemeral=True)


class Meme(commands.Cog):
    """Next-Gen Reddit & Meme Stream Engine."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.cache: dict[str, list[dict]] = {}  # "subreddit:sort" -> list of posts
        self.last_fetch: dict[str, float] = {}  # "subreddit:sort" -> timestamp
        self._session: Optional[aiohttp.ClientSession] = None

    async def cog_load(self):
        self._session = aiohttp.ClientSession()

    async def cog_unload(self):
        if self._session and not self._session.closed:
            await self._session.close()

    def _get_session(self) -> aiohttp.ClientSession:
        if hasattr(self.bot, "session") and self.bot.session and not self.bot.session.closed:
            return self.bot.session
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def fetch_posts_from_reddit(self, subreddit: str, sort: str = "hot") -> list[dict]:
        """Direct Reddit JSON fetch with post queueing."""
        url = f"https://www.reddit.com/r/{subreddit}/{sort}.json?limit=50"
        headers = {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "application/json",
        }
        session = self._get_session()

        try:
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                if resp.status == 403 or resp.status == 404:
                    logger.debug("Reddit direct API returned status %d for r/%s", resp.status, subreddit)
                    return []
                if resp.status != 200:
                    return []

                data = await resp.json()
                children = data.get("data", {}).get("children", [])

                posts = []
                for child in children:
                    post = child.get("data", {})
                    # Strict safety filters
                    if post.get("over_18") or post.get("stickied") or post.get("is_video"):
                        continue

                    title = post.get("title", "").strip()
                    p_url = post.get("url", "")
                    selftext = post.get("selftext", "").strip()
                    is_image = any(p_url.lower().endswith(ext) for ext in (".png", ".jpg", ".jpeg", ".gif", ".webp")) or "i.redd.it" in p_url or "i.imgur.com" in p_url
                    is_text = bool(selftext) and not is_image

                    if not is_image and not is_text:
                        continue

                    posts.append({
                        "title": title or "Reddit Post",
                        "url": p_url if is_image else "",
                        "author": post.get("author", "anonymous"),
                        "subreddit": post.get("subreddit", subreddit),
                        "ups": post.get("ups", 0),
                        "comments": post.get("num_comments", 0),
                        "permalink": f"https://reddit.com{post.get('permalink')}",
                        "is_text": is_text,
                        "selftext": selftext,
                    })

                random.shuffle(posts)
                return posts
        except Exception as e:
            logger.debug("Reddit direct fetch failed for r/%s: %s", subreddit, e)
            return []

    async def fetch_from_meme_api(self, subreddit: str) -> list[dict]:
        """Proxy fallback via meme-api.com."""
        url = f"https://meme-api.com/gimme/{subreddit}/50"
        headers = {"User-Agent": "NexoraDiscordBot/2.5"}
        session = self._get_session()

        try:
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                if resp.status != 200:
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
                        "is_text": False,
                        "selftext": "",
                    })

                random.shuffle(memes)
                return memes
        except Exception as e:
            logger.debug("Meme API fallback failed for r/%s: %s", subreddit, e)
            return []

    async def fetch_post(self, subreddit: str = "memes", sort: str = "hot") -> dict:
        """Fetch post from queue cache or refresh from network."""
        key = f"{subreddit.lower()}:{sort.lower()}"
        now = time.time()

        if key not in self.cache or len(self.cache[key]) == 0 or (now - self.last_fetch.get(key, 0) > 420):
            # 1. Primary: Direct Reddit
            fresh = await self.fetch_posts_from_reddit(subreddit, sort)

            # 2. Secondary: Meme API
            if not fresh:
                fresh = await self.fetch_from_meme_api(subreddit)

            if fresh:
                self.cache[key] = fresh
                self.last_fetch[key] = now

        if key in self.cache and len(self.cache[key]) > 0:
            return self.cache[key].pop()

        # Fallback post matching category if possible
        matched = [p for p in FALLBACK_POSTS if p["subreddit"].lower() == subreddit.lower()]
        return random.choice(matched or FALLBACK_POSTS)

    @commands.hybrid_command(
        name="reddit",
        description="🌐 Browse any subreddit with live post streaming, sorting, and random hopping",
        aliases=["r", "sub"],
    )
    @app_commands.describe(
        subreddit="Subreddit name to browse (e.g. memes, aww, ProgrammerHumor, showerthoughts)",
        sort="Sort mode: hot, top, new, rising (default: hot)",
    )
    @app_commands.choices(
        sort=[
            app_commands.Choice(name="🔥 Hot (Trending)", value="hot"),
            app_commands.Choice(name="⭐ Top (Most Upvoted)", value="top"),
            app_commands.Choice(name="✨ New (Latest Posts)", value="new"),
            app_commands.Choice(name="📈 Rising (Gaining Momentum)", value="rising"),
        ]
    )
    async def reddit(
        self,
        ctx: commands.Context,
        subreddit: Optional[str] = None,
        sort: Optional[str] = "hot",
    ):
        if ctx.interaction:
            await ctx.interaction.response.defer()

        # Sanitize subreddit
        if not subreddit:
            target_sub = random.choice(CURATED_SUBREDDITS)
        else:
            cleaned = re.sub(r"^r/", "", subreddit.strip().lower())
            if not re.match(r"^[a-zA-Z0-9_]{2,30}$", cleaned):
                return await ctx.send("❌ Invalid subreddit name. Please provide 2-30 alphanumeric characters.", ephemeral=True)
            target_sub = cleaned

        target_sort = (sort or "hot").lower()
        if target_sort not in ("hot", "top", "new", "rising"):
            target_sort = "hot"

        post_data = await self.fetch_post(target_sub, target_sort)
        view = RedditCardView(self, post_data, ctx.author, target_sub, target_sort)
        await send_view(ctx, view)
        logger.info("Reddit: %s browsed r/%s (%s)", ctx.author, target_sub, target_sort)

    @commands.hybrid_command(
        name="meme",
        description="🐸 Browse fresh, top-upvoted trending memes from Reddit",
    )
    @app_commands.describe(
        category="Meme category: dank, memes, wholesome, me_irl, programmer, gaming, aww, or showerthoughts",
    )
    @app_commands.choices(
        category=[
            app_commands.Choice(name="🔥 Dank Memes (r/dankmemes)", value="dank"),
            app_commands.Choice(name="🐸 General Memes (r/memes)", value="memes"),
            app_commands.Choice(name="💖 Wholesome (r/wholesomememes)", value="wholesome"),
            app_commands.Choice(name="🛋️ Relatable (r/me_irl)", value="me_irl"),
            app_commands.Choice(name="💻 Programmer Humor (r/ProgrammerHumor)", value="programmer"),
            app_commands.Choice(name="🎮 Gaming Memes (r/gaming)", value="gaming"),
            app_commands.Choice(name="🐶 Cute Animals (r/aww)", value="aww"),
            app_commands.Choice(name="🚿 Shower Thoughts (r/showerthoughts)", value="showerthoughts"),
        ]
    )
    async def meme(self, ctx: commands.Context, category: Optional[str] = "memes"):
        selected_cat = (category or "memes").lower()
        sub = SUBREDDIT_CATEGORIES.get(selected_cat, selected_cat)

        if ctx.interaction:
            await ctx.interaction.response.defer()

        post_data = await self.fetch_post(sub, "hot")
        view = RedditCardView(self, post_data, ctx.author, sub, "hot")
        await send_view(ctx, view)
        logger.info("Meme: %s viewed meme in r/%s", ctx.author, sub)


async def setup(bot: commands.Bot):
    await bot.add_cog(Meme(bot))
    logger.debug("Loaded Meme & Reddit Stream Engine")
