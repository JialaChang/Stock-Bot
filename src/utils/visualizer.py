import mplfinance as mpf
import pandas as pd
import io
import matplotlib
import matplotlib.pyplot as plt

# 關閉 GUI 互動模式，強制將 Matplotlib 渲染後端設為 'Agg'，適用於伺服器端純生成圖片
matplotlib.use('Agg')

class StockVisualizer:
    """負責股票資料視覺化的靜態工具類，封裝 mplfinance 的繪圖邏輯"""
    MARKET_COLORS = mpf.make_marketcolors(
        up='red',
        down='green',
        edge='inherit',
        wick='inherit',
        volume='#87ceeb',
    )
    MPF_STYLE = mpf.make_mpf_style(marketcolors=MARKET_COLORS, gridstyle='--')

    @classmethod
    def generate_history_chart(cls, ticker: str, data: pd.DataFrame, days: int = 61) -> io.BytesIO:
        """生成歷史日線 K 線圖 (包含均線與成交量)，回傳記憶體緩衝區以供 Discord 直接讀取"""
        # 裁切指定天數的資料進行渲染
        plot_data = data.iloc[-days:]

        # 建立移動平均線 (MA) 的覆蓋圖層
        addplot = [
            mpf.make_addplot(plot_data['MA5'], color="#FFA41C", width=1, label='5MA'),
            mpf.make_addplot(plot_data['MA10'], color="#05B3F3", width=1, label='10MA'),
            mpf.make_addplot(plot_data['MA20'], color="#A137E4", width=1, label='20MA')
        ]

        # 宣告記憶體流，避免將圖片寫入實體硬碟
        buffer = io.BytesIO()

        mpf.plot(
            plot_data,
            type='candle',
            addplot=addplot,
            style=cls.MPF_STYLE,
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
        # 將指標撥回起點以讀取
        buffer.seek(0)
        plt.close('all')
        return buffer
    
    @classmethod
    def generate_intraday_chart(cls, ticker: str, data: pd.DataFrame) -> io.BytesIO:
        """生成盤中分時折線圖，利用紅綠分色顯示相對於開盤價的漲跌勢"""
        # 提取開盤價
        open_price = data['Open'].iloc[0]
        
        # 分離高於與低於開盤價的數據
        above_open = data['Close'].where(data['Close'] >= open_price)
        below_open = data['Close'].where(data['Close'] < open_price)
        
        # 建立開盤價參考線與紅綠分段線
        ref_line = pd.Series(open_price, index=data.index)
        addplot = [mpf.make_addplot(ref_line, color='#a0a0a0', linestyle='dotted', width=2)]
        
        # 動態掛載紅綠折線圖層
        if above_open.notna().any():
            addplot.append(mpf.make_addplot(above_open, color='#e74c3c', width=1))
        if below_open.notna().any():
            addplot.append(mpf.make_addplot(below_open, color='#2ecc71', width=1))
        
        # 設定相對於基準價的半透明區域填滿效果
        fills = [
            dict(y1=data['Close'].values, y2=open_price, where=(data['Close'] >= open_price).values, color='#e74c3c', alpha=0.1),
            dict(y1=data['Close'].values, y2=open_price, where=(data['Close'] < open_price).values, color='#2ecc71', alpha=0.1)
        ]

        buffer = io.BytesIO()

        mpf.plot(
            data,
            type='line',
            linecolor='#555555',
            addplot=addplot,
            fill_between=fills,
            style=cls.MPF_STYLE,
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