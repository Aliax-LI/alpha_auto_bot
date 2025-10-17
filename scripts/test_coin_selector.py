#!/usr/bin/env python3
"""测试选币策略模块"""
import sys
from pathlib import Path
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.strategy.coin_selector import coin_selector
from src.core.data_fetcher import data_fetcher
from src.indicators.technical import technical_indicators
from src.monitor.logger import system_logger
from loguru import logger


def print_section(title: str):
    """打印章节标题"""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)


def test_get_markets():
    """测试获取市场列表"""
    print_section("1. 测试获取USDT永续合约市场")
    
    try:
        symbols = data_fetcher.get_usdt_perpetual_symbols()
        
        if symbols:
            logger.success(f"✅ 成功获取 {len(symbols)} 个USDT永续合约")
            logger.info(f"前10个合约: {symbols[:10]}")
            return True
        else:
            logger.error("❌ 未获取到任何合约")
            return False
            
    except Exception as e:
        logger.exception(f"❌ 获取市场列表失败: {e}")
        return False


def test_ticker_data():
    """测试获取ticker数据"""
    print_section("2. 测试获取Ticker数据")
    
    try:
        symbols = data_fetcher.get_usdt_perpetual_symbols()
        if not symbols:
            logger.error("❌ 没有可用的交易对")
            return False
        
        # 测试单个ticker
        test_symbol = symbols[0]
        logger.info(f"测试获取 {test_symbol} 的ticker数据...")
        
        ticker = data_fetcher.fetch_ticker_24h(test_symbol)
        
        if ticker:
            logger.success(f"✅ 成功获取ticker数据")
            logger.info(f"  交易对: {ticker['symbol']}")
            logger.info(f"  最新价: {ticker.get('last', 'N/A')}")
            logger.info(f"  24h成交量: {ticker.get('volume', 0):,.0f} USDT")
            logger.info(f"  24h涨跌幅: {ticker.get('percentage', 0):.2f}%")
            return True
        else:
            logger.error("❌ 未获取到ticker数据")
            return False
            
    except Exception as e:
        logger.exception(f"❌ 获取ticker数据失败: {e}")
        return False


def test_volatility_calculation():
    """测试波动率计算"""
    print_section("3. 测试波动率计算")
    
    try:
        symbols = data_fetcher.get_usdt_perpetual_symbols()
        if not symbols:
            return False
        
        test_symbol = symbols[0]
        logger.info(f"测试计算 {test_symbol} 的波动率...")
        
        # 获取1小时K线
        df = data_fetcher.fetch_ohlcv_df(test_symbol, '1h', limit=50)
        
        if df.empty:
            logger.error("❌ 未获取到K线数据")
            return False
        
        # 计算波动率
        volatility = coin_selector.calculate_volatility(df)
        
        logger.success(f"✅ 波动率计算成功")
        logger.info(f"  交易对: {test_symbol}")
        logger.info(f"  波动率: {volatility:.4f} ({volatility*100:.2f}%)")
        logger.info(f"  最新价: {df['close'].iloc[-1]:.2f}")
        
        # 判断是否在合理范围
        if 0.03 <= volatility <= 0.15:
            logger.success(f"  ✅ 波动率在合理范围 [3%, 15%]")
        else:
            logger.warning(f"  ⚠️  波动率超出合理范围 [3%, 15%]")
        
        return True
        
    except Exception as e:
        logger.exception(f"❌ 波动率计算失败: {e}")
        return False


def test_ema_alignment():
    """测试EMA排列检查（新功能）"""
    print_section("4. 测试EMA排列检查")
    
    try:
        symbols = data_fetcher.get_usdt_perpetual_symbols()
        if not symbols:
            return False
        
        test_symbol = symbols[0]
        logger.info(f"测试检查 {test_symbol} 的EMA排列...")
        
        # 获取1小时K线
        df = data_fetcher.fetch_ohlcv_df(test_symbol, '1h', limit=100)
        
        if df.empty:
            logger.error("❌ 未获取到K线数据")
            return False
        
        # 检查EMA排列
        ema_result = coin_selector.check_ema_alignment(df)
        
        logger.success(f"✅ EMA排列检查成功")
        logger.info(f"  交易对: {test_symbol}")
        logger.info(f"  排列方向: {ema_result['direction']}")
        logger.info(f"  是否排列整齐: {ema_result['aligned']}")
        
        if ema_result['aligned']:
            logger.success(f"  ✅ EMA排列整齐，方向：{ema_result['direction'].upper()}")
        else:
            logger.warning(f"  ⚠️  EMA排列混乱")
        
        return True
        
    except Exception as e:
        logger.exception(f"❌ EMA排列检查失败: {e}")
        return False


def test_trend_stability():
    """测试趋势持续性检查（新功能）"""
    print_section("5. 测试趋势持续性检查")
    
    try:
        symbols = data_fetcher.get_usdt_perpetual_symbols()
        if not symbols:
            return False
        
        test_symbol = symbols[0]
        logger.info(f"测试检查 {test_symbol} 的趋势持续性...")
        
        # 获取1小时K线
        df = data_fetcher.fetch_ohlcv_df(test_symbol, '1h', limit=50)
        
        if df.empty:
            logger.error("❌ 未获取到K线数据")
            return False
        
        # 检查多头和空头趋势持续性
        stability_up = coin_selector.check_trend_stability(df, 'up')
        stability_down = coin_selector.check_trend_stability(df, 'down')
        
        logger.success(f"✅ 趋势持续性检查成功")
        logger.info(f"  交易对: {test_symbol}")
        logger.info(f"  多头趋势稳定: {stability_up['stable']}")
        logger.info(f"  符合多头趋势K线数: {stability_up['trend_bars']}/{stability_up['check_count']}")
        logger.info(f"  空头趋势稳定: {stability_down['stable']}")
        logger.info(f"  符合空头趋势K线数: {stability_down['trend_bars']}/{stability_down['check_count']}")
        
        return True
        
    except Exception as e:
        logger.exception(f"❌ 趋势持续性检查失败: {e}")
        return False


def test_pullback_quality():
    """测试回调质量评估（核心新功能）"""
    print_section("6. 测试回调质量评估 ⭐️ 核心功能")
    
    try:
        symbols = data_fetcher.get_usdt_perpetual_symbols()
        if not symbols:
            return False
        
        test_symbol = symbols[0]
        logger.info(f"测试评估 {test_symbol} 的回调质量...")
        
        # 获取15分钟K线
        df = data_fetcher.fetch_ohlcv_df(test_symbol, '15m', limit=100)
        
        if df.empty:
            logger.error("❌ 未获取到K线数据")
            return False
        
        # 评估多头和空头市场回调质量
        pullback_up = coin_selector.check_pullback_quality(df, 'up')
        pullback_down = coin_selector.check_pullback_quality(df, 'down')
        
        logger.success(f"✅ 回调质量评估成功")
        logger.info(f"  交易对: {test_symbol}")
        logger.info(f"  --- 多头市场回调 ---")
        logger.info(f"  回调质量评分: {pullback_up['quality_score']:.1f}/10")
        logger.info(f"  回调次数: {pullback_up['pullback_count']}")
        logger.info(f"  健康回调次数: {pullback_up['healthy_pullbacks']}")
        logger.info(f"  频率评分: {pullback_up['frequency_score']:.1f}/5")
        logger.info(f"  健康度评分: {pullback_up['health_score']:.1f}/5")
        
        logger.info(f"  --- 空头市场回调 ---")
        logger.info(f"  回调质量评分: {pullback_down['quality_score']:.1f}/10")
        logger.info(f"  回调次数: {pullback_down['pullback_count']}")
        logger.info(f"  健康回调次数: {pullback_down['healthy_pullbacks']}")
        
        if pullback_up['quality_score'] >= 3 or pullback_down['quality_score'] >= 3:
            logger.success(f"  ✅ 回调质量良好，适合回调交易")
        else:
            logger.warning(f"  ⚠️  回调质量较差")
        
        return True
        
    except Exception as e:
        logger.exception(f"❌ 回调质量评估失败: {e}")
        return False


def test_intraday_volatility():
    """测试日内波动特征计算（新功能）"""
    print_section("7. 测试日内波动特征")
    
    try:
        symbols = data_fetcher.get_usdt_perpetual_symbols()
        if not symbols:
            return False
        
        test_symbol = symbols[0]
        logger.info(f"测试计算 {test_symbol} 的日内波动特征...")
        
        # 获取5分钟K线
        df = data_fetcher.fetch_ohlcv_df(test_symbol, '5m', limit=100)
        
        if df.empty:
            logger.error("❌ 未获取到K线数据")
            return False
        
        # 计算日内波动
        intraday_vol = coin_selector.calculate_intraday_volatility(df)
        
        logger.success(f"✅ 日内波动特征计算成功")
        logger.info(f"  交易对: {test_symbol}")
        logger.info(f"  平均5分钟波动: {intraday_vol['avg_range']*100:.3f}%")
        logger.info(f"  是否适合日内交易: {intraday_vol['suitable']}")
        logger.info(f"  波动稳定性: {intraday_vol['stability']:.3f}")
        
        if intraday_vol['suitable']:
            logger.success(f"  ✅ 波动适中，适合日内交易")
        else:
            logger.warning(f"  ⚠️  波动不适合日内交易")
        
        return True
        
    except Exception as e:
        logger.exception(f"❌ 日内波动特征计算失败: {e}")
        return False


def test_liquidity_check():
    """测试流动性检查"""
    print_section("4. 测试流动性评估")
    
    try:
        symbols = data_fetcher.get_usdt_perpetual_symbols()
        if not symbols:
            return False
        
        test_symbol = symbols[0]
        logger.info(f"测试评估 {test_symbol} 的流动性...")
        
        # 获取订单簿
        orderbook = data_fetcher.fetch_orderbook_analysis(test_symbol, limit=10)
        
        if not orderbook:
            logger.error("❌ 未获取到订单簿数据")
            return False
        
        logger.success(f"✅ 订单簿数据获取成功")
        logger.info(f"  交易对: {test_symbol}")
        logger.info(f"  买盘深度: {orderbook.get('bid_depth', 0):,.2f} USDT")
        logger.info(f"  卖盘深度: {orderbook.get('ask_depth', 0):,.2f} USDT")
        logger.info(f"  总流动性: {orderbook.get('bid_depth', 0) + orderbook.get('ask_depth', 0):,.2f} USDT")
        logger.info(f"  买卖比: {orderbook.get('bid_ask_ratio', 0):.2f}")
        logger.info(f"  价差: {orderbook.get('spread_pct', 0):.4f}%")
        
        # 判断流动性
        liquidity = orderbook.get('bid_depth', 0) + orderbook.get('ask_depth', 0)
        if liquidity > 100000:
            logger.success(f"  ✅ 流动性充足 (>10万USDT)")
        else:
            logger.warning(f"  ⚠️  流动性不足 (<10万USDT)")
        
        return True
        
    except Exception as e:
        logger.exception(f"❌ 流动性评估失败: {e}")
        return False


def test_adx_calculation():
    """测试ADX计算"""
    print_section("5. 测试ADX趋势强度计算")
    
    try:
        symbols = data_fetcher.get_usdt_perpetual_symbols()
        if not symbols:
            return False
        
        test_symbol = symbols[0]
        logger.info(f"测试计算 {test_symbol} 的ADX...")
        
        # 获取1小时K线
        df = data_fetcher.fetch_ohlcv_df(test_symbol, '1h', limit=50)
        
        if df.empty:
            logger.error("❌ 未获取到K线数据")
            return False
        
        # 计算ADX
        df = technical_indicators.calculate_adx(df)
        adx = df['adx'].iloc[-1]
        plus_di = df['plus_di'].iloc[-1]
        minus_di = df['minus_di'].iloc[-1]
        
        logger.success(f"✅ ADX计算成功")
        logger.info(f"  交易对: {test_symbol}")
        logger.info(f"  ADX: {adx:.2f}")
        logger.info(f"  +DI: {plus_di:.2f}")
        logger.info(f"  -DI: {minus_di:.2f}")
        
        # 判断趋势
        if adx > 25:
            trend_direction = "上升趋势" if plus_di > minus_di else "下降趋势"
            logger.success(f"  ✅ 有明显趋势 (ADX>25) - {trend_direction}")
        else:
            logger.warning(f"  ⚠️  趋势不明显 (ADX<25)")
        
        return True
        
    except Exception as e:
        logger.exception(f"❌ ADX计算失败: {e}")
        return False


def test_coin_evaluation():
    """测试单个币种评估"""
    print_section("6. 测试单个币种综合评估")
    
    try:
        symbols = data_fetcher.get_usdt_perpetual_symbols()
        if not symbols:
            return False
        
        # 获取所有ticker
        logger.info("获取所有ticker数据（这可能需要一些时间）...")
        tickers = data_fetcher.fetch_all_tickers(symbols)
        
        if not tickers:
            logger.error("❌ 未获取到ticker数据")
            return False
        
        logger.success(f"✅ 成功获取 {len(tickers)} 个ticker")
        
        # 测试评估几个币种
        test_count = min(3, len(symbols))
        logger.info(f"\n测试评估前 {test_count} 个币种...")
        
        for i in range(test_count):
            symbol = symbols[i]
            if symbol not in tickers:
                continue
            
            logger.info(f"\n{'─' * 40}")
            logger.info(f"评估 {symbol}...")
            
            result = coin_selector.evaluate_coin(symbol, tickers[symbol])
            
            if result['passed']:
                logger.success(f"  ✅ {symbol} 通过筛选（日内顺势回调交易）")
                logger.info(f"    综合评分: {result['score']:.2f}/52")
                logger.info(f"    趋势方向: {result.get('trend_direction', 'N/A').upper()}")
                logger.info(f"    趋势明确性: {result.get('trend_clarity', 0):.1f}")
                logger.info(f"    ADX强度: {result['adx']:.1f}")
                logger.info(f"    趋势持续性: {result.get('stability', 0)}/10根K线")
                logger.info(f"    回调质量: {result.get('pullback_quality', 0):.1f}/10 ⭐️")
                logger.info(f"    回调次数: {result.get('pullback_count', 0)}")
                logger.info(f"    日内波动: {result.get('intraday_range', 0)*100:.3f}%")
                logger.info(f"    24h成交量: {result['volume_24h']/1000000:.1f}M USDT")
                logger.info(f"    流动性: {result['liquidity']/1000:.0f}K USDT")
                
                # 显示评分细节
                if 'score_details' in result:
                    details = result['score_details']
                    logger.info(f"    评分明细: 明确性={details.get('trend_clarity', 0):.1f}, "
                              f"强度={details.get('trend_strength', 0):.1f}, "
                              f"持续={details.get('stability', 0):.1f}, "
                              f"回调={details.get('pullback', 0):.1f}, "
                              f"流动={details.get('liquidity', 0):.1f}, "
                              f"成交量={details.get('volume', 0):.1f}, "
                              f"波动={details.get('volatility', 0):.1f}")
            else:
                logger.warning(f"  ⚠️  {symbol} 未通过筛选")
                logger.info(f"    原因: {result.get('reason', 'unknown')}")
        
        return True
        
    except Exception as e:
        logger.exception(f"❌ 币种评估失败: {e}")
        return False


def test_full_selection():
    """测试完整选币流程"""
    print_section("7. 测试完整选币流程")
    
    try:
        logger.info("开始完整选币流程（这可能需要几分钟）...")
        logger.warning("⚠️  注意：这将扫描所有USDT永续合约")
        
        # 执行选币
        start_time = datetime.now()
        selected_coins = coin_selector.select_coins()
        elapsed_time = (datetime.now() - start_time).total_seconds()
        
        if selected_coins:
            logger.success(f"✅ 选币完成！耗时: {elapsed_time:.2f}秒")
            logger.info(f"\n选中的币种（共 {len(selected_coins)} 个）:")
            
            for i, symbol in enumerate(selected_coins, 1):
                logger.opt(colors=True).info(f"  <cyan>{i:2d}. {symbol}</cyan>")
            
            return True
        else:
            logger.warning("⚠️  未选中任何币种")
            return False
            
    except Exception as e:
        logger.exception(f"❌ 选币流程失败: {e}")
        return False


def test_selection_details():
    """测试选币详细信息"""
    print_section("8. 查看选币详细信息")
    
    try:
        # 获取已选择的币种
        selected_coins = coin_selector.get_selected_coins()
        
        if not selected_coins:
            logger.warning("⚠️  没有已选择的币种，先执行选币...")
            selected_coins = coin_selector.select_coins()
        
        if not selected_coins:
            logger.error("❌ 仍然没有选中的币种")
            return False
        
        logger.info(f"\n当前选中的 {len(selected_coins)} 个币种详情：\n")
        
        # 获取ticker数据
        tickers = data_fetcher.fetch_all_tickers()
        
        # 创建表格显示
        print(f"{'排名':<6}{'交易对':<20}{'评分':<8}{'24h成交量':<18}{'涨跌幅':<10}{'价格':<12}")
        print("─" * 80)
        
        for i, symbol in enumerate(selected_coins, 1):
            if symbol in tickers:
                ticker = tickers[symbol]
                
                # 重新评估获取评分
                result = coin_selector.evaluate_coin(symbol, ticker)
                
                score = result.get('score', 0) if result['passed'] else 0
                volume = ticker.get('volume', 0)
                percentage = ticker.get('percentage', 0)
                price = ticker.get('last', 0)
                
                # 颜色标记
                pct_color = 'green' if percentage > 0 else 'red'
                
                logger.opt(colors=True).info(
                    f"<cyan>{i:<6}</cyan>"
                    f"<yellow>{symbol:<20}</yellow>"
                    f"<magenta>{score:>6.2f}</magenta>  "
                    f"{volume:>16,.0f}  "
                    f"<{pct_color}>{percentage:>8.2f}%</{pct_color}> "
                    f"{price:>10.2f}"
                )
        
        return True
        
    except Exception as e:
        logger.exception(f"❌ 获取详细信息失败: {e}")
        return False


def run_all_tests():
    """运行所有测试"""
    logger.info("\n" + "🚀" * 40)
    logger.info("  OKX 选币策略测试")
    logger.info("🚀" * 40)
    
    results = []
    
    # 运行各项测试
    tests = [
        ("获取市场列表", test_get_markets),
        ("获取Ticker数据", test_ticker_data),
        ("计算波动率", test_volatility_calculation),
        ("EMA排列检查 [新]", test_ema_alignment),
        ("趋势持续性检查 [新]", test_trend_stability),
        ("回调质量评估 [新] ⭐️", test_pullback_quality),
        ("日内波动特征 [新]", test_intraday_volatility),
        ("评估流动性", test_liquidity_check),
        ("计算ADX", test_adx_calculation),
        ("币种评估 [已优化]", test_coin_evaluation),
        ("完整选币流程 [已优化]", test_full_selection),
        ("查看详细信息", test_selection_details),
    ]
    
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            logger.exception(f"测试 [{name}] 出现异常")
            results.append((name, False))
    
    # 总结
    print_section("测试结果汇总")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        logger.opt(colors=True).info(f"{name:.<40} <{'green' if result else 'red'}>{status}</>")
    
    print("\n" + "=" * 80)
    logger.opt(colors=True).info(
        f"总计: <cyan>{passed}/{total}</cyan> 测试通过 "
        f"(<{'green' if passed == total else 'yellow'}>{passed/total*100:.1f}%</>)"
    )
    print("=" * 80 + "\n")
    
    if passed == total:
        logger.success("🎉 所有测试通过！选币策略运行正常！")
        return 0
    else:
        logger.warning("⚠️  部分测试未通过，请检查配置和网络连接")
        return 1


if __name__ == '__main__':
    import time
    
    try:
        # 添加一些提示
        logger.info("=" * 80)
        logger.info("📋 测试说明:")
        logger.info("  1. 确保已配置正确的API密钥")
        logger.info("  2. 确保网络连接正常（可能需要代理）")
        logger.info("  3. 测试过程可能需要几分钟")
        logger.info("  4. 某些测试需要请求大量API，请耐心等待")
        logger.info("=" * 80)
        logger.info("")
        
        # 等待用户确认
        logger.warning("测试将在 3 秒后开始...")
        time.sleep(3)
        
        # 运行测试
        exit_code = run_all_tests()
        
        sys.exit(exit_code)
        
    except KeyboardInterrupt:
        logger.warning("\n\n⚠️  测试被用户中断")
        sys.exit(1)
    except Exception as e:
        logger.exception("❌ 测试过程中出现未预期的错误")
        sys.exit(1)

