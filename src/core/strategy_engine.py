"""
ALGOX 策略引擎
实现信号生成、过滤器和风险管理计算
"""
import pandas as pd
import numpy as np
from typing import Optional, Dict, Any, Tuple
from loguru import logger

from ..indicators.heikinashi import HeikinAshi
from ..indicators.technical import TechnicalIndicators as TI
from ..indicators.renko import ATRRenkoBuilder, RenkoSignalGenerator


class AlgoxStrategy:
    """ALGOX 策略引擎"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化策略引擎
        
        Args:
            config: 策略配置字典
        """
        self.config = config
        
        # 策略参数
        self.setup_type = config.get('setup_type', 'Open/Close')
        self.tps_type = config.get('tps_type', 'Trailing')
        self.filter_type = config.get('filter_type', 'No Filtering')
        # 兼容 htf_multiplier 和 tf_multiplier 两种命名
        self.tf_multiplier = config.get('htf_multiplier', config.get('tf_multiplier', 18))
        
        # RSI 参数（兼容配置文件的命名）
        self.rsi_period = config.get('rsi_period', 7)
        self.rsi_top_limit = config.get('rsi_high', config.get('rsi_top_limit', 45))
        self.rsi_bottom_limit = config.get('rsi_low', config.get('rsi_bottom_limit', 10))
        
        # ATR 过滤参数
        self.atr_filter_period = config.get('atr_filter_period', 5)
        self.atr_filter_ma_period = config.get('atr_filter_ma_period', 5)
        self.atr_filter_ma_type = config.get('atr_filter_ma_type', 'EMA')
        
        # Renko 参数
        self.renko_atr_period = config.get('renko_atr_period', 3)
        self.renko_ema_fast = config.get('renko_ema_fast', 2)
        self.renko_ema_slow = config.get('renko_ema_slow', 10)
        
        # 风险管理参数
        self.atr_risk_period = config.get('atr_risk_period', 20)
        self.profit_factor = config.get('profit_factor', 2.5)
        self.stop_factor = config.get('stop_factor', 1.0)
        
        # 初始化 Renko 构建器和信号生成器
        if self.setup_type == 'Renko':
            self.renko_builder = ATRRenkoBuilder(atr_period=self.renko_atr_period)
            self.renko_signal_gen = RenkoSignalGenerator(
                ema_fast=self.renko_ema_fast,
                ema_slow=self.renko_ema_slow
            )
        
        logger.info(
            f"✅ 策略引擎初始化: {self.setup_type} / {self.tps_type} / {self.filter_type}"
        )
    
    def resample_timeframe(self, df: pd.DataFrame, multiplier: int) -> pd.DataFrame:
        """
        将数据重采样到更高时间框架
        
        Args:
            df: 原始数据框
            multiplier: 时间框架倍数
            
        Returns:
            重采样后的数据框
        """
        # 确保索引是时间戳
        if not isinstance(df.index, pd.DatetimeIndex):
            df = df.set_index('timestamp')
        
        # 根据倍数确定重采样规则
        # 假设基础时间框架是分钟级
        resample_rule = f'{multiplier}min'  # min 表示分钟（替代已弃用的 'T'）
        
        resampled = df.resample(resample_rule).agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum'
        }).dropna()
        
        return resampled
    
    def generate_signal(self, df: pd.DataFrame) -> Optional[str]:
        """
        生成交易信号
        
        Args:
            df: K线数据框
            
        Returns:
            'BUY', 'SELL', 或 None
        """
        if len(df) < 50:  # 确保有足够的数据
            logger.warning("数据不足，无法生成信号")
            return None
        
        # 1. 应用过滤器
        if not self._apply_filter(df):
            return None
        
        # 2. 重采样到高时间框架
        htf_df = self.resample_timeframe(df, self.tf_multiplier)
        
        if len(htf_df) < 2:
            logger.warning("高时间框架数据不足")
            return None
        
        # 3. 根据设置类型生成信号
        if self.setup_type == 'Open/Close':
            signal = self._oc_signal(htf_df)
        elif self.setup_type == 'Renko':
            signal = self._renko_signal(htf_df)
        else:
            logger.error(f"未知的设置类型: {self.setup_type}")
            return None
        
        if signal:
            logger.info(f"🎯 信号生成: {signal}")
        
        return signal
    
    def _oc_signal(self, htf_df: pd.DataFrame) -> Optional[str]:
        """
        Open/Close 模式信号生成
        基于 Heikin Ashi Close/Open 交叉
        
        Args:
            htf_df: 高时间框架数据
            
        Returns:
            交易信号
        """
        # 计算 Heikin Ashi
        ha_df = HeikinAshi.calculate(htf_df)
        
        # 检测交叉
        signal = HeikinAshi.detect_crossover(ha_df)
        
        return signal
    
    def _renko_signal(self, htf_df: pd.DataFrame) -> Optional[str]:
        """
        Renko 模式信号生成
        基于完整的 ATR-based Renko + EMA 交叉
        
        Args:
            htf_df: 高时间框架数据
            
        Returns:
            交易信号
        """
        try:
            # 1. 构建 Renko 图表
            renko_df = self.renko_builder.build(htf_df)
            
            if renko_df.empty or len(renko_df) < 2:
                logger.debug("Renko 数据不足")
                return None
            
            # 2. 基于 Renko + EMA 生成信号
            signal = self.renko_signal_gen.generate_signal(renko_df)
            
            # 3. 可选：检查趋势强度
            if signal:
                trend_strength = self.renko_signal_gen.get_trend_strength(renko_df)
                logger.debug(f"Renko 趋势强度: {trend_strength:.2%}")
            
            return signal
            
        except Exception as e:
            logger.error(f"❌ Renko 信号生成失败: {e}")
            return None
    
    def _apply_filter(self, df: pd.DataFrame) -> bool:
        """
        应用过滤器
        
        Args:
            df: K线数据
            
        Returns:
            是否通过过滤
        """
        # 计算指标
        rsi = TI.rsi(df['close'], self.rsi_period)
        atr = TI.atr(df, self.atr_filter_period)
        
        if self.atr_filter_ma_type == 'EMA':
            atr_ma = TI.ema(atr, self.atr_filter_ma_period)
        else:
            atr_ma = TI.sma(atr, self.atr_filter_ma_period)
        
        # 获取最新值
        current_rsi = rsi.iloc[-1] if not rsi.empty else 50
        current_atr = atr.iloc[-1] if not atr.empty else 0
        current_atr_ma = atr_ma.iloc[-1] if not atr_ma.empty else 0
        
        # 过滤条件（修正：与旧版本保持一致）
        # RSI在范围内 = 适合交易的趋势市场
        rsi_trend_condition = self.rsi_bottom_limit < current_rsi < self.rsi_top_limit
        # ATR小于均值 = 非横盘，适合交易
        atr_condition = current_atr < current_atr_ma
        
        # 横盘市场条件（反向）
        rsi_sideways_condition = not rsi_trend_condition
        atr_sideways_condition = current_atr >= current_atr_ma
        
        # 根据过滤类型判断
        filter_map = {
            'No Filtering': True,
            'Filter with ATR': atr_condition,
            'Filter with RSI': rsi_trend_condition,
            'ATR or RSI': atr_condition or rsi_trend_condition,
            'ATR and RSI': atr_condition and rsi_trend_condition,
            'Entry Only in sideways market(By ATR or RSI)': atr_sideways_condition or rsi_sideways_condition,
            'Entry Only in sideways market(By ATR and RSI)': atr_sideways_condition and rsi_sideways_condition,
        }
        
        result = filter_map.get(self.filter_type, True)
        
        if not result:
            logger.debug(
                f"过滤器未通过: {self.filter_type} "
                f"(RSI={current_rsi:.2f}, ATR={current_atr:.4f}, ATR_MA={current_atr_ma:.4f})"
            )
        
        return result
    
    def calculate_tp_sl(
        self, 
        entry_price: float, 
        direction: str, 
        atr_value: float
    ) -> Dict[str, float]:
        """
        计算止盈止损价格
        
        Args:
            entry_price: 入场价格
            direction: 'LONG' 或 'SHORT'
            atr_value: ATR 值
            
        Returns:
            包含 tp1, tp2, tp3, sl 的字典
        """
        factor = self.profit_factor
        
        if direction == 'LONG':
            tp1 = entry_price + atr_value * factor * 1
            tp2 = entry_price + atr_value * factor * 2
            tp3 = entry_price + atr_value * factor * 3
            sl = entry_price - atr_value * factor * self.stop_factor
        else:  # SHORT
            tp1 = entry_price - atr_value * factor * 1
            tp2 = entry_price - atr_value * factor * 2
            tp3 = entry_price - atr_value * factor * 3
            sl = entry_price + atr_value * factor * self.stop_factor
        
        levels = {
            'tp1': tp1,
            'tp2': tp2,
            'tp3': tp3,
            'sl': sl
        }
        
        logger.debug(
            f"计算 TP/SL: 入场={entry_price:.2f}, 方向={direction}, "
            f"TP1={tp1:.2f}, TP2={tp2:.2f}, TP3={tp3:.2f}, SL={sl:.2f}"
        )
        
        return levels
    
    def check_tp_sl_hit(
        self, 
        current_price: float,
        high: float,
        low: float,
        state: float,
        tp_levels: Dict[str, float]
    ) -> Tuple[Optional[str], Optional[float]]:
        """
        检查是否触及止盈或止损
        
        Args:
            current_price: 当前价格
            high: 当前K线最高价
            low: 当前K线最低价
            state: 当前状态
            tp_levels: 止盈止损价格字典
            
        Returns:
            (触发类型, 新状态) 元组
            触发类型: 'TP1', 'TP2', 'TP3', 'SL', None
        """
        if state == 0.0:
            return None, None
        
        is_long = state > 0
        
        # 多头逻辑
        if is_long:
            # 检查止损
            if low <= tp_levels['sl']:
                return 'SL', 0.0
            
            # 检查止盈
            if state == 1.0 and high >= tp_levels['tp1']:
                return 'TP1', 1.1
            elif state == 1.1 and high >= tp_levels['tp2']:
                return 'TP2', 1.2
            elif state == 1.2 and high >= tp_levels['tp3']:
                return 'TP3', 1.3
        
        # 空头逻辑
        else:
            # 检查止损
            if high >= tp_levels['sl']:
                return 'SL', 0.0
            
            # 检查止盈
            if state == -1.0 and low <= tp_levels['tp1']:
                return 'TP1', -1.1
            elif state == -1.1 and low <= tp_levels['tp2']:
                return 'TP2', -1.2
            elif state == -1.2 and low <= tp_levels['tp3']:
                return 'TP3', -1.3
        
        return None, None
    
    def get_atr(self, df: pd.DataFrame) -> float:
        """
        获取当前 ATR 值（用于风险管理）
        
        Args:
            df: K线数据
            
        Returns:
            ATR 值
        """
        atr = TI.atr(df, self.atr_risk_period)
        return atr.iloc[-1] if not atr.empty else 0.0

