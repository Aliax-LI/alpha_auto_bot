#!/usr/bin/env python3
"""信号诊断脚本 - 详细分析为什么没有生成交易信号"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.strategy.trend_analyzer import trend_analyzer
from src.strategy.signal_generator import SignalGenerator
from src.core.data_fetcher import data_fetcher
from loguru import logger


def display_rebound_scores(score_result, df, trend_direction):
    """显示反弹入场模式评分"""
    logger.info("\n🎯 反弹入场模式评分详情")
    logger.info("=" * 60)
    
    details = score_result['details']
    rsi = df['rsi'].iloc[-1] if 'rsi' in df.columns else 50
    
    # RSI反弹/回落
    if trend_direction == 'down':
        logger.info("\n1️⃣  RSI反弹 (最高4分)")
        rsi_bounce = details.get('rsi_bounce', {})
        logger.info(f"   得分: {rsi_bounce.get('score', 0)}/4")
        logger.info(f"   RSI当前: {rsi:.2f}")
        if rsi < 30:
            rsi_prev = df['rsi'].iloc[-2] if len(df) > 1 else 50
            if rsi > rsi_prev:
                logger.success(f"   ✅ RSI开始反弹 ({rsi_prev:.1f} → {rsi:.1f})")
            else:
                logger.warning(f"   ⚠️  RSI仍在下降 ({rsi_prev:.1f} → {rsi:.1f})")
    else:
        logger.info("\n1️⃣  RSI回落 (最高4分)")
        rsi_drop = details.get('rsi_drop', {})
        logger.info(f"   得分: {rsi_drop.get('score', 0)}/4")
        logger.info(f"   RSI当前: {rsi:.2f}")
        if rsi > 70:
            rsi_prev = df['rsi'].iloc[-2] if len(df) > 1 else 50
            if rsi < rsi_prev:
                logger.success(f"   ✅ RSI开始回落 ({rsi_prev:.1f} → {rsi:.1f})")
            else:
                logger.warning(f"   ⚠️  RSI仍在上升 ({rsi_prev:.1f} → {rsi:.1f})")
    
    # KDJ金叉/死叉
    logger.info("\n2️⃣  KDJ交叉 (最高3分)")
    kdj = details.get('kdj', {})
    logger.info(f"   得分: {kdj.get('score', 0)}/3")
    if kdj.get('valid'):
        logger.success(f"   ✅ KDJ{'金叉' if trend_direction == 'down' else '死叉'}形成")
    
    # K线形态
    logger.info("\n3️⃣  K线形态 (最高3分)")
    pattern = details.get('pattern', {})
    logger.info(f"   得分: {pattern.get('score', 0)}/3")
    if pattern.get('valid'):
        logger.success(f"   ✅ 识别到{pattern.get('pattern', 'N/A')}")
    
    # 成交量
    logger.info("\n4️⃣  成交量确认 (最高2分)")
    volume = details.get('volume', {})
    logger.info(f"   得分: {volume.get('score', 0)}/2")


def display_breakout_scores(score_result, df, trend_direction):
    """显示突破入场模式评分"""
    logger.info("\n🎯 突破入场模式评分详情")
    logger.info("=" * 60)
    
    details = score_result['details']
    
    # 突破关键位
    logger.info("\n1️⃣  突破关键位 (最高5分)")
    breakout = details.get('breakout', {})
    logger.info(f"   得分: {breakout.get('score', 0)}/5")
    if breakout.get('valid'):
        logger.success(f"   ✅ 突破价位: {breakout.get('level', 0):.4f}")
    
    # 成交量放大
    logger.info("\n2️⃣  成交量放大 (最高4分)")
    volume = details.get('volume', {})
    logger.info(f"   得分: {volume.get('score', 0)}/4")
    if volume.get('valid'):
        logger.success(f"   ✅ 成交量比率: {volume.get('ratio', 0):.2f}x")
    
    # RSI突破50
    logger.info("\n3️⃣  RSI突破50 (最高2分)")
    rsi = details.get('rsi', {})
    logger.info(f"   得分: {rsi.get('score', 0)}/2")
    
    # MACD金叉/死叉
    logger.info("\n4️⃣  MACD交叉 (最高3分)")
    macd = details.get('macd', {})
    logger.info(f"   得分: {macd.get('score', 0)}/3")


def display_trend_following_scores(score_result, df, trend_direction):
    """显示趋势跟随模式评分"""
    logger.info("\n🎯 趋势跟随模式评分详情")
    logger.info("=" * 60)
    
    details = score_result['details']
    
    # ADX强趋势
    logger.info("\n1️⃣  ADX强趋势 (最高5分)")
    adx = details.get('adx', {})
    logger.info(f"   得分: {adx.get('score', 0)}/5")
    if adx.get('valid'):
        logger.success(f"   ✅ ADX: {adx.get('adx', 0):.2f}")
    
    # EMA顺势
    logger.info("\n2️⃣  EMA顺势 (最高3分)")
    ema = details.get('ema', {})
    logger.info(f"   得分: {ema.get('score', 0)}/3")
    
    # RSI顺势
    logger.info("\n3️⃣  RSI顺势 (最高2分)")
    rsi = details.get('rsi', {})
    logger.info(f"   得分: {rsi.get('score', 0)}/2")
    
    # K线方向一致
    logger.info("\n4️⃣  K线方向一致 (最高2分)")
    candle = details.get('candle_direction', {})
    logger.info(f"   得分: {candle.get('score', 0)}/2")
    
    # 成交量持续
    logger.info("\n5️⃣  成交量持续 (最高2分)")
    volume = details.get('volume', {})
    logger.info(f"   得分: {volume.get('score', 0)}/2")


def display_pullback_scores(score_result, df, trend_direction):
    """显示回调入场模式评分"""
    logger.info("\n🎯 回调入场模式评分详情")
    logger.info("=" * 60)
    
    details = score_result['details']
    
    # 斐波那契
    logger.info("\n1️⃣  斐波那契回撤 (最高2分)")
    fib = details.get('fibonacci', {})
    logger.info(f"   得分: {fib.get('score', 0)}/2")
    
    # 支撑阻力
    logger.info("\n2️⃣  支撑阻力位 (最高2分)")
    sr = details.get('support_resistance', {})
    logger.info(f"   得分: {sr.get('score', 0)}/2")
    
    # RSI
    logger.info("\n3️⃣  RSI条件 (最高1分)")
    rsi = details.get('rsi', {})
    logger.info(f"   得分: {rsi.get('score', 0)}/1")
    
    # KDJ
    logger.info("\n4️⃣  KDJ交叉 (最高1分)")
    kdj = details.get('kdj', {})
    logger.info(f"   得分: {kdj.get('score', 0)}/1")
    
    # MACD
    logger.info("\n5️⃣  MACD收敛 (最高1分)")
    macd = details.get('macd', {})
    logger.info(f"   得分: {macd.get('score', 0)}/1")
    
    # K线形态
    logger.info("\n6️⃣  K线形态 (最高2分)")
    pattern = details.get('candlestick', {})
    logger.info(f"   得分: {pattern.get('score', 0)}/2")
    
    # 成交量
    logger.info("\n7️⃣  成交量确认 (最高2分)")
    volume = details.get('volume', {})
    logger.info(f"   得分: {volume.get('score', 0)}/2")
    
    # 布林带
    logger.info("\n8️⃣  布林带 (最高1分)")
    bb = details.get('bollinger', {})
    logger.info(f"   得分: {bb.get('score', 0)}/1")


def diagnose_signal(symbol: str = "ARB/USDT:USDT"):
    """
    诊断为什么没有生成交易信号
    
    Args:
        symbol: 交易对符号
    """
    logger.info("=" * 80)
    logger.info(f"  {symbol} 信号诊断")
    logger.info("=" * 80)
    
    # 获取数据
    logger.info("获取市场数据...")
    data_5m = data_fetcher.fetch_ohlcv_df(symbol, '5m', limit=200)
    data_15m = data_fetcher.fetch_ohlcv_df(symbol, '15m', limit=100)
    data_1h = data_fetcher.fetch_ohlcv_df(symbol, '1h', limit=100)
    
    if data_5m.empty:
        logger.error("数据获取失败")
        return
    
    current_price = data_5m['close'].iloc[-1]
    logger.success(f"✅ 当前价格: {current_price:.4f} USDT\n")
    
    # 趋势分析
    logger.info("分析趋势...")
    trend_info = trend_analyzer.analyze(data_5m, data_15m, data_1h)
    
    logger.info(f"趋势方向: {trend_info.direction.upper()}")
    logger.info(f"趋势强度: {trend_info.strength:.2%}")
    logger.info(f"是否强趋势: {trend_info.is_strong}\n")
    
    if not trend_info.is_strong:
        logger.warning("❌ 趋势不够强，无法生成信号")
        logger.info(f"   趋势强度: {trend_info.strength:.2%} (需要 >= 60%)")
        return
    
    # 详细评分分析
    logger.info("=" * 80)
    logger.info("  详细评分分析")
    logger.info("=" * 80)
    
    signal_gen = SignalGenerator()
    trend_direction = trend_info.direction
    
    # 先计算所有技术指标（重要！）
    logger.info("\n计算技术指标...")
    from src.indicators.technical import technical_indicators
    df_with_indicators = technical_indicators.calculate_all_indicators(data_5m.copy())
    logger.success("✅ 指标计算完成\n")
    
    # 检测入场模式
    logger.info("🔍 检测入场模式...")
    from src.strategy.signal_generator import EntryMode
    entry_mode = signal_gen.detect_entry_mode(df_with_indicators, trend_info)
    logger.success(f"✅ 当前入场模式: {entry_mode.value.upper()}")
    
    # 模式说明
    mode_descriptions = {
        'pullback': '回调入场 - 趋势中的健康回调',
        'breakout': '突破入场 - 趋势初期突破关键位',
        'trend_following': '趋势跟随 - 强趋势中顺势入场',
        'rebound': '反弹入场 - 超卖/超买后的反弹'
    }
    logger.info(f"   📝 说明: {mode_descriptions.get(entry_mode.value, '未知模式')}\n")
    
    # 根据入场模式调用相应的评分方法
    if entry_mode == EntryMode.REBOUND:
        score_result = signal_gen.score_rebound_entry(df_with_indicators, trend_direction)
        final_signal_type = 'up' if trend_direction == 'down' else 'down'
        display_rebound_scores(score_result, df_with_indicators, trend_direction)
    elif entry_mode == EntryMode.BREAKOUT:
        score_result = signal_gen.score_breakout_entry(df_with_indicators, trend_direction)
        final_signal_type = trend_direction
        display_breakout_scores(score_result, df_with_indicators, trend_direction)
    elif entry_mode == EntryMode.TREND_FOLLOWING:
        score_result = signal_gen.score_trend_following_entry(df_with_indicators, trend_direction)
        final_signal_type = trend_direction
        display_trend_following_scores(score_result, df_with_indicators, trend_direction)
    else:  # PULLBACK
        score_result = signal_gen.score_pullback_entry(df_with_indicators, trend_direction)
        final_signal_type = trend_direction
        display_pullback_scores(score_result, df_with_indicators, trend_direction)
    
    # 总评分
    total_score = score_result['total_score']
    min_score = score_result['min_score']
    
    logger.info("\n" + "=" * 80)
    logger.info(f"  总评分: {total_score}/{min_score}")
    logger.info("=" * 80)
    
    if total_score >= min_score:
        logger.success(f"✅ 评分达标 ({total_score} >= {min_score})，可以生成信号！")
        logger.success(f"   信号类型: {'做多 (LONG)' if final_signal_type == 'up' else '做空 (SHORT)'}")
    else:
        logger.error(f"❌ 评分不足 ({total_score} < {min_score})，无法生成信号")
        logger.info(f"\n需要提升 {min_score - total_score} 分才能生成信号")
    
    # 显示模式特定建议
    logger.info("\n" + "=" * 80)
    logger.info("  💡 智能建议")
    logger.info("=" * 80)
    
    rsi = df_with_indicators['rsi'].iloc[-1] if 'rsi' in df_with_indicators.columns else 50
    adx = df_with_indicators['adx'].iloc[-1] if 'adx' in df_with_indicators.columns else 0
    
    if entry_mode == EntryMode.REBOUND:
        logger.info(f"\n当前模式: 反弹入场 ({'做多反弹' if trend_direction == 'down' else '做空回落'})")
        logger.info("等待关键信号:")
        if trend_direction == 'down':
            logger.info(f"  • RSI反弹确认 (当前{rsi:.1f}, 需要>25且上升)")
            logger.info("  • KDJ低位金叉 (K上穿D且K<30)")
            logger.info("  • 出现看涨K线形态")
        else:
            logger.info(f"  • RSI回落确认 (当前{rsi:.1f}, 需要<75且下降)")
            logger.info("  • KDJ高位死叉 (K下穿D且K>70)")
            logger.info("  • 出现看跌K线形态")
    
    elif entry_mode == EntryMode.BREAKOUT:
        logger.info("\n当前模式: 突破入场")
        logger.info("等待关键信号:")
        logger.info("  • 价格突破关键支撑/阻力位")
        logger.info("  • 成交量显著放大 (>1.5倍平均)")
        logger.info("  • RSI突破50中线")
        logger.info("  • MACD金叉/死叉确认")
    
    elif entry_mode == EntryMode.TREND_FOLLOWING:
        logger.info("\n当前模式: 趋势跟随")
        logger.info("等待关键信号:")
        logger.info(f"  • ADX保持强势 (当前{adx:.1f}, 需要>30)")
        logger.info("  • EMA多头/空头排列")
        logger.info(f"  • RSI保持顺势区间 (当前{rsi:.1f})")
        logger.info("  • 连续顺势K线")
    
    else:  # PULLBACK
        logger.info("\n当前模式: 回调入场")
        logger.info("等待关键信号:")
        logger.info("  • 价格回调到斐波那契关键位")
        logger.info("  • 触及支撑/阻力位")
        logger.info("  • RSI回到合理区间")
        logger.info("  • KDJ金叉/死叉")
    
    # 通用建议
    logger.info("\n💡 下一步行动:")
    if total_score < min_score:
        logger.info(f"   1. 持续监控：每5-10分钟检查一次")
        logger.info(f"   2. 等待关键信号形成")
        logger.info(f"   3. 当前缺少 {min_score - total_score} 分")
    else:
        logger.success("   ✅ 可以入场交易！")
        logger.info(f"   1. 确认入场价格: {df_with_indicators['close'].iloc[-1]:.4f}")
        logger.info("   2. 设置止损止盈")
        logger.info("   3. 控制仓位大小")
    
    logger.info("\n" + "=" * 80)


def main():
    """主函数"""
    import argparse
    import time
    from datetime import datetime
    
    parser = argparse.ArgumentParser(description='诊断交易信号')
    parser.add_argument('symbol', nargs='?', default='ARB/USDT:USDT', help='交易对符号')
    parser.add_argument('-w', '--watch', action='store_true', help='持续监控模式（每1分钟执行一次）')
    parser.add_argument('-i', '--interval', type=int, default=60, help='监控间隔（秒），默认60秒')
    args = parser.parse_args()
    
    # 标准化交易对格式
    symbol = args.symbol.upper()
    if ':' not in symbol and 'USDT' in symbol:
        # 如果没有:符号，添加:USDT后缀（合约）
        if not symbol.endswith(':USDT'):
            symbol = symbol.replace('USDT', '/USDT:USDT')
    
    if args.watch:
        # 持续监控模式
        logger.info(f"🔄 启动持续监控模式")
        logger.info(f"   币种: {symbol}")
        logger.info(f"   间隔: {args.interval}秒")
        logger.info(f"   按 Ctrl+C 停止监控\n")
        
        iteration = 0
        try:
            while True:
                iteration += 1
                current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                logger.info("\n" + "🔔" * 40)
                logger.info(f"第 {iteration} 次检查 - {current_time}")
                logger.info("🔔" * 40 + "\n")
                
                try:
                    diagnose_signal(symbol)
                except Exception as e:
                    logger.error(f"❌ 诊断过程出错: {e}")
                
                # 等待下一次执行
                logger.info(f"\n⏰ 等待 {args.interval} 秒后进行下一次检查...")
                logger.info(f"   下次检查时间: {datetime.fromtimestamp(time.time() + args.interval).strftime('%H:%M:%S')}")
                time.sleep(args.interval)
                
        except KeyboardInterrupt:
            logger.info("\n\n✋ 监控已停止")
            logger.info(f"   总共执行了 {iteration} 次检查")
            logger.info(f"   监控时长: {iteration * args.interval // 60} 分钟")
    else:
        # 单次执行模式
        diagnose_signal(symbol)


if __name__ == '__main__':
    main()
