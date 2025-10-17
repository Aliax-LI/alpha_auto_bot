"""数据获取模块"""
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from .exchange_client import exchange_client
from ..monitor.logger import system_logger
import tzlocal



class DataFetcher:
    """数据获取类"""
    
    def __init__(self):
        """初始化数据获取器"""
        self.exchange = exchange_client
        self._cache = {}  # 简单缓存
    
    def fetch_ohlcv_df(self, symbol: str, timeframe: str = '5m', limit: int = 200, since: int = None, until:int = None) -> pd.DataFrame:
        """
        获取K线数据并转换为DataFrame
        
        Args:
            symbol: 交易对符号
            timeframe: 时间周期
            since: 开始数据戳
            until: 结束数据戳
            limit: 数据条数
            
        Returns:
            K线数据DataFrame
        """
        try:
            tzlocal.get_localzone()
            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, limit, since, until)
            
            df = pd.DataFrame(
                ohlcv,
                columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
            )
            
            # 转换时间戳
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True).dt.tz_convert(tzlocal.get_localzone())
            df.set_index('timestamp', inplace=True)
            
            return df
        
        except Exception as e:
            system_logger.error(f"Error fetching OHLCV for {symbol}: {e}")
            return pd.DataFrame()
    
    def fetch_multi_timeframe(self, 
                              symbol: str,
                              timeframes: List[str] = None) -> Dict[str, pd.DataFrame]:
        """
        获取多周期K线数据
        
        Args:
            symbol: 交易对符号
            timeframes: 时间周期列表
            
        Returns:
            多周期数据字典
        """
        if timeframes is None:
            timeframes = ['5m', '15m', '1h']
        
        data = {}
        for tf in timeframes:
            limit = 200 if tf == '5m' else (100 if tf == '15m' else 50)
            df = self.fetch_ohlcv_df(symbol, tf, limit)
            if not df.empty:
                data[tf] = df
        
        return data
    
    def fetch_orderbook_analysis(self, symbol: str, limit: int = 20) -> Dict:
        """
        获取并分析订单簿数据
        
        Args:
            symbol: 交易对符号
            limit: 深度档位
            
        Returns:
            订单簿分析结果
        """
        try:
            orderbook = self.exchange.fetch_order_book(symbol, limit)
            
            bids = np.array(orderbook['bids'])  # [[price, amount], ...]
            asks = np.array(orderbook['asks'])
            
            if len(bids) == 0 or len(asks) == 0:
                return {}
            
            # 计算买卖盘深度
            bid_depth = np.sum(bids[:, 0] * bids[:, 1])  # 价格 * 数量
            ask_depth = np.sum(asks[:, 0] * asks[:, 1])
            
            # 最佳买卖价
            best_bid = bids[0][0]
            best_ask = asks[0][0]
            
            # 价差
            spread = best_ask - best_bid
            spread_pct = (spread / best_bid) * 100
            
            # 买卖比
            bid_ask_ratio = bid_depth / ask_depth if ask_depth > 0 else 0
            
            return {
                'bid_depth': bid_depth,
                'ask_depth': ask_depth,
                'best_bid': best_bid,
                'best_ask': best_ask,
                'spread': spread,
                'spread_pct': spread_pct,
                'bid_ask_ratio': bid_ask_ratio,
                'bids': bids.tolist(),
                'asks': asks.tolist(),
            }
        
        except Exception as e:
            system_logger.error(f"Error fetching orderbook for {symbol}: {e}")
            return {}
    
    def fetch_recent_trades(self, symbol: str, limit: int = 100) -> Dict:
        """
        获取并分析最近成交数据
        
        Args:
            symbol: 交易对符号
            limit: 数据条数
            
        Returns:
            成交分析结果
        """
        try:
            trades = self.exchange.fetch_trades(symbol, limit)
            
            if not trades:
                return {}
            
            # 转换为DataFrame
            df = pd.DataFrame(trades)
            
            # 计算主动买卖
            buy_volume = df[df['side'] == 'buy']['amount'].sum()
            sell_volume = df[df['side'] == 'sell']['amount'].sum()
            total_volume = buy_volume + sell_volume
            
            buy_ratio = buy_volume / total_volume if total_volume > 0 else 0
            
            # 识别大单
            df['value'] = df['price'] * df['amount']
            large_threshold = df['value'].quantile(0.9)  # 前10%算大单
            large_trades = df[df['value'] >= large_threshold]
            
            large_buy = large_trades[large_trades['side'] == 'buy']['value'].sum()
            large_sell = large_trades[large_trades['side'] == 'sell']['value'].sum()
            
            return {
                'buy_volume': buy_volume,
                'sell_volume': sell_volume,
                'buy_ratio': buy_ratio,
                'large_buy': large_buy,
                'large_sell': large_sell,
                'large_trades_count': len(large_trades),
                'total_trades': len(trades),
            }
        
        except Exception as e:
            system_logger.error(f"Error fetching trades for {symbol}: {e}")
            return {}
    
    def fetch_ticker_24h(self, symbol: str) -> Dict:
        """
        获取24小时ticker数据
        
        Args:
            symbol: 交易对符号
            
        Returns:
            ticker数据
        """
        try:
            ticker = self.exchange.fetch_ticker(symbol)
            return {
                'symbol': symbol,
                'last': ticker.get('last'),
                'bid': ticker.get('bid'),
                'ask': ticker.get('ask'),
                'volume': ticker.get('quoteVolume', ticker.get('volume')),
                'change': ticker.get('change'),
                'percentage': ticker.get('percentage'),
                'high': ticker.get('high'),
                'low': ticker.get('low'),
            }
        except Exception as e:
            system_logger.error(f"Error fetching ticker for {symbol}: {e}")
            return {}
    
    def fetch_all_tickers(self, symbols=None) -> Dict[str, Dict]:
        """
        获取所有交易对的ticker数据
        
        Returns:
            所有ticker数据
        """
        try:
            tickers = self.exchange.fetch_tickers(symbols)
            return tickers
        except Exception as e:
            system_logger.error(f"Error fetching all tickers: {e}")
            return {}
    
    def get_usdt_perpetual_symbols(self) -> List[str]:
        """
        获取所有USDT永续合约交易对
        
        Returns:
            交易对列表
        """
        try:
            markets = self.exchange.fetch_markets()
            
            # 筛选USDT永续合约
            symbols = []
            for market in markets:
                if (market.get('quote') == 'USDT' and 
                    market.get('type') == 'swap' and
                    market.get('active') and
                    market.get('linear')):
                    symbols.append(market['symbol'])
            
            system_logger.info(f"Found {len(symbols)} USDT perpetual contracts")
            return symbols
        
        except Exception as e:
            system_logger.error(f"Error fetching markets: {e}")
            return []
    
    def fetch_account_balance(self, balance_type='swap') -> Dict:
        """
        获取账户余额
        
        Returns:
            余额信息
        """
        try:
            balance = self.exchange.fetch_balance(params={
                'type': balance_type
            })
            
            # 提取USDT余额
            usdt_balance = balance.get('USDT', {})
            
            return {
                'total': usdt_balance.get('total', 0),
                'free': usdt_balance.get('free', 0),
                'used': usdt_balance.get('used', 0),
                'balance': balance,
            }
        except Exception as e:
            system_logger.error(f"Error fetching balance: {e}")
            return {'total': 0, 'free': 0, 'used': 0}
    
    def fetch_positions_info(self, symbols: List[str] = None) -> Dict[str, Dict]:
        """
        获取持仓信息
        
        Args:
            symbols: 交易对列表
            
        Returns:
            持仓信息字典
        """
        try:
            positions = self.exchange.fetch_positions(symbols)
            
            position_dict = {}
            for pos in positions:
                if pos.get('contracts', 0) > 0:  # 只返回有持仓的
                    symbol = pos['symbol']
                    position_dict[symbol] = {
                        'symbol': symbol,
                        'side': pos.get('side'),
                        'contracts': pos.get('contracts'),
                        'contractSize': pos.get('contractSize'),
                        'entryPrice': pos.get('entryPrice'),
                        'markPrice': pos.get('markPrice'),
                        'liquidationPrice': pos.get('liquidationPrice'),
                        'leverage': pos.get('leverage'),
                        'unrealizedPnl': pos.get('unrealizedPnl'),
                        'percentage': pos.get('percentage'),
                    }
            
            return position_dict
        
        except Exception as e:
            system_logger.error(f"Error fetching positions: {e}")
            return {}


# 全局数据获取器实例
data_fetcher = DataFetcher()

