import mplfinance as mpf
import pandas as pd
import io
import matplotlib
import matplotlib.pyplot as plt

# 將圖表輸出成檔案
matplotlib.use('Agg')

class StockVisualizer:
    @staticmethod
    def generate_chart(ticker: str, data: pd.DataFrame, days: int  = 28) -> io.BytesIO:
        """根據 DataFrame 繪製 K 線與均線圖，並回傳 BytesIO 記憶體緩衝區"""
        print(f"[{ticker}] 準備畫圖，最後 3 筆資料日期為：\n", data.tail(3))
        # 直接使用在 analyzer 算好的 data
        plot_data = data.iloc[-days:]

        addplot = [
            mpf.make_addplot(plot_data['MA5'], color="#FFA41C", width=1, label='5MA'),
            mpf.make_addplot(plot_data['MA10'], color="#05B3F3", width=1, label='10MA'),
            mpf.make_addplot(plot_data['MA20'], color="#A137E4", width=1, label='20MA')
        ]
        color = mpf.make_marketcolors(
            # price
            up='red',
            down='green',
            edge='inherit',
            wick='inherit',
            # volume
            volume='#87ceeb',
        )
        style = mpf.make_mpf_style(marketcolors=color, gridstyle='--')

        # 取得一塊記憶體空間
        buffer = io.BytesIO()

        mpf.plot(
            plot_data,
            type='candle',
            addplot=addplot,
            style=style,
            title=f"\n{ticker}",
            show_nontrading=False,

            volume=True,
            volume_alpha=0.3,
            panel_ratios=(3, 1),

            savefig=buffer
        )
        # 將記憶體指標指向起始位置
        buffer.seek(0)
        # 釋放記憶體
        plt.close('all')
        return buffer
