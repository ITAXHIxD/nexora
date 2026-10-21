"""
utils/autoresponder_engine.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Production-grade autoresponder matching engine, variable renderer,
and rich response builder for Nexora.

Features:
  • Match Modes: exact, contains, startswith, endswith, whole_word, regex
  • Multi-trigger support per responder
  • Case-sensitive and case-insensitive matching
  • Safe regex execution with ReDoS heuristic checks and length limits
  • Channel & Role inclusions and exclusions
  • Deterministic priority resolution & conflict modes
  • Dynamic safe variable templating (no eval/exec)
  • Rich multi-embed rendering & reaction support
  • Per-user, per-channel, and per-server cooldown enforcement
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import copy
import logging
import re
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

import discord

logger = logging.getLogger(__name__)

# Maximum regex length and patterns known to cause catastrophic backtracking
MAX_REGEX_LENGTH = 200
DANGEROUS_REGEX_PATTERNS = [
    re.compile(r"(\([^\)]*[\+\*][^\)]*\)[\+\*])"),       # (a+)+ or (.*)*
    re.compile(r"(\[[^\]]*[\+\*][^\]]*\][\+\*])"),       # [0-9+]+
    re.compile(r"([a-zA-Z0-9]\+)+\+"),                   # nested +
]

VALID_MATCH_MODES = {"exact", "contains", "startswith", "endswith", "whole_word", "regex"}
VALID_CONFLICT_MODES = {"first_match", "all_matches"}

# Match mode weights for deterministic tie-breaking (higher = more specific)
MODE_WEIGHTS = {
    "exact": 100,
    "whole_word": 80,
    "regex": 60,
    "startswith": 40,
    "endswith": 40,
    "contains": 20,
}


def sanitize_regex(pattern: str) -> Tuple[bool, Optional[str]]:
    """
    Validate a regex pattern for safety and syntax.
    Returns (is_valid, error_message).
    """
    if len(pattern) > MAX_REGEX_LENGTH:
        return False, f"Regular expression exceeds maximum length of {MAX_REGEX_LENGTH} characters."
    
    for dangerous in DANGEROUS_REGEX_PATTERNS:
        if dangerous.search(pattern):
            return False, "Dangerous regular expression detected (risk of catastrophic backtracking)."
    
    try:
        re.compile(pattern)
    except re.error as err:
        return False, f"Invalid regex pattern: {err}"
    
    return True, None


@dataclass
class AutoResponderItem:
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = ""
    triggers: List[str] = field(default_factory=list)
    match_mode: str = "contains"
    case_sensitive: bool = False
    replies: List[str] = field(default_factory=list)
    embeds: List[Dict[str, Any]] = field(default_factory=list)
    reactions: List[str] = field(default_factory=list)
    reply_to_message: bool = True
    mention_author: bool = False
    allowed_mentions: bool = False
    delete_trigger: bool = False
    delay_seconds: float = 0.0
    enabled: bool = True
    priority: int = 0
    channels: List[int] = field(default_factory=list)          # Allowed channels (empty = all)
    roles: List[int] = field(default_factory=list)             # Allowed roles (empty = all)
    excluded_channels: List[int] = field(default_factory=list) # Denied channels
    excluded_roles: List[int] = field(default_factory=list)    # Denied roles
    cooldown_user: float = 3.0                                 # Per-user cooldown in seconds
    cooldown_channel: float = 0.0                              # Per-channel cooldown
    cooldown_server: float = 0.0                               # Per-server cooldown
    hits: int = 0
    last_triggered_at: Optional[str] = None
    created_by: int = 0
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AutoResponderItem":
        item = cls(
            id=str(data.get("id") or str(uuid.uuid4())[:8]),
            name=str(data.get("name") or ""),
            match_mode=str(data.get("match_mode", "contains")).lower(),
            case_sensitive=bool(data.get("case_sensitive", False)),
            reply_to_message=bool(data.get("reply_to_message", True)),
            mention_author=bool(data.get("mention_author", False)),
            allowed_mentions=bool(data.get("allowed_mentions", False)),
            delete_trigger=bool(data.get("delete_trigger", False)),
            delay_seconds=float(data.get("delay_seconds", 0.0)),
            enabled=bool(data.get("enabled", True)),
            priority=int(data.get("priority", 0)),
            hits=int(data.get("hits", 0)),
            last_triggered_at=data.get("last_triggered_at"),
            created_by=int(data.get("created_by", 0)),
            created_at=str(data.get("created_at") or datetime.now(timezone.utc).isoformat()),
            updated_at=data.get("updated_at"),
        )

        # Handle triggers (support both legacy `trigger` string and new `triggers` list)
        raw_triggers = data.get("triggers")
        if isinstance(raw_triggers, list):
            item.triggers = [str(t).strip() for t in raw_triggers if str(t).strip()]
        elif "trigger" in data and str(data["trigger"]).strip():
            item.triggers = [str(data["trigger"]).strip()]

        # Handle replies (support both legacy `reply` string and `replies` list)
        raw_replies = data.get("replies")
        if isinstance(raw_replies, list):
            item.replies = [str(r) for r in raw_replies if str(r).strip()]
        elif "reply" in data and str(data["reply"]).strip():
            item.replies = [str(data["reply"])]

        # Handle embeds
        raw_embeds = data.get("embeds")
        if isinstance(raw_embeds, list):
            item.embeds = [dict(e) for e in raw_embeds if isinstance(e, dict)]

        # Handle reactions
        raw_reactions = data.get("reactions")
        if isinstance(raw_reactions, list):
            item.reactions = [str(rx).strip() for rx in raw_reactions if str(rx).strip()]

        # Cooldowns
        cooldown_data = data.get("cooldown")
        if isinstance(cooldown_data, dict):
            item.cooldown_user = float(cooldown_data.get("user", item.cooldown_user))
            item.cooldown_channel = float(cooldown_data.get("channel", item.cooldown_channel))
            item.cooldown_server = float(cooldown_data.get("server", item.cooldown_server))
        else:
            item.cooldown_user = float(data.get("cooldown_user", 3.0))
            item.cooldown_channel = float(data.get("cooldown_channel", 0.0))
            item.cooldown_server = float(data.get("cooldown_server", 0.0))

        # Channel & Role permissions
        item.channels = [int(c) for c in data.get("channels", []) if str(c).isdigit()]
        item.roles = [int(r) for r in data.get("roles", []) if str(r).isdigit()]
        item.excluded_channels = [int(c) for c in data.get("excluded_channels", []) if str(c).isdigit()]
        item.excluded_roles = [int(r) for r in data.get("excluded_roles", []) if str(r).isdigit()]

        if not item.name and item.triggers:
            item.name = item.triggers[0][:30]

        return item

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "triggers": self.triggers,
            # Legacy mirror for backwards compatibility
            "trigger": self.triggers[0] if self.triggers else "",
            "match_mode": self.match_mode,
            "case_sensitive": self.case_sensitive,
            "replies": self.replies,
            "reply": self.replies[0] if self.replies else "",
            "embeds": self.embeds,
            "reactions": self.reactions,
            "reply_to_message": self.reply_to_message,
            "mention_author": self.mention_author,
            "allowed_mentions": self.allowed_mentions,
            "delete_trigger": self.delete_trigger,
            "delay_seconds": self.delay_seconds,
            "enabled": self.enabled,
            "priority": self.priority,
            "channels": self.channels,
            "roles": self.roles,
            "excluded_channels": self.excluded_channels,
            "excluded_roles": self.excluded_roles,
            "cooldown": {
                "user": self.cooldown_user,
                "channel": self.cooldown_channel,
                "server": self.cooldown_server,
            },
            "hits": self.hits,
            "last_triggered_at": self.last_triggered_at,
            "created_by": self.created_by,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass
class GuildAutoResponderSettings:
    enabled: bool = True
    conflict_mode: str = "first_match"  # 'first_match' or 'all_matches'
    ignored_channels: List[int] = field(default_factory=list)
    ignored_roles: List[int] = field(default_factory=list)
    default_cooldown: float = 3.0

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GuildAutoResponderSettings":
        return cls(
            enabled=bool(data.get("enabled", True)),
            conflict_mode=str(data.get("conflict_mode", "first_match")).lower(),
            ignored_channels=[int(c) for c in data.get("ignored_channels", []) if str(c).isdigit()],
            ignored_roles=[int(r) for r in data.get("ignored_roles", []) if str(r).isdigit()],
            default_cooldown=float(data.get("default_cooldown", 3.0)),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "enabled": self.enabled,
            "conflict_mode": self.conflict_mode,
            "ignored_channels": self.ignored_channels,
            "ignored_roles": self.ignored_roles,
            "default_cooldown": self.default_cooldown,
        }


class AutoResponderEngine:
    """
    Central matching, rate-limiting, and rendering engine.
    Stateless with respect to Discord guilds except for memory cooldown tracking.
    """

    def __init__(self):
        # Cooldown trackers:
        # key: (guild_id, responder_id, user_id) -> timestamp
        self._user_cooldowns: Dict[Tuple[int, str, int], float] = {}
        # key: (guild_id, responder_id, channel_id) -> timestamp
        self._channel_cooldowns: Dict[Tuple[int, str, int], float] = {}
        # key: (guild_id, responder_id) -> timestamp
        self._server_cooldowns: Dict[Tuple[int, str], float] = {}
        # Compiled regex cache: (pattern, case_sensitive) -> Pattern
        self._regex_cache: Dict[Tuple[str, bool], Optional[re.Pattern]] = {}
        self._last_cleanup = time.time()

    def _cleanup_expired_cooldowns(self, now: float) -> None:
        """Prune cooldown entries older than 5 minutes to prevent memory leaks."""
        if now - self._last_cleanup < 300.0:
            return
        self._last_cleanup = now
        cutoff = now - 300.0
        self._user_cooldowns = {k: v for k, v in self._user_cooldowns.items() if v > cutoff}
        self._channel_cooldowns = {k: v for k, v in self._channel_cooldowns.items() if v > cutoff}
        self._server_cooldowns = {k: v for k, v in self._server_cooldowns.items() if v > cutoff}

    def get_compiled_regex(self, pattern: str, case_sensitive: bool) -> Optional[re.Pattern]:
        cache_key = (pattern, case_sensitive)
        if cache_key in self._regex_cache:
            return self._regex_cache[cache_key]

        is_valid, _ = sanitize_regex(pattern)
        if not is_valid:
            self._regex_cache[cache_key] = None
            return None

        flags = 0 if case_sensitive else re.IGNORECASE
        try:
            compiled = re.compile(pattern, flags)
            self._regex_cache[cache_key] = compiled
            return compiled
        except Exception as exc:
            logger.debug("Regex compile failed for %r: %s", pattern, exc)
            self._regex_cache[cache_key] = None
            return None

    def match_trigger(
        self,
        trigger: str,
        message_content: str,
        match_mode: str,
        case_sensitive: bool,
    ) -> bool:
        """
        Check if message_content satisfies the given trigger and match mode.
        """
        if not trigger or not message_content:
            return False

        mode = match_mode.lower()
        text = message_content if case_sensitive else message_content.casefold()
        t = trigger if case_sensitive else trigger.casefold()

        if mode == "exact":
            return text.strip() == t.strip()

        elif mode == "contains":
            return t in text

        elif mode == "startswith":
            return text.strip().startswith(t.strip())

        elif mode == "endswith":
            return text.strip().endswith(t.strip())

        elif mode == "whole_word":
            escaped = re.escape(t.strip())
            pattern = rf"(?:\b|^){escaped}(?:\b|$)"
            flags = 0 if case_sensitive else re.IGNORECASE
            try:
                return bool(re.search(pattern, message_content, flags))
            except Exception:
                return False

        elif mode == "regex":
            compiled = self.get_compiled_regex(trigger, case_sensitive)
            if compiled is None:
                return False
            try:
                return bool(compiled.search(message_content))
            except Exception:
                return False

        return False

    def is_eligible(
        self,
        item: AutoResponderItem,
        settings: GuildAutoResponderSettings,
        channel_id: int,
        member_role_ids: Set[int],
    ) -> Tuple[bool, str]:
        """
        Check channel and role inclusions and exclusions.
        Returns (is_eligible, reason_if_not).
        """
        if not item.enabled:
            return False, "Responder is disabled"

        if not settings.enabled:
            return False, "Server autoresponder is disabled in settings"

        # Server-wide channel exclusions
        if channel_id in settings.ignored_channels:
            return False, "Channel is ignored in server settings"

        # Responder channel exclusions
        if channel_id in item.excluded_channels:
            return False, "Channel is excluded for this responder"

        # Responder channel inclusions
        if item.channels and channel_id not in item.channels:
            return False, "Channel is not in responder's allowed channel list"

        # Server-wide role exclusions
        if member_role_ids.intersection(settings.ignored_roles):
            return False, "Member has a server-ignored role"

        # Responder role exclusions
        if member_role_ids.intersection(item.excluded_roles):
            return False, "Member has a responder-excluded role"

        # Responder role inclusions
        if item.roles and not member_role_ids.intersection(item.roles):
            return False, "Member does not have any of the required roles"

        return True, "Eligible"

    def check_and_apply_cooldown(
        self,
        guild_id: int,
        item: AutoResponderItem,
        user_id: int,
        channel_id: int,
        dry_run: bool = False,
    ) -> Tuple[bool, float]:
        """
        Check whether responder is under cooldown for this user, channel, or server.
        If not on cooldown and dry_run is False, updates the cooldown timestamps.
        Returns (is_on_cooldown, remaining_seconds).
        """
        now = time.time()
        self._cleanup_expired_cooldowns(now)

        # 1. User cooldown
        u_key = (guild_id, item.id, user_id)
        if item.cooldown_user > 0:
            last = self._user_cooldowns.get(u_key, 0.0)
            diff = now - last
            if diff < item.cooldown_user:
                return True, round(item.cooldown_user - diff, 1)

        # 2. Channel cooldown
        c_key = (guild_id, item.id, channel_id)
        if item.cooldown_channel > 0:
            last = self._channel_cooldowns.get(c_key, 0.0)
            diff = now - last
            if diff < item.cooldown_channel:
                return True, round(item.cooldown_channel - diff, 1)

        # 3. Server cooldown
        s_key = (guild_id, item.id)
        if item.cooldown_server > 0:
            last = self._server_cooldowns.get(s_key, 0.0)
            diff = now - last
            if diff < item.cooldown_server:
                return True, round(item.cooldown_server - diff, 1)

        if not dry_run:
            if item.cooldown_user > 0:
                self._user_cooldowns[u_key] = now
            if item.cooldown_channel > 0:
                self._channel_cooldowns[c_key] = now
            if item.cooldown_server > 0:
                self._server_cooldowns[s_key] = now

        return False, 0.0

    def evaluate_message(
        self,
        message_content: str,
        responders: List[AutoResponderItem],
        settings: GuildAutoResponderSettings,
        channel_id: int,
        member_role_ids: Set[int],
        user_id: int,
        guild_id: int,
        dry_run: bool = False,
    ) -> List[Tuple[AutoResponderItem, str]]:
        """
        Evaluate message against all responders in the guild.
        Returns a list of tuples: (matched_responder, matched_trigger).
        Respects conflict_mode ('first_match' or 'all_matches').
        """
        if not settings.enabled or not responders or not message_content.strip():
            return []

        matched_candidates: List[Tuple[int, int, int, AutoResponderItem, str]] = []

        for item in responders:
            eligible, _ = self.is_eligible(item, settings, channel_id, member_role_ids)
            if not eligible:
                continue

            for trigger in item.triggers:
                if self.match_trigger(trigger, message_content, item.match_mode, item.case_sensitive):
                    on_cd, _ = self.check_and_apply_cooldown(
                        guild_id, item, user_id, channel_id, dry_run=True
                    )
                    if on_cd:
                        continue

                    mode_weight = MODE_WEIGHTS.get(item.match_mode, 10)
                    trigger_len = len(trigger)
                    # Priority tuple: (item.priority, mode_weight, trigger_len)
                    matched_candidates.append(
                        (item.priority, mode_weight, trigger_len, item, trigger)
                    )
                    break  # One match per item is sufficient

        if not matched_candidates:
            return []

        # Sort descending by priority, specificity, trigger length
        matched_candidates.sort(key=lambda x: (x[0], x[1], x[2]), reverse=True)

        results: List[Tuple[AutoResponderItem, str]] = []
        if settings.conflict_mode == "first_match":
            top = matched_candidates[0]
            item, trigger = top[3], top[4]
            if not dry_run:
                self.check_and_apply_cooldown(guild_id, item, user_id, channel_id, dry_run=False)
            results.append((item, trigger))
        else:
            # all_matches: limit to 3 max to prevent flood
            for candidate in matched_candidates[:3]:
                item, trigger = candidate[3], candidate[4]
                if not dry_run:
                    self.check_and_apply_cooldown(guild_id, item, user_id, channel_id, dry_run=False)
                results.append((item, trigger))

        return results

    @staticmethod
    def render_variables(
        template: str,
        message: discord.Message,
        extra_vars: Optional[Dict[str, str]] = None,
    ) -> str:
        """
        Render variable placeholders into string without using eval or exec.
        Safe against arbitrary execution and missing attributes.
        """
        if not template:
            return ""

        guild = message.guild
        author = message.author
        channel = message.channel

        replacements = {
            "{user}": getattr(author, "display_name", "User"),
            "{user.name}": getattr(author, "name", "User"),
            "{user.mention}": getattr(author, "mention", ""),
            "{user.id}": str(getattr(author, "id", "")),
            "{user.avatar}": (
                getattr(author, "display_avatar", None).url
                if hasattr(author, "display_avatar")
                else ""
            ),
            "{server}": getattr(guild, "name", "Server") if guild else "Direct Message",
            "{server.name}": getattr(guild, "name", "Server") if guild else "Direct Message",
            "{server.id}": str(getattr(guild, "id", "")) if guild else "",
            "{guild.id}": str(getattr(guild, "id", "")) if guild else "",
            "{server.icon}": (
                guild.icon.url if guild and getattr(guild, "icon", None) else ""
            ),
            "{channel}": getattr(channel, "mention", "") if hasattr(channel, "mention") else "",
            "{channel.mention}": getattr(channel, "mention", "") if hasattr(channel, "mention") else "",
            "{channel.name}": getattr(channel, "name", "") if hasattr(channel, "name") else "",
            "{channel.id}": str(getattr(channel, "id", "")),
            "{members}": str(getattr(guild, "member_count", 0)) if guild else "1",
            "{timestamp}": str(int(time.time())),
            "{created_at}": (
                discord.utils.format_dt(message.created_at, style="R")
                if hasattr(message, "created_at") and message.created_at
                else ""
            ),
        }

        if extra_vars:
            replacements.update(extra_vars)

        text = template
        # Replace tokens by longest name first to avoid partial replacements
        for token in sorted(replacements.keys(), key=len, reverse=True):
            if token in text:
                text = text.replace(token, str(replacements[token]))

        # Handle simple {random:min-max} helper
        def _replace_random(match):
            try:
                lo = int(match.group(1))
                hi = int(match.group(2))
                import random
                return str(random.randint(lo, hi))
            except Exception:
                return match.group(0)

        text = re.sub(r"\{random:(\d+)-(\d+)\}", _replace_random, text)

        return text

    @classmethod
    def build_embeds(
        cls,
        embed_data_list: List[Dict[str, Any]],
        message: discord.Message,
    ) -> List[discord.Embed]:
        """
        Convert raw embed dictionaries to discord.Embed objects with rendered variables.
        """
        embeds: List[discord.Embed] = []
        if not embed_data_list:
            return embeds

        for data in embed_data_list[:10]:  # Discord supports max 10 embeds per message
            if not isinstance(data, dict):
                continue

            title = cls.render_variables(str(data.get("title", "")), message).strip()
            desc = cls.render_variables(str(data.get("description", "")), message).strip()
            
            # Resolve color
            color = data.get("color")
            color_int = 0x5865F2  # Default blurple
            if isinstance(color, int):
                color_int = color
            elif isinstance(color, str):
                clean_c = color.lstrip("#").replace("0x", "").strip()
                if re.fullmatch(r"[0-9a-fA-F]{6}", clean_c):
                    color_int = int(clean_c, 16)

            embed = discord.Embed(
                title=title[:256] if title else None,
                description=desc[:4096] if desc else None,
                color=color_int,
            )

            # URL
            url = data.get("url")
            if isinstance(url, str) and url.startswith(("http://", "https://")):
                embed.url = url

            # Author
            author_data = data.get("author")
            if isinstance(author_data, dict):
                a_name = cls.render_variables(str(author_data.get("name", "")), message).strip()
                if a_name:
                    a_url = author_data.get("url")
                    a_icon = author_data.get("icon_url")
                    embed.set_author(
                        name=a_name[:256],
                        url=a_url if isinstance(a_url, str) and a_url.startswith(("http://", "https://")) else None,
                        icon_url=a_icon if isinstance(a_icon, str) and a_icon.startswith(("http://", "https://")) else None,
                    )

            # Footer
            footer_data = data.get("footer")
            if isinstance(footer_data, dict):
                f_text = cls.render_variables(str(footer_data.get("text", "")), message).strip()
                if f_text:
                    f_icon = footer_data.get("icon_url")
                    embed.set_footer(
                        text=f_text[:2048],
                        icon_url=f_icon if isinstance(f_icon, str) and f_icon.startswith(("http://", "https://")) else None,
                    )

            # Thumbnail
            thumb = data.get("thumbnail")
            if isinstance(thumb, str) and thumb.startswith(("http://", "https://")):
                embed.set_thumbnail(url=thumb)
            elif isinstance(thumb, dict) and isinstance(thumb.get("url"), str):
                embed.set_thumbnail(url=thumb["url"])

            # Image
            img = data.get("image")
            if isinstance(img, str) and img.startswith(("http://", "https://")):
                embed.set_image(url=img)
            elif isinstance(img, dict) and isinstance(img.get("url"), str):
                embed.set_image(url=img["url"])

            # Fields
            fields = data.get("fields")
            if isinstance(fields, list):
                for f in fields[:25]:
                    if isinstance(f, dict):
                        f_name = cls.render_variables(str(f.get("name", "")), message).strip()
                        f_val = cls.render_variables(str(f.get("value", "")), message).strip()
                        if f_name and f_val:
                            embed.add_field(
                                name=f_name[:256],
                                value=f_val[:1024],
                                inline=bool(f.get("inline", True)),
                            )

            # Timestamp
            if data.get("timestamp"):
                embed.timestamp = datetime.now(timezone.utc)

            embeds.append(embed)

        return embeds
