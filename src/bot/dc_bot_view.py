import discord
from discord.ui import Button, View
import io
import logging

logger = logging.getLogger(__name__)

class DiscordStockChart(View):
    """持有圖表狀態的 Discord UI 元件，允許使用者在日線圖與分時圖之間切換"""
    def __init__(self, stock_ticker: str, history_bytes: bytes, intraday_bytes: bytes):
        super().__init__(timeout=300.0)
        self.stock_ticker = stock_ticker
        self.message = None       # 儲存 Message 參考，供 on_timeout 清理使用
        self.is_history = True    # 目前顯示的圖表類型
        self.history_bytes = history_bytes
        self.intraday_bytes = intraday_bytes

    async def on_timeout(self):
        """逾時後將訊息替換為過期提示並清空圖片 bytes"""
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
                
        self.history_bytes = None
        self.intraday_bytes = None

    @discord.ui.button(label="查看盤中走勢", style=discord.ButtonStyle.primary, custom_id="btn_toggle")
    async def btn_toggle(self, interaction: discord.Interaction, button: Button):
        """切換歷史日線圖與盤中分時圖，並更新訊息"""
        await interaction.response.defer()

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

        self.is_history = not self.is_history
        button.style = discord.ButtonStyle.primary
        file = discord.File(io.BytesIO(file_bytes), filename=filename)
        
        embed = interaction.message.embeds[0] # pyright: ignore[reportOptionalMemberAccess]
        embed.set_image(url=f"attachment://{filename}")
        await interaction.message.edit(embed=embed, attachments=[file], view=self) # pyright: ignore[reportOptionalMemberAccess]