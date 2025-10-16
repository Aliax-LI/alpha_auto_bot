"""OKX合约日内顺势回调交易系统 - 主程序"""
import time
import signal
import sys
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler

from src.core.data_fetcher import data_fetcher
from src.strategy.coin_selector import coin_selector
from src.strategy.trend_analyzer import trend_analyzer
from src.strategy.signal_generator import signal_generator
from src.strategy.position_sizer import position_sizer
from src.risk.risk_manager import risk_manager
from src.execution.trader import trader
from src.monitor.performance import performance_monitor
from src.utils.config import config
from src.utils.database import database
from src.monitor.logger import system_logger, trading_logger


class TradingSystem:
    """交易系统主类"""
    
    def __init__(self):
        """初始化"""
        self.running = False
        self.scheduler = BackgroundScheduler()
        self.system_config = config.get_system_config()
        self.loop_interval = self.system_config.get('loop_interval', 300)
        
        system_logger.info("Trading system initialized")
    
    def setup_signal_handlers(self):
        """设置信号处理器"""
        def signal_handler(sig, frame):
            system_logger.info("Received termination signal. Shutting down...")
            self.stop()
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    
    def setup_scheduler(self):
        """设置定时任务"""
        report_time = config.get('monitoring.report_time', '20:00')
        
        # 每日报告
        self.scheduler.add_job(
            self.generate_daily_report,
            'cron',
            hour=int(report_time.split(':')[0]),
            minute=int(report_time.split(':')[1])
        )
        
        # 数据库备份
        self.scheduler.add_job(
            database.backup,
            'cron',
            hour=2,
            minute=0
        )
        
        self.scheduler.start()
        system_logger.info("Scheduler started")
    
    def generate_daily_report(self):
        """生成日终报告"""
        try:
            performance_monitor.generate_daily_report()
        except Exception as e:
            system_logger.error(f"Error generating daily report: {e}")
    
    def process_symbol(self, symbol: str):
        """
        处理单个交易对
        
        Args:
            symbol: 交易对符号
        """
        try:
            # 1. 获取多周期数据
            data_5m = data_fetcher.fetch_ohlcv_df(symbol, '5m', limit=200)
            data_15m = data_fetcher.fetch_ohlcv_df(symbol, '15m', limit=100)
            data_1h = data_fetcher.fetch_ohlcv_df(symbol, '1h', limit=50)
            
            if data_5m.empty or data_15m.empty or data_1h.empty:
                system_logger.warning(f"Insufficient data for {symbol}")
                return
            
            # 2. 趋势分析
            trend = trend_analyzer.analyze(data_5m, data_15m, data_1h)
            
            if not trend.is_strong:
                system_logger.debug(f"{symbol}: Trend not strong enough")
                return
            
            system_logger.info(f"{symbol}: Strong {trend.direction} trend detected (strength={trend.strength:.2f})")
            
            # 3. 检查是否已有持仓
            from src.risk.stop_loss import stop_loss_manager
            existing_positions = stop_loss_manager.get_all_positions()
            
            for order_id, position in existing_positions.items():
                if position['symbol'] == symbol:
                    # 已有持仓，只监控不开新仓
                    trader.monitor_position(order_id)
                    return
            
            # 4. 生成交易信号
            signal = signal_generator.generate_signal(symbol, data_5m, trend)
            
            if not signal or signal.score < config.get('signal_scoring.min_score', 7):
                system_logger.debug(f"{symbol}: No valid signal")
                return
            
            system_logger.info(f"{symbol}: Signal generated - {signal}")
            
            # 5. 订单流确认
            from src.indicators.order_flow import order_flow_analyzer
            if not order_flow_analyzer.supports_signal(symbol, signal.signal_type):
                system_logger.info(f"{symbol}: Order flow does not support signal")
                database.add_signal({
                    'symbol': symbol,
                    'signal_type': signal.signal_type,
                    'score': signal.score,
                    'price': signal.entry_price,
                    'executed': False,
                    'not_executed_reason': 'order_flow_not_support',
                    'score_details': signal.score_details,
                })
                return
            
            # 6. 风控检查
            if not risk_manager.can_open_position():
                system_logger.warning(f"{symbol}: Risk manager prevents opening position")
                database.add_signal({
                    'symbol': symbol,
                    'signal_type': signal.signal_type,
                    'score': signal.score,
                    'price': signal.entry_price,
                    'executed': False,
                    'not_executed_reason': 'risk_check_failed',
                    'score_details': signal.score_details,
                })
                return
            
            # 7. 计算仓位
            position_info = position_sizer.calculate(signal)
            
            if not position_info:
                system_logger.error(f"{symbol}: Failed to calculate position size")
                return
            
            # 应用仓位倍数（如有连续亏损）
            multiplier = risk_manager.get_position_size_multiplier()
            if multiplier != 1.0:
                position_info['contracts'] *= multiplier
                position_info['position_size_usdt'] *= multiplier
                system_logger.info(f"{symbol}: Position size adjusted by {multiplier:.0%}")
            
            system_logger.info(
                f"{symbol}: Position size calculated - "
                f"{position_info['contracts']:.4f} contracts, "
                f"leverage={position_info['leverage']}x"
            )
            
            # 8. 执行交易
            order_id = trader.open_position(
                symbol=symbol,
                signal_type=signal.signal_type,
                position_info=position_info,
                entry_price=signal.entry_price,
                stop_loss=signal.stop_loss,
                take_profit=signal.take_profit
            )
            
            if order_id:
                # 记录信号
                database.add_signal({
                    'symbol': symbol,
                    'signal_type': signal.signal_type,
                    'score': signal.score,
                    'price': signal.entry_price,
                    'support_level': signal.support_level,
                    'resistance_level': signal.resistance_level,
                    'executed': True,
                    'order_id': order_id,
                    'score_details': signal.score_details,
                })
                
                system_logger.info(f"{symbol}: Trade executed successfully - {order_id}")
            else:
                system_logger.error(f"{symbol}: Failed to execute trade")
                database.add_signal({
                    'symbol': symbol,
                    'signal_type': signal.signal_type,
                    'score': signal.score,
                    'price': signal.entry_price,
                    'executed': False,
                    'not_executed_reason': 'execution_failed',
                    'score_details': signal.score_details,
                })
        
        except Exception as e:
            system_logger.error(f"Error processing {symbol}: {e}", exc_info=True)
    
    def run_trading_loop(self):
        """运行交易主循环"""
        try:
            system_logger.info("=" * 80)
            system_logger.info(f"Trading loop started at {datetime.now()}")
            system_logger.info("=" * 80)
            
            # 1. 更新币种池
            if coin_selector.should_update():
                selected_coins = coin_selector.select_coins()
            else:
                selected_coins = coin_selector.get_selected_coins()
            
            if not selected_coins:
                system_logger.warning("No coins selected for trading")
                return
            
            system_logger.info(f"Processing {len(selected_coins)} symbols")
            
            # 2. 监控现有持仓
            trader.monitor_all_positions()
            
            # 3. 遍历每个币种寻找机会
            for symbol in selected_coins:
                self.process_symbol(symbol)
                time.sleep(1)  # 避免API限流
            
            # 4. 风控检查
            risk_manager.check_daily_loss_limit()
            risk_manager.check_weekly_loss_limit()
            
            system_logger.info(f"Trading loop completed at {datetime.now()}")
        
        except Exception as e:
            system_logger.error(f"Error in trading loop: {e}", exc_info=True)
    
    def start(self):
        """启动交易系统"""
        system_logger.info("=" * 80)
        system_logger.info("OKX Intraday Trading System Starting...")
        system_logger.info("=" * 80)
        
        # 设置信号处理
        self.setup_signal_handlers()
        
        # 设置定时任务
        self.setup_scheduler()
        
        # 标记运行状态
        self.running = True
        
        system_logger.info(f"Loop interval: {self.loop_interval} seconds")
        system_logger.info("System started. Press Ctrl+C to stop.")
        
        # 主循环
        while self.running:
            try:
                self.run_trading_loop()
                
                # 等待下一个周期
                system_logger.info(f"Waiting {self.loop_interval} seconds for next loop...")
                time.sleep(self.loop_interval)
            
            except KeyboardInterrupt:
                system_logger.info("Keyboard interrupt received")
                break
            except Exception as e:
                system_logger.error(f"Unexpected error in main loop: {e}", exc_info=True)
                time.sleep(60)  # 发生错误后等待1分钟再继续
    
    def stop(self):
        """停止交易系统"""
        system_logger.info("Stopping trading system...")
        self.running = False
        
        if self.scheduler.running:
            self.scheduler.shutdown()
        
        system_logger.info("Trading system stopped")


def main():
    """主函数"""
    # 创建交易系统实例
    system = TradingSystem()
    
    # 启动系统
    system.start()


if __name__ == '__main__':
    main()

