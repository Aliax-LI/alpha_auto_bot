"""
技术指标计算
使用 TA-Lib 库实现，确保与行业标准一致
"""
import pandas as pd
import numpy as np
import talib
from typing import Union


class TechnicalIndicators:
    """技术指标计算类（使用 TA-Lib）"""
    
    @staticmethod
    def rsi(series: pd.Series, period: int = 14) -> pd.Series:
        """
        计算 RSI (Relative Strength Index)
        使用 TA-Lib 实现
        
        Args:
            series: 价格序列
            period: RSI 周期
            
        Returns:
            RSI 序列
        """
        rsi_values = talib.RSI(series.values, timeperiod=period)
        return pd.Series(rsi_values, index=series.index)
    
    @staticmethod
    def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
        """
        计算 ATR (Average True Range)
        使用 TA-Lib 实现（Wilder's smoothing）
        
        Args:
            df: 包含 high, low, close 的 DataFrame
            period: ATR 周期
            
        Returns:
            ATR 序列
        """
        atr_values = talib.ATR(
            df['high'].values,
            df['low'].values,
            df['close'].values,
            timeperiod=period
        )
        return pd.Series(atr_values, index=df.index)
    
    @staticmethod
    def ema(series: pd.Series, period: int) -> pd.Series:
        """
        计算 EMA (Exponential Moving Average)
        使用 TA-Lib 实现
        
        Args:
            series: 价格序列
            period: EMA 周期
            
        Returns:
            EMA 序列
        """
        ema_values = talib.EMA(series.values, timeperiod=period)
        return pd.Series(ema_values, index=series.index)
    
    @staticmethod
    def sma(series: pd.Series, period: int) -> pd.Series:
        """
        计算 SMA (Simple Moving Average)
        使用 TA-Lib 实现
        
        Args:
            series: 价格序列
            period: SMA 周期
            
        Returns:
            SMA 序列
        """
        sma_values = talib.SMA(series.values, timeperiod=period)
        return pd.Series(sma_values, index=series.index)
    
    @staticmethod
    def crossover(series1: pd.Series, series2: pd.Series) -> bool:
        """
        检测序列1是否上穿序列2
        
        Args:
            series1: 快线
            series2: 慢线
            
        Returns:
            是否上穿
        """
        if len(series1) < 2 or len(series2) < 2:
            return False
        
        return (series1.iloc[-2] <= series2.iloc[-2] and 
                series1.iloc[-1] > series2.iloc[-1])
    
    @staticmethod
    def crossunder(series1: pd.Series, series2: pd.Series) -> bool:
        """
        检测序列1是否下穿序列2
        
        Args:
            series1: 快线
            series2: 慢线
            
        Returns:
            是否下穿
        """
        if len(series1) < 2 or len(series2) < 2:
            return False
        
        return (series1.iloc[-2] >= series2.iloc[-2] and 
                series1.iloc[-1] < series2.iloc[-1])
    
    @staticmethod
    def truncate(number: float, decimals: int) -> float:
        """
        截断小数位数（不四舍五入）
        
        Args:
            number: 待截断的数字
            decimals: 保留的小数位数
            
        Returns:
            截断后的数字
        """
        factor = 10 ** decimals
        return int(number * factor) / factor

