"""
ATR-based Renko 图表构建器
基于 ATR 动态调整砖块大小，过滤时间噪音，专注于价格趋势
使用 TA-Lib 计算 ATR 和 EMA 指标
"""
import pandas as pd
import numpy as np
from typing import List, Tuple, Optional
from loguru import logger

from .technical import TechnicalIndicators as TI  # TA-Lib 实现


class RenkoBlock:
    """Renko 砖块数据结构"""
    
    def __init__(
        self, 
        open_price: float, 
        close_price: float, 
        high: float, 
        low: float,
        direction: int,  # 1 为看涨，-1 为看跌
        timestamp: pd.Timestamp = None
    ):
        self.open = open_price
        self.close = close_price
        self.high = high
        self.low = low
        self.direction = direction
        self.timestamp = timestamp
    
    def __repr__(self):
        direction_str = "🟢" if self.direction > 0 else "🔴"
        return f"{direction_str} Renko[{self.open:.2f} → {self.close:.2f}]"


class ATRRenkoBuilder:
    """ATR-based Renko 图表构建器"""
    
    def __init__(self, atr_period: int = 14, use_atr: bool = True):
        """
        初始化 Renko 构建器
        
        Args:
            atr_period: ATR 计算周期
            use_atr: 是否使用 ATR（True）或固定砖块大小（False）
        """
        self.atr_period = atr_period
        self.use_atr = use_atr
        self.blocks: List[RenkoBlock] = []
        
        logger.info(f"✅ Renko 构建器初始化: ATR周期={atr_period}, 使用ATR={use_atr}")
    
    def build(self, df: pd.DataFrame, brick_size: Optional[float] = None) -> pd.DataFrame:
        """
        从 OHLC 数据构建 Renko 图表
        
        Args:
            df: 包含 open, high, low, close, timestamp 的 DataFrame
            brick_size: 固定砖块大小（如果 use_atr=False）
            
        Returns:
            Renko 砖块的 DataFrame，包含 open, high, low, close, direction
        """
        if len(df) < self.atr_period + 10:
            logger.warning(f"数据不足以构建 Renko: {len(df)} < {self.atr_period + 10}")
            return pd.DataFrame()
        
        # 确保有 timestamp 列
        if 'timestamp' not in df.columns and isinstance(df.index, pd.DatetimeIndex):
            df = df.reset_index()
            df.rename(columns={'index': 'timestamp'}, inplace=True)
        
        # 1. 计算砖块大小
        if self.use_atr:
            # 使用 ATR 作为砖块大小
            atr_series = TI.atr(df, self.atr_period)
            # 使用最新的 ATR 值作为砖块大小
            brick_size = atr_series.iloc[-1] if not atr_series.empty else df['close'].std()
            logger.info(f"📊 使用 ATR 砖块大小: {brick_size:.4f}")
        else:
            if brick_size is None:
                # 如果未提供固定砖块大小，使用价格标准差的 1%
                brick_size = df['close'].std() * 0.01
            logger.info(f"📊 使用固定砖块大小: {brick_size:.4f}")
        
        # 2. 构建 Renko 砖块
        self.blocks = []
        
        # 初始化第一个砖块
        first_price = df['close'].iloc[0]
        current_brick_base = self._round_to_brick(first_price, brick_size)
        
        # 遍历所有价格
        for idx, row in df.iterrows():
            high = row['high']
            low = row['low']
            close = row['close']
            timestamp = row.get('timestamp', pd.Timestamp.now())
            
            # 检查是否需要形成新的砖块
            new_blocks = self._check_new_bricks(
                current_brick_base, 
                high, 
                low, 
                close,
                brick_size,
                timestamp
            )
            
            if new_blocks:
                self.blocks.extend(new_blocks)
                # 更新当前砖块基准价
                current_brick_base = new_blocks[-1].close
        
        # 3. 转换为 DataFrame
        if not self.blocks:
            logger.warning("未生成任何 Renko 砖块")
            return pd.DataFrame()
        
        renko_df = pd.DataFrame([
            {
                'timestamp': block.timestamp,
                'open': block.open,
                'high': block.high,
                'low': block.low,
                'close': block.close,
                'direction': block.direction
            }
            for block in self.blocks
        ])
        
        logger.info(f"✅ 生成 {len(renko_df)} 个 Renko 砖块")
        
        return renko_df
    
    def _round_to_brick(self, price: float, brick_size: float) -> float:
        """
        将价格向下舍入到砖块大小的整数倍
        
        Args:
            price: 原始价格
            brick_size: 砖块大小
            
        Returns:
            舍入后的价格
        """
        return np.floor(price / brick_size) * brick_size
    
    def _check_new_bricks(
        self, 
        base_price: float, 
        high: float, 
        low: float,
        close: float,
        brick_size: float,
        timestamp: pd.Timestamp
    ) -> List[RenkoBlock]:
        """
        检查是否需要形成新的砖块
        
        Args:
            base_price: 当前砖块基准价
            high: 当前K线最高价
            low: 当前K线最低价
            close: 当前K线收盘价
            brick_size: 砖块大小
            timestamp: 时间戳
            
        Returns:
            新生成的砖块列表（可能为空、一个或多个）
        """
        new_blocks = []
        
        # 计算价格相对于基准价的移动
        up_move = high - base_price
        down_move = base_price - low
        
        # 向上突破：形成看涨砖块
        if up_move >= brick_size:
            num_bricks = int(up_move / brick_size)
            for i in range(num_bricks):
                brick_open = base_price + i * brick_size
                brick_close = brick_open + brick_size
                
                block = RenkoBlock(
                    open_price=brick_open,
                    close_price=brick_close,
                    high=brick_close,
                    low=brick_open,
                    direction=1,  # 看涨
                    timestamp=timestamp
                )
                new_blocks.append(block)
        
        # 向下突破：形成看跌砖块
        elif down_move >= brick_size:
            num_bricks = int(down_move / brick_size)
            for i in range(num_bricks):
                brick_open = base_price - i * brick_size
                brick_close = brick_open - brick_size
                
                block = RenkoBlock(
                    open_price=brick_open,
                    close_price=brick_close,
                    high=brick_open,
                    low=brick_close,
                    direction=-1,  # 看跌
                    timestamp=timestamp
                )
                new_blocks.append(block)
        
        return new_blocks
    
    def get_trend(self) -> int:
        """
        获取当前趋势
        
        Returns:
            1: 看涨, -1: 看跌, 0: 无趋势
        """
        if not self.blocks:
            return 0
        
        return self.blocks[-1].direction
    
    def get_reversal_count(self, lookback: int = 5) -> Tuple[int, int]:
        """
        统计最近的趋势反转次数
        
        Args:
            lookback: 回溯砖块数量
            
        Returns:
            (看涨砖块数, 看跌砖块数)
        """
        if len(self.blocks) < lookback:
            lookback = len(self.blocks)
        
        recent_blocks = self.blocks[-lookback:]
        bullish_count = sum(1 for b in recent_blocks if b.direction > 0)
        bearish_count = sum(1 for b in recent_blocks if b.direction < 0)
        
        return bullish_count, bearish_count


class RenkoSignalGenerator:
    """基于 Renko 的交易信号生成器"""
    
    def __init__(self, ema_fast: int = 2, ema_slow: int = 10):
        """
        初始化信号生成器
        
        Args:
            ema_fast: 快速 EMA 周期
            ema_slow: 慢速 EMA 周期
        """
        self.ema_fast = ema_fast
        self.ema_slow = ema_slow
        
        logger.info(f"✅ Renko 信号生成器: EMA({ema_fast}/{ema_slow})")
    
    def generate_signal(self, renko_df: pd.DataFrame) -> Optional[str]:
        """
        基于 Renko + EMA 交叉生成信号
        
        Args:
            renko_df: Renko 砖块 DataFrame
            
        Returns:
            'BUY', 'SELL', 或 None
        """
        if len(renko_df) < max(self.ema_fast, self.ema_slow) + 2:
            logger.debug("Renko 数据不足以生成信号")
            return None
        
        # 计算 EMA（基于 Renko close）
        ema_fast_series = TI.ema(renko_df['close'], self.ema_fast)
        ema_slow_series = TI.ema(renko_df['close'], self.ema_slow)
        
        # 检测交叉
        if TI.crossover(ema_fast_series, ema_slow_series):
            logger.info(f"🎯 Renko 信号: BUY (EMA{self.ema_fast} 上穿 EMA{self.ema_slow})")
            return 'BUY'
        
        if TI.crossunder(ema_fast_series, ema_slow_series):
            logger.info(f"🎯 Renko 信号: SELL (EMA{self.ema_fast} 下穿 EMA{self.ema_slow})")
            return 'SELL'
        
        return None
    
    def get_trend_strength(self, renko_df: pd.DataFrame) -> float:
        """
        计算趋势强度（基于 EMA 距离）
        
        Args:
            renko_df: Renko 砖块 DataFrame
            
        Returns:
            趋势强度（0-1）
        """
        if len(renko_df) < max(self.ema_fast, self.ema_slow) + 1:
            return 0.0
        
        ema_fast_series = TI.ema(renko_df['close'], self.ema_fast)
        ema_slow_series = TI.ema(renko_df['close'], self.ema_slow)
        
        # 计算相对距离
        distance = abs(ema_fast_series.iloc[-1] - ema_slow_series.iloc[-1])
        price_range = renko_df['close'].max() - renko_df['close'].min()
        
        if price_range == 0:
            return 0.0
        
        strength = min(distance / price_range, 1.0)
        
        return strength


def test_renko_builder():
    """测试 Renko 构建器"""
    import random
    
    # 生成测试数据
    dates = pd.date_range('2024-01-01', periods=100, freq='1H')
    prices = [100.0]
    
    for _ in range(99):
        change = random.uniform(-2, 2)
        new_price = prices[-1] + change
        prices.append(new_price)
    
    df = pd.DataFrame({
        'timestamp': dates,
        'open': prices,
        'high': [p + random.uniform(0, 1) for p in prices],
        'low': [p - random.uniform(0, 1) for p in prices],
        'close': [p + random.uniform(-0.5, 0.5) for p in prices],
    })
    
    # 构建 Renko
    builder = ATRRenkoBuilder(atr_period=14)
    renko_df = builder.build(df)
    
    print(f"\n生成了 {len(renko_df)} 个 Renko 砖块")
    print(renko_df.head(10))
    
    # 生成信号
    signal_gen = RenkoSignalGenerator(ema_fast=2, ema_slow=10)
    signal = signal_gen.generate_signal(renko_df)
    
    print(f"\n当前信号: {signal}")
    print(f"趋势强度: {signal_gen.get_trend_strength(renko_df):.2%}")


if __name__ == '__main__':
    test_renko_builder()

