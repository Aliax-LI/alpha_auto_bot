"""
Renko 实现测试脚本
使用 ccxt 获取币安实盘数据测试 ATR-based Renko 构建器和信号生成
"""
import sys
from pathlib import Path
import pandas as pd
import numpy as np
import ccxt
from datetime import datetime, timedelta

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.indicators.renko import ATRRenkoBuilder, RenkoSignalGenerator
from src.indicators.technical import TechnicalIndicators as TI
from loguru import logger

# 配置日志
logger.remove()
logger.add(sys.stdout, level="INFO")

# 代理配置
PROXY = 'http://127.0.0.1:7890'
SYMBOL = 'BTC/USDT:USDT'
EXCHANGE = 'binance'


def fetch_binance_data(
    symbol: str = SYMBOL,
    timeframe: str = '5m',
    limit: int = 500
) -> pd.DataFrame:
    """
    从币安获取实盘 K 线数据
    
    Args:
        symbol: 交易对 (BTC/USDT:USDT)
        timeframe: 时间框架 (1m, 5m, 15m, 1h, etc.)
        limit: 获取的K线数量
        
    Returns:
        包含 OHLCV 数据的 DataFrame
    """
    try:
        logger.info(f"🔗 连接币安交易所...")
        logger.info(f"   交易对: {symbol}")
        logger.info(f"   时间框架: {timeframe}")
        logger.info(f"   数量: {limit} 根K线")
        
        # 初始化交易所
        exchange = ccxt.binance({
            'proxies': {
                'http': PROXY,
                'https': PROXY,
            },
            'timeout': 30000,
            'enableRateLimit': True,
        })
        
        # 获取 OHLCV 数据
        ohlcv = exchange.fetch_ohlcv(
            symbol=symbol,
            timeframe=timeframe,
            limit=limit
        )
        
        # 转换为 DataFrame
        df = pd.DataFrame(
            ohlcv,
            columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
        )
        
        # 转换时间戳
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        
        logger.info(f"✅ 成功获取 {len(df)} 根K线")
        logger.info(f"   时间范围: {df['timestamp'].iloc[0]} → {df['timestamp'].iloc[-1]}")
        logger.info(f"   价格范围: {df['close'].min():.2f} - {df['close'].max():.2f}")
        
        return df
        
    except Exception as e:
        logger.error(f"❌ 获取数据失败: {e}")
        logger.warning("⚠️ 请确认:")
        logger.warning("   1. 代理是否正常运行 (http://127.0.0.1:7890)")
        logger.warning("   2. 网络连接是否正常")
        logger.warning("   3. 交易对格式是否正确")
        raise


def test_renko_basic():
    """测试基本 Renko 构建（使用实盘数据）"""
    logger.info("=" * 60)
    logger.info("测试 1: 基本 Renko 构建（实盘数据）")
    logger.info("=" * 60)
    
    # 获取实盘数据
    df = fetch_binance_data(timeframe='5m', limit=200)
    
    # 构建 Renko
    builder = ATRRenkoBuilder(atr_period=14, use_atr=True)
    renko_df = builder.build(df)
    
    if not renko_df.empty:
        logger.info(f"✅ 生成 {len(renko_df)} 个 Renko 砖块")
        logger.info(f"   看涨砖块: {(renko_df['direction'] == 1).sum()}")
        logger.info(f"   看跌砖块: {(renko_df['direction'] == -1).sum()}")
        
        # 显示前几个砖块
        logger.info("\n前 5 个 Renko 砖块:")
        for i, row in renko_df.head(5).iterrows():
            direction = "🟢" if row['direction'] == 1 else "🔴"
            logger.info(
                f"   {direction} {row['open']:.2f} → {row['close']:.2f}"
            )
    else:
        logger.error("❌ 未生成任何 Renko 砖块")
    
    return renko_df


def test_renko_signals():
    """测试 Renko 信号生成（使用实盘数据）"""
    logger.info("\n" + "=" * 60)
    logger.info("测试 2: Renko 信号生成（实盘数据）")
    logger.info("=" * 60)
    
    # 获取实盘数据
    df = fetch_binance_data(timeframe='5m', limit=300)
    
    # 构建 Renko
    builder = ATRRenkoBuilder(atr_period=14, use_atr=True)
    renko_df = builder.build(df)
    
    if renko_df.empty:
        logger.error("❌ Renko 数据为空")
        return
    
    # 生成信号
    signal_gen = RenkoSignalGenerator(ema_fast=2, ema_slow=10)
    
    # 模拟实时信号生成
    signals = []
    for i in range(30, len(renko_df), 5):  # 每5个砖块检查一次
        partial_df = renko_df.iloc[:i]
        signal = signal_gen.generate_signal(partial_df)
        
        if signal:
            strength = signal_gen.get_trend_strength(partial_df)
            signals.append({
                'index': i,
                'signal': signal,
                'strength': strength,
                'price': partial_df['close'].iloc[-1]
            })
    
    logger.info(f"✅ 生成 {len(signals)} 个信号")
    
    if signals:
        logger.info("\n信号详情:")
        for s in signals[:10]:  # 显示前 10 个
            logger.info(
                f"   {s['signal']:5s} @ {s['price']:8.2f} "
                f"(强度: {s['strength']:.1%})"
            )
    
    return signals


def test_renko_comparison():
    """对比不同 ATR 周期的 Renko（使用实盘数据）"""
    logger.info("\n" + "=" * 60)
    logger.info("测试 3: 对比不同 ATR 周期（实盘数据）")
    logger.info("=" * 60)
    
    # 获取实盘数据
    df = fetch_binance_data(timeframe='5m', limit=250)
    
    atr_periods = [3, 7, 14, 21]
    
    for period in atr_periods:
        builder = ATRRenkoBuilder(atr_period=period, use_atr=True)
        renko_df = builder.build(df)
        
        if not renko_df.empty:
            bullish = (renko_df['direction'] == 1).sum()
            bearish = (renko_df['direction'] == -1).sum()
            
            logger.info(
                f"ATR({period:2d}): {len(renko_df):3d} 砖块 "
                f"(🟢{bullish} / 🔴{bearish})"
            )


def test_renko_with_ema():
    """测试 Renko + EMA 趋势分析（使用实盘数据）"""
    logger.info("\n" + "=" * 60)
    logger.info("测试 4: Renko + EMA 趋势分析（实盘数据）")
    logger.info("=" * 60)
    
    # 获取实盘数据
    df = fetch_binance_data(timeframe='5m', limit=200)
    
    builder = ATRRenkoBuilder(atr_period=14, use_atr=True)
    renko_df = builder.build(df)
    
    if renko_df.empty:
        logger.error("❌ Renko 数据为空")
        return
    
    # 计算 EMA
    ema2 = TI.ema(renko_df['close'], 2)
    ema10 = TI.ema(renko_df['close'], 10)
    
    # 显示最近的趋势
    logger.info("\n最近 10 个砖块的趋势:")
    for i in range(max(0, len(renko_df) - 10), len(renko_df)):
        row = renko_df.iloc[i]
        direction = "🟢" if row['direction'] == 1 else "🔴"
        
        ema2_val = ema2.iloc[i] if i < len(ema2) else 0
        ema10_val = ema10.iloc[i] if i < len(ema10) else 0
        
        # EMA 关系
        if ema2_val > ema10_val:
            ema_trend = "📈"
        elif ema2_val < ema10_val:
            ema_trend = "📉"
        else:
            ema_trend = "➡️"
        
        logger.info(
            f"   {direction} {row['close']:8.2f} | "
            f"EMA2:{ema2_val:8.2f} EMA10:{ema10_val:8.2f} {ema_trend}"
        )


def run_all_tests():
    """运行所有测试（使用币安实盘数据）"""
    logger.info("🚀 开始 Renko 实现测试（币安实盘数据）")
    logger.info(f"📊 交易对: {SYMBOL}")
    logger.info(f"🌐 代理: {PROXY}\n")
    
    try:
        test_renko_basic()
        test_renko_signals()
        test_renko_comparison()
        test_renko_with_ema()
        
        logger.info("\n" + "=" * 60)
        logger.info("✅ 所有测试完成！")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"❌ 测试失败: {e}", exc_info=True)


if __name__ == '__main__':
    run_all_tests()

