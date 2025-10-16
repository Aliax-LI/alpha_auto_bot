"""选币策略模块"""
import pandas as pd
import numpy as np
from typing import List, Dict
from datetime import datetime, timedelta
from ..core.data_fetcher import data_fetcher
from ..indicators.technical import technical_indicators
from ..utils.config import config
from ..monitor.logger import system_logger, TradingLogger


class CoinSelector:
    """选币策略类"""
    
    def __init__(self):
        """初始化"""
        self.data_fetcher = data_fetcher
        self.config = config.get('coin_selection', {})
        self.selected_coins = []
        self.last_update = None
    
    def should_update(self) -> bool:
        """
        判断是否需要更新币种池
        
        Returns:
            是否需要更新
        """
        if self.last_update is None:
            return True
        
        update_interval = self.config.get('update_interval', 3600)
        elapsed = (datetime.now() - self.last_update).total_seconds()
        
        return elapsed >= update_interval
    
    def calculate_volatility(self, df: pd.DataFrame) -> float:
        """
        计算波动率
        
        Args:
            df: K线数据
            
        Returns:
            波动率（ATR/价格）
        """
        if df.empty or len(df) < 14:
            return 0
        
        # 使用ATR计算波动率
        df = technical_indicators.calculate_atr(df)
        atr = df['atr'].iloc[-1]
        price = df['close'].iloc[-1]
        
        volatility = atr / price if price > 0 else 0
        
        return volatility
    
    def evaluate_coin(self, symbol: str, ticker: Dict) -> Dict:
        """
        评估单个币种
        
        Args:
            symbol: 交易对符号
            ticker: ticker数据
            
        Returns:
            评估结果
        """
        try:
            # 获取24h数据
            volume_24h = ticker.get('quoteVolume', ticker.get('volume', 0))
            
            # 成交量筛选
            min_volume = self.config.get('min_volume_24h', 5000000)
            if volume_24h < min_volume:
                return {'symbol': symbol, 'passed': False, 'reason': 'low_volume'}
            
            # 获取1小时K线计算指标
            df_1h = self.data_fetcher.fetch_ohlcv_df(symbol, '1h', limit=50)
            if df_1h.empty or len(df_1h) < 20:
                return {'symbol': symbol, 'passed': False, 'reason': 'insufficient_data'}
            
            # 计算波动率
            volatility = self.calculate_volatility(df_1h)
            volatility_range = self.config.get('volatility_range', [0.03, 0.15])
            
            if not (volatility_range[0] <= volatility <= volatility_range[1]):
                return {'symbol': symbol, 'passed': False, 'reason': 'volatility_out_of_range'}
            
            # 计算ADX
            df_1h = technical_indicators.calculate_adx(df_1h)
            adx = df_1h['adx'].iloc[-1]
            min_adx = self.config.get('min_adx', 25)
            
            if pd.isna(adx) or adx < min_adx:
                return {'symbol': symbol, 'passed': False, 'reason': 'weak_trend'}
            
            # 获取订单簿评估流动性
            orderbook = self.data_fetcher.fetch_orderbook_analysis(symbol, limit=10)
            if not orderbook:
                return {'symbol': symbol, 'passed': False, 'reason': 'no_orderbook'}
            
            liquidity = orderbook.get('bid_depth', 0) + orderbook.get('ask_depth', 0)
            min_liquidity = self.config.get('liquidity_depth_threshold', 100000)
            
            if liquidity < min_liquidity:
                return {'symbol': symbol, 'passed': False, 'reason': 'low_liquidity'}
            
            # 计算评分
            score = 0
            score += min(volume_24h / 10000000, 10)  # 成交量评分（最高10分）
            score += min(adx / 10, 5)  # ADX评分（最高5分）
            score += min(volatility * 50, 5)  # 波动率评分（最高5分）
            score += min(liquidity / 100000, 5)  # 流动性评分（最高5分）
            
            return {
                'symbol': symbol,
                'passed': True,
                'score': score,
                'volume_24h': volume_24h,
                'volatility': volatility,
                'adx': adx,
                'liquidity': liquidity,
            }
        
        except Exception as e:
            system_logger.error(f"Error evaluating {symbol}: {e}")
            return {'symbol': symbol, 'passed': False, 'reason': 'error'}
    
    def select_coins(self) -> List[str]:
        """
        选择币种
        
        Returns:
            选中的币种列表
        """
        system_logger.info("Starting coin selection process...")
        
        # 获取所有USDT永续合约
        all_symbols = self.data_fetcher.get_usdt_perpetual_symbols()
        
        if not all_symbols:
            system_logger.warning("No symbols found")
            return []
        
        system_logger.info(f"Found {len(all_symbols)} USDT perpetual contracts")
        
        # 获取所有ticker数据
        tickers = self.data_fetcher.fetch_all_tickers()
        
        # 评估每个币种
        candidates = []
        for symbol in all_symbols:
            if symbol not in tickers:
                continue
            
            result = self.evaluate_coin(symbol, tickers[symbol])
            
            if result['passed']:
                candidates.append(result)
        
        system_logger.info(f"Found {len(candidates)} candidates after filtering")
        
        # 按评分排序
        candidates.sort(key=lambda x: x['score'], reverse=True)
        
        # 选择Top N
        max_coins = self.config.get('max_selected_coins', 10)
        selected = candidates[:max_coins]
        
        self.selected_coins = [c['symbol'] for c in selected]
        self.last_update = datetime.now()
        
        # 记录日志
        system_logger.info(f"Selected {len(self.selected_coins)} coins: {', '.join(self.selected_coins)}")
        
        for coin in selected:
            system_logger.info(
                f"  {coin['symbol']}: score={coin['score']:.2f}, "
                f"volume={coin['volume_24h']:.0f}, "
                f"volatility={coin['volatility']:.4f}, "
                f"adx={coin['adx']:.2f}"
            )
        
        return self.selected_coins
    
    def get_selected_coins(self) -> List[str]:
        """
        获取已选择的币种
        
        Returns:
            币种列表
        """
        if self.should_update():
            return self.select_coins()
        
        return self.selected_coins


# 全局选币器实例
coin_selector = CoinSelector()

