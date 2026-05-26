import mplfinance as mpf
import pandas as pd
import io
import matplotlib
import matplotlib.pyplot as plt

# 將圖表輸出成檔案
matplotlib.use('Agg')

class StockVisualizer:
    @staticmethod
    def generate_history_chart(ticker: str, data: pd.DataFrame, days: int  = 61) -> io.BytesIO:
        """根據 DataFrame 繪製 K 線與均線圖，並回傳 BytesIO 記憶體緩衝區"""
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
            datetime_format='%m/%d',
            tight_layout=True,
            xrotation=0,

            volume=True,
            volume_alpha=0.3,
            panel_ratios=(4, 1),

            savefig=buffer
        )
        # 將記憶體指標指向起始位置
        buffer.seek(0)
        # 釋放記憶體
        plt.close('all')
        return buffer
    
    @staticmethod
    def generate_intraday_chart(ticker: str, data: pd.DataFrame) -> io.BytesIO:
        """根據 DataFrame 繪製當日分時走勢折線圖"""
        # 取得開盤價作為判斷基準
        open_price = data['Open'].iloc[0]
        
        # 分離高於與低於開盤價的數據
        above_open = data['Close'].where(data['Close'] >= open_price)
        below_open = data['Close'].where(data['Close'] < open_price)
        
        # 建立開盤價參考線與紅綠分段線
        ref_line = pd.Series(open_price, index=data.index)
        addplot = [mpf.make_addplot(ref_line, color='#a0a0a0', linestyle='dotted', width=2)]
        
        # 檢查數據再加入繪圖陣列
        # 避免一路漲或跌的情況報錯
        if above_open.notna().any():
            addplot.append(mpf.make_addplot(above_open, color='#e74c3c', width=1))
        if below_open.notna().any():
            addplot.append(mpf.make_addplot(below_open, color='#2ecc71', width=1))
        
        # 設定紅綠色的半透明填滿面積
        fills = [
            dict(y1=data['Close'].values, y2=open_price, where=(data['Close'] >= open_price).values, color='#e74c3c', alpha=0.1),
            dict(y1=data['Close'].values, y2=open_price, where=(data['Close'] <= open_price).values, color='#2ecc71', alpha=0.1)
        ]

        # 設定樣式
        color = mpf.make_marketcolors(up='red', down='green', edge='inherit', wick='inherit', volume='#87ceeb')
        style = mpf.make_mpf_style(marketcolors=color, gridstyle='--')

        buffer = io.BytesIO()

        mpf.plot(
            data,
            type='line',
            linecolor='#555555',
            addplot=addplot,
            fill_between=fills,
            style=style,
            title=f"\n{ticker}",
            datetime_format='%H:%M',
            tight_layout=True,
            xrotation=0,
            
            volume=True,
            volume_alpha=0.3,
            panel_ratios=(4, 1),
            savefig=buffer
        )
        
        buffer.seek(0)
        plt.close('all')
        return buffer