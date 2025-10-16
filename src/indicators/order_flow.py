"""订单流分析模块"""
import pandas as pd
import numpy as np
from typing import Dict, Optional
from ..core.data_fetcher import data_fetcher
from ..utils.config import config
from ..monitor.logger import system_logger


class OrderFlowAnalyzer:
    """订单流分析类"""
    
    def __init__(self):
        """初始化"""
        self.data_fetcher = data_fetcher
        self.config = config.get('order_flow', {})
    
    def analyze_orderbook(self, symbol: str) -> Dict:
        """
        分析订单簿
        
        Args:
            symbol: 交易对符号
            
        Returns:
            订单簿分析结果
        """
        try:
            depth_levels = self.config.get('orderbook_depth_levels', 5)
            orderbook = self.data_fetcher.fetch_orderbook_analysis(symbol, depth_levels)
            
            if not orderbook:
                return {}
            
            # 买卖盘力量对比
            bid_depth = orderbook['bid_depth']
            ask_depth = orderbook['ask_depth']
            bid_ask_ratio = orderbook['bid_ask_ratio']
            
            # 判断盘口压力
            pressure = 'neutral'
            if bid_ask_ratio > 1.5:
                pressure = 'buy_pressure'  # 买盘强
            elif bid_ask_ratio < 0.67:
                pressure = 'sell_pressure'  # 卖盘强
            
            # 检查大额挂单
            bids = np.array(orderbook['bids'])
            asks = np.array(orderbook['asks'])
            
            avg_bid_size = np.mean(bids[:, 1]) if len(bids) > 0 else 0
            avg_ask_size = np.mean(asks[:, 1]) if len(asks) > 0 else 0
            
            large_bid_count = np.sum(bids[:, 1] > avg_bid_size * 3) if len(bids) > 0 else 0
            large_ask_count = np.sum(asks[:, 1] > avg_ask_size * 3) if len(asks) > 0 else 0
            
            return {
                'bid_depth': bid_depth,
                'ask_depth': ask_depth,
                'bid_ask_ratio': bid_ask_ratio,
                'pressure': pressure,
                'spread_pct': orderbook['spread_pct'],
                'large_bid_count': int(large_bid_count),
                'large_ask_count': int(large_ask_count),
            }
        
        except Exception as e:
            system_logger.error(f"Error analyzing orderbook for {symbol}: {e}")
            return {}
    
    def analyze_trades(self, symbol: str) -> Dict:
        """
        分析成交数据
        
        Args:
            symbol: 交易对符号
            
        Returns:
            成交分析结果
        """
        try:
            trades = self.data_fetcher.fetch_recent_trades(symbol, limit=100)
            
            if not trades:
                return {}
            
            buy_ratio = trades['buy_ratio']
            
            # 判断主动买卖方向
            trade_direction = 'neutral'
            active_ratio_threshold = self.config.get('active_buy_ratio_threshold', 0.60)
            
            if buy_ratio > active_ratio_threshold:
                trade_direction = 'buy_active'  # 主动买入
            elif buy_ratio < (1 - active_ratio_threshold):
                trade_direction = 'sell_active'  # 主动卖出
            
            # 大单分析
            large_threshold = self.config.get('large_order_threshold', 100000)
            large_buy = trades['large_buy']
            large_sell = trades['large_sell']
            
            large_order_signal = 'neutral'
            if large_buy > large_sell * 2:
                large_order_signal = 'large_buy'
            elif large_sell > large_buy * 2:
                large_order_signal = 'large_sell'
            
            return {
                'buy_ratio': buy_ratio,
                'trade_direction': trade_direction,
                'large_buy': large_buy,
                'large_sell': large_sell,
                'large_order_signal': large_order_signal,
                'large_trades_count': trades['large_trades_count'],
                'total_trades': trades['total_trades'],
            }
        
        except Exception as e:
            system_logger.error(f"Error analyzing trades for {symbol}: {e}")
            return {}
    
    def analyze_order_flow(self, symbol: str) -> Dict:
        """
        综合订单流分析
        
        Args:
            symbol: 交易对符号
            
        Returns:
            综合分析结果
        """
        orderbook_analysis = self.analyze_orderbook(symbol)
        trades_analysis = self.analyze_trades(symbol)
        
        if not orderbook_analysis or not trades_analysis:
            return {
                'signal': 'neutral',
                'strength': 0,
                'details': {}
            }
        
        # 综合评分
        score = 0
        
        # 订单簿信号
        if orderbook_analysis['pressure'] == 'buy_pressure':
            score += 1
        elif orderbook_analysis['pressure'] == 'sell_pressure':
            score -= 1
        
        # 成交信号
        if trades_analysis['trade_direction'] == 'buy_active':
            score += 2
        elif trades_analysis['trade_direction'] == 'sell_active':
            score -= 2
        
        # 大单信号
        if trades_analysis['large_order_signal'] == 'large_buy':
            score += 2
        elif trades_analysis['large_order_signal'] == 'large_sell':
            score -= 2
        
        # 判断最终信号
        signal = 'neutral'
        if score >= 3:
            signal = 'strong_buy'
        elif score >= 1:
            signal = 'buy'
        elif score <= -3:
            signal = 'strong_sell'
        elif score <= -1:
            signal = 'sell'
        
        strength = abs(score) / 5  # 归一化到0-1
        
        return {
            'signal': signal,
            'strength': strength,
            'score': score,
            'orderbook': orderbook_analysis,
            'trades': trades_analysis,
        }
    
    def supports_signal(self, symbol: str, signal_type: str) -> bool:
        """
        检查订单流是否支持交易信号
        
        Args:
            symbol: 交易对符号
            signal_type: 信号类型 ('long' or 'short')
            
        Returns:
            是否支持
        """
        analysis = self.analyze_order_flow(symbol)
        
        if not analysis or analysis['signal'] == 'neutral':
            return True  # 中性不阻止
        
        if signal_type == 'long':
            # 做多信号，订单流应该是买入
            return analysis['signal'] in ['buy', 'strong_buy']
        elif signal_type == 'short':
            # 做空信号，订单流应该是卖出
            return analysis['signal'] in ['sell', 'strong_sell']
        
        return True


# 全局订单流分析器实例
order_flow_analyzer = OrderFlowAnalyzer()

