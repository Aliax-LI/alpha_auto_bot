"""
实盘交易主程序
"""
import sys
import signal
from loguru import logger
from src.utils.config_loader import ConfigLoader
from src.core.live_trading_engine import LiveTradingEngine


# 全局引擎实例
engine = None


def signal_handler(sig, frame):
    """处理Ctrl+C信号"""
    logger.info("\n\n收到停止信号，正在安全退出...")
    if engine:
        engine.stop()
    sys.exit(0)


def main():
    """主函数"""
    global engine

    # 设置日志
    logger.remove()
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | <level>{message}</level>",
        level="DEBUG"  # 改为DEBUG级别，显示所有调试信息
    )
    logger.add(
        "logs/trading_{time:YYYY-MM-DD}.log",
        rotation="1 day",
        retention="30 days",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {message}",
        level="DEBUG"
    )

    logger.info("=" * 80)
    logger.info("🚀 ALGOX 实盘交易系统")
    logger.info("=" * 80)

    # 注册信号处理
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        # 1. 加载配置
        logger.info("📁 加载配置文件...")
        config_loader = ConfigLoader("config/config.yaml")
        config = config_loader.load()

        # 3. 初始化交易引擎
        logger.info("⚙️  初始化交易引擎...")
        engine = LiveTradingEngine(config)

        # 4. 打印配置摘要
        logger.info("\n📋 交易配置:")
        logger.info(f"   交易对: {config['trading']['symbol']}")
        logger.info(f"   时间框架: {config['trading']['base_timeframe']}")
        logger.info(f"   策略模式: {config['strategy']['setup_type']}")
        logger.info(f"   过滤器: {config['strategy']['filter_type']}")
        logger.info(f"   止盈止损: {config['strategy']['tps_type']}")
        logger.info(f"   仓位比例: {config['risk_management']['position_size']*100:.0f}%")
        logger.info(f"   最大回撤: {config['risk_management']['max_drawdown_percent']}%")

        # 5. 启动引擎
        logger.info("\n" + "=" * 80)
        engine.start()

    except KeyboardInterrupt:
        logger.info("\n收到中断信号")
        if engine:
            engine.stop()
    except Exception as e:
        logger.error(f"❌ 程序异常: {e}", exc_info=True)
        if engine:
            engine.stop()
    finally:
        logger.info("\n" + "=" * 80)
        logger.info("👋 程序已退出")
        logger.info("=" * 80)


if __name__ == "__main__":
    main()

