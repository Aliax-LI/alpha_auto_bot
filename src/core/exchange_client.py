"""CCXT交易所客户端封装"""
import ccxt
import time
from typing import Dict, List, Optional, Any

import pandas as pd

from ..utils.config import config
from ..monitor.logger import system_logger


class ExchangeClient:
    """交易所客户端类"""
    
    def __init__(self):
        """初始化交易所客户端"""
        self.exchange = None
        self._init_exchange()
    
    def _init_exchange(self):
        """初始化交易所连接"""
        exchange_config = config.get_exchange_config()
        system_config = config.get_system_config()
        
        exchange_name = exchange_config.get('name', 'okx')
        api_key = exchange_config.get('api_key')
        secret = exchange_config.get('secret')
        proxy = exchange_config.get('proxy')
        
        # 创建交易所实例
        exchange_class = getattr(ccxt, exchange_name)
        
        exchange_params = {
            'apiKey': api_key,
            'secret': secret,
            'timeout': system_config.get('api_timeout', 5) * 1000,
            'enableRateLimit': True,
        }
        
        if proxy:
            exchange_params['proxies'] = {
                'http': proxy,
                'https': proxy,
            }
        
        self.exchange = exchange_class(exchange_params)
        system_logger.info(f"Exchange client initialized: {exchange_name}")
    
    def _retry_request(self, func, *args, **kwargs):
        """
        带重试的请求
        
        Args:
            func: 要执行的函数
            *args: 函数参数
            **kwargs: 函数关键字参数
            
        Returns:
            函数执行结果
        """
        max_retries = config.get('system.api_retry_times', 3)
        
        for attempt in range(max_retries):
            try:
                return func(*args, **kwargs)
            except ccxt.NetworkError as e:
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt  # 指数退避
                    system_logger.warning(f"Network error, retrying in {wait_time}s: {e}")
                    time.sleep(wait_time)
                else:
                    system_logger.error(f"Network error after {max_retries} retries: {e}")
                    raise
            except ccxt.ExchangeError as e:
                system_logger.error(f"Exchange error: {e}")
                raise
            except Exception as e:
                system_logger.error(f"Unexpected error: {e}")
                raise
    
    def fetch_markets(self) -> List[Dict]:
        """
        获取所有市场信息
        
        Returns:
            市场信息列表
        """
        return self._retry_request(self.exchange.fetch_markets)
    
    def fetch_ticker(self, symbol: str) -> Dict:
        """
        获取ticker数据
        
        Args:
            symbol: 交易对符号
            
        Returns:
            ticker数据
        """
        return self._retry_request(self.exchange.fetch_ticker, symbol)
    
    def fetch_tickers(self, symbols: List[str] = None) -> Dict:
        """
        获取多个ticker数据
        
        Args:
            symbols: 交易对符号列表
            
        Returns:
            ticker数据字典
        """
        return self._retry_request(self.exchange.fetch_tickers, symbols)

    
    def fetch_ohlcv(self, symbol: str, timeframe: str = '5m', limit: int = 200, since: int = None, until: int = None) -> List[List]:
        """
        获取K线数据
        
        Args:
            symbol: 交易对符号
            timeframe: 时间周期
            since: 时间
            until: 时间
            limit: 数据条数
            
        Returns:
            K线数据 [[timestamp, open, high, low, close, volume], ...]
        """
        return self._retry_request(self.exchange.fetch_ohlcv, symbol, timeframe, since=since, limit=limit, params={
            'until': until,
        })
    
    def fetch_order_book(self, symbol: str, limit: int = 20) -> Dict:
        """
        获取订单簿数据
        
        Args:
            symbol: 交易对符号
            limit: 深度档位
            
        Returns:
            订单簿数据
        """
        return self._retry_request(self.exchange.fetch_order_book, symbol, limit)
    
    def fetch_trades(self, symbol: str, limit: int = 100) -> List[Dict]:
        """
        获取最近成交数据
        
        Args:
            symbol: 交易对符号
            limit: 数据条数
            
        Returns:
            成交数据列表
        """
        return self._retry_request(self.exchange.fetch_trades, symbol, limit=limit)
    
    def fetch_balance(self, params) -> Dict:
        """
        获取账户余额
        
        Returns:
            余额信息
        """
        return self._retry_request(self.exchange.fetch_balance, params)
    
    def fetch_positions(self, symbols: List[str] = None) -> List[Dict]:
        """
        获取持仓信息
        
        Args:
            symbols: 交易对列表
            
        Returns:
            持仓信息列表
        """
        return self._retry_request(self.exchange.fetch_positions, symbols)
    
    def create_order(self, 
                     symbol: str,
                     order_type: str,
                     side: str,
                     amount: float,
                     price: float = None,
                     params: Dict = None) -> Dict:
        """
        创建订单
        
        Args:
            symbol: 交易对符号
            order_type: 订单类型 (market/limit)
            side: 方向 (buy/sell)
            amount: 数量
            price: 价格（限价单需要）
            params: 其他参数
            
        Returns:
            订单信息
        """
        if params is None:
            params = {}
        
        system_logger.info(f"Creating order: {symbol} {side} {order_type} amount={amount} price={price}")
        return self._retry_request(
            self.exchange.create_order,
            symbol, order_type, side, amount, price, params
        )
    
    def cancel_order(self, order_id: str, symbol: str) -> Dict:
        """
        取消订单
        
        Args:
            order_id: 订单ID
            symbol: 交易对符号
            
        Returns:
            订单信息
        """
        system_logger.info(f"Cancelling order: {order_id} {symbol}")
        return self._retry_request(self.exchange.cancel_order, order_id, symbol)
    
    def fetch_order(self, order_id: str, symbol: str) -> Dict:
        """
        获取订单信息
        
        Args:
            order_id: 订单ID
            symbol: 交易对符号
            
        Returns:
            订单信息
        """
        return self._retry_request(self.exchange.fetch_order, order_id, symbol)
    
    def fetch_open_orders(self, symbol: str = None) -> List[Dict]:
        """
        获取未完成订单
        
        Args:
            symbol: 交易对符号
            
        Returns:
            订单列表
        """
        return self._retry_request(self.exchange.fetch_open_orders, symbol)
    
    def set_leverage(self, leverage: int, symbol: str, params: Dict = None) -> Dict:
        """
        设置杠杆
        
        Args:
            leverage: 杠杆倍数
            symbol: 交易对符号
            params: 其他参数
            
        Returns:
            设置结果
        """
        if params is None:
            params = {}
        
        system_logger.info(f"Setting leverage: {symbol} {leverage}x")
        return self._retry_request(self.exchange.set_leverage, leverage, symbol, params)
    
    def set_margin_mode(self, margin_mode: str, symbol: str, params: Dict = None) -> Dict:
        """
        设置保证金模式
        
        Args:
            margin_mode: 保证金模式 (cross/isolated)
            symbol: 交易对符号
            params: 其他参数
            
        Returns:
            设置结果
        """
        if params is None:
            params = {}
        
        system_logger.info(f"Setting margin mode: {symbol} {margin_mode}")
        return self._retry_request(self.exchange.set_margin_mode, margin_mode, symbol, params)


# 全局交易所客户端实例
exchange_client = ExchangeClient()

