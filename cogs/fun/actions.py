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


def load_gif_list(action_key: str) -> List[str]:
    """Load GIF list from a specific JSON file."""
    file_path = os.path.join(GIF_FOLDER, f"{action_key}.json")

    if not os.path.exists(file_path):
        logger.warning("No GIF file for action '%s': %s", action_key, file_path)
        return []

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
            logger.warning("GIF file for '%s' is not a list.", action_key)
            return []
    except Exception as e:
        logger.error("Failed to read %s: %s", file_path, e)
        return []


class ActionLayoutView(NexoraView):
    """Components V2 Action Card View with optional GIF media gallery."""

    def __init__(
        self,
        author: discord.Member,
        target: Union[discord.Member, List[discord.Member]],
        action_key: str,
        emoji: str,
        label: str,
        desc: str,
        gif_url: Optional[str] = None,
        color: int = BRAND_COLOR,
        timeout: float = 120,
    ):
        super().__init__(user_id=author.id, color=color, timeout=timeout)
        self.author = author
        self.targets = target if isinstance(target, list) else [target]
        self.target = self.targets[0]
        self.action_key = action_key
        self.emoji = emoji
        self.label = label
        self.desc = desc
        self.gif_url = gif_url
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

        # Narrative text
        self.add_text(f"### {self.desc}")

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
        self.add_footer("Nexora Actions · Stay cute, not toxic (uwu)")

        # Action Buttons
        row = discord.ui.ActionRow()
        if any(t.id != self.author.id for t in self.targets):
            return_btn = discord.ui.Button(
                label=f"{self.label} Back!",
                emoji=self.emoji,
                style=discord.ButtonStyle.secondary,
            )
            return_btn.callback = self._on_return_action
            row.add_item(return_btn)

        row.add_item(DismissButton(user_id=self.author.id))
        self.container.add_item(row)

    async def _on_return_action(self, interaction: discord.Interaction):
        target_ids = [t.id for t in self.targets]
        if interaction.user.id not in target_ids:
            names = ", ".join(t.display_name for t in self.targets)
            await interaction.response.send_message(
                f"❌ Only {names} can return this {self.label.lower()}!",
                ephemeral=True,
            )
            return

        # Disable return button on the original card
        for item in self.container.children:
            if isinstance(item, discord.ui.ActionRow):
                for child in item.children:
                    if isinstance(child, discord.ui.Button) and child.label == f"{self.label} Back!":
                        child.disabled = True
                        child.label = f"Returned by {interaction.user.display_name} 💕"

        await interaction.response.edit_message(view=self)

        # Send reciprocal card
        gifs = load_gif_list(self.action_key)
        new_gif = random.choice(gifs) if gifs else None

        return_view = ActionLayoutView(
            author=interaction.user,
            target=self.author,
            action_key=self.action_key,
            emoji=self.emoji,
            label=f"{self.label} Back",
            desc=f"**{interaction.user.display_name}** warmly returned the {self.label.lower()} to **{self.author.display_name}**! 💞",
            gif_url=new_gif,
            color=self._color,
        )
        await interaction.followup.send(view=return_view)


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

    view = ActionLayoutView(
        author=author,
        target=targets_list,
        action_key=action_key,
        emoji=emoji,
        label=label,
        desc=desc,
        gif_url=gif_url,
        color=color_val,
    )
    await send_view(ctx, view)
