"""交易信号生成模块"""
import pandas as pd
import numpy as np
from typing import Dict, Optional
from dataclasses import dataclass
from enum import Enum
from ..indicators.support_resistance import support_resistance
from ..indicators.order_flow import order_flow_analyzer
from ..utils.config import config
from ..monitor.logger import system_logger, TradingLogger


class EntryMode(Enum):
    """入场模式枚举"""
    PULLBACK = "pullback"  # 回调入场（原模式）：趋势中的健康回撤
    BREAKOUT = "breakout"  # 突破入场：趋势初期突破关键位
    TREND_FOLLOWING = "trend_following"  # 趋势跟随：强趋势中顺势入场
    REBOUND = "rebound"  # 反弹入场：超卖/超买后的反弹


@dataclass
class TradingSignal:
    """交易信号类"""
    symbol: str
    signal_type: str  # 'long' or 'short'
    score: float
    entry_price: float
    stop_loss: float
    take_profit: float
    score_details: Dict
    entry_mode: str = None  # 入场模式
    support_level: float = None
    resistance_level: float = None
    
    def __str__(self):
        mode_str = f" mode={self.entry_mode}" if self.entry_mode else ""
        return f"Signal({self.symbol} {self.signal_type}{mode_str} score={self.score:.1f})"


class SignalGenerator:
    """信号生成器类"""
    
    def __init__(self):
        """初始化"""
        self.config = config.get_signal_config()
        self.risk_config = config.get_risk_config()
        self.sr = support_resistance
        self.order_flow = order_flow_analyzer
    
    def detect_entry_mode(self, df: pd.DataFrame, trend_info) -> EntryMode:
        """
        检测当前适合的入场模式
        
        Args:
            df: K线数据
            trend_info: 趋势信息
            
        Returns:
            入场模式
        """
        if 'rsi' not in df.columns:
            return EntryMode.PULLBACK
        
        rsi = df['rsi'].iloc[-1]
        adx = df['adx'].iloc[-1] if 'adx' in df.columns else 0
        current_price = df['close'].iloc[-1]
        
        # 1. 反弹入场：RSI超卖/超买
        if trend_info.direction == 'down' and rsi < 30:
            # 下跌超卖，等待反弹做多
            return EntryMode.REBOUND
        elif trend_info.direction == 'up' and rsi > 70:
            # 上涨超买，等待回落做空
            return EntryMode.REBOUND
        
        # 2. 趋势跟随：强趋势且RSI在中性区或顺势区
        if adx > 30:
            if trend_info.direction == 'down' and 40 <= rsi <= 60:
                # 强势下跌，RSI中性，可顺势做空
                return EntryMode.TREND_FOLLOWING
            elif trend_info.direction == 'up' and 40 <= rsi <= 60:
                # 强势上涨，RSI中性，可顺势做多
                return EntryMode.TREND_FOLLOWING
        
        # 3. 突破入场：价格突破关键位
        sr_levels = self.sr.get_nearest_support_resistance(df, current_price)
        if sr_levels:
            nearest_resistance = sr_levels.get('nearest_resistance', float('inf'))
            nearest_support = sr_levels.get('nearest_support', 0)
            
            # 突破阻力位（做多）
            if trend_info.direction == 'up' and nearest_resistance:
                if current_price >= nearest_resistance * 0.999:  # 接近或突破阻力
                    return EntryMode.BREAKOUT
            
            # 突破支撑位（做空）
            elif trend_info.direction == 'down' and nearest_support:
                if current_price <= nearest_support * 1.001:  # 接近或突破支撑
                    return EntryMode.BREAKOUT
        
        # 4. 默认：回调入场
        return EntryMode.PULLBACK
    
    def check_fibonacci_pullback(self, df: pd.DataFrame, trend_direction: str) -> Dict:
        """
        检查斐波那契回撤
        
        Args:
            df: K线数据
            trend_direction: 趋势方向
            
        Returns:
            回撤分析结果
        """
        fib_levels = self.sr.calculate_fibonacci_retracement(df)
        
        if not fib_levels or fib_levels.get('trend') == 'neutral':
            return {'valid': False, 'score': 0}
        
        current_price = df['close'].iloc[-1]
        
        # 检查是否在关键回撤位附近（±1%容差）
        tolerance = 0.01
        at_fibonacci = False
        fib_level = None
        
        for level_name in ['level_382', 'level_500', 'level_618']:
            level = fib_levels.get(level_name)
            if level and abs(current_price - level) / level <= tolerance:
                at_fibonacci = True
                fib_level = level
                break
        
        # 判断回撤是否与趋势一致
        if trend_direction == 'up' and fib_levels.get('trend') == 'up' and at_fibonacci:
            return {'valid': True, 'score': 2, 'level': fib_level, 'type': level_name}
        elif trend_direction == 'down' and fib_levels.get('trend') == 'down' and at_fibonacci:
            return {'valid': True, 'score': 2, 'level': fib_level, 'type': level_name}
        
        return {'valid': False, 'score': 0}
    
    def check_support_resistance_touch(self, df: pd.DataFrame, trend_direction: str) -> Dict:
        """
        检查是否触及支撑/阻力位
        
        Args:
            df: K线数据
            trend_direction: 趋势方向
            
        Returns:
            分析结果
        """
        current_price = df['close'].iloc[-1]
        sr_levels = self.sr.get_nearest_support_resistance(df, current_price)
        
        tolerance = 0.005  # 0.5%容差
        
        # 上升趋势检查支撑位
        if trend_direction == 'up':
            nearest_support = sr_levels.get('nearest_support')
            if nearest_support and abs(current_price - nearest_support) / nearest_support <= tolerance:
                return {'valid': True, 'score': 2, 'level': nearest_support, 'type': 'support'}
        
        # 下降趋势检查阻力位
        elif trend_direction == 'down':
            nearest_resistance = sr_levels.get('nearest_resistance')
            if nearest_resistance and abs(current_price - nearest_resistance) / nearest_resistance <= tolerance:
                return {'valid': True, 'score': 2, 'level': nearest_resistance, 'type': 'resistance'}
        
        return {'valid': False, 'score': 0}
    
    def check_rsi_condition(self, df: pd.DataFrame, trend_direction: str) -> Dict:
        """
        检查RSI条件
        
        Args:
            df: K线数据（已包含RSI）
            trend_direction: 趋势方向
            
        Returns:
            RSI分析结果
        """
        if 'rsi' not in df.columns or len(df) < 2:
            return {'valid': False, 'score': 0}
        
        rsi_current = df['rsi'].iloc[-1]
        rsi_prev = df['rsi'].iloc[-2]
        
        if pd.isna(rsi_current) or pd.isna(rsi_prev):
            return {'valid': False, 'score': 0}
        
        # 上升趋势：RSI从超卖区反弹
        if trend_direction == 'up':
            if 30 <= rsi_current <= 45 and rsi_current > rsi_prev:
                return {'valid': True, 'score': 1, 'rsi': rsi_current}
        
        # 下降趋势：RSI从超买区回落
        elif trend_direction == 'down':
            if 55 <= rsi_current <= 70 and rsi_current < rsi_prev:
                return {'valid': True, 'score': 1, 'rsi': rsi_current}
        
        return {'valid': False, 'score': 0}
    
    def check_kdj_crossover(self, df: pd.DataFrame, trend_direction: str) -> Dict:
        """
        检查KDJ金叉/死叉
        
        Args:
            df: K线数据（已包含KDJ）
            trend_direction: 趋势方向
            
        Returns:
            KDJ分析结果
        """
        if 'kdj_k' not in df.columns or 'kdj_d' not in df.columns or len(df) < 2:
            return {'valid': False, 'score': 0}
        
        k_current = df['kdj_k'].iloc[-1]
        d_current = df['kdj_d'].iloc[-1]
        k_prev = df['kdj_k'].iloc[-2]
        d_prev = df['kdj_d'].iloc[-2]
        
        if any(pd.isna(x) for x in [k_current, d_current, k_prev, d_prev]):
            return {'valid': False, 'score': 0}
        
        # 上升趋势：低位金叉
        if trend_direction == 'up':
            if k_prev < d_prev and k_current > d_current and k_current < 30:
                return {'valid': True, 'score': 1, 'k': k_current, 'd': d_current}
        
        # 下降趋势：高位死叉
        elif trend_direction == 'down':
            if k_prev > d_prev and k_current < d_current and k_current > 70:
                return {'valid': True, 'score': 1, 'k': k_current, 'd': d_current}
        
        return {'valid': False, 'score': 0}
    
    def check_macd_convergence(self, df: pd.DataFrame, trend_direction: str) -> Dict:
        """
        检查MACD收敛（柱状图缩短）
        
        Args:
            df: K线数据（已包含MACD）
            trend_direction: 趋势方向
            
        Returns:
            MACD分析结果
        """
        if 'macd_hist' not in df.columns or len(df) < 3:
            return {'valid': False, 'score': 0}
        
        hist_current = df['macd_hist'].iloc[-1]
        hist_prev = df['macd_hist'].iloc[-2]
        hist_prev2 = df['macd_hist'].iloc[-3]
        
        if any(pd.isna(x) for x in [hist_current, hist_prev, hist_prev2]):
            return {'valid': False, 'score': 0}
        
        # 上升趋势：负柱状图缩短（即将金叉）
        if trend_direction == 'up':
            if hist_current < 0 and abs(hist_current) < abs(hist_prev) < abs(hist_prev2):
                return {'valid': True, 'score': 1, 'hist': hist_current}
        
        # 下降趋势：正柱状图缩短（即将死叉）
        elif trend_direction == 'down':
            if hist_current > 0 and abs(hist_current) < abs(hist_prev) < abs(hist_prev2):
                return {'valid': True, 'score': 1, 'hist': hist_current}
        
        return {'valid': False, 'score': 0}
    
    def check_candlestick_pattern(self, df: pd.DataFrame, trend_direction: str) -> Dict:
        """
        检查K线形态
        
        Args:
            df: K线数据（已包含形态识别）
            trend_direction: 趋势方向
            
        Returns:
            形态分析结果
        """
        # 看涨形态
        bullish_patterns = ['pattern_hammer', 'pattern_engulfing', 'pattern_morning_star', 'pattern_piercing']
        # 看跌形态
        bearish_patterns = ['pattern_shooting_star', 'pattern_hanging_man', 'pattern_evening_star']
        
        # 检查最近2根K线
        for i in [-1, -2]:
            if trend_direction == 'up':
                for pattern in bullish_patterns:
                    if pattern in df.columns and df[pattern].iloc[i] > 0:
                        return {'valid': True, 'score': 2, 'pattern': pattern}
            
            elif trend_direction == 'down':
                for pattern in bearish_patterns:
                    if pattern in df.columns and df[pattern].iloc[i] < 0:
                        return {'valid': True, 'score': 2, 'pattern': pattern}
        
        return {'valid': False, 'score': 0}
    
    def check_volume_confirmation(self, df: pd.DataFrame, trend_direction: str) -> Dict:
        """
        检查成交量确认
        
        Args:
            df: K线数据（已包含成交量指标）
            trend_direction: 趋势方向
            
        Returns:
            成交量分析结果
        """
        if len(df) < 5:
            return {'valid': False, 'score': 0}
        
        # 检查最近5根K线
        recent = df.tail(5)
        
        # 计算平均成交量
        avg_volume = recent['volume'].mean()
        current_volume = recent['volume'].iloc[-1]
        
        # 判断K线方向
        current_candle_up = recent['close'].iloc[-1] > recent['open'].iloc[-1]
        
        # 上升趋势：最新K线上涨且成交量放大
        if trend_direction == 'up':
            if current_candle_up and current_volume > avg_volume * 1.2:
                return {'valid': True, 'score': 2, 'volume_ratio': current_volume / avg_volume}
        
        # 下降趋势：最新K线下跌且成交量放大
        elif trend_direction == 'down':
            if not current_candle_up and current_volume > avg_volume * 1.2:
                return {'valid': True, 'score': 2, 'volume_ratio': current_volume / avg_volume}
        
        return {'valid': False, 'score': 0}
    
    def check_bollinger_bounce(self, df: pd.DataFrame, trend_direction: str) -> Dict:
        """
        检查布林带支撑/阻力
        
        Args:
            df: K线数据（已包含布林带）
            trend_direction: 趋势方向
            
        Returns:
            布林带分析结果
        """
        if 'bb_lower' not in df.columns or 'bb_upper' not in df.columns:
            return {'valid': False, 'score': 0}
        
        current_price = df['close'].iloc[-1]
        bb_lower = df['bb_lower'].iloc[-1]
        bb_upper = df['bb_upper'].iloc[-1]
        
        if any(pd.isna(x) for x in [current_price, bb_lower, bb_upper]):
            return {'valid': False, 'score': 0}
        
        tolerance = 0.005  # 0.5%
        
        # 上升趋势：触及下轨
        if trend_direction == 'up':
            if abs(current_price - bb_lower) / bb_lower <= tolerance:
                return {'valid': True, 'score': 1, 'level': bb_lower}
        
        # 下降趋势：触及上轨
        elif trend_direction == 'down':
            if abs(current_price - bb_upper) / bb_upper <= tolerance:
                return {'valid': True, 'score': 1, 'level': bb_upper}
        
        return {'valid': False, 'score': 0}
    
    def score_rebound_entry(self, df: pd.DataFrame, trend_direction: str) -> Dict:
        """
        反弹入场模式评分（超卖/超买反弹）
        
        Args:
            df: K线数据
            trend_direction: 趋势方向
            
        Returns:
            评分结果
        """
        score_details = {}
        total_score = 0
        
        rsi = df['rsi'].iloc[-1] if 'rsi' in df.columns else 50
        rsi_prev = df['rsi'].iloc[-2] if 'rsi' in df.columns and len(df) > 1 else 50
        
        # 反弹入场是反向交易，trend_direction是原趋势
        # 下跌超卖 -> 做多反弹
        if trend_direction == 'down':
            # 1. RSI反弹（4分）
            if rsi < 30 and rsi > rsi_prev:
                score_details['rsi_bounce'] = {'valid': True, 'score': 4, 'rsi': rsi}
                total_score += 4
            elif rsi < 30:
                score_details['rsi_bounce'] = {'valid': False, 'score': 0, 'rsi': rsi, 'reason': 'RSI未反弹'}
            
            # 2. KDJ低位金叉（3分）
            if 'kdj_k' in df.columns and 'kdj_d' in df.columns and len(df) > 1:
                k = df['kdj_k'].iloc[-1]
                d = df['kdj_d'].iloc[-1]
                k_prev = df['kdj_k'].iloc[-2]
                d_prev = df['kdj_d'].iloc[-2]
                
                if k_prev < d_prev and k > d and k < 30:
                    score_details['kdj'] = {'valid': True, 'score': 3, 'k': k, 'd': d}
                    total_score += 3
                else:
                    score_details['kdj'] = {'valid': False, 'score': 0}
            
            # 3. 看涨K线形态（3分）
            bullish_patterns = ['pattern_hammer', 'pattern_engulfing', 'pattern_morning_star']
            for pattern in bullish_patterns:
                if pattern in df.columns and df[pattern].iloc[-1] > 0:
                    score_details['pattern'] = {'valid': True, 'score': 3, 'pattern': pattern}
                    total_score += 3
                    break
        
        # 上涨超买 -> 做空回落
        else:  # trend_direction == 'up'
            # 1. RSI回落（4分）
            if rsi > 70 and rsi < rsi_prev:
                score_details['rsi_drop'] = {'valid': True, 'score': 4, 'rsi': rsi}
                total_score += 4
            elif rsi > 70:
                score_details['rsi_drop'] = {'valid': False, 'score': 0, 'rsi': rsi, 'reason': 'RSI未回落'}
            
            # 2. KDJ高位死叉（3分）
            if 'kdj_k' in df.columns and 'kdj_d' in df.columns and len(df) > 1:
                k = df['kdj_k'].iloc[-1]
                d = df['kdj_d'].iloc[-1]
                k_prev = df['kdj_k'].iloc[-2]
                d_prev = df['kdj_d'].iloc[-2]
                
                if k_prev > d_prev and k < d and k > 70:
                    score_details['kdj'] = {'valid': True, 'score': 3, 'k': k, 'd': d}
                    total_score += 3
                else:
                    score_details['kdj'] = {'valid': False, 'score': 0}
            
            # 3. 看跌K线形态（3分）
            bearish_patterns = ['pattern_shooting_star', 'pattern_hanging_man', 'pattern_evening_star']
            for pattern in bearish_patterns:
                if pattern in df.columns and df[pattern].iloc[-1] < 0:
                    score_details['pattern'] = {'valid': True, 'score': 3, 'pattern': pattern}
                    total_score += 3
                    break
        
        # 4. 成交量确认（2分）
        if len(df) >= 5:
            avg_volume = df['volume'].tail(5).mean()
            current_volume = df['volume'].iloc[-1]
            if current_volume > avg_volume * 1.2:
                score_details['volume'] = {'valid': True, 'score': 2}
                total_score += 2
        
        return {'mode': 'rebound', 'total_score': total_score, 'details': score_details, 'min_score': 6}
    
    def score_breakout_entry(self, df: pd.DataFrame, trend_direction: str) -> Dict:
        """
        突破入场模式评分（趋势初期）
        
        Args:
            df: K线数据
            trend_direction: 趋势方向
            
        Returns:
            评分结果
        """
        score_details = {}
        total_score = 0
        current_price = df['close'].iloc[-1]
        
        # 1. 突破关键位（5分）
        sr_levels = self.sr.get_nearest_support_resistance(df, current_price)
        if trend_direction == 'up':
            nearest_resistance = sr_levels.get('nearest_resistance')
            if nearest_resistance and current_price >= nearest_resistance * 0.998:
                score_details['breakout'] = {'valid': True, 'score': 5, 'level': nearest_resistance}
                total_score += 5
        else:
            nearest_support = sr_levels.get('nearest_support')
            if nearest_support and current_price <= nearest_support * 1.002:
                score_details['breakout'] = {'valid': True, 'score': 5, 'level': nearest_support}
                total_score += 5
        
        # 2. 成交量放大（4分）
        if len(df) >= 5:
            avg_volume = df['volume'].tail(20).mean() if len(df) >= 20 else df['volume'].mean()
            current_volume = df['volume'].iloc[-1]
            volume_ratio = current_volume / avg_volume
            
            if volume_ratio > 1.5:
                score_details['volume'] = {'valid': True, 'score': 4, 'ratio': volume_ratio}
                total_score += 4
            elif volume_ratio > 1.2:
                score_details['volume'] = {'valid': True, 'score': 2, 'ratio': volume_ratio}
                total_score += 2
        
        # 3. RSI突破50（2分）
        if 'rsi' in df.columns:
            rsi = df['rsi'].iloc[-1]
            rsi_prev = df['rsi'].iloc[-2] if len(df) > 1 else 50
            
            if trend_direction == 'up' and rsi > 50 and rsi_prev <= 50:
                score_details['rsi'] = {'valid': True, 'score': 2, 'rsi': rsi}
                total_score += 2
            elif trend_direction == 'down' and rsi < 50 and rsi_prev >= 50:
                score_details['rsi'] = {'valid': True, 'score': 2, 'rsi': rsi}
                total_score += 2
        
        # 4. MACD金叉/死叉（3分）
        if 'macd' in df.columns and 'macd_signal' in df.columns and len(df) > 1:
            macd = df['macd'].iloc[-1]
            signal = df['macd_signal'].iloc[-1]
            macd_prev = df['macd'].iloc[-2]
            signal_prev = df['macd_signal'].iloc[-2]
            
            # 金叉
            if trend_direction == 'up' and macd_prev < signal_prev and macd > signal:
                score_details['macd'] = {'valid': True, 'score': 3}
                total_score += 3
            # 死叉
            elif trend_direction == 'down' and macd_prev > signal_prev and macd < signal:
                score_details['macd'] = {'valid': True, 'score': 3}
                total_score += 3
        
        return {'mode': 'breakout', 'total_score': total_score, 'details': score_details, 'min_score': 7}
    
    def score_trend_following_entry(self, df: pd.DataFrame, trend_direction: str) -> Dict:
        """
        趋势跟随模式评分（强趋势中期）
        
        Args:
            df: K线数据
            trend_direction: 趋势方向
            
        Returns:
            评分结果
        """
        score_details = {}
        total_score = 0
        
        # 1. ADX强趋势（5分）
        if 'adx' in df.columns:
            adx = df['adx'].iloc[-1]
            if adx > 30:
                score_details['adx'] = {'valid': True, 'score': 5, 'adx': adx}
                total_score += 5
            elif adx > 25:
                score_details['adx'] = {'valid': True, 'score': 3, 'adx': adx}
                total_score += 3
        
        # 2. EMA顺势（3分）
        if 'ema_9' in df.columns and 'ema_21' in df.columns:
            ema9 = df['ema_9'].iloc[-1]
            ema21 = df['ema_21'].iloc[-1]
            price = df['close'].iloc[-1]
            
            if trend_direction == 'up' and price > ema9 > ema21:
                score_details['ema'] = {'valid': True, 'score': 3}
                total_score += 3
            elif trend_direction == 'down' and price < ema9 < ema21:
                score_details['ema'] = {'valid': True, 'score': 3}
                total_score += 3
        
        # 3. RSI顺势且未超买/超卖（2分）
        if 'rsi' in df.columns:
            rsi = df['rsi'].iloc[-1]
            if trend_direction == 'up' and 40 <= rsi <= 70:
                score_details['rsi'] = {'valid': True, 'score': 2, 'rsi': rsi}
                total_score += 2
            elif trend_direction == 'down' and 30 <= rsi <= 60:
                score_details['rsi'] = {'valid': True, 'score': 2, 'rsi': rsi}
                total_score += 2
        
        # 4. K线方向一致（2分）
        if len(df) >= 3:
            closes = df['close'].tail(3)
            if trend_direction == 'up' and all(closes.iloc[i] > closes.iloc[i-1] for i in range(1, len(closes))):
                score_details['candle_direction'] = {'valid': True, 'score': 2}
                total_score += 2
            elif trend_direction == 'down' and all(closes.iloc[i] < closes.iloc[i-1] for i in range(1, len(closes))):
                score_details['candle_direction'] = {'valid': True, 'score': 2}
                total_score += 2
        
        # 5. 成交量持续（2分）
        if len(df) >= 5:
            recent_volumes = df['volume'].tail(3)
            avg_volume = df['volume'].tail(10).mean()
            if recent_volumes.mean() > avg_volume:
                score_details['volume'] = {'valid': True, 'score': 2}
                total_score += 2
        
        return {'mode': 'trend_following', 'total_score': total_score, 'details': score_details, 'min_score': 7}
    
    def score_pullback_entry(self, df: pd.DataFrame, trend_direction: str) -> Dict:
        """
        回调入场模式评分（优化版）
        
        Args:
            df: K线数据
            trend_direction: 趋势方向
            
        Returns:
            评分结果
        """
        score_details = {}
        total_score = 0
        
        # 使用现有的检查方法
        fib_result = self.check_fibonacci_pullback(df, trend_direction)
        score_details['fibonacci'] = fib_result
        total_score += fib_result.get('score', 0)
        
        sr_result = self.check_support_resistance_touch(df, trend_direction)
        score_details['support_resistance'] = sr_result
        total_score += sr_result.get('score', 0)
        
        rsi_result = self.check_rsi_condition(df, trend_direction)
        score_details['rsi'] = rsi_result
        total_score += rsi_result.get('score', 0)
        
        kdj_result = self.check_kdj_crossover(df, trend_direction)
        score_details['kdj'] = kdj_result
        total_score += kdj_result.get('score', 0)
        
        macd_result = self.check_macd_convergence(df, trend_direction)
        score_details['macd'] = macd_result
        total_score += macd_result.get('score', 0)
        
        pattern_result = self.check_candlestick_pattern(df, trend_direction)
        score_details['candlestick'] = pattern_result
        total_score += pattern_result.get('score', 0)
        
        volume_result = self.check_volume_confirmation(df, trend_direction)
        score_details['volume'] = volume_result
        total_score += volume_result.get('score', 0)
        
        bb_result = self.check_bollinger_bounce(df, trend_direction)
        score_details['bollinger'] = bb_result
        total_score += bb_result.get('score', 0)
        
        return {'mode': 'pullback', 'total_score': total_score, 'details': score_details, 'min_score': 7}
    
    def calculate_stop_loss_take_profit(self, 
                                        symbol: str,
                                        df: pd.DataFrame,
                                        signal_type: str,
                                        entry_price: float) -> Dict:
        """
        计算止损止盈价格
        
        Args:
            symbol: 交易对
            df: K线数据
            signal_type: 信号类型
            entry_price: 入场价格
            
        Returns:
            止损止盈价格
        """
        # 固定止损百分比
        fixed_stop_pct = self.risk_config.get('fixed_stop_loss', 0.02)
        risk_reward = self.risk_config.get('risk_reward_ratio', 3)
        
        # 获取ATR
        atr = df['atr'].iloc[-1] if 'atr' in df.columns else 0
        
        # 获取支撑阻力位
        sr_levels = self.sr.get_nearest_support_resistance(df, entry_price)
        
        if signal_type == 'long':
            # 止损：取固定止损和技术止损中较近的
            fixed_stop = entry_price * (1 - fixed_stop_pct)
            tech_stop = sr_levels.get('nearest_support', fixed_stop) * 0.995  # 支撑下方0.5%
            
            stop_loss = max(fixed_stop, tech_stop)  # 取较高的（较近的）
            
            # 止盈
            stop_distance = entry_price - stop_loss
            take_profit = entry_price + stop_distance * risk_reward
        
        else:  # short
            # 止损
            fixed_stop = entry_price * (1 + fixed_stop_pct)
            tech_stop = sr_levels.get('nearest_resistance', fixed_stop) * 1.005  # 阻力上方0.5%
            
            stop_loss = min(fixed_stop, tech_stop)  # 取较低的（较近的）
            
            # 止盈
            stop_distance = stop_loss - entry_price
            take_profit = entry_price - stop_distance * risk_reward
        
        return {
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'stop_distance_pct': abs(entry_price - stop_loss) / entry_price,
        }
    
    def generate_signal(self, 
                       symbol: str,
                       df: pd.DataFrame,
                       trend_info) -> Optional[TradingSignal]:
        """
        生成交易信号（支持多种入场模式）
        
        Args:
            symbol: 交易对
            df: K线数据（5分钟）
            trend_info: 趋势信息
            
        Returns:
            交易信号或None
        """
        if not trend_info.is_strong:
            return None
        
        trend_direction = trend_info.direction
        current_price = df['close'].iloc[-1]
        
        # 1. 检测入场模式
        entry_mode = self.detect_entry_mode(df, trend_info)
        system_logger.info(f"{symbol} 检测到入场模式: {entry_mode.value}")
        
        # 2. 根据模式进行评分
        if entry_mode == EntryMode.REBOUND:
            score_result = self.score_rebound_entry(df, trend_direction)
            # 反弹入场的信号方向与趋势相反
            final_signal_type = 'up' if trend_direction == 'down' else 'down'
        elif entry_mode == EntryMode.BREAKOUT:
            score_result = self.score_breakout_entry(df, trend_direction)
            final_signal_type = trend_direction
        elif entry_mode == EntryMode.TREND_FOLLOWING:
            score_result = self.score_trend_following_entry(df, trend_direction)
            final_signal_type = trend_direction
        else:  # PULLBACK
            score_result = self.score_pullback_entry(df, trend_direction)
            final_signal_type = trend_direction
        
        total_score = score_result['total_score']
        score_details = score_result['details']
        min_score = score_result['min_score']
        
        # 3. 订单流分析（额外加分）
        order_flow_result = self.order_flow.analyze_order_flow(symbol)
        if order_flow_result:
            score_details['order_flow'] = order_flow_result
            # 订单流支持则加2分
            if ((final_signal_type == 'up' and order_flow_result['signal'] in ['buy', 'strong_buy']) or
                (final_signal_type == 'down' and order_flow_result['signal'] in ['sell', 'strong_sell'])):
                total_score += 2
                system_logger.info(f"{symbol} 订单流支持 +2分")
        
        # 4. 检查最低评分
        system_logger.info(f"{symbol} {entry_mode.value}模式 总评分: {total_score}/{min_score}")
        
        if total_score < min_score:
            system_logger.info(f"{symbol} 评分不足 ({total_score} < {min_score})，不生成信号")
            return None
        
        # 5. 计算止损止盈
        stops = self.calculate_stop_loss_take_profit(symbol, df, final_signal_type, current_price)
        
        # 6. 获取支撑阻力位
        sr_levels = self.sr.get_nearest_support_resistance(df, current_price)
        
        # 7. 创建信号
        signal = TradingSignal(
            symbol=symbol,
            signal_type=final_signal_type,  # 'up' -> 'long', 'down' -> 'short'
            score=total_score,
            entry_price=current_price,
            stop_loss=stops['stop_loss'],
            take_profit=stops['take_profit'],
            score_details=score_details,
            entry_mode=entry_mode.value,
            support_level=sr_levels.get('nearest_support'),
            resistance_level=sr_levels.get('nearest_resistance'),
        )
        
        system_logger.info(f"✅ 生成信号: {signal}")
        
        return signal


# 全局信号生成器实例
signal_generator = SignalGenerator()

