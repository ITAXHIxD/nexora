"""
cogs/fun/actions.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Nexora Fun Actions Engine · Powered by Discord Components V2
Provides interactive, responsive action cards for hug, slap, kiss,
cuddle, bonk, bite, poke, blush, kick, kill, pat, punch, and boop.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import discord
from discord.ext import commands
from typing import Optional, List, Union
import random
import json
import os
import logging

from utils.ui import NexoraView, DismissButton, send_view, BRAND_COLOR

logger = logging.getLogger(__name__)

GIF_FOLDER = "data/owo_gifs"

STYLE_PRESETS = {
    "hug": {
        "emoji": "🤗",
        "label": "Hug",
        "color": discord.Color.from_rgb(255, 175, 204),
    },
    "boop": {
        "emoji": "👉🐽",
        "label": "Boop",
        "color": discord.Color.from_rgb(255, 220, 180),
    },
    "cuddle": {
        "emoji": "🐻",
        "label": "Cuddle",
        "color": discord.Color.from_rgb(185, 160, 255),
    },
    "slap": {
        "emoji": "👋",
        "label": "Slap",
        "color": discord.Color.from_rgb(255, 140, 140),
    },
    "bite": {
        "emoji": "🦷",
        "label": "Bite",
        "color": discord.Color.from_rgb(230, 230, 180),
    },
    "bonk": {
        "emoji": "🔨",
        "label": "Bonk",
        "color": discord.Color.from_rgb(160, 160, 255),
    },
    "poke": {
        "emoji": "👉",
        "label": "Poke",
        "color": discord.Color.from_rgb(255, 230, 130),
    },
    "blush": {
        "emoji": "🥺",
        "label": "Blush",
        "color": discord.Color.from_rgb(255, 183, 194),
    },
    "kick": {
        "emoji": "🦵",
        "label": "Kick",
        "color": discord.Color.from_rgb(255, 200, 100),
    },
    "kicks": {
        "emoji": "🦵",
        "label": "Kick",
        "color": discord.Color.from_rgb(255, 200, 100),
    },
    "kill": {
        "emoji": "🔪",
        "label": "Kill",
        "color": discord.Color.from_rgb(200, 50, 50),
    },
    "kiss": {
        "emoji": "💋",
        "label": "Kiss",
        "color": discord.Color.from_rgb(255, 105, 180),
    },
    "pat": {
        "emoji": "🐱",
        "label": "Pat",
        "color": discord.Color.from_rgb(135, 206, 235),
    },
    "punch": {
        "emoji": "👊",
        "label": "Punch",
        "color": discord.Color.from_rgb(255, 69, 0),
    },
}


_GIF_CACHE: dict[str, List[str]] = {}
_ACTION_COUNTS_FILE = "data/action_counts.json"
_ACTION_COUNTS_CACHE: Optional[dict[str, int]] = None

CHAOS_ACTIONS = {"slap", "punch", "kick", "kicks", "kill", "bite", "bonk", "poke"}


def _increment_action_count(u1_id: int, u2_id: int, action_key: str) -> int:
    """Increment and return the pairwise action count with O(1) RAM cache."""
    global _ACTION_COUNTS_CACHE
    if _ACTION_COUNTS_CACHE is None:
        try:
            if os.path.exists(_ACTION_COUNTS_FILE):
                with open(_ACTION_COUNTS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    _ACTION_COUNTS_CACHE = data if isinstance(data, dict) else {}
            else:
                _ACTION_COUNTS_CACHE = {}
        except Exception:
            _ACTION_COUNTS_CACHE = {}

    a, b = sorted((int(u1_id), int(u2_id)))
    canon_action = "kick" if action_key == "kicks" else action_key
    pair_key = f"{a}:{b}:{canon_action}"
    count = int(_ACTION_COUNTS_CACHE.get(pair_key, 0)) + 1
    _ACTION_COUNTS_CACHE[pair_key] = count

    try:
        os.makedirs("data", exist_ok=True)
        with open(_ACTION_COUNTS_FILE, "w", encoding="utf-8") as f:
            json.dump(_ACTION_COUNTS_CACHE, f)
    except Exception:
        pass
    return count


def load_gif_list(action_key: str) -> List[str]:
    """Load GIF list from a specific JSON file with O(1) in-memory caching."""
    if action_key in _GIF_CACHE:
        return _GIF_CACHE[action_key]

    file_path = os.path.join(GIF_FOLDER, f"{action_key}.json")

    if not os.path.exists(file_path):
        logger.warning("No GIF file for action '%s': %s", action_key, file_path)
        _GIF_CACHE[action_key] = []
        return []

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                _GIF_CACHE[action_key] = data
                return data
            logger.warning("GIF file for '%s' is not a list.", action_key)
            _GIF_CACHE[action_key] = []
            return []
    except Exception as e:
        logger.error("Failed to read %s: %s", file_path, e)
        return []


class ActionLayoutView(NexoraView):
    """Components V2 Action Card View with optional GIF media gallery."""

    def __init__(
        self,
        author: Union[discord.Member, discord.User],
        target: Union[discord.Member, discord.User, List[Union[discord.Member, discord.User]]],
        action_key: str,
        emoji: str,
        label: str,
        desc: str,
        gif_url: Optional[str] = None,
        color: int = BRAND_COLOR,
        pair_count: int = 0,
        timeout: float = 180,
    ):
        # Pass user_id=None so target users can click "{Label} Back!" and "New GIF"
        super().__init__(user_id=None, color=color, timeout=timeout)
        self.author = author
        self.targets = target if isinstance(target, list) else [target]
        self.target = self.targets[0]
        self.action_key = action_key
        self.emoji = emoji
        self.label = label
        self.desc = desc
        self.gif_url = gif_url
        self.pair_count = pair_count
        self._returned = False
        self._build()

    def _build(self):
        self.clear_container()

        # Header Section with author avatar
        if len(self.targets) == 1 and self.author.id == self.targets[0].id:
            sub = f"> {self.author.mention} *(self-interaction)*"
        else:
            mentions_str = ", ".join(t.mention for t in self.targets)
            sub = f"> {self.author.mention} ➔ {mentions_str}"

        header_text = f"# {self.emoji} {self.label}\n{sub}"
        thumb_url = str(self.author.display_avatar.url)
        self.add_section(header_text, thumbnail_url=thumb_url)
        self.add_separator(discord.SeparatorSpacing.small)

        # Narrative text + optional streak counter
        body = f"### {self.desc}"
        if self.pair_count > 0 and len(self.targets) == 1 and self.author.id != self.targets[0].id:
            streak_icon = "⚔️" if self.action_key in CHAOS_ACTIONS else "💞"
            body += f"\n-# {streak_icon} **{self.author.display_name}** & **{self.targets[0].display_name}** {self.action_key} streak: **{self.pair_count}x**"
        self.add_text(body)

        # Media Gallery GIF
        if self.gif_url:
            try:
                self.container.add_item(
                    discord.ui.MediaGallery(
                        discord.MediaGalleryItem(self.gif_url)
                    )
                )
            except Exception as exc:
                logger.warning("Could not attach MediaGallery GIF: %s", exc)

        # Footer
        self.add_footer("Nexora Actions · Click the button below to retaliate or shuffle GIF!")

        # Action Buttons
        base_label = STYLE_PRESETS.get(self.action_key, {}).get("label", self.action_key.capitalize())
        row = discord.ui.ActionRow()
        if any(t.id != self.author.id for t in self.targets):
            return_btn = discord.ui.Button(
                label=f"Returned! ✨" if self._returned else f"{base_label} Back!",
                emoji=self.emoji,
                style=discord.ButtonStyle.secondary if self._returned else discord.ButtonStyle.primary,
                disabled=self._returned,
            )
            return_btn.callback = self._on_return_action
            row.add_item(return_btn)

        again_btn = discord.ui.Button(
            label="New GIF",
            emoji="🔄",
            style=discord.ButtonStyle.secondary,
        )
        again_btn.callback = self._on_shuffle_gif
        row.add_item(again_btn)

        row.add_item(DismissButton(user_id=self.author.id))
        self.container.add_item(row)

    async def _on_shuffle_gif(self, interaction: discord.Interaction):
        allowed_ids = {self.author.id} | {t.id for t in self.targets}
        if interaction.user.id not in allowed_ids:
            return await interaction.response.send_message(
                "❌ Only participants in this action card can shuffle the GIF!",
                ephemeral=True,
            )
        gifs = load_gif_list(self.action_key)
        candidates = [g for g in gifs if g != self.gif_url] or gifs
        if candidates:
            self.gif_url = random.choice(candidates)
            self._build()
        await interaction.response.edit_message(view=self)

    async def _on_return_action(self, interaction: discord.Interaction):
        target_ids = [t.id for t in self.targets]
        if interaction.user.id not in target_ids:
            names = ", ".join(t.display_name for t in self.targets)
            await interaction.response.send_message(
                f"❌ Only **{names}** can return this {self.action_key}!",
                ephemeral=True,
            )
            return

        self._returned = True
        self._build()
        await interaction.response.edit_message(view=self)

        # Send reciprocal card as a brand-new message so they can keep chaining!
        gifs = load_gif_list(self.action_key)
        new_gif = random.choice(gifs) if gifs else None
        base_label = STYLE_PRESETS.get(self.action_key, {}).get("label", self.action_key.capitalize())
        new_count = _increment_action_count(interaction.user.id, self.author.id, self.action_key)

        if self.action_key in CHAOS_ACTIONS:
            ret_desc = f"**{interaction.user.display_name}** retaliated and returned the {base_label.lower()} to **{self.author.display_name}**! 💥"
        else:
            ret_desc = f"**{interaction.user.display_name}** warmly returned the {base_label.lower()} to **{self.author.display_name}**! 💞"

        return_view = ActionLayoutView(
            author=interaction.user,
            target=self.author,
            action_key=self.action_key,
            emoji=self.emoji,
            label=f"{base_label} Back",
            desc=ret_desc,
            gif_url=new_gif,
            color=self._color,
            pair_count=new_count,
        )
        msg = None
        if interaction.channel:
            try:
                msg = await interaction.channel.send(view=return_view)
            except Exception:
                pass
        if msg is None:
            msg = await interaction.followup.send(view=return_view, wait=True)
        return_view.message = msg


async def send_owo_action_embed(
    ctx: commands.Context,
    target: Union[discord.Member, List[discord.Member]],
    action_key: str,
    *,
    text_template: str,
    self_template: Optional[str] = None,
    extra_note: Optional[str] = None,
    color: Optional[discord.Color] = None,
    action_emoji: Optional[str] = None,
    action_label: Optional[str] = None,
):
    """
    Modern Components V2 Action card dispatcher supporting single or multi-user targets.
    """
    author: discord.Member = ctx.author

    preset = STYLE_PRESETS.get(action_key, {})
    emoji: str = action_emoji or preset.get("emoji", "✨")
    label: str = action_label or preset.get("label", action_key.capitalize())

    col = color or preset.get("color", BRAND_COLOR)
    if isinstance(col, discord.Color):
        color_val = col.value
    elif isinstance(col, int):
        color_val = col
    else:
        color_val = BRAND_COLOR

    if isinstance(target, (list, tuple)):
        targets_list = list(target)
    elif target:
        targets_list = [target]
    else:
        targets_list = [author]

    if len(targets_list) > 1:
        names = ", ".join(f"**{m.display_name}**" for m in targets_list[:-1]) + f" and **{targets_list[-1].display_name}**"
        desc = text_template.format(
            author=author.display_name,
            target=names,
        )
    elif targets_list[0].id == author.id:
        if self_template:
            desc = self_template.format(author=author.display_name)
        else:
            desc = (
                f"**{author.display_name}** interacts with themselves… "
                f"weird owo energy detected. (〃￣ω￣〃ゞ"
            )
    else:
        desc = text_template.format(
            author=author.display_name,
            target=targets_list[0].display_name,
        )

    if extra_note:
        desc += f"\n\n{extra_note}"

    gifs = load_gif_list(action_key)
    gif_url = random.choice(gifs) if gifs else None

    pair_count = 0
    if len(targets_list) == 1 and targets_list[0].id != author.id:
        pair_count = _increment_action_count(author.id, targets_list[0].id, action_key)

    view = ActionLayoutView(
        author=author,
        target=targets_list,
        action_key=action_key,
        emoji=emoji,
        label=label,
        desc=desc,
        gif_url=gif_url,
        color=color_val,
        pair_count=pair_count,
    )
    await send_view(ctx, view)
