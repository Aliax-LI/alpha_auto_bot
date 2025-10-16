"""TA-Lib技术指标封装"""
import pandas as pd
import numpy as np
import talib
from typing import Dict, Tuple
from ..utils.config import config
from ..monitor.logger import system_logger


class TechnicalIndicators:
    """技术指标计算类"""
    
    def __init__(self):
        """初始化"""
        self.indicator_config = config.get_indicator_config()
    
    def calculate_ema(self, df: pd.DataFrame, periods: list = None) -> pd.DataFrame:
        """
        计算EMA指标
        
        Args:
            df: K线数据
            periods: EMA周期列表
            
        Returns:
            添加了EMA列的DataFrame
        """
        if periods is None:
            periods = self.indicator_config.get('ema_periods', [9, 21, 50])
        
        for period in periods:
            df[f'ema_{period}'] = talib.EMA(df['close'], timeperiod=period)
        
        return df
    
    def calculate_macd(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        计算MACD指标
        
        Args:
            df: K线数据
            
        Returns:
            添加了MACD列的DataFrame
        """
        params = self.indicator_config.get('macd_params', [12, 26, 9])
        
        macd, signal, hist = talib.MACD(
            df['close'],
            fastperiod=params[0],
            slowperiod=params[1],
            signalperiod=params[2]
        )
        
        df['macd'] = macd
        df['macd_signal'] = signal
        df['macd_hist'] = hist
        
        return df
    
    def calculate_rsi(self, df: pd.DataFrame, period: int = None) -> pd.DataFrame:
        """
        计算RSI指标
        
        Args:
            df: K线数据
            period: RSI周期
            
        Returns:
            添加了RSI列的DataFrame
        """
        if period is None:
            period = self.indicator_config.get('rsi_period', 14)
        
        df['rsi'] = talib.RSI(df['close'], timeperiod=period)
        
        return df
    
    def calculate_stochastic(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        计算KDJ指标（随机指标）
        
        Args:
            df: K线数据
            
        Returns:
            添加了KDJ列的DataFrame
        """
        params = self.indicator_config.get('kdj_params', [9, 3, 3])
        
        k, d = talib.STOCH(
            df['high'],
            df['low'],
            df['close'],
            fastk_period=params[0],
            slowk_period=params[1],
            slowd_period=params[2]
        )
        
        df['kdj_k'] = k
        df['kdj_d'] = d
        df['kdj_j'] = 3 * k - 2 * d  # J = 3K - 2D
        
        return df
    
    def calculate_adx(self, df: pd.DataFrame, period: int = None) -> pd.DataFrame:
        """
        计算ADX指标
        
        Args:
            df: K线数据
            period: ADX周期
            
        Returns:
            添加了ADX列的DataFrame
        """
        if period is None:
            period = self.indicator_config.get('adx_period', 14)
        
        df['adx'] = talib.ADX(df['high'], df['low'], df['close'], timeperiod=period)
        df['plus_di'] = talib.PLUS_DI(df['high'], df['low'], df['close'], timeperiod=period)
        df['minus_di'] = talib.MINUS_DI(df['high'], df['low'], df['close'], timeperiod=period)
        
        return df
    
    def calculate_atr(self, df: pd.DataFrame, period: int = None) -> pd.DataFrame:
        """
        计算ATR指标
        
        Args:
            df: K线数据
            period: ATR周期
            
        Returns:
            添加了ATR列的DataFrame
        """
        if period is None:
            period = self.indicator_config.get('atr_period', 14)
        
        df['atr'] = talib.ATR(df['high'], df['low'], df['close'], timeperiod=period)
        
        return df
    
    def calculate_bollinger_bands(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        计算布林带指标
        
        Args:
            df: K线数据
            
        Returns:
            添加了布林带列的DataFrame
        """
        params = self.indicator_config.get('bb_params', [20, 2])
        
        upper, middle, lower = talib.BBANDS(
            df['close'],
            timeperiod=params[0],
            nbdevup=params[1],
            nbdevdn=params[1]
        )
        
        df['bb_upper'] = upper
        df['bb_middle'] = middle
        df['bb_lower'] = lower
        
        return df
    
    def calculate_supertrend(self, df: pd.DataFrame, period: int = 10, multiplier: float = 3) -> pd.DataFrame:
        """
        计算SuperTrend指标
        
        Args:
            df: K线数据
            period: ATR周期
            multiplier: ATR乘数
            
        Returns:
            添加了SuperTrend列的DataFrame
        """
        # 计算ATR
        atr = talib.ATR(df['high'], df['low'], df['close'], timeperiod=period)
        
        # 计算基本上下轨
        hl2 = (df['high'] + df['low']) / 2
        basic_upper = hl2 + multiplier * atr
        basic_lower = hl2 - multiplier * atr
        
        # 初始化
        supertrend = pd.Series(index=df.index, dtype=float)
        direction = pd.Series(index=df.index, dtype=int)
        
        # 计算SuperTrend
        for i in range(period, len(df)):
            if i == period:
                supertrend.iloc[i] = basic_lower.iloc[i]
                direction.iloc[i] = 1
            else:
                # 上升趋势
                if direction.iloc[i-1] == 1:
                    if df['close'].iloc[i] <= supertrend.iloc[i-1]:
                        supertrend.iloc[i] = basic_upper.iloc[i]
                        direction.iloc[i] = -1
                    else:
                        supertrend.iloc[i] = max(basic_lower.iloc[i], supertrend.iloc[i-1])
                        direction.iloc[i] = 1
                # 下降趋势
                else:
                    if df['close'].iloc[i] >= supertrend.iloc[i-1]:
                        supertrend.iloc[i] = basic_lower.iloc[i]
                        direction.iloc[i] = 1
                    else:
                        supertrend.iloc[i] = min(basic_upper.iloc[i], supertrend.iloc[i-1])
                        direction.iloc[i] = -1
        
        df['supertrend'] = supertrend
        df['supertrend_direction'] = direction
        
        return df
    
    def calculate_obv(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        计算OBV指标
        
        Args:
            df: K线数据
            
        Returns:
            添加了OBV列的DataFrame
        """
        df['obv'] = talib.OBV(df['close'], df['volume'])
        
        return df
    
    def calculate_volume_sma(self, df: pd.DataFrame, period: int = None) -> pd.DataFrame:
        """
        计算成交量均线
        
        Args:
            df: K线数据
            period: 周期
            
        Returns:
            添加了成交量均线的DataFrame
        """
        if period is None:
            period = self.indicator_config.get('volume_sma_period', 20)
        
        df['volume_sma'] = talib.SMA(df['volume'], timeperiod=period)
        
        return df
    
    def identify_candlestick_patterns(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        识别K线形态
        
        Args:
            df: K线数据
            
        Returns:
            添加了形态识别列的DataFrame
        """
        # 看涨形态
        df['pattern_hammer'] = talib.CDLHAMMER(df['open'], df['high'], df['low'], df['close'])
        df['pattern_engulfing'] = talib.CDLENGULFING(df['open'], df['high'], df['low'], df['close'])
        df['pattern_morning_star'] = talib.CDLMORNINGSTAR(df['open'], df['high'], df['low'], df['close'])
        df['pattern_piercing'] = talib.CDLPIERCING(df['open'], df['high'], df['low'], df['close'])
        
        # 看跌形态
        df['pattern_shooting_star'] = talib.CDLSHOOTINGSTAR(df['open'], df['high'], df['low'], df['close'])
        df['pattern_hanging_man'] = talib.CDLHANGINGMAN(df['open'], df['high'], df['low'], df['close'])
        df['pattern_evening_star'] = talib.CDLEVENINGSTAR(df['open'], df['high'], df['low'], df['close'])
        
        return df
    
    def calculate_all_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        计算所有技术指标
        
        Args:
            df: K线数据
            
        Returns:
            添加了所有指标的DataFrame
        """
        if df.empty or len(df) < 50:
            system_logger.warning("Insufficient data for indicator calculation")
            return df
        
        try:
            df = self.calculate_ema(df)
            df = self.calculate_macd(df)
            df = self.calculate_rsi(df)
            df = self.calculate_stochastic(df)
            df = self.calculate_adx(df)
            df = self.calculate_atr(df)
            df = self.calculate_bollinger_bands(df)
            df = self.calculate_supertrend(df)
            df = self.calculate_obv(df)
            df = self.calculate_volume_sma(df)
            df = self.identify_candlestick_patterns(df)
            
            return df
        
        except Exception as e:
            system_logger.error(f"Error calculating indicators: {e}")
            return df


# 全局技术指标实例
technical_indicators = TechnicalIndicators()

