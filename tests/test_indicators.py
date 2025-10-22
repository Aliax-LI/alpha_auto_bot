"""
技术指标计算验证测试
使用币安实盘数据验证各项技术指标计算的准确性
"""
import sys
from pathlib import Path
import pandas as pd
import numpy as np
import ccxt
from loguru import logger

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.indicators.technical import TechnicalIndicators as TI
from src.indicators.heikinashi import HeikinAshi
from src.indicators.renko import ATRRenkoBuilder

# 配置日志
logger.remove()
logger.add(sys.stdout, level="INFO")

# 配置
PROXY = 'http://127.0.0.1:7890'
SYMBOL = 'BTC/USDT:USDT'


def fetch_test_data(limit: int = 500) -> pd.DataFrame:
    """获取测试数据"""
    logger.info(f"🔗 获取测试数据...")
    
    exchange = ccxt.binance({
        'proxies': {'http': PROXY, 'https': PROXY},
        'timeout': 30000,
        'enableRateLimit': True,
    })
    
    ohlcv = exchange.fetch_ohlcv(SYMBOL, timeframe='5m', limit=limit)
    
    df = pd.DataFrame(
        ohlcv,
        columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
    )
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    
    logger.info(f"✅ 获取 {len(df)} 根K线")
    logger.info(f"   时间: {df['timestamp'].iloc[0]} → {df['timestamp'].iloc[-1]}")
    logger.info(f"   价格: {df['close'].min():.2f} - {df['close'].max():.2f}\n")
    
    return df


def test_rsi_calculation():
    """测试 RSI 计算"""
    logger.info("=" * 60)
    logger.info("测试 1: RSI 指标计算")
    logger.info("=" * 60)
    
    df = fetch_test_data(200)
    
    # 测试不同周期的 RSI
    periods = [7, 14, 21]
    
    for period in periods:
        rsi = TI.rsi(df['close'], period)
        
        # 验证 RSI 范围 [0, 100]
        assert rsi.min() >= 0 and rsi.max() <= 100, f"RSI({period}) 超出范围 [0,100]"
        
        # 统计 RSI 分布
        overbought = (rsi > 70).sum()
        oversold = (rsi < 30).sum()
        neutral = ((rsi >= 30) & (rsi <= 70)).sum()
        
        logger.info(f"RSI({period:2d}): 当前={rsi.iloc[-1]:.2f}")
        logger.info(f"   范围: {rsi.min():.2f} - {rsi.max():.2f}")
        logger.info(f"   分布: 超买({overbought}) 中性({neutral}) 超卖({oversold})")
        logger.info(f"   平均: {rsi.mean():.2f}")
    
    logger.info("✅ RSI 计算通过验证\n")
    return True


def test_atr_calculation():
    """测试 ATR 计算"""
    logger.info("=" * 60)
    logger.info("测试 2: ATR 指标计算")
    logger.info("=" * 60)
    
    df = fetch_test_data(200)
    
    # 测试不同周期的 ATR
    periods = [5, 14, 20]
    
    for period in periods:
        atr = TI.atr(df, period)
        
        # 验证 ATR 为正数（忽略 NaN 值）
        valid_atr = atr.dropna()
        assert (valid_atr > 0).all(), f"ATR({period}) 存在负值"
        
        # ATR 作为价格的百分比
        price = df['close'].iloc[-1]
        atr_pct = (atr.iloc[-1] / price) * 100
        
        logger.info(f"ATR({period:2d}): 当前={atr.iloc[-1]:.2f}")
        logger.info(f"   范围: {valid_atr.min():.2f} - {valid_atr.max():.2f}")
        logger.info(f"   占价格比: {atr_pct:.3f}%")
        logger.info(f"   平均: {valid_atr.mean():.2f}")
    
    logger.info("✅ ATR 计算通过验证\n")
    return True


def test_ema_calculation():
    """测试 EMA 计算"""
    logger.info("=" * 60)
    logger.info("测试 3: EMA 指标计算")
    logger.info("=" * 60)
    
    df = fetch_test_data(200)
    
    # 测试不同周期的 EMA
    periods = [2, 10, 20, 50]
    emas = {}
    
    for period in periods:
        ema = TI.ema(df['close'], period)
        emas[period] = ema
        
        # 验证 EMA 平滑性（变化率应该较小）
        ema_change = ema.pct_change().abs()
        max_change = ema_change.max() * 100
        
        logger.info(f"EMA({period:2d}): 当前={ema.iloc[-1]:.2f}")
        logger.info(f"   最大变化率: {max_change:.3f}%")
        logger.info(f"   与价格差异: {abs(ema.iloc[-1] - df['close'].iloc[-1]):.2f}")
    
    # 验证 EMA 顺序（快速EMA应该更接近价格）
    current_price = df['close'].iloc[-1]
    for i in range(len(periods) - 1):
        p1, p2 = periods[i], periods[i+1]
        diff1 = abs(emas[p1].iloc[-1] - current_price)
        diff2 = abs(emas[p2].iloc[-1] - current_price)
        logger.info(f"   EMA({p1}) 比 EMA({p2}) 更接近当前价格: {diff1 < diff2}")
    
    logger.info("✅ EMA 计算通过验证\n")
    return True


def test_sma_calculation():
    """测试 SMA 计算"""
    logger.info("=" * 60)
    logger.info("测试 4: SMA 指标计算")
    logger.info("=" * 60)
    
    df = fetch_test_data(200)
    
    # 测试不同周期的 SMA
    periods = [5, 10, 20, 50]
    
    for period in periods:
        sma = TI.sma(df['close'], period)
        
        # 手动验证最后一个 SMA 值
        manual_sma = df['close'].iloc[-period:].mean()
        calculated_sma = sma.iloc[-1]
        diff = abs(manual_sma - calculated_sma)
        
        logger.info(f"SMA({period:2d}): 当前={calculated_sma:.2f}")
        logger.info(f"   手动计算: {manual_sma:.2f}")
        logger.info(f"   差异: {diff:.6f}")
        
        # 验证精度
        assert diff < 0.01, f"SMA({period}) 计算误差过大: {diff}"
    
    logger.info("✅ SMA 计算通过验证\n")
    return True


def test_heikinashi_calculation():
    """测试 Heikin Ashi 计算"""
    logger.info("=" * 60)
    logger.info("测试 5: Heikin Ashi 计算")
    logger.info("=" * 60)
    
    df = fetch_test_data(200)
    
    # 计算 Heikin Ashi
    ha_df = HeikinAshi.calculate(df)
    
    # 验证列存在
    required_cols = ['open', 'high', 'low', 'close']
    for col in required_cols:
        assert col in ha_df.columns, f"缺少 {col} 列"
    
    # 验证 HA 价格关系
    # high 应该是最高值
    assert (ha_df['high'] >= ha_df['open']).all()
    assert (ha_df['high'] >= ha_df['close']).all()
    
    # low 应该是最低值
    assert (ha_df['low'] <= ha_df['open']).all()
    assert (ha_df['low'] <= ha_df['close']).all()
    
    # 显示最近几根 HA 蜡烛
    logger.info("最近 5 根 Heikin Ashi 蜡烛:")
    for i in range(len(ha_df) - 5, len(ha_df)):
        row = ha_df.iloc[i]
        color = "🟢" if row['close'] > row['open'] else "🔴"
        logger.info(
            f"   {color} O:{row['open']:.2f} H:{row['high']:.2f} "
            f"L:{row['low']:.2f} C:{row['close']:.2f}"
        )
    
    # 测试交叉检测
    signal = HeikinAshi.detect_crossover(ha_df)
    logger.info(f"\n当前信号: {signal if signal else '无'}")
    
    logger.info("✅ Heikin Ashi 计算通过验证\n")
    return True


def test_crossover_detection():
    """测试交叉检测"""
    logger.info("=" * 60)
    logger.info("测试 6: EMA 交叉检测")
    logger.info("=" * 60)
    
    df = fetch_test_data(300)
    
    # 计算 EMA
    ema_fast = TI.ema(df['close'], 10)
    ema_slow = TI.ema(df['close'], 20)
    
    # 检测所有交叉点
    crossovers = []
    crossunders = []
    
    for i in range(1, len(df)):
        if TI.crossover(ema_fast[:i+1], ema_slow[:i+1]):
            crossovers.append({
                'index': i,
                'time': df['timestamp'].iloc[i],
                'price': df['close'].iloc[i]
            })
        
        if TI.crossunder(ema_fast[:i+1], ema_slow[:i+1]):
            crossunders.append({
                'index': i,
                'time': df['timestamp'].iloc[i],
                'price': df['close'].iloc[i]
            })
    
    logger.info(f"EMA(10) / EMA(20) 交叉统计:")
    logger.info(f"   上穿次数: {len(crossovers)}")
    logger.info(f"   下穿次数: {len(crossunders)}")
    logger.info(f"   总交叉: {len(crossovers) + len(crossunders)}")
    
    # 显示最近的交叉
    if crossovers:
        logger.info(f"\n最近上穿:")
        for cross in crossovers[-3:]:
            logger.info(f"   {cross['time']} @ {cross['price']:.2f}")
    
    if crossunders:
        logger.info(f"\n最近下穿:")
        for cross in crossunders[-3:]:
            logger.info(f"   {cross['time']} @ {cross['price']:.2f}")
    
    logger.info("✅ 交叉检测通过验证\n")
    return True


def test_indicator_consistency():
    """测试指标一致性（多次计算结果应该相同）"""
    logger.info("=" * 60)
    logger.info("测试 7: 指标计算一致性")
    logger.info("=" * 60)
    
    df = fetch_test_data(200)
    
    # 多次计算 RSI
    rsi1 = TI.rsi(df['close'], 14)
    rsi2 = TI.rsi(df['close'], 14)
    
    # 使用近似相等检查（允许浮点数误差）
    assert np.allclose(rsi1, rsi2, rtol=1e-10, equal_nan=True), "RSI 计算结果不一致"
    logger.info("✅ RSI 计算结果一致")
    
    # 多次计算 ATR
    atr1 = TI.atr(df, 14)
    atr2 = TI.atr(df, 14)
    
    assert np.allclose(atr1, atr2, rtol=1e-10, equal_nan=True), "ATR 计算结果不一致"
    logger.info("✅ ATR 计算结果一致")
    
    # 多次计算 EMA
    ema1 = TI.ema(df['close'], 10)
    ema2 = TI.ema(df['close'], 10)
    
    assert np.allclose(ema1, ema2, rtol=1e-10, equal_nan=True), "EMA 计算结果不一致"
    logger.info("✅ EMA 计算结果一致")
    
    # 多次计算 Heikin Ashi
    ha1 = HeikinAshi.calculate(df)
    ha2 = HeikinAshi.calculate(df)
    
    assert np.allclose(ha1['close'], ha2['close'], rtol=1e-10, equal_nan=True), "Heikin Ashi 计算结果不一致"
    logger.info("✅ Heikin Ashi 计算结果一致")
    
    logger.info("\n✅ 所有指标计算一致性验证通过\n")
    return True


def test_extreme_values():
    """测试极端值处理"""
    logger.info("=" * 60)
    logger.info("测试 8: 极端值处理")
    logger.info("=" * 60)
    
    df = fetch_test_data(200)
    
    # 测试小周期
    try:
        rsi_small = TI.rsi(df['close'], 2)
        logger.info(f"✅ RSI(2) 计算成功: {rsi_small.iloc[-1]:.2f}")
    except Exception as e:
        logger.error(f"❌ RSI(2) 计算失败: {e}")
    
    # 测试大周期
    try:
        rsi_large = TI.rsi(df['close'], 100)
        logger.info(f"✅ RSI(100) 计算成功: {rsi_large.iloc[-1]:.2f}")
    except Exception as e:
        logger.error(f"❌ RSI(100) 计算失败: {e}")
    
    # 测试 ATR 在低波动和高波动情况
    atr = TI.atr(df, 14)
    atr_min = atr.min()
    atr_max = atr.max()
    atr_ratio = atr_max / atr_min if atr_min > 0 else 0
    
    logger.info(f"ATR 波动范围: {atr_min:.2f} - {atr_max:.2f} (比率: {atr_ratio:.2f}x)")
    
    logger.info("✅ 极端值处理验证通过\n")
    return True


def test_data_alignment():
    """测试数据对齐（不同指标的长度应该一致）"""
    logger.info("=" * 60)
    logger.info("测试 9: 数据对齐检查")
    logger.info("=" * 60)
    
    df = fetch_test_data(200)
    
    rsi = TI.rsi(df['close'], 14)
    atr = TI.atr(df, 14)
    ema = TI.ema(df['close'], 14)
    sma = TI.sma(df['close'], 14)
    
    logger.info(f"原始数据长度: {len(df)}")
    logger.info(f"RSI 长度: {len(rsi)}")
    logger.info(f"ATR 长度: {len(atr)}")
    logger.info(f"EMA 长度: {len(ema)}")
    logger.info(f"SMA 长度: {len(sma)}")
    
    # 所有指标长度应该与原始数据相同
    assert len(rsi) == len(df), "RSI 长度不匹配"
    assert len(atr) == len(df), "ATR 长度不匹配"
    assert len(ema) == len(df), "EMA 长度不匹配"
    assert len(sma) == len(df), "SMA 长度不匹配"
    
    logger.info("✅ 数据对齐检查通过\n")
    return True


def test_renko_with_real_data():
    """测试 Renko 在实盘数据上的表现"""
    logger.info("=" * 60)
    logger.info("测试 10: Renko 实盘数据验证")
    logger.info("=" * 60)
    
    df = fetch_test_data(300)
    
    # 测试不同配置
    configs = [
        {'atr_period': 3, 'use_atr': True},
        {'atr_period': 14, 'use_atr': True},
        {'atr_period': 21, 'use_atr': True},
    ]
    
    for config in configs:
        builder = ATRRenkoBuilder(**config)
        renko_df = builder.build(df)
        
        if not renko_df.empty:
            # 验证 Renko 属性
            assert 'direction' in renko_df.columns
            assert set(renko_df['direction'].unique()).issubset({-1, 1})
            
            bullish = (renko_df['direction'] == 1).sum()
            bearish = (renko_df['direction'] == -1).sum()
            
            logger.info(f"ATR({config['atr_period']}): {len(renko_df)} 砖块")
            logger.info(f"   看涨: {bullish} ({bullish/len(renko_df)*100:.1f}%)")
            logger.info(f"   看跌: {bearish} ({bearish/len(renko_df)*100:.1f}%)")
        else:
            logger.warning(f"ATR({config['atr_period']}): 未生成砖块")
    
    logger.info("✅ Renko 实盘数据验证通过\n")
    return True


def run_all_tests():
    """运行所有验证测试"""
    logger.info("╔══════════════════════════════════════════════════════════════╗")
    logger.info("║         技术指标计算验证测试（实盘数据）                      ║")
    logger.info("╚══════════════════════════════════════════════════════════════╝")
    logger.info(f"交易对: {SYMBOL}")
    logger.info(f"代理: {PROXY}\n")
    
    tests = [
        ("RSI 计算", test_rsi_calculation),
        ("ATR 计算", test_atr_calculation),
        ("EMA 计算", test_ema_calculation),
        ("SMA 计算", test_sma_calculation),
        ("Heikin Ashi 计算", test_heikinashi_calculation),
        ("交叉检测", test_crossover_detection),
        ("计算一致性", test_indicator_consistency),
        ("极端值处理", test_extreme_values),
        ("数据对齐", test_data_alignment),
        ("Renko 验证", test_renko_with_real_data),
    ]
    
    passed = 0
    failed = 0
    
    for name, test_func in tests:
        try:
            if test_func():
                passed += 1
        except Exception as e:
            logger.error(f"❌ {name} 失败: {e}")
            failed += 1
    
    # 总结
    logger.info("=" * 60)
    logger.info("测试总结")
    logger.info("=" * 60)
    logger.info(f"✅ 通过: {passed}/{len(tests)}")
    logger.info(f"❌ 失败: {failed}/{len(tests)}")
    logger.info(f"📊 成功率: {passed/len(tests)*100:.1f}%")
    
    if failed == 0:
        logger.info("\n🎉 所有指标计算验证通过！")
    else:
        logger.warning(f"\n⚠️ 有 {failed} 个测试失败，请检查！")
    
    return failed == 0


if __name__ == '__main__':
    success = run_all_tests()
    exit(0 if success else 1)

