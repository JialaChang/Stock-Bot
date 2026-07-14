import discord
from discord.ext import commands
import sys, os
import logging
from dotenv import load_dotenv
import asyncio

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from src.data import StockDataFetcher
from src.quant import compute_indicators_for_discord, BacktestEngine, RSIStrategy, EMAStrategy
from src.utils import generate_history_chart, generate_intraday_chart, generate_backtest_chart
from src.bot import send_stock_response, send_backtest_response

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
# Specifying a test guild speeds up command sync; without it commands go through a global sync (takes about 1 hour to take effect).
GUILD_ID = os.getenv('GUILD')
GUILD = discord.Object(id=int(GUILD_ID)) if GUILD_ID else None

logger = logging.getLogger(__name__)

# Validate environment variables
if not TOKEN:
    raise ValueError("DISCORD_TOKEN not found in environment variables")
if not GUILD:
    logger.warning("GUILD_ID not found in environment variables")

# Intents decide which gateway events the bot subscribes to; undeclared events are not pushed.
intents = discord.Intents.default()
bot = commands.Bot(command_prefix='$', intents=intents)

@bot.event
async def on_ready():
    if GUILD:
        bot.tree.copy_global_to(guild=GUILD)
    await bot.tree.sync()
    logger.info(f"Discord Bot Login Identity --> {bot.user}")

@bot.event
async def on_disconnect():
    logger.info("Discord Bot Disconnected...")

@bot.tree.command(name="stock", description="Enter a ticker to query info and charts (TW/US stocks and some indices only)")
async def analyze_stock(interaction: discord.Interaction, ticker: str):
    # defer() prevents Discord from timing out the interaction if processing takes over 3 seconds
    await interaction.response.defer()

    try:
        fetcher = StockDataFetcher(ticker)
        # asyncio.to_thread offloads the blocking SQLite/yfinance calls to a thread pool so the event loop is not blocked
        stock_name = await asyncio.to_thread(fetcher.fetch_stock_name)
        stock_ticker = fetcher.ticker

        # Run requests concurrently to improve responsiveness
        history_data, intraday_data = await asyncio.gather(
            asyncio.to_thread(fetcher.fetch_historical_data),
            asyncio.to_thread(fetcher.fetch_intraday_data)
        )

        if history_data.empty or intraday_data.empty:
            await interaction.followup.send(f"Could not retrieve data for `{stock_ticker}`...\n> Please check that the ticker is correct, or the stock may not be in the database yet")
            logger.warning(f"Failed to retrieve data for '{stock_ticker}'")
            return

        latest_time = await asyncio.to_thread(fetcher.fetch_latest_time)

        snapshot = await asyncio.to_thread(
            compute_indicators_for_discord, stock_ticker, stock_name, history_data, intraday_data, latest_time
        )

        history_buffer, intraday_buffer = await asyncio.gather(
            asyncio.to_thread(generate_history_chart, stock_ticker, history_data),
            asyncio.to_thread(generate_intraday_chart, stock_ticker, intraday_data)
        )
        history_bytes = history_buffer.getvalue()
        intraday_bytes = intraday_buffer.getvalue()
        history_buffer.close()
        intraday_buffer.close()

        await send_stock_response(interaction, snapshot, history_bytes, intraday_bytes)
        logger.info(f"Response for '{stock_ticker}' sent successfully")

    except Exception as e:
        logger.error(f"Error sending response for '{ticker}': {e}")
        await interaction.followup.send("An error occurred, please try again later or check that the ticker is correct.")


STRATEGIES = {"RSI": RSIStrategy, "EMA": EMAStrategy}
PERIODS = {"1mo": 30, "3mo": 90, "6mo": 180,
           "1y": 365, "2y": 730, "3y": 1095, "5y": 1825, "10y": 3650}

@bot.tree.command(name="backtest", description="Enter a ticker to run a strategy backtest and show a chart (TW/US stocks and some indices only)")
@discord.app_commands.choices(
    strategy=[discord.app_commands.Choice(name=name, value=name) for name in STRATEGIES],
    period=[discord.app_commands.Choice(name=p, value=p) for p in PERIODS]
)
async def backtest_stock(interaction: discord.Interaction, ticker: str, strategy: discord.app_commands.Choice[str], period: discord.app_commands.Choice[str]):
    await interaction.response.defer()

    try:
        fetcher = StockDataFetcher(ticker)
        stock_ticker = fetcher.ticker

        data = await asyncio.to_thread(fetcher.fetch_historical_data, days=PERIODS[period.value])
        if data.empty:
            await interaction.followup.send(f"Could not retrieve historical data for `{stock_ticker}`...\n> Please check that the ticker is correct, or the stock may not be in the database yet")
            logger.warning(f"Failed to retrieve data for '{stock_ticker}'")
            return

        engine = BacktestEngine()
        engine.strategy = STRATEGIES[strategy.value]()
        result = await asyncio.to_thread(engine.run, stock_ticker, data)

        chart_buffer = await asyncio.to_thread(generate_backtest_chart, stock_ticker, result)
        chart_bytes = chart_buffer.getvalue()
        chart_buffer.close()

        await send_backtest_response(interaction, result, strategy.name, chart_bytes)
        logger.info(f"Backtest result for '{stock_ticker}' sent successfully")

    except Exception as e:
        logger.error(f"Error sending backtest for '{ticker}': {e}")
        await interaction.followup.send("An error occurred, please try again later or check that the ticker is correct.")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    try:
        logger.info("Starting Discord bot...")
        bot.run(TOKEN)
    except Exception as e:
        logger.error(f"Discord bot Error : {e}")
