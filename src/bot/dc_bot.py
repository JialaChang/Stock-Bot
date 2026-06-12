import discord
from discord.ext import commands
import os
import io
import logging
from dotenv import load_dotenv
import asyncio

from src.data import StockDataFetcher
from src.quant import TechnicalAnalyzer
from src.utils import StockVisualizer
from src.bot import DiscordStockChart

# 載入 .env 環境變數
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
# 指定測試伺服器可加快 Discord 斜線指令同步速度 (Global Sync 需約 1 小時)
GUILD_ID = os.getenv('GUILD')
GUILD = discord.Object(id=int(GUILD_ID)) if GUILD_ID else None

logger = logging.getLogger(__name__)

# 檢查環境變數
if not TOKEN:
    raise ValueError("DISCORD_TOKEN not found in environment variables")
if not GUILD:
    logger.warning("GUILD_ID not found in environment variables")

# 初始化 Bot 實例並申請預設權限
intents = discord.Intents.default()
bot = commands.Bot(command_prefix='$', intents=intents)

# 機器人上線通知
@bot.event
async def on_ready():
    if GUILD:
        bot.tree.copy_global_to(guild=GUILD)
    await bot.tree.sync()
    logger.info(f"Discord Bot Login Identity --> {bot.user}")

# 機器人離線通知
@bot.event
async def on_disconnect():
    logger.info("Discord Bot Disconnected...")

# 機器人指令
@bot.tree.command(name="stock", description="輸入股票代碼查詢資訊與圖表（若不是台股與美股請輸入完整後綴）")
async def analyze_stock(interaction: discord.Interaction, ticker: str):
    # 延遲回應，避免處理時間過長導致 Discord API 判定互動失敗
    await interaction.response.defer()

    try:
        fetcher = StockDataFetcher(ticker)
        # 使用 to_thread 讓同步 IO (SQLite 查詢) 在背景執行序池執行，避免阻塞 Event Loop
        stock_name = await asyncio.to_thread(fetcher.fetch_stock_name)
        stock_ticker = fetcher.ticker

        # 並發請求 (Concurrency)：同時抓取歷史資料與盤中資料，提升整體響應速度
        history_data, intraday_data = await asyncio.gather(
            asyncio.to_thread(fetcher.fetch_historical_data),
            asyncio.to_thread(fetcher.fetch_intraday_data)
        )
        
        # Payload 完整性校驗
        if history_data.empty or intraday_data.empty:
            await interaction.followup.send(f"無法取得 `{stock_ticker}` 的股票資料...\n> 請確認輸入的股票代碼是否正確，或該股票尚未加入本系統資料庫")
            logger.warning(f"'{stock_ticker}' 資料取得失敗")
            return
            
        latest_time = await asyncio.to_thread(fetcher.fetch_latest_time)
        
        # 背景執行技術指標運算
        snapshot = await asyncio.to_thread(
            TechnicalAnalyzer.analyze, stock_ticker, stock_name, history_data, intraday_data, latest_time
        )

        # 並發渲染兩張圖表
        history_buffer, intraday_buffer = await asyncio.gather(
            asyncio.to_thread(StockVisualizer.generate_history_chart, stock_ticker, history_data),
            asyncio.to_thread(StockVisualizer.generate_intraday_chart, stock_ticker, intraday_data)
        )
        history_bytes = history_buffer.getvalue()
        intraday_bytes = intraday_buffer.getvalue()
        
        history_buffer.close()
        intraday_buffer.close()

        file = discord.File(io.BytesIO(history_bytes), filename="chart.png")

        # 根據漲跌幅給定 Embed 的側邊飾條顏色 (紅漲、綠跌、灰平盤)
        color = 0xe74c3c if snapshot.change_percent > 0 else (0x2ecc71 if snapshot.change_percent < 0 else 0x676767)
        
        # 構建資料展示 Payload
        embed = discord.Embed(
            title=f"📈 {snapshot.name} ({snapshot.ticker})",
            color=color,
        )
        embed.add_field(name="價格", value=f"**{snapshot.current_price:.2f}**", inline=True)
        embed.add_field(name="漲跌", value=f"**{snapshot.change_str}**", inline=True)
        embed.add_field(name="RSI", value=f"**{snapshot.rsi_value:.2f}**", inline=True)
        embed.set_footer(text=f"資料時間: {snapshot.latest_time_str}   |   資料來源: Yahoo Finance")
        embed.set_image(url="attachment://chart.png")

        # 實例化狀態保持元件 (View) 並將其綁定於輸出的 Message 上
        view = DiscordStockChart(stock_ticker, history_bytes, intraday_bytes)
        msg = await interaction.followup.send(embed=embed, file=file, view=view)
        view.message = msg

        logger.info(f"'{stock_ticker}' 訊息輸出成功")

    except Exception as e:
        logger.error(f"'{ticker}' 訊息輸出錯誤：{e}")
        await interaction.followup.send("發生錯誤，請稍後再試或確認股票代碼是否正確。")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    bot.run(TOKEN)