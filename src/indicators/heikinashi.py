"""
Heikin Ashi 蜡烛图指标
平滑价格波动，减少市场噪音
使用 TA-Lib 辅助函数优化计算
"""
import pandas as pd
import numpy as np
import talib
from typing import Optional


class HeikinAshi:
    """Heikin Ashi 指标计算类）"""
    
    @staticmethod
    def calculate(df: pd.DataFrame) -> pd.DataFrame:
        """
        计算 Heikin Ashi 蜡烛图
        使用 TA-Lib 优化计算
        
        Args:
            df: 包含 open, high, low, close 的 DataFrame
            
        Returns:
            包含 HA open, high, low, close 的 DataFrame
        """
        ha_df = pd.DataFrame(index=df.index)
        
        # HA Close = (O + H + L + C) / 4
        # 使用 TA-Lib AVGPRICE
        ha_close = talib.AVGPRICE(
            df['open'].values,
            df['high'].values,
            df['low'].values,
            df['close'].values
        )
        ha_df['close'] = pd.Series(ha_close, index=df.index)
        
        # HA Open 需要逐行计算
        ha_df['open'] = np.nan
        
        # 第一根蜡烛的 HA Open = (Open + Close) / 2
        ha_df.loc[ha_df.index[0], 'open'] = (
            df.loc[df.index[0], 'open'] + df.loc[df.index[0], 'close']
        ) / 2
        
        # 后续蜡烛的 HA Open = (前一根 HA Open + 前一根 HA Close) / 2
        for i in range(1, len(ha_df)):
            ha_df.iloc[i, ha_df.columns.get_loc('open')] = (
                ha_df.iloc[i-1, ha_df.columns.get_loc('open')] + 
                ha_df.iloc[i-1, ha_df.columns.get_loc('close')]
            ) / 2
        
        # HA High = max(H, HA Open, HA Close)
        ha_df['high'] = df[['high']].join(ha_df[['open', 'close']]).max(axis=1)
        
        # HA Low = min(L, HA Open, HA Close)
        ha_df['low'] = df[['low']].join(ha_df[['open', 'close']]).min(axis=1)
        
        return ha_df
    
    @staticmethod
    def is_bullish(ha_df: pd.DataFrame, index: int = -1) -> bool:
        """
        判断指定位置是否为看涨蜡烛（HA Close > HA Open）
        
        Args:
            ha_df: Heikin Ashi DataFrame
            index: 索引位置，默认为最后一根
            
        Returns:
            是否看涨
        """
        return ha_df['close'].iloc[index] > ha_df['open'].iloc[index]
    
    @staticmethod
    def is_bearish(ha_df: pd.DataFrame, index: int = -1) -> bool:
        """
        判断指定位置是否为看跌蜡烛（HA Close < HA Open）
        
        Args:
            ha_df: Heikin Ashi DataFrame
            index: 索引位置，默认为最后一根
            
        Returns:
            是否看跌
        """
        return ha_df['close'].iloc[index] < ha_df['open'].iloc[index]
    
    @staticmethod
    def detect_crossover(ha_df: pd.DataFrame) -> Optional[str]:
        """
        检测 HA Close 和 HA Open 的交叉
        
        Args:
            ha_df: Heikin Ashi DataFrame
            
        Returns:
            'BUY' - 上穿信号
            'SELL' - 下穿信号
            None - 无信号
        """
        if len(ha_df) < 2:
            return None
        
        current_close = ha_df['close'].iloc[-1]
        current_open = ha_df['open'].iloc[-1]
        prev_close = ha_df['close'].iloc[-2]
        prev_open = ha_df['open'].iloc[-2]
        
        # 上穿：前一根 close <= open，当前 close > open
        if prev_close <= prev_open and current_close > current_open:
            return 'BUY'
        
        # 下穿：前一根 close >= open，当前 close < open
        if prev_close >= prev_open and current_close < current_open:
            return 'SELL'
        
        return None

