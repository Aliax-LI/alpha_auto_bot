"""
订单簿分析器（可选）
分析盘口深度、流动性、大单墙等
"""
import numpy as np
from typing import Dict, Any, List, Tuple
from loguru import logger

from ..data.binance_client import BinanceClient


class OrderbookAnalyzer:
    """订单簿分析器类"""
    
    def __init__(self, client: BinanceClient, config: Dict[str, Any]):
        """
        初始化订单簿分析器
        
        Args:
            client: 币安客户端
            config: 配置字典
        """
        self.client = client
        self.min_liquidity_ratio = config.get('min_liquidity_ratio', 2.0)
        
        logger.info(f"✅ 订单簿分析器初始化: 最小流动性比率={self.min_liquidity_ratio}")
    
    def check_liquidity(self, symbol: str, required_amount: float) -> bool:
        """
        检查流动性是否充足
        
        Args:
            symbol: 交易对符号
            required_amount: 需要的数量（以交易对基础货币计）
            
        Returns:
            流动性是否充足
        """
        try:
            orderbook = self.client.fetch_orderbook(symbol, limit=20)
            
            # 计算前10档的总量
            bid_volume = sum([bid[1] for bid in orderbook['bids'][:10]])
            ask_volume = sum([ask[1] for ask in orderbook['asks'][:10]])
            
            # 取买卖盘的最小值
            available_liquidity = min(bid_volume, ask_volume)
            
            # 判断流动性是否足够（需要大于所需数量的N倍）
            is_sufficient = available_liquidity >= required_amount * self.min_liquidity_ratio
            
            if not is_sufficient:
                logger.warning(
                    f"⚠️  流动性不足: 可用={available_liquidity:.4f}, "
                    f"需要={required_amount * self.min_liquidity_ratio:.4f}"
                )
            
            return is_sufficient
            
        except Exception as e:
            logger.error(f"❌ 检查流动性失败: {e}")
            # 出错时保守处理，返回 False
            return False
    
    def detect_walls(
        self, 
        symbol: str, 
        threshold: float = 2.0
    ) -> Dict[str, List[Tuple[float, float]]]:
        """
        检测订单簿中的大单墙
        
        Args:
            symbol: 交易对符号
            threshold: 大单墙阈值（相对于平均值的倍数）
            
        Returns:
            包含 support（买单墙）和 resistance（卖单墙）的字典
        """
        try:
            orderbook = self.client.fetch_orderbook(symbol, limit=50)
            
            bids = orderbook['bids']
            asks = orderbook['asks']
            
            # 计算平均订单量
            avg_bid_size = np.mean([bid[1] for bid in bids])
            avg_ask_size = np.mean([ask[1] for ask in asks])
            
            # 检测大单墙（大于平均值的N倍）
            bid_walls = [
                (bid[0], bid[1]) 
                for bid in bids 
                if bid[1] > avg_bid_size * threshold
            ]
            
            ask_walls = [
                (ask[0], ask[1]) 
                for ask in asks 
                if ask[1] > avg_ask_size * threshold
            ]
            
            if bid_walls:
                logger.info(f"🛡️  检测到{len(bid_walls)}个支撑位（买单墙）")
            if ask_walls:
                logger.info(f"🛡️  检测到{len(ask_walls)}个阻力位（卖单墙）")
            
            return {
                'support': bid_walls,
                'resistance': ask_walls
            }
            
        except Exception as e:
            logger.error(f"❌ 检测大单墙失败: {e}")
            return {'support': [], 'resistance': []}
    
    def get_spread(self, symbol: str, limit: int = 5) -> Dict[str, float]:
        """
        获取买卖价差
        
        Args:
            symbol: 交易对符号
            limit: 订单深度（币安期货最小5）
            
        Returns:
            包含 spread, spread_pct 的字典
        """
        try:
            # 币安期货API要求limit最小为5
            if limit < 5:
                limit = 5
            orderbook = self.client.fetch_orderbook(symbol, limit=limit)
            
            best_bid = orderbook['bids'][0][0]
            best_ask = orderbook['asks'][0][0]
            
            spread = best_ask - best_bid
            spread_pct = (spread / best_bid) * 100
            
            return {
                'spread': spread,
                'spread_pct': spread_pct,
                'best_bid': best_bid,
                'best_ask': best_ask
            }
            
        except Exception as e:
            logger.error(f"❌ 获取价差失败: {e}")
            return {'spread': 0, 'spread_pct': 0, 'best_bid': 0, 'best_ask': 0}
    
    def get_order_book_imbalance(self, symbol: str, depth: int = 10) -> float:
        """
        计算订单簿失衡度（买卖压力指标）
        
        Args:
            symbol: 交易对符号
            depth: 计算深度
            
        Returns:
            失衡度 (-1 到 1)，正值表示买压强，负值表示卖压强
        """
        try:
            orderbook = self.client.fetch_orderbook(symbol, limit=depth)
            
            # 计算买卖盘总量
            bid_volume = sum([bid[1] for bid in orderbook['bids'][:depth]])
            ask_volume = sum([ask[1] for ask in orderbook['asks'][:depth]])
            
            # 计算失衡度
            total_volume = bid_volume + ask_volume
            if total_volume == 0:
                return 0.0
            
            imbalance = (bid_volume - ask_volume) / total_volume
            
            return imbalance
            
        except Exception as e:
            logger.error(f"❌ 计算订单簿失衡度失败: {e}")
            return 0.0

