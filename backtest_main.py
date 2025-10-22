"""
主回测脚本
使用历史数据验证 ALGOX 策略
"""
import sys
from pathlib import Path
from datetime import datetime, timedelta
from loguru import logger

from src.backtest.data_loader import HistoricalDataLoader
from src.backtest.backtest_engine import BacktestEngine
from src.backtest.reporter import BacktestReporter
from src.backtest.visualizer import BacktestVisualizer
from src.utils.config_loader import load_config


def main():
    """主函数"""
    
    # 加载回测配置（先加载配置，以便获取日志级别）
    config = load_config('config/backtest_config.yaml')
    
    # 从配置文件读取日志级别
    log_level = config.get('logging', {}).get('level', 'INFO')
    
    # 配置日志
    logger.remove()
    logger.add(sys.stdout, level=log_level)
    logger.add("logs/backtest_{time}.log", level="DEBUG", rotation="10 MB")
    
    logger.info("=" * 80)
    logger.info("                     ALGOX 策略回测系统")
    logger.info("=" * 80)
    logger.info(f"🔧 日志级别: {log_level}")
    
    # 回测参数
    SYMBOL = config['exchange']['symbol']
    TIMEFRAME = config['strategy']['timeframe']
    PROXY = config['exchange'].get('proxy', 'http://127.0.0.1:7890')
    
    # 回测时间范围
    DAYS_BACK = config['backtest'].get('days_back', 7)
    END_DATE = datetime.now()
    START_DATE = END_DATE - timedelta(days=DAYS_BACK)
    
    logger.info(f"\n📅 回测配置")
    logger.info(f"  交易对:     {SYMBOL}")
    logger.info(f"  时间框架:   {TIMEFRAME}")
    logger.info(f"  开始时间:   {START_DATE.strftime('%Y-%m-%d %H:%M')}")
    logger.info(f"  结束时间:   {END_DATE.strftime('%Y-%m-%d %H:%M')}")
    
    # 1. 加载历史数据
    logger.info("\n" + "=" * 80)
    logger.info("步骤 1/3: 加载历史数据")
    logger.info("=" * 80)
    
    data_loader = HistoricalDataLoader(
        exchange_id='binance',
        proxy=PROXY
    )
    
    # 获取基础时间框架数据
    base_df = data_loader.fetch_ohlcv(
        symbol=SYMBOL,
        timeframe=TIMEFRAME,
        since=START_DATE,
        until=END_DATE
    )
    
    if base_df.empty:
        logger.error("❌ 未能获取历史数据，退出")
        return
    
    # 获取高级时间框架数据（用于 Heikin Ashi 和 Renko）
    htf_multiplier = config['strategy'].get('htf_multiplier', 18)
    htf_data = data_loader.get_multiple_timeframes(
        symbol=SYMBOL,
        base_timeframe=TIMEFRAME,
        multiplier=htf_multiplier,
        since=START_DATE,
        until=END_DATE
    )
    
    htf_df = htf_data['htf']
    
    # 2. 运行回测
    logger.info("\n" + "=" * 80)
    logger.info("步骤 2/3: 运行回测")
    logger.info("=" * 80)
    
    # 准备回测配置
    backtest_config = {
        # 策略类型
        'setup_type': config['strategy'].get('setup_type', 'Open/Close'),
        'filter_type': config['strategy'].get('filter_type', 'No Filtering'),
        'tps_type': config['strategy'].get('tps_type', 'Trailing'),
        
        # RSI 参数
        'rsi_period': config['strategy'].get('rsi_period', 7),
        'rsi_high': config['strategy'].get('rsi_high', 45),
        'rsi_low': config['strategy'].get('rsi_low', 10),
        
        # ATR 过滤参数
        'atr_filter_period': config['strategy'].get('atr_filter_period', 5),
        'atr_filter_ma_period': config['strategy'].get('atr_filter_ma_period', 5),
        'atr_filter_ma_type': config['strategy'].get('atr_filter_ma_type', 'EMA'),
        
        # 风险管理 ATR 参数（止盈止损计算）
        'atr_risk_period': config['strategy'].get('atr_risk_period', 20),
        'profit_factor': config['strategy'].get('profit_factor', 2.5),
        'stop_factor': config['strategy'].get('stop_factor', 1.0),
        
        # 分批止盈配置
        'enable_partial_exits': config['strategy'].get('enable_partial_exits', False),
        'tp1_factor': config['strategy'].get('tp1_factor', 1.5),
        'tp2_factor': config['strategy'].get('tp2_factor', 2.0),
        'tp1_percent': config['strategy'].get('tp1_percent', 50) / 100,  # 转换为小数
        'tp2_percent': config['strategy'].get('tp2_percent', 30) / 100,  # 转换为小数
        
        # 最大回撤保护
        'max_drawdown_percent': config['backtest'].get('max_drawdown_percent', 10),
        
        # 时间框架
        'htf_multiplier': htf_multiplier,
        
        # 资金管理
        'initial_capital': config['backtest'].get('initial_capital', 10000.0),
        'position_size': config['backtest'].get('position_size', 0.95),
        
        # 风险管理（分批止盈 - 旧配置，保留兼容性）
        'equity_per_trade': config.get('risk', {}).get('equity_per_trade', 50),
        'tp1_qty_percent': config.get('risk', {}).get('tp1_qty_percent', 50),
        'tp2_qty_percent': config.get('risk', {}).get('tp2_qty_percent', 30),
        'tp3_qty_percent': config.get('risk', {}).get('tp3_qty_percent', 20),
    }
    
    engine = BacktestEngine(backtest_config)
    results = engine.run(base_df, htf_df)
    
    # 3. 生成报告
    logger.info("\n" + "=" * 80)
    logger.info("步骤 3/4: 生成回测报告")
    logger.info("=" * 80)
    
    reporter = BacktestReporter()
    reporter.print_results(results, backtest_config)
    
    # 保存结果
    output_dir = Path("backtest_results")
    output_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    trades_file = output_dir / f"trades_{timestamp}.csv"
    equity_file = output_dir / f"equity_{timestamp}.csv"
    chart_file = output_dir / f"chart_{timestamp}.png"
    equity_chart_file = output_dir / f"equity_{timestamp}.png"
    
    reporter.save_to_csv(results, str(trades_file))
    reporter.save_equity_curve(results, str(equity_file))
    
    # 生成图表
    logger.info("\n" + "=" * 80)
    logger.info("步骤 4/4: 生成可视化图表")
    logger.info("=" * 80)
    
    # 限制显示的K线数量（最后500根）
    display_df = base_df.tail(500) if len(base_df) > 500 else base_df
    
    visualizer = BacktestVisualizer()
    # visualizer.plot_results(
    #     df=display_df,
    #     trades=results['trades'],
    #     output_file=str(chart_file),
    #     timezone='Asia/Shanghai'
    # )
    
    visualizer.plot_equity_curve(
        equity_df=results['equity_curve'],
        output_file=str(equity_chart_file),
        timezone='Asia/Shanghai'
    )
    
    # 生成摘要
    summary = reporter.generate_summary(results)
    logger.info("\n📊 回测摘要")
    logger.info("-" * 80)
    for key, value in summary.items():
        logger.info(f"  {key:12s}: {value}")
    
    # 数据完整性检查
    if results.get('lookahead_checks'):
        logger.info("\n⚠️ 未来数据检查:")
        logger.info("-" * 80)
        for check in results['lookahead_checks']:
            logger.info(f"  {check}")
    else:
        logger.info("\n✅ 未发现未来数据泄露")
    
    logger.info("\n📁 输出文件:")
    logger.info("-" * 80)
    logger.info(f"  交易记录: {trades_file}")
    logger.info(f"  权益曲线: {equity_file}")
    # logger.info(f"  K线图表: {chart_file}")
    logger.info(f"  权益图表: {equity_chart_file}")
    
    logger.info("\n" + "=" * 80)
    logger.info("✅ 回测完成！")
    logger.info("=" * 80)


if __name__ == '__main__':
    main()

