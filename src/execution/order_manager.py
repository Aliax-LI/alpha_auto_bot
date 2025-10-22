"""
订单管理器
处理订单执行、超时、滑点控制等
"""
import time
from typing import Optional, Dict, Any
from loguru import logger

from ..data.binance_client import BinanceClient


class OrderManager:
    """订单管理器类"""
    
    def __init__(self, client: BinanceClient, config: Dict[str, Any]):
        """
        初始化订单管理器
        
        Args:
            client: 币安客户端
            config: 执行配置
        """
        self.client = client
        self.config = config
        
        self.use_limit_orders = config.get('use_limit_orders', True)
        self.order_timeout = config.get('order_timeout', 30)
        self.price_tick_offset = config.get('price_tick_offset', 0.01)
        self.enable_orderbook_analysis = config.get('enable_orderbook_analysis', False)
        
        # 如果启用订单簿分析，导入分析器
        self.orderbook_analyzer = None
        if self.enable_orderbook_analysis:
            from .orderbook_analyzer import OrderbookAnalyzer
            self.orderbook_analyzer = OrderbookAnalyzer(client, config)
        
        logger.info(
            f"✅ 订单管理器初始化: "
            f"限价单={self.use_limit_orders}, "
            f"超时={self.order_timeout}s, "
            f"订单簿分析={self.enable_orderbook_analysis}"
        )
    
    def execute_entry(
        self, 
        symbol: str, 
        direction: str, 
        size: float
    ) -> Optional[Dict[str, Any]]:
        """
        执行入场订单
        
        Args:
            symbol: 交易对符号
            direction: 'buy' 或 'sell'
            size: 订单数量
            
        Returns:
            订单信息字典，失败返回 None
        """
        try:
            # 1. 订单簿分析（如果启用）
            if self.orderbook_analyzer:
                if not self.orderbook_analyzer.check_liquidity(symbol, size * 2):
                    logger.warning(f"⚠️  流动性不足，取消订单")
                    return None
            
            # 2. 执行订单
            if self.use_limit_orders:
                return self._execute_limit_order(symbol, direction, size)
            else:
                return self._execute_market_order(symbol, direction, size)
                
        except Exception as e:
            logger.error(f"❌ 执行入场订单失败: {e}")
            return None
    
    def _execute_market_order(
        self, 
        symbol: str, 
        direction: str, 
        size: float
    ) -> Optional[Dict[str, Any]]:
        """
        执行市价单
        
        Args:
            symbol: 交易对符号
            direction: 'buy' 或 'sell'
            size: 订单数量
            
        Returns:
            订单信息
        """
        try:
            order = self.client.create_order(
                symbol=symbol,
                side=direction,
                amount=size,
                order_type='market',
            )
            
            logger.info(f"✅ 市价单成交: {direction.upper()} {size:.4f} {symbol}")
            return order
            
        except Exception as e:
            logger.error(f"❌ 市价单失败: {e}")
            return None
    
    def _execute_limit_order(
        self, 
        symbol: str, 
        direction: str, 
        size: float
    ) -> Optional[Dict[str, Any]]:
        """
        执行限价单（带超时机制）
        
        Args:
            symbol: 交易对符号
            direction: 'buy' 或 'sell'
            size: 订单数量
            
        Returns:
            订单信息
        """
        try:
            # 获取订单簿
            orderbook = self.client.fetch_orderbook(symbol, limit=5)
            
            # 计算限价单价格（略优于市价）
            if direction == 'buy':
                # 买入：在ask价下方挂单
                best_ask = orderbook['asks'][0][0]
                price = best_ask - self.price_tick_offset
            else:
                # 卖出：在bid价上方挂单
                best_bid = orderbook['bids'][0][0]
                price = best_bid + self.price_tick_offset
            
            # 创建限价单
            order = self.client.create_order(
                symbol=symbol,
                side=direction,
                amount=size,
                price=price,
                order_type='limit'
            )
            
            order_id = order['id']
            logger.info(
                f"📝 限价单已挂: {direction.upper()} {size:.4f} @ {price:.2f}"
            )
            
            # 等待成交或超时
            start_time = time.time()
            while time.time() - start_time < self.order_timeout:
                # 查询订单状态
                order_status = self.client.fetch_order(order_id, symbol)
                
                if order_status['status'] == 'closed':
                    logger.info(f"✅ 限价单成交: {order_id}")
                    return order_status
                
                time.sleep(1)
            
            # 超时，取消订单
            logger.warning(f"⏰ 限价单超时，取消订单: {order_id}")
            self.client.cancel_order(order_id, symbol)
            
            # 超时后使用市价单补单
            logger.info("🔄 使用市价单补单...")
            return self._execute_market_order(symbol, direction, size)
            
        except Exception as e:
            logger.error(f"❌ 限价单执行失败: {e}")
            # 失败后尝试市价单
            logger.info("🔄 回退到市价单...")
            return self._execute_market_order(symbol, direction, size)
    
    def execute_exit(
        self, 
        symbol: str, 
        direction: str, 
        size: float,
        order_type: str = 'market'
    ) -> Optional[Dict[str, Any]]:
        """
        执行平仓订单（通常使用市价单快速平仓）
        
        Args:
            symbol: 交易对符号
            direction: 'buy' 或 'sell' （平仓方向）
            size: 订单数量
            order_type: 订单类型
            
        Returns:
            订单信息
        """
        try:
            order = self.client.create_order(
                symbol=symbol,
                side=direction,
                amount=size,
                order_type=order_type
            )
            
            logger.info(f"✅ 平仓订单成交: {direction.upper()} {size:.4f} {symbol}")
            return order
            
        except Exception as e:
            logger.error(f"❌ 平仓订单失败: {e}")
            return None
    
    def cancel_all_orders(self, symbol: str):
        """
        取消所有未成交订单
        
        Args:
            symbol: 交易对符号
        """
        try:
            # ccxt 的 cancel_all_orders 方法
            result = self.client.exchange.cancel_all_orders(symbol)
            logger.info(f"🚫 已取消所有订单: {symbol}")
            return result
        except Exception as e:
            logger.error(f"❌ 取消所有订单失败: {e}")
            return None

