"""订单管理模块"""
import time
from typing import Dict, Optional, List
from datetime import datetime
from .exchange_client import exchange_client
from ..utils.database import database
from ..monitor.logger import system_logger, TradingLogger


class OrderManager:
    """订单管理类"""
    
    def __init__(self):
        """初始化"""
        self.exchange = exchange_client
        self.db = database
        self.active_orders = {}  # order_id -> order_info
    
    def create_market_order(self,
                           symbol: str,
                           side: str,
                           amount: float,
                           params: Dict = None) -> Optional[Dict]:
        """
        创建市价单
        
        Args:
            symbol: 交易对
            side: 方向 (buy/sell)
            amount: 数量
            params: 额外参数
            
        Returns:
            订单信息
        """
        try:
            order = self.exchange.create_order(
                symbol=symbol,
                order_type='market',
                side=side,
                amount=amount,
                params=params or {}
            )
            
            if order:
                self.active_orders[order['id']] = order
                system_logger.info(f"Market order created: {order['id']} {symbol} {side} {amount}")
            
            return order
        
        except Exception as e:
            system_logger.error(f"Failed to create market order: {e}")
            return None
    
    def create_limit_order(self,
                          symbol: str,
                          side: str,
                          amount: float,
                          price: float,
                          params: Dict = None) -> Optional[Dict]:
        """
        创建限价单
        
        Args:
            symbol: 交易对
            side: 方向 (buy/sell)
            amount: 数量
            price: 价格
            params: 额外参数
            
        Returns:
            订单信息
        """
        try:
            order = self.exchange.create_order(
                symbol=symbol,
                order_type='limit',
                side=side,
                amount=amount,
                price=price,
                params=params or {}
            )
            
            if order:
                self.active_orders[order['id']] = order
                system_logger.info(f"Limit order created: {order['id']} {symbol} {side} {amount}@{price}")
            
            return order
        
        except Exception as e:
            system_logger.error(f"Failed to create limit order: {e}")
            return None
    
    def cancel_order(self, order_id: str, symbol: str) -> bool:
        """
        取消订单
        
        Args:
            order_id: 订单ID
            symbol: 交易对
            
        Returns:
            是否成功
        """
        try:
            result = self.exchange.cancel_order(order_id, symbol)
            
            if order_id in self.active_orders:
                del self.active_orders[order_id]
            
            system_logger.info(f"Order cancelled: {order_id}")
            return True
        
        except Exception as e:
            system_logger.error(f"Failed to cancel order {order_id}: {e}")
            return False
    
    def get_order_status(self, order_id: str, symbol: str) -> Optional[Dict]:
        """
        获取订单状态
        
        Args:
            order_id: 订单ID
            symbol: 交易对
            
        Returns:
            订单状态
        """
        try:
            order = self.exchange.fetch_order(order_id, symbol)
            return order
        
        except Exception as e:
            system_logger.error(f"Failed to get order status {order_id}: {e}")
            return None
    
    def wait_for_order_fill(self, 
                           order_id: str,
                           symbol: str,
                           timeout: int = 60,
                           check_interval: int = 2) -> bool:
        """
        等待订单成交
        
        Args:
            order_id: 订单ID
            symbol: 交易对
            timeout: 超时时间（秒）
            check_interval: 检查间隔（秒）
            
        Returns:
            是否成交
        """
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            order = self.get_order_status(order_id, symbol)
            
            if not order:
                return False
            
            status = order.get('status')
            
            if status == 'closed' or status == 'filled':
                system_logger.info(f"Order filled: {order_id}")
                return True
            elif status == 'canceled' or status == 'cancelled':
                system_logger.warning(f"Order cancelled: {order_id}")
                return False
            
            time.sleep(check_interval)
        
        system_logger.warning(f"Order fill timeout: {order_id}")
        return False
    
    def set_stop_loss_order(self,
                           symbol: str,
                           side: str,
                           amount: float,
                           stop_price: float) -> Optional[Dict]:
        """
        设置止损单
        
        Args:
            symbol: 交易对
            side: 方向 (buy/sell for closing)
            amount: 数量
            stop_price: 止损价
            
        Returns:
            订单信息
        """
        try:
            # OKX止损单参数
            params = {
                'stopPrice': stop_price,
                'type': 'stop_market',
            }
            
            order = self.exchange.create_order(
                symbol=symbol,
                order_type='stop',
                side=side,
                amount=amount,
                params=params
            )
            
            if order:
                system_logger.info(f"Stop loss order set: {order['id']} {symbol} @ {stop_price}")
            
            return order
        
        except Exception as e:
            system_logger.error(f"Failed to set stop loss: {e}")
            return None
    
    def set_take_profit_order(self,
                             symbol: str,
                             side: str,
                             amount: float,
                             take_profit_price: float) -> Optional[Dict]:
        """
        设置止盈单
        
        Args:
            symbol: 交易对
            side: 方向
            amount: 数量
            take_profit_price: 止盈价
            
        Returns:
            订单信息
        """
        try:
            # OKX止盈单参数
            params = {
                'stopPrice': take_profit_price,
                'type': 'take_profit_market',
            }
            
            order = self.exchange.create_order(
                symbol=symbol,
                order_type='take_profit',
                side=side,
                amount=amount,
                params=params
            )
            
            if order:
                system_logger.info(f"Take profit order set: {order['id']} {symbol} @ {take_profit_price}")
            
            return order
        
        except Exception as e:
            system_logger.error(f"Failed to set take profit: {e}")
            return None
    
    def get_open_orders(self, symbol: str = None) -> List[Dict]:
        """
        获取未完成订单
        
        Args:
            symbol: 交易对（可选）
            
        Returns:
            订单列表
        """
        try:
            orders = self.exchange.fetch_open_orders(symbol)
            return orders
        
        except Exception as e:
            system_logger.error(f"Failed to get open orders: {e}")
            return []
    
    def close_position(self,
                      symbol: str,
                      side: str,
                      amount: float,
                      order_type: str = 'market') -> Optional[Dict]:
        """
        平仓
        
        Args:
            symbol: 交易对
            side: 持仓方向 (long/short)
            amount: 数量
            order_type: 订单类型
            
        Returns:
            订单信息
        """
        # 确定平仓方向（与持仓相反）
        close_side = 'sell' if side == 'long' else 'buy'
        
        if order_type == 'market':
            return self.create_market_order(symbol, close_side, amount)
        else:
            system_logger.error(f"Unsupported order type for closing: {order_type}")
            return None


# 全局订单管理器实例
order_manager = OrderManager()

