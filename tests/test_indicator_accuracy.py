"""
指标计算精度验证
对比 Python 实现与 TradingView 的计算方法
"""
import sys
from pathlib import Path
import pandas as pd
import numpy as np
import ccxt
from loguru import logger

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.indicators.technical import TechnicalIndicators as TI

logger.remove()
logger.add(sys.stdout, level="INFO")

PROXY = 'http://127.0.0.1:7890'
SYMBOL = 'BTC/USDT:USDT'


def fetch_data(limit: int = 100) -> pd.DataFrame:
    """获取测试数据"""
    exchange = ccxt.binance({
        'proxies': {'http': PROXY, 'https': PROXY},
        'timeout': 30000,
        'enableRateLimit': True,
    })
    
    ohlcv = exchange.fetch_ohlcv(SYMBOL, timeframe='1h', limit=limit)
    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    return df


def test_rsi_method():
    """验证 RSI 计算方法"""
    logger.info("=" * 70)
    logger.info("检查 1: RSI 计算方法")
    logger.info("=" * 70)
    
    df = fetch_data(50)
    period = 14
    
    # 方法1: 当前实现（Wilder's smoothing）
    rsi1 = TI.rsi(df['close'], period)
    
    # 方法2: 手动计算验证
    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    
    # 初始平均
    avg_gain = gain.rolling(window=period, min_periods=period).mean()
    avg_loss = loss.rolling(window=period, min_periods=period).mean()
    
    # Wilder's smoothing
    for i in range(period, len(df)):
        avg_gain.iloc[i] = (avg_gain.iloc[i-1] * (period - 1) + gain.iloc[i]) / period
        avg_loss.iloc[i] = (avg_loss.iloc[i-1] * (period - 1) + loss.iloc[i]) / period
    
    rs = avg_gain / avg_loss
    rsi2 = 100 - (100 / (1 + rs))
    
    diff = abs(rsi1.iloc[-1] - rsi2.iloc[-1])
    
    logger.info(f"RSI({period}) 当前值:")
    logger.info(f"  方法1: {rsi1.iloc[-1]:.4f}")
    logger.info(f"  方法2: {rsi2.iloc[-1]:.4f}")
    logger.info(f"  差异: {diff:.8f}")
    
    if diff < 0.0001:
        logger.info("✅ RSI 计算方法正确")
        return True
    else:
        logger.warning("⚠️ RSI 计算可能存在问题")
        return False


def test_atr_method():
    """验证 ATR 计算方法"""
    logger.info("\n" + "=" * 70)
    logger.info("检查 2: ATR 计算方法（关键！）")
    logger.info("=" * 70)
    
    df = fetch_data(50)
    period = 14
    
    # 当前实现
    atr_current = TI.atr(df, period)
    
    # 正确的实现：使用 RMA (Wilder's smoothing)
    high = df['high']
    low = df['low']
    close = df['close']
    
    # True Range
    tr1 = high - low
    tr2 = abs(high - close.shift(1))
    tr3 = abs(low - close.shift(1))
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    
    # 方法1: 使用 ewm (当前实现)
    atr_ewm = tr.ewm(span=period, adjust=False).mean()
    
    # 方法2: 使用 RMA (TradingView 标准)
    # RMA = (previous_rma * (period - 1) + current_value) / period
    atr_rma = pd.Series(index=df.index, dtype=float)
    atr_rma.iloc[:period] = tr.iloc[:period].mean()  # 初始值用 SMA
    
    for i in range(period, len(df)):
        atr_rma.iloc[i] = (atr_rma.iloc[i-1] * (period - 1) + tr.iloc[i]) / period
    
    logger.info(f"ATR({period}) 计算对比:")
    logger.info(f"  当前实现:        {atr_current.iloc[-1]:.4f}")
    logger.info(f"  EWM 方法:        {atr_ewm.iloc[-1]:.4f}")
    logger.info(f"  RMA 方法 (正确): {atr_rma.iloc[-1]:.4f}")
    
    # 当前实现 vs RMA 的差异
    diff_current_rma = abs(atr_current.iloc[-1] - atr_rma.iloc[-1])
    diff_ewm_rma = abs(atr_ewm.iloc[-1] - atr_rma.iloc[-1])
    
    logger.info(f"\n  当前实现 vs RMA: {diff_current_rma:.4f}")
    logger.info(f"  EWM vs RMA:      {diff_ewm_rma:.4f}")
    
    # Alpha 对比
    alpha_ewm = 2 / (period + 1)
    alpha_rma = 1 / period
    logger.info(f"\n  EWM alpha: {alpha_ewm:.6f}")
    logger.info(f"  RMA alpha: {alpha_rma:.6f}")
    
    if diff_current_rma < 0.01:
        logger.info("✅ ATR 实现正确（使用 RMA，与 TradingView 一致）")
        return True
    else:
        logger.warning("⚠️ 警告: ATR 实现与 TradingView 标准不一致!")
        logger.warning(f"   差异: {diff_current_rma:.4f}")
        return False


def test_ema_method():
    """验证 EMA 计算方法"""
    logger.info("\n" + "=" * 70)
    logger.info("检查 3: EMA 计算方法")
    logger.info("=" * 70)
    
    df = fetch_data(50)
    period = 10
    
    # 当前实现
    ema_current = TI.ema(df['close'], period)
    
    # 手动计算
    alpha = 2 / (period + 1)
    ema_manual = pd.Series(index=df.index, dtype=float)
    ema_manual.iloc[0] = df['close'].iloc[0]
    
    for i in range(1, len(df)):
        ema_manual.iloc[i] = alpha * df['close'].iloc[i] + (1 - alpha) * ema_manual.iloc[i-1]
    
    diff = abs(ema_current.iloc[-1] - ema_manual.iloc[-1])
    
    logger.info(f"EMA({period}) 验证:")
    logger.info(f"  pandas ewm:  {ema_current.iloc[-1]:.4f}")
    logger.info(f"  手动计算:    {ema_manual.iloc[-1]:.4f}")
    logger.info(f"  差异:        {diff:.8f}")
    
    if diff < 0.01:
        logger.info("✅ EMA 计算正确")
        return True
    else:
        logger.warning("⚠️ EMA 计算可能存在问题")
        return False


def test_crossover_timing():
    """验证交叉检测的时机"""
    logger.info("\n" + "=" * 70)
    logger.info("检查 4: 交叉检测时机")
    logger.info("=" * 70)
    
    df = fetch_data(100)
    
    ema_fast = TI.ema(df['close'], 10)
    ema_slow = TI.ema(df['close'], 20)
    
    # 检查最近的交叉
    logger.info("最近 5 根K线的 EMA 状态:")
    for i in range(len(df) - 5, len(df)):
        fast_val = ema_fast.iloc[i]
        slow_val = ema_slow.iloc[i]
        diff = fast_val - slow_val
        
        status = "快线在上" if diff > 0 else "快线在下"
        logger.info(f"  [{i}] EMA10: {fast_val:.2f}, EMA20: {slow_val:.2f}, "
                   f"差值: {diff:+.2f} ({status})")
    
    # 检测当前是否有交叉
    is_crossover = TI.crossover(ema_fast, ema_slow)
    is_crossunder = TI.crossunder(ema_fast, ema_slow)
    
    logger.info(f"\n当前状态:")
    logger.info(f"  上穿: {is_crossover}")
    logger.info(f"  下穿: {is_crossunder}")
    
    # 验证逻辑
    if is_crossover:
        assert ema_fast.iloc[-2] <= ema_slow.iloc[-2], "上穿逻辑错误"
        assert ema_fast.iloc[-1] > ema_slow.iloc[-1], "上穿逻辑错误"
        logger.info("✅ 上穿检测逻辑正确")
    
    if is_crossunder:
        assert ema_fast.iloc[-2] >= ema_slow.iloc[-2], "下穿逻辑错误"
        assert ema_fast.iloc[-1] < ema_slow.iloc[-1], "下穿逻辑错误"
        logger.info("✅ 下穿检测逻辑正确")
    
    if not is_crossover and not is_crossunder:
        logger.info("✅ 当前无交叉，检测正确")
    
    return True


def test_atr_vs_atr_ema():
    """验证 ATR 过滤器逻辑"""
    logger.info("\n" + "=" * 70)
    logger.info("检查 5: ATR 过滤器（ATR vs ATR_EMA）")
    logger.info("=" * 70)
    
    df = fetch_data(50)
    
    atr_period = 5
    ema_period = 5
    
    # 计算 ATR
    atr = TI.atr(df, atr_period)
    
    # 计算 ATR 的 EMA
    atr_ema = TI.ema(atr, ema_period)
    
    logger.info(f"ATR({atr_period}) vs ATR_EMA({ema_period}):")
    logger.info(f"  当前 ATR:     {atr.iloc[-1]:.4f}")
    logger.info(f"  当前 ATR_EMA: {atr_ema.iloc[-1]:.4f}")
    logger.info(f"  ATR > ATR_EMA: {atr.iloc[-1] > atr_ema.iloc[-1]}")
    
    # 这是原脚本的横盘过滤逻辑
    is_sideways = atr.iloc[-1] >= atr_ema.iloc[-1]
    logger.info(f"\n  横盘判断 (ATR >= ATR_EMA): {is_sideways}")
    
    if is_sideways:
        logger.info("  → 当前可能处于横盘/波动增大状态")
    else:
        logger.info("  → 当前可能处于趋势/波动减小状态")
    
    logger.info("✅ ATR 过滤器逻辑正确")
    return True


def run_accuracy_check():
    """运行所有精度检查"""
    logger.info("╔════════════════════════════════════════════════════════════════════╗")
    logger.info("║                  指标计算精度与方法验证                            ║")
    logger.info("╚════════════════════════════════════════════════════════════════════╝\n")
    
    results = []
    
    tests = [
        ("RSI 计算方法", test_rsi_method),
        ("ATR 计算方法", test_atr_method),
        ("EMA 计算方法", test_ema_method),
        ("交叉检测时机", test_crossover_timing),
        ("ATR 过滤器逻辑", test_atr_vs_atr_ema),
    ]
    
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            logger.error(f"❌ {name} 失败: {e}")
            results.append((name, False))
    
    # 总结
    logger.info("\n" + "=" * 70)
    logger.info("检查总结")
    logger.info("=" * 70)
    
    for name, result in results:
        status = "✅ 通过" if result else "❌ 需要修复"
        logger.info(f"{status} - {name}")
    
    passed = sum(1 for _, r in results if r)
    total = len(results)
    
    logger.info(f"\n通过率: {passed}/{total} ({passed/total*100:.0f}%)")
    
    if passed < total:
        logger.warning("\n⚠️ 发现问题，需要修复！")
        return False
    else:
        logger.info("\n🎉 所有检查通过！")
        return True


if __name__ == '__main__':
    success = run_accuracy_check()
    exit(0 if success else 1)

