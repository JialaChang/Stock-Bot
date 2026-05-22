import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
import asyncio

from core import StockDataFetcher, TechnicalAnalyzer, StockVisualizer


# 載入 .env 環境變數
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
# 即時同步指令到伺服器 (非必要)
GUILD_ID = os.getenv('GUILD')
GUILD = discord.Object(id=int(GUILD_ID)) if GUILD_ID else None
# 檢查環境變數
if TOKEN is None:
    raise ValueError("DISCORD_TOKEN not found in environment variables")
if GUILD is None:
    print("GUILD_ID not found in environment variables")


# 設定機器人權限
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='$', intents=intents)

# 機器人上線通知
@bot.event
async def on_ready():
    if GUILD:
        bot.tree.copy_global_to(guild=GUILD)
    await bot.tree.sync()
    print(f"[BOT] Login Identity --> {bot.user}")

# 機器人指令
@bot.tree.command(name="stock", description="輸入股票代碼查詢資訊與圖表（若不是台股與美股請輸入完整後綴）")
async def analyze_stock(interaction: discord.Interaction, ticker: str):
    # 延長機器人回應的時間
    await interaction.response.defer()

    try:
        # 初始化基本資訊
        fetcher = StockDataFetcher(ticker)
        stock_name = fetcher.fetch_stock_name()
        stock_ticker = fetcher.ticker

        # 抓取股票資料
        history_data, intraday_data = await asyncio.gather(
            asyncio.to_thread(fetcher.fetch_historical_data),
            asyncio.to_thread(fetcher.fetch_intraday_data)
        )
        if history_data.empty:
            await interaction.followup.send("無法取得股票資訊，請確認代碼是否正確...")
            return
        latest_time = await asyncio.to_thread(fetcher.fetch_latest_time)
        
        # 技術指標分析
        snapshot = TechnicalAnalyzer.analyze(stock_ticker, stock_name, history_data, latest_time)

        # 輸出圖表 buffer
        image_buffer = await asyncio.to_thread(StockVisualizer.generate_chart, stock_ticker, history_data)
        file = discord.File(image_buffer, filename="chart.png")

        # 將資料打包成 Embed 輸出
        # embed color: red, green, gray
        if snapshot.change_percent > 0: color = 0xe74c3c
        elif snapshot.change_percent < 0: color = 0x2ecc71
        else: color = 0x676767 # 67
        # create Embed
        embed = discord.Embed(
            title=f"📈 {snapshot.name} ({snapshot.ticker})",
            color=color,
        )
        embed.add_field(name="價格", value=f"**{snapshot.current_price:.2f}**", inline=True)
        embed.add_field(name="漲跌", value=f"**{snapshot.change_str}**", inline=True)
        embed.add_field(name="RSI", value=f"**{snapshot.rsi_value:.2f}**", inline=True)
        embed.set_footer(text=f"資料時間: {snapshot.latest_time_str}   |   資料來源: Yahoo Finance")
        embed.set_image(url="attachment://chart.png")

        await interaction.followup.send(embed=embed, file=file)

    except Exception as e:
        await interaction.followup.send(f"發生錯誤：{e}")

if __name__ == "__main__":
    bot.run(TOKEN)