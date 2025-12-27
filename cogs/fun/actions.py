# cogs/fun/owo_base.py

import discord
from discord.ext import commands
from typing import Optional, List, Dict, Any
import random
import json
import os

GIF_FOLDER = "data/owo_gifs"

# Per-action style presets:
#  - emoji: big icon in header
#  - label: action name in header
#  - color: embed color
STYLE_PRESETS = {}
STYLE_PRESETS.update({
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
    "kill": {
        "emoji": "🔪",
        "label": "Kill",
        "color": discord.Color.from_rgb(200, 50, 50),
    },

})



def load_gif_list(action_key: str) -> List[str]:
    """Load GIF list from a specific JSON file."""
    file_path = os.path.join(GIF_FOLDER, f"{action_key}.json")

    if not os.path.exists(file_path):
        print(f"[WARN] No GIF file for action '{action_key}': {file_path}")
        return []

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            # We expect a simple list of URLs
            if isinstance(data, list):
                return data
            print(f"[WARN] GIF file for '{action_key}' is not a list.")
            return []
    except Exception as e:
        print(f"[ERROR] Failed to read {file_path}: {e}")
        return []


async def send_owo_action_embed(
    ctx: commands.Context,
    target: discord.Member,
    action_key: str,
    *,
    text_template: str,
    self_template: Optional[str] = None,
    extra_note: Optional[str] = None,
    color: Optional[discord.Color] = None,
    action_emoji: Optional[str] = None,   # <- NEW
    action_label: Optional[str] = None,   # <- NEW
):
    """
    Generic OwO-style embed builder.

    text_template: used when author != target.
    self_template: used when author == target.
    action_key: used for presets + GIF file name.
    """

    author: discord.Member = ctx.author

    # ------- Styling from presets -------
    preset = STYLE_PRESETS.get(action_key, {})
    emoji: str = action_emoji or preset.get("emoji", "💚")
    label: str = action_label or preset.get("label", action_key.capitalize())
    color: discord.Color = color or preset.get("color", discord.Color.blurple())

    # ------- Text logic -------
    if target.id == author.id:
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
            target=target.display_name
        )

    if extra_note:
        desc += f"\n\n{extra_note}"

    # OwO frame
    header_line = f"{emoji} {label}"
    sub_line = f"{author.display_name} → {target.display_name}"

    framed_header = (
        f"╭─ {header_line}\n"
        f"╰─ {sub_line}\n\n"
    )

    embed = discord.Embed(
        description=framed_header + desc,
        color=color,
    )

    gifs = load_gif_list(action_key)
    if gifs:
        embed.set_image(url=random.choice(gifs))

    embed.set_footer(text="nexora actions • stay cute, not toxic (uwu)")
    await ctx.send(embed=embed)
