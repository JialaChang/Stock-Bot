# dc_bot_command.py
import discord
from discord.ui import Button, View
import io
import logging

logger = logging.getLogger(__name__)

class DiscordStockChart(View):
    """
    Discord 互動式 UI 元件 (View)\n
    負責管理單一股票查詢結果的狀態 (State)，允許使用者透過點擊按鈕在歷史日線與盤中走勢圖之間切換
    """
    def __init__(self, stock_ticker: str, history_bytes: bytes, intraday_bytes: bytes):
        super().__init__(timeout=300.0)  # 設定 5 分鐘的 Timeout 週期
        self.stock_ticker = stock_ticker
        self.message = None              # 儲存與此 View 綁定的 Discord Message 參考
        self.is_history = True           # 狀態標記：記錄當前顯示的圖表類型
        self.history_bytes = history_bytes
        self.intraday_bytes = intraday_bytes

    async def on_timeout(self):
        """超時清理機制：移除 Discord UI 元件並釋放記憶體，避免 Memory Leak"""
        if self.message:
            try:
                expired_embed = discord.Embed(
                    title=f"{self.stock_ticker} 查詢已過期",
                    description="此訊息超過 5 分鐘已自動刪除，請重新輸入 `/stock` 查詢",
                    color=0x2f3136
                )
                await self.message.edit(embed=expired_embed, attachments=[], view=None) # pyright: ignore[reportGeneralTypeIssues]
                logger.info(f"'{self.stock_ticker}' 訊息已刪除")
            except Exception as e:
                logger.error(f"'{self.stock_ticker}' 訊息刪除失敗：{e}")
                
        # 釋放記憶體緩衝區
        self.history_bytes = None
        self.intraday_bytes = None

    @discord.ui.button(label="查看盤中走勢", style=discord.ButtonStyle.primary, custom_id="btn_toggle")
    async def btn_toggle(self, interaction: discord.Interaction, button: Button):
        """處理按鈕點擊事件，切換圖表狀態並更新訊息 Payload"""
        # 延遲回應，避免處理時間過長導致 Discord API 判定互動失敗
        await interaction.response.defer()

        # 根據當前狀態，決定目標圖表資料與按鈕的下一個標籤
        if self.is_history:
            if not self.intraday_bytes:
                await interaction.followup.send("目前無盤中分時資料！", ephemeral=True)
                return
            file_bytes, filename = self.intraday_bytes, "chart_intra.png"
            button.label = "查看歷史日線"
        else:
            if not self.history_bytes:
                await interaction.followup.send("目前無歷史日線資料！", ephemeral=True)
                return
            file_bytes, filename = self.history_bytes, "chart_hist.png"
            button.label = "查看盤中走勢"

        # 更新內部狀態與按鈕屬性
        self.is_history = not self.is_history
        button.style = discord.ButtonStyle.primary
        file = discord.File(io.BytesIO(file_bytes), filename=filename)
        
        # 替換圖片並更新訊息
        embed = interaction.message.embeds[0] # pyright: ignore[reportOptionalMemberAccess]
        embed.set_image(url=f"attachment://{filename}")
        await interaction.message.edit(embed=embed, attachments=[file], view=self) # pyright: ignore[reportOptionalMemberAccess]