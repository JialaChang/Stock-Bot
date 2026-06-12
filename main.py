"""
系統進入點 (Entry Point)
負責初始化環境設定、設定全域日誌格式，並啟動 Discord Bot 實例。
"""
import logging
from src.bot.dc_bot import bot, TOKEN

# 配置全域日誌統一輸出格式
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    try:
        logger.info("Starting system...")
        bot.run(TOKEN) # pyright: ignore[reportArgumentType]
    except Exception as e:
        logger.error(f"System Error : {e}")