import discord
from discord.ext import commands
import os
import logging
from dotenv import load_dotenv
import asyncio

from src.data import StockDataFetcher
from src.quant import compute_indicators_for_discord
from src.utils import generate_history_chart, generate_intraday_chart
from src.bot import send_stock_response

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
# 指定測試伺服器 Guild 可加快指令同步；不設定則走 Global Sync（約 1 小時生效）
GUILD_ID = os.getenv('GUILD')
GUILD = discord.Object(id=int(GUILD_ID)) if GUILD_ID else None

logger = logging.getLogger(__name__)

# 檢查環境變數
if not TOKEN:
    raise ValueError("DISCORD_TOKEN not found in environment variables")
if not GUILD:
    logger.warning("GUILD_ID not found in environment variables")

# Intents 決定 Bot 訂閱哪些 Gateway 事件，未宣告的事件不會被推送
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

@bot.tree.command(name="stock", description="輸入股票代碼查詢資訊與圖表（僅支援台股美股與部份指數）")
async def analyze_stock(interaction: discord.Interaction, ticker: str):
    # defer() 避免處理超過 3 秒導致 Discord 判定互動逾時
    await interaction.response.defer()

    try:
        fetcher = StockDataFetcher(ticker)
        # asyncio.to_thread 將同步阻塞的 SQLite/yfinance 呼叫卸載至執行緒池，避免阻塞 Event Loop
        stock_name = await asyncio.to_thread(fetcher.fetch_stock_name)
        stock_ticker = fetcher.ticker

        # 並發請求提升響應速度
        history_data, intraday_data = await asyncio.gather(
            asyncio.to_thread(fetcher.fetch_historical_data),
            asyncio.to_thread(fetcher.fetch_intraday_data)
        )

        if history_data.empty or intraday_data.empty:
            await interaction.followup.send(f"無法取得 `{stock_ticker}` 的股票資料...\n> 請確認輸入的股票代碼是否正確，或該股票尚未加入本系統資料庫")
            logger.warning(f"'{stock_ticker}' 資料取得失敗")
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
        logger.info(f"'{stock_ticker}' 訊息輸出成功")

    except Exception as e:
        logger.error(f"'{ticker}' 訊息輸出錯誤：{e}")
        await interaction.followup.send("發生錯誤，請稍後再試或確認股票代碼是否正確。")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    try:
        logger.info("Starting Discord bot...")
        bot.run(TOKEN)
    except Exception as e:
        logger.error(f"Discord bot Error : {e}")