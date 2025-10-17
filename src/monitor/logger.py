"""日志系统模块 - 基于 loguru"""
import sys
from pathlib import Path
from loguru import logger
from ..utils.config import config


class LoguruLogger:
    """Loguru日志管理类"""
    
    _initialized = False
    
    @classmethod
    def initialize(cls):
        """初始化日志系统"""
        if cls._initialized:
            return
        
        # 创建日志目录
        root_dir = Path(__file__).parent.parent.parent
        log_dir = root_dir / "logs"
        log_dir.mkdir(exist_ok=True)
        
        # 获取配置
        log_level = config.get('monitoring.log_level', 'INFO')
        retention_days = config.get('monitoring.log_retention_days', 30)
        
        # 移除默认处理器
        logger.remove()
        
        # 1. 控制台输出 - 彩色、美化格式
        logger.add(
            sys.stdout,
            level="INFO",
            format=(
                "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
                "<level>{level: <8}</level> | "
                "<cyan>{name}</cyan>:<cyan>{function}</cyan> | "
                "<level>{message}</level>"
            ),
            colorize=True,
        )
        
        # 2. 主日志文件 - 所有级别
        logger.add(
            log_dir / "trading.log",
            level="DEBUG",
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function} | {message}",
            rotation="00:00",  # 每天午夜轮转
            retention=f"{retention_days} days",
            compression="zip",  # 压缩旧日志
            encoding="utf-8",
        )
        
        # 3. 错误日志文件 - 仅ERROR及以上
        logger.add(
            log_dir / "trading_error.log",
            level="ERROR",
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function} | {message}",
            rotation="00:00",
            retention="30 days",
            compression="zip",
            encoding="utf-8",
        )
        
        # 4. 交易专用日志文件
        logger.add(
            log_dir / "trades.log",
            level="INFO",
            format="{time:YYYY-MM-DD HH:mm:ss}|{message}",
            rotation="00:00",
            retention="90 days",
            compression="zip",
            encoding="utf-8",
            filter=lambda record: "TRADE" in record["message"] or "SIGNAL" in record["message"],
        )
        
        cls._initialized = True
        logger.info("Loguru logger initialized successfully")
    
    @classmethod
    def get_logger(cls, name: str = None):
        """
        获取日志器（兼容接口）
        
        Args:
            name: 日志器名称（loguru中不使用，仅为兼容）
            
        Returns:
            logger实例
        """
        if not cls._initialized:
            cls.initialize()
        return logger


class TradingLogger:
    """交易日志类（兼容原有接口）"""
    
    @classmethod
    def get_logger(cls, name: str = 'trading'):
        """获取日志器"""
        return LoguruLogger.get_logger(name)
    
    @classmethod
    def log_trade(cls, 
                  symbol: str,
                  side: str,
                  action: str,
                  price: float,
                  amount: float,
                  order_id: str = None,
                  pnl: float = None,
                  **kwargs):
        """
        记录交易日志
        
        Args:
            symbol: 交易对
            side: 方向 (long/short)
            action: 动作 (open/close)
            price: 价格
            amount: 数量
            order_id: 订单ID
            pnl: 盈亏
            **kwargs: 其他信息
        """
        log_parts = [
            f"<cyan><bold>TRADE</bold></cyan>",
            f"symbol=<yellow>{symbol}</yellow>",
            f"side=<{'green' if side=='long' else 'red'}>{side}</>",
            f"action=<magenta>{action}</magenta>",
            f"price=<white>{price}</white>",
            f"amount=<white>{amount}</white>"
        ]
        
        if order_id:
            log_parts.append(f"order_id=<blue>{order_id}</blue>")
        if pnl is not None:
            color = 'green' if pnl > 0 else 'red'
            log_parts.append(f"pnl=<{color}><bold>{pnl:.2f}</bold></>")
        
        for key, value in kwargs.items():
            log_parts.append(f"{key}={value}")
        
        logger.opt(colors=True).info(" | ".join(log_parts))
    
    @classmethod
    def log_signal(cls,
                   symbol: str,
                   signal_type: str,
                   score: float,
                   executed: bool,
                   reason: str = None,
                   **kwargs):
        """
        记录信号日志
        
        Args:
            symbol: 交易对
            signal_type: 信号类型 (long/short)
            score: 信号评分
            executed: 是否执行
            reason: 不执行原因
            **kwargs: 其他信息
        """
        log_parts = [
            f"<blue><bold>SIGNAL</bold></blue>",
            f"symbol=<yellow>{symbol}</yellow>",
            f"type=<{'green' if signal_type=='long' else 'red'}>{signal_type}</>",
            f"score=<cyan><bold>{score:.1f}</bold></cyan>",
            f"executed=<{'green' if executed else 'yellow'}>{executed}</>"
        ]
        
        if reason:
            log_parts.append(f"reason=<red>{reason}</red>")
        
        for key, value in kwargs.items():
            log_parts.append(f"{key}={value}")
        
        logger.opt(colors=True).info(" | ".join(log_parts))
    
    @classmethod
    def log_risk_alert(cls, alert_type: str, message: str, **kwargs):
        """
        记录风控告警
        
        Args:
            alert_type: 告警类型
            message: 告警消息
            **kwargs: 其他信息
        """
        log_parts = [
            f"<red><bold>⚠️  RISK_ALERT</bold></red>",
            f"type=<yellow>{alert_type}</yellow>",
            f"message=<red><bold>{message}</bold></red>"
        ]
        
        for key, value in kwargs.items():
            log_parts.append(f"{key}=<yellow>{value}</yellow>")
        
        logger.opt(colors=True).warning(" | ".join(log_parts))


# 初始化日志系统
LoguruLogger.initialize()

# 全局日志器实例（兼容原有接口）
trading_logger = logger.bind(name="trading")
system_logger = logger.bind(name="system")
