# dc_bot_command.py
import discord
from discord.ui import Button, View
import asyncio
import io
from datetime import datetime, timezone, timedelta

# 日誌輸出函式
def log_print(msg: str):
    # 設定為台灣時區 (UTC+8)
    tz = timezone(timedelta(hours=8))
    now = datetime.now(tz).strftime("%H:%M:%S")
    print(f"({now}) {msg}")

# Discord 訊息物件
class DiscordStockChart(View):
    def __init__(self, stock_ticker: str, history_bytes: bytes, intraday_bytes: bytes):
        # 設定五分鐘的有效時間
        super().__init__(timeout=300.0)
        self.stock_ticker = stock_ticker
        self.message = None  # 用來儲存 Bot 發出的訊息物件
        self.is_history = True  # 預設初始圖表是歷史日線
        # 儲存圖片的記憶體位置
        self.history_bytes = history_bytes
        self.intraday_bytes = intraday_bytes


    async def on_timeout(self):
        """超時後把刪除訊息並清空記憶體"""
        if self.message:
            try:
                expired_embed = discord.Embed(
                    title=f"{self.stock_ticker} 查詢已過期",
                    description="此訊息超過 5 分鐘已自動刪除，請重新輸入 `/stock` 查詢",
                    color=0x2f3136
                )
                await self.message.edit(embed=expired_embed, attachments=[], view=None) # pyright: ignore[reportGeneralTypeIssues]
                log_print(f"[BOT] '{self.stock_ticker}' 訊息已刪除")
            except Exception as e:
                log_print(f"[BOT] '{self.stock_ticker}' 訊息刪除失敗：{e}")
        # 將自身數據清空
        self.history_bytes = None
        self.intraday_bytes = None

    @discord.ui.button(label="查看盤中走勢", style=discord.ButtonStyle.primary, custom_id="btn_toggle")
    async def btn_toggle(self, interaction: discord.Interaction, button: Button):
        """點擊按鈕切換圖表"""
        await interaction.response.defer()

        # 判斷當前圖表
        if self.is_history:
            # 切換到盤中走勢
            if not self.intraday_bytes:
                await interaction.followup.send("目前無盤中分時資料！", ephemeral=True)
                return
            
            file = discord.File(io.BytesIO(self.intraday_bytes), filename="chart_intra.png")
            filename = "chart_intra.png"
                     
            button.label = "查看歷史日線"
            button.style = discord.ButtonStyle.primary
            self.is_history = False

        else:
            # 切換回歷史日線圖
            if not self.history_bytes:
                await interaction.followup.send("目前無歷史日線資料！", ephemeral=True)
                return

            file = discord.File(io.BytesIO(self.history_bytes), filename="chart_hist.png")
            filename="chart_hist.png"

            button.label = "查看盤中走勢"
            button.style = discord.ButtonStyle.primary
            self.is_history = True
        
        # 替換圖片並更新訊息
        embed = interaction.message.embeds[0] # pyright: ignore[reportOptionalMemberAccess]
        embed.set_image(url=f"attachment://{filename}")
        await interaction.message.edit(embed=embed, attachments=[file], view=self) # pyright: ignore[reportOptionalMemberAccess]