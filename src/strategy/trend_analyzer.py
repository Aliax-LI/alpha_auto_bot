"""趋势分析模块"""
import pandas as pd
import numpy as np
from typing import Dict, List
from dataclasses import dataclass
from ..indicators.technical import technical_indicators
from ..monitor.logger import system_logger


@dataclass
class TrendInfo:
    """趋势信息类"""
    direction: str  # 'up', 'down', 'neutral'
    strength: float  # 0-1
    is_strong: bool
    details: Dict
    
    def __str__(self):
        return f"Trend(direction={self.direction}, strength={self.strength:.2f}, is_strong={self.is_strong})"


class TrendAnalyzer:
    """趋势分析类"""
    
    def __init__(self):
        """初始化"""
        self.indicators = technical_indicators
    
    def check_ema_alignment(self, df: pd.DataFrame) -> Dict:
        """
        检查EMA排列
        
        Args:
            df: K线数据（已包含EMA指标）
            
        Returns:
            EMA排列结果
        """
        if 'ema_9' not in df.columns or 'ema_21' not in df.columns or 'ema_50' not in df.columns:
            return {'aligned': False, 'direction': 'neutral'}
        
        ema_9 = df['ema_9'].iloc[-1]
        ema_21 = df['ema_21'].iloc[-1]
        ema_50 = df['ema_50'].iloc[-1]
        
        # 检查是否有效值
        if pd.isna(ema_9) or pd.isna(ema_21) or pd.isna(ema_50):
            return {'aligned': False, 'direction': 'neutral'}
        
        # 多头排列
        if ema_9 > ema_21 > ema_50:
            return {'aligned': True, 'direction': 'up'}
        
        # 空头排列
        elif ema_9 < ema_21 < ema_50:
            return {'aligned': True, 'direction': 'down'}
        
        else:
            return {'aligned': False, 'direction': 'neutral'}
    
    def check_macd_signal(self, df: pd.DataFrame) -> Dict:
        """
        检查MACD信号
        
        Args:
            df: K线数据（已包含MACD指标）
            
        Returns:
            MACD信号结果
        """
        if 'macd' not in df.columns or 'macd_signal' not in df.columns or 'macd_hist' not in df.columns:
            return {'signal': 'neutral'}
        
        macd = df['macd'].iloc[-1]
        signal = df['macd_signal'].iloc[-1]
        hist = df['macd_hist'].iloc[-1]
        
        if pd.isna(macd) or pd.isna(signal) or pd.isna(hist):
            return {'signal': 'neutral'}
        
        # 多头信号：MACD在零轴上方且柱状图为正
        if macd > 0 and hist > 0:
            return {'signal': 'bullish', 'strength': min(abs(hist) / abs(macd), 1)}
        
        # 空头信号：MACD在零轴下方且柱状图为负
        elif macd < 0 and hist < 0:
            return {'signal': 'bearish', 'strength': min(abs(hist) / abs(macd), 1)}
        
        else:
            return {'signal': 'neutral', 'strength': 0}
    
    def check_adx_strength(self, df: pd.DataFrame) -> Dict:
        """
        检查ADX趋势强度
        
        Args:
            df: K线数据（已包含ADX指标）
            
        Returns:
            ADX分析结果
        """
        if 'adx' not in df.columns or 'plus_di' not in df.columns or 'minus_di' not in df.columns:
            return {'strong_trend': False, 'direction': 'neutral'}
        
        adx = df['adx'].iloc[-1]
        plus_di = df['plus_di'].iloc[-1]
        minus_di = df['minus_di'].iloc[-1]
        
        if pd.isna(adx) or pd.isna(plus_di) or pd.isna(minus_di):
            return {'strong_trend': False, 'direction': 'neutral'}
        
        strong_trend = adx > 25
        
        if strong_trend:
            if plus_di > minus_di:
                direction = 'up'
            else:
                direction = 'down'
        else:
            direction = 'neutral'
        
        return {
            'strong_trend': strong_trend,
            'direction': direction,
            'adx': adx,
            'plus_di': plus_di,
            'minus_di': minus_di,
        }
    
    def check_supertrend(self, df: pd.DataFrame) -> Dict:
        """
        检查SuperTrend指标
        
        Args:
            df: K线数据（已包含SuperTrend指标）
            
        Returns:
            SuperTrend分析结果
        """
        if 'supertrend_direction' not in df.columns:
            return {'signal': 'neutral'}
        
        direction = df['supertrend_direction'].iloc[-1]
        
        if pd.isna(direction):
            return {'signal': 'neutral'}
        
        if direction == 1:
            return {'signal': 'bullish'}
        elif direction == -1:
            return {'signal': 'bearish'}
        else:
            return {'signal': 'neutral'}
    
    def check_volume_trend(self, df: pd.DataFrame) -> Dict:
        """
        检查成交量趋势
        
        Args:
            df: K线数据
            
        Returns:
            成交量分析结果
        """
        if len(df) < 3:
            return {'confirmation': False}
        
        # 获取最近3根K线
        recent = df.tail(3)
        
        # 计算上涨和下跌K线的成交量
        up_candles = recent[recent['close'] > recent['open']]
        down_candles = recent[recent['close'] < recent['open']]
        
        up_volume = up_candles['volume'].sum() if len(up_candles) > 0 else 0
        down_volume = down_candles['volume'].sum() if len(down_candles) > 0 else 0
        
        total_volume = up_volume + down_volume
        
        if total_volume == 0:
            return {'confirmation': False, 'direction': 'neutral'}
        
        # 上涨成交量占比
        up_ratio = up_volume / total_volume
        
        if up_ratio > 0.6:
            return {'confirmation': True, 'direction': 'up', 'ratio': up_ratio}
        elif up_ratio < 0.4:
            return {'confirmation': True, 'direction': 'down', 'ratio': 1 - up_ratio}
        else:
            return {'confirmation': False, 'direction': 'neutral', 'ratio': up_ratio}
    
    def analyze_single_timeframe(self, df: pd.DataFrame, timeframe: str) -> Dict:
        """
        分析单个时间周期
        
        Args:
            df: K线数据
            timeframe: 时间周期
            
        Returns:
            分析结果
        """
        if df.empty or len(df) < 50:
            return {'direction': 'neutral', 'strength': 0}
        
        # 计算所有指标
        df = self.indicators.calculate_all_indicators(df)
        
        # 检查各项指标
        ema_result = self.check_ema_alignment(df)
        macd_result = self.check_macd_signal(df)
        adx_result = self.check_adx_strength(df)
        supertrend_result = self.check_supertrend(df)
        volume_result = self.check_volume_trend(df)
        
        # 综合评分
        score = 0
        confirmations = 0
        
        # EMA排列
        if ema_result['aligned']:
            confirmations += 1
            score += 2 if ema_result['direction'] == 'up' else -2
        
        # MACD
        if macd_result['signal'] == 'bullish':
            confirmations += 1
            score += 2
        elif macd_result['signal'] == 'bearish':
            confirmations += 1
            score -= 2
        
        # ADX
        if adx_result['strong_trend']:
            confirmations += 1
            score += 2 if adx_result['direction'] == 'up' else -2
        
        # SuperTrend
        if supertrend_result['signal'] == 'bullish':
            confirmations += 1
            score += 1
        elif supertrend_result['signal'] == 'bearish':
            confirmations += 1
            score -= 1
        
        # 成交量
        if volume_result['confirmation']:
            confirmations += 1
            score += 1 if volume_result['direction'] == 'up' else -1
        
        # 判断趋势方向
        if score >= 4:
            direction = 'up'
        elif score <= -4:
            direction = 'down'
        else:
            direction = 'neutral'
        
        # 计算强度（0-1）
        strength = min(abs(score) / 8, 1)
        
        return {
            'timeframe': timeframe,
            'direction': direction,
            'strength': strength,
            'score': score,
            'confirmations': confirmations,
            'ema': ema_result,
            'macd': macd_result,
            'adx': adx_result,
            'supertrend': supertrend_result,
            'volume': volume_result,
        }
    
    def analyze_multi_timeframe(self, 
                                data_5m: pd.DataFrame,
                                data_15m: pd.DataFrame,
                                data_1h: pd.DataFrame) -> TrendInfo:
        """
        多周期趋势分析
        
        Args:
            data_5m: 5分钟数据
            data_15m: 15分钟数据
            data_1h: 1小时数据
            
        Returns:
            趋势信息
        """
        # 分析各周期
        result_5m = self.analyze_single_timeframe(data_5m, '5m')
        result_15m = self.analyze_single_timeframe(data_15m, '15m')
        result_1h = self.analyze_single_timeframe(data_1h, '1h')
        
        # 检查共振
        directions = [result_5m['direction'], result_15m['direction'], result_1h['direction']]
        
        # 三周期共振
        if directions.count('up') >= 2:
            direction = 'up'
            resonance = directions.count('up')
        elif directions.count('down') >= 2:
            direction = 'down'
            resonance = directions.count('down')
        else:
            direction = 'neutral'
            resonance = 0
        
        # 计算综合强度（主要看5分钟周期，参考其他周期）
        strength = (result_5m['strength'] * 0.5 + 
                   result_15m['strength'] * 0.3 + 
                   result_1h['strength'] * 0.2)
        
        # 判断是否强趋势
        is_strong = (resonance >= 2 and 
                    result_5m['confirmations'] >= 3 and 
                    strength >= 0.6)
        
        details = {
            '5m': result_5m,
            '15m': result_15m,
            '1h': result_1h,
            'resonance': resonance,
        }
        
        return TrendInfo(
            direction=direction,
            strength=strength,
            is_strong=is_strong,
            details=details
        )
    
    def analyze(self, 
                data_5m: pd.DataFrame,
                data_15m: pd.DataFrame,
                data_1h: pd.DataFrame) -> TrendInfo:
        """
        分析趋势（对外接口）
        
        Args:
            data_5m: 5分钟数据
            data_15m: 15分钟数据
            data_1h: 1小时数据
            
        Returns:
            趋势信息
        """
        return self.analyze_multi_timeframe(data_5m, data_15m, data_1h)


# 全局趋势分析器实例
trend_analyzer = TrendAnalyzer()

