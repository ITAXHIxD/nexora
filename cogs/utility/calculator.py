"""
cogs/utility/calculator.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Interactive Components V2 Mathematical Calculator
Features safe expression evaluation and an interactive on-screen button keypad.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import ast
import logging
import math
import operator
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from utils.ui import (
    BRAND_COLOR,
    ERROR_COLOR,
    SUCCESS_COLOR,
    DismissButton,
    NexoraView,
    send_view,
)

logger = logging.getLogger(__name__)

# ── Safe math operations map ──────────────────────────────────────────────────
SAFE_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}

SAFE_FUNCTIONS = {
    "sqrt": math.sqrt,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "log": math.log,
    "log10": math.log10,
    "abs": abs,
    "round": round,
    "pi": math.pi,
    "e": math.e,
}


def safe_eval(expr: str) -> float:
    """Safely evaluates a math expression without eval/exec vulnerabilities."""
    expr = expr.replace("^", "**").replace("×", "*").replace("÷", "/")

    def _eval(node):
        if isinstance(node, ast.Expression):
            return _eval(node.body)
        elif isinstance(node, ast.Constant):
            if isinstance(node.value, (int, float)):
                return node.value
            raise ValueError("Invalid constant")
        elif isinstance(node, ast.BinOp):
            left = _eval(node.left)
            right = _eval(node.right)
            op_type = type(node.op)
            if op_type in SAFE_OPERATORS:
                # Prevent huge power DOS attacks
                if op_type == ast.Pow and (right > 1000 or left > 10000):
                    raise ValueError("Exponent too large")
                return SAFE_OPERATORS[op_type](left, right)
            raise ValueError(f"Unsupported operator: {op_type}")
        elif isinstance(node, ast.UnaryOp):
            operand = _eval(node.operand)
            op_type = type(node.op)
            if op_type in SAFE_OPERATORS:
                return SAFE_OPERATORS[op_type](operand)
            raise ValueError("Unsupported unary operator")
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in SAFE_FUNCTIONS:
                fn = SAFE_FUNCTIONS[node.func.id]
                args = [_eval(arg) for arg in node.args]
                return fn(*args)
            raise ValueError("Unsupported function call")
        elif isinstance(node, ast.Name):
            if node.id in SAFE_FUNCTIONS:
                return SAFE_FUNCTIONS[node.id]
            raise ValueError(f"Unknown variable: {node.id}")
        else:
            raise ValueError("Invalid mathematical syntax")

    parsed = ast.parse(expr, mode="eval")
    return _eval(parsed)


class CalculatorKeypadView(NexoraView):
    """Components V2 Interactive Keypad Calculator."""

    def __init__(self, bot: commands.Bot, user: discord.abc.User, timeout: float = 180):
        super().__init__(bot=bot, user_id=user.id, color=BRAND_COLOR, timeout=timeout)
        self.expression = ""
        self.result = ""
        self.user = user
        self._build_keypad()

    def _build_keypad(self):
        self.clear_container()

        display_expr = self.expression or "0"
        display_res = f"= **{self.result}**" if self.result else ""

        header = (
            f"# 🧮 Nexora Interactive Calculator\n"
            f"> ```\n"
            f"> {display_expr}\n"
            f"> ```\n"
            f"{display_res}"
        )
        self.add_section(header)
        self.add_separator(discord.SeparatorSpacing.small)

        # 4 Rows of keypad buttons
        grid = [
            [("C", discord.ButtonStyle.danger), ("(", discord.ButtonStyle.secondary), (")", discord.ButtonStyle.secondary), ("÷", discord.ButtonStyle.primary)],
            [("7", discord.ButtonStyle.secondary), ("8", discord.ButtonStyle.secondary), ("9", discord.ButtonStyle.secondary), ("×", discord.ButtonStyle.primary)],
            [("4", discord.ButtonStyle.secondary), ("5", discord.ButtonStyle.secondary), ("6", discord.ButtonStyle.secondary), ("-", discord.ButtonStyle.primary)],
            [("1", discord.ButtonStyle.secondary), ("2", discord.ButtonStyle.secondary), ("3", discord.ButtonStyle.secondary), ("+", discord.ButtonStyle.primary)],
            [("0", discord.ButtonStyle.secondary), (".", discord.ButtonStyle.secondary), ("⌫", discord.ButtonStyle.danger), ("=", discord.ButtonStyle.success)],
        ]

        for row in grid:
            buttons = []
            for label, style in row:
                btn = discord.ui.Button(label=label, style=style)
                btn.callback = self._make_btn_callback(label)
                buttons.append(btn)
            self.add_row(*buttons)

        self.add_footer(f"Session active for {self.user.display_name} · Click buttons to calculate")

    def _make_btn_callback(self, label: str):
        async def callback(interaction: discord.Interaction):
            if label == "C":
                self.expression = ""
                self.result = ""
            elif label == "⌫":
                self.expression = self.expression[:-1]
                self.result = ""
            elif label == "=":
                if self.expression:
                    try:
                        res = safe_eval(self.expression)
                        # Format nicely
                        if isinstance(res, float) and res.is_integer():
                            res = int(res)
                        self.result = f"{res:g}" if isinstance(res, float) else f"{res:,}"
                    except Exception as e:
                        self.result = "Error"
            else:
                if self.result and self.result != "Error":
                    # If just calculated, typing an operator continues from result
                    if label in ("+", "-", "×", "÷"):
                        self.expression = self.result + label
                    else:
                        self.expression = label
                    self.result = ""
                else:
                    self.expression += label

            self._build_keypad()
            await interaction.response.edit_message(view=self)

        return callback


class Calculator(commands.Cog):
    """Mathematical calculations and interactive keypad."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(
        name="calc",
        aliases=["calculate", "math"],
        description="🧮 Evaluate a math expression or open an interactive on-screen calculator",
    )
    @app_commands.describe(
        expression="Math expression to evaluate (e.g. 2 + 2, 5 * (10 - 3), sqrt(144)). Leave empty for keypad",
    )
    async def calc(self, ctx: commands.Context, *, expression: Optional[str] = None):
        if not expression:
            view = CalculatorKeypadView(self.bot, ctx.author)
            return await send_view(ctx, view)

        try:
            val = safe_eval(expression)
            if isinstance(val, float) and val.is_integer():
                val = int(val)
            formatted_res = f"{val:g}" if isinstance(val, float) else f"{val:,}"

            view = NexoraView(color=SUCCESS_COLOR, timeout=120)
            view.add_section(
                f"# 🧮 Math Evaluation\n"
                f"> **Expression:** `{expression}`\n\n"
                f"# = `{formatted_res}`"
            )
            view.add_footer(f"Calculated for {ctx.author.display_name}")
            view.add_row(DismissButton(user_id=ctx.author.id))
            await send_view(ctx, view)
        except Exception as e:
            view = NexoraView(color=ERROR_COLOR, timeout=60)
            view.add_section(
                f"# ❌ Calculation Error\n"
                f"> Could not evaluate `{expression}`\n\n"
                f"• **Reason:** {e}"
            )
            view.add_footer("Supported: +, -, *, /, %, ^, sqrt, sin, cos, tan, log, pi, e")
            await send_view(ctx, view)


async def setup(bot: commands.Bot):
    await bot.add_cog(Calculator(bot))
    logger.debug("Loaded Calculator")
