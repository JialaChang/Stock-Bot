"""
系統進入點 (Entry Point)
負責初始化環境設定、設定全域日誌格式
"""
import logging

# 配置全域日誌統一輸出格式
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    pass