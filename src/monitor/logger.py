"""日志系统模块"""
import logging
import os
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from pathlib import Path
from datetime import datetime
from typing import Optional
from ..utils.config import config


class TradingLogger:
    """交易日志类"""
    
    _loggers = {}
    
    @classmethod
    def get_logger(cls, name: str = 'trading') -> logging.Logger:
        """
        获取日志器
        
        Args:
            name: 日志器名称
            
        Returns:
            日志器实例
        """
        if name in cls._loggers:
            return cls._loggers[name]
        
        logger = cls._create_logger(name)
        cls._loggers[name] = logger
        return logger
    
    @classmethod
    def _create_logger(cls, name: str) -> logging.Logger:
        """
        创建日志器
        
        Args:
            name: 日志器名称
            
        Returns:
            日志器实例
        """
        # 创建日志目录
        root_dir = Path(__file__).parent.parent.parent
        log_dir = root_dir / "logs"
        log_dir.mkdir(exist_ok=True)
        
        # 获取配置
        log_level = config.get('monitoring.log_level', 'INFO')
        log_rotation = config.get('monitoring.log_rotation', 'daily')
        
        # 创建日志器
        logger = logging.getLogger(name)
        logger.setLevel(getattr(logging, log_level))
        
        # 避免重复添加处理器
        if logger.handlers:
            return logger
        
        # 创建格式器
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # 控制台处理器
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
        # 文件处理器 - 所有日志
        if log_rotation == 'daily':
            file_handler = TimedRotatingFileHandler(
                log_dir / f"{name}.log",
                when='midnight',
                interval=1,
                backupCount=config.get('monitoring.log_retention_days', 30),
                encoding='utf-8'
            )
        else:
            file_handler = RotatingFileHandler(
                log_dir / f"{name}.log",
                maxBytes=10*1024*1024,  # 10MB
                backupCount=10,
                encoding='utf-8'
            )
        
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        
        # 错误日志处理器
        error_handler = TimedRotatingFileHandler(
            log_dir / f"{name}_error.log",
            when='midnight',
            interval=1,
            backupCount=30,
            encoding='utf-8'
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(formatter)
        logger.addHandler(error_handler)
        
        # 交易日志处理器（如果是交易日志器）
        if name == 'trading':
            trade_handler = TimedRotatingFileHandler(
                log_dir / "trades.log",
                when='midnight',
                interval=1,
                backupCount=90,
                encoding='utf-8'
            )
            trade_handler.setLevel(logging.INFO)
            trade_formatter = logging.Formatter(
                '%(asctime)s|%(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            trade_handler.setFormatter(trade_formatter)
            logger.addHandler(trade_handler)
        
        return logger
    
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
        logger = cls.get_logger('trading')
        
        log_parts = [
            f"TRADE",
            f"symbol={symbol}",
            f"side={side}",
            f"action={action}",
            f"price={price}",
            f"amount={amount}"
        ]
        
        if order_id:
            log_parts.append(f"order_id={order_id}")
        if pnl is not None:
            log_parts.append(f"pnl={pnl}")
        
        for key, value in kwargs.items():
            log_parts.append(f"{key}={value}")
        
        logger.info("|".join(log_parts))
    
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
        logger = cls.get_logger('trading')
        
        log_parts = [
            f"SIGNAL",
            f"symbol={symbol}",
            f"type={signal_type}",
            f"score={score}",
            f"executed={executed}"
        ]
        
        if reason:
            log_parts.append(f"reason={reason}")
        
        for key, value in kwargs.items():
            log_parts.append(f"{key}={value}")
        
        logger.info("|".join(log_parts))
    
    @classmethod
    def log_risk_alert(cls, alert_type: str, message: str, **kwargs):
        """
        记录风控告警
        
        Args:
            alert_type: 告警类型
            message: 告警消息
            **kwargs: 其他信息
        """
        logger = cls.get_logger('trading')
        
        log_parts = [
            f"RISK_ALERT",
            f"type={alert_type}",
            f"message={message}"
        ]
        
        for key, value in kwargs.items():
            log_parts.append(f"{key}={value}")
        
        logger.warning("|".join(log_parts))


# 全局日志器实例
trading_logger = TradingLogger.get_logger('trading')
system_logger = TradingLogger.get_logger('system')

