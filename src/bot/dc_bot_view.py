import discord
from discord.ui import Button, View
import io
import logging

from src.models.stock import StockSnapshot
from src.models.trade import BacktestResult


logger = logging.getLogger(__name__)


def display_name(name: str, ticker: str) -> str:
    """`name (ticker)`, or the bare ticker when no name is known."""
    return f"{name} ({ticker})" if name != ticker else ticker


def _change_color(value: float) -> int:
    """Red for up, green for down, grey for flat (TW convention)."""
    return 0xe74c3c if value > 0 else 0x2ecc71 if value < 0 else 0x676767


class ChartToggleView(View):
    """Button view toggling between the daily and intraday charts."""
    def __init__(self, stock_ticker: str, history_bytes: bytes, intraday_bytes: bytes | None):
        super().__init__(timeout=300.0)
        self.stock_ticker = stock_ticker
        self.message = None       # Set by the sender, for cleanup in on_timeout
        self.is_history = True
        self.history_bytes = history_bytes
        self.intraday_bytes = intraday_bytes

        if not intraday_bytes:
            for item in self.children:
                if isinstance(item, Button) and item.custom_id == "btn_toggle":
                    item.disabled = True
                    item.label = "Intraday unavailable"

    async def on_timeout(self):
        """Replace the message with an expiry notice and free the images."""
        if self.message:
            try:
                expired_embed = discord.Embed(
                    title=f"{self.stock_ticker} query expired",
                    description="This message expired after 5 minutes and was removed automatically. Run `/stock` again to query.",
                    color=0x2f3136
                )
                await self.message.edit(embed=expired_embed, attachments=[], view=None) # pyright: ignore[reportGeneralTypeIssues]
                logger.info(f"Message for '{self.stock_ticker}' removed")
            except Exception as e:
                logger.error(f"Failed to remove message for '{self.stock_ticker}': {e}")

        self.history_bytes = None
        self.intraday_bytes = None

    @discord.ui.button(label="View intraday", style=discord.ButtonStyle.primary, custom_id="btn_toggle")
    async def btn_toggle(self, interaction: discord.Interaction, button: Button):
        """Swap the displayed chart."""
        await interaction.response.defer()

        if self.is_history:
            if not self.intraday_bytes:
                await interaction.followup.send("No intraday data available!", ephemeral=True)
                return
            file_bytes, filename = self.intraday_bytes, "chart_intra.png"
            button.label = "View daily"
        else:
            if not self.history_bytes:
                await interaction.followup.send("No daily historical data available!", ephemeral=True)
                return
            file_bytes, filename = self.history_bytes, "chart_hist.png"
            button.label = "View intraday"

        self.is_history = not self.is_history
        button.style = discord.ButtonStyle.primary
        file = discord.File(io.BytesIO(file_bytes), filename=filename)

        embed = interaction.message.embeds[0] # pyright: ignore[reportOptionalMemberAccess]
        embed.set_image(url=f"attachment://{filename}")
        await interaction.message.edit(embed=embed, attachments=[file], view=self) # pyright: ignore[reportOptionalMemberAccess]


async def send_stock_response(interaction: discord.Interaction, snapshot: StockSnapshot, history_bytes: bytes, intraday_bytes: bytes | None) -> None:
    """Send the `/stock` Embed."""
    embed = discord.Embed(title=f"📈 {display_name(snapshot.name, snapshot.ticker)}",
                          color=_change_color(snapshot.change_percent))
    embed.add_field(name="Price", value=f"**{snapshot.current_price:.2f}**", inline=True)
    embed.add_field(name="Change", value=f"**{snapshot.change_str}**", inline=True)
    embed.add_field(name="RSI", value=f"**{snapshot.rsi_str}**", inline=True)
    embed.set_footer(text=f"Data time: {snapshot.latest_time_str}   |   Source: Yahoo Finance")
    embed.set_image(url="attachment://chart.png")

    file = discord.File(io.BytesIO(history_bytes), filename="chart.png")
    view = ChartToggleView(snapshot.ticker, history_bytes, intraday_bytes)
    msg = await interaction.followup.send(embed=embed, file=file, view=view)
    view.message = msg


async def send_backtest_response(interaction: discord.Interaction, result: BacktestResult, stock_name: str, strategy_label: str, chart_bytes: bytes) -> None:
    """Send the `/backtest` Embed."""
    embed = discord.Embed(title=f"📊 {display_name(stock_name, result.ticker)} backtest ({strategy_label})",
                          color=_change_color(result.total_return))
    embed.add_field(name="Total return", value=f"**{result.total_return:.2f}%**", inline=True)
    embed.add_field(name="Win rate", value=f"**{result.win_rate:.2f}%**", inline=True)
    embed.add_field(name="Max drawdown", value=f"**{result.max_drawdown:.2f}%**", inline=True)
    embed.add_field(name="Trade count", value=f"**{result.trade_count}**", inline=True)
    embed.set_image(url="attachment://backtest.png")

    file = discord.File(io.BytesIO(chart_bytes), filename="backtest.png")
    await interaction.followup.send(embed=embed, file=file)
