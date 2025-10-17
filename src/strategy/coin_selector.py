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
    
    def check_ema_alignment(self, df: pd.DataFrame) -> Dict:
        """
        检查EMA排列方向
        
        Args:
            df: K线数据
            
        Returns:
            EMA排列结果 {'direction': 'up'/'down'/'neutral', 'aligned': bool}
        """
        if df.empty or len(df) < 50:
            return {'direction': 'neutral', 'aligned': False}
        
        # 计算EMA
        df = technical_indicators.calculate_ema(df)
        
        ema_9 = df['ema_9'].iloc[-1]
        ema_21 = df['ema_21'].iloc[-1]
        ema_50 = df['ema_50'].iloc[-1]
        
        if pd.isna(ema_9) or pd.isna(ema_21) or pd.isna(ema_50):
            return {'direction': 'neutral', 'aligned': False}
        
        # 多头排列
        if ema_9 > ema_21 > ema_50:
            return {'direction': 'up', 'aligned': True}
        # 空头排列
        elif ema_9 < ema_21 < ema_50:
            return {'direction': 'down', 'aligned': True}
        else:
            return {'direction': 'neutral', 'aligned': False}
    
    def check_trend_stability(self, df: pd.DataFrame, direction: str) -> Dict:
        """
        检查趋势持续性
        
        Args:
            df: K线数据
            direction: 趋势方向 'up' 或 'down'
            
        Returns:
            趋势持续性评估结果
        """
        if df.empty or len(df) < 10:
            return {'stable': False, 'trend_bars': 0}
        
        # 确保有EMA21
        if 'ema_21' not in df.columns:
            df = technical_indicators.calculate_ema(df, [21])
        
        # 统计最近10根K线中符合趋势的数量
        trend_bars = 0
        check_count = min(10, len(df))
        
        for i in range(-check_count, 0):
            if direction == 'up':
                if df['close'].iloc[i] > df['ema_21'].iloc[i]:
                    trend_bars += 1
            elif direction == 'down':
                if df['close'].iloc[i] < df['ema_21'].iloc[i]:
                    trend_bars += 1
        
        # 至少70%的K线符合趋势方向
        stable = trend_bars >= (check_count * 0.7)
        
        return {'stable': stable, 'trend_bars': trend_bars, 'check_count': check_count}
    
    def check_pullback_quality(self, df: pd.DataFrame, direction: str) -> Dict:
        """
        检查回调质量（针对日内顺势回调交易）
        
        Args:
            df: K线数据（建议使用15分钟）
            direction: 趋势方向 'up' 或 'down'
            
        Returns:
            回调质量评估
        """
        if df.empty or len(df) < 20:
            return {'quality_score': 0, 'pullback_count': 0}
        
        # 确保有必要的指标
        if 'ema_21' not in df.columns or 'ema_50' not in df.columns:
            df = technical_indicators.calculate_ema(df, [21, 50])
        
        pullback_count = 0
        healthy_pullbacks = 0
        check_count = min(20, len(df) - 1)
        
        for i in range(-check_count, -1):
            if direction == 'up':
                # 多头市场的健康回调：
                # 1. 价格触及或跌破EMA21
                # 2. 但仍在EMA50之上
                # 3. 下一根K线重新站上EMA21
                if (df['low'].iloc[i] <= df['ema_21'].iloc[i] and 
                    df['close'].iloc[i] > df['ema_50'].iloc[i]):
                    pullback_count += 1
                    # 检查是否恢复
                    if i < -1 and df['close'].iloc[i+1] > df['ema_21'].iloc[i+1]:
                        healthy_pullbacks += 1
            
            elif direction == 'down':
                # 空头市场的健康回调：
                # 1. 价格触及或突破EMA21
                # 2. 但仍在EMA50之下
                # 3. 下一根K线重新跌破EMA21
                if (df['high'].iloc[i] >= df['ema_21'].iloc[i] and 
                    df['close'].iloc[i] < df['ema_50'].iloc[i]):
                    pullback_count += 1
                    # 检查是否恢复
                    if i < -1 and df['close'].iloc[i+1] < df['ema_21'].iloc[i+1]:
                        healthy_pullbacks += 1
        
        # 回调频率评分（2-8次为最佳）
        frequency_score = 0
        if 2 <= pullback_count <= 8:
            frequency_score = 5
        elif 1 <= pullback_count <= 10:
            frequency_score = 3
        
        # 回调健康度评分
        health_score = 0
        if pullback_count > 0:
            health_ratio = healthy_pullbacks / pullback_count
            health_score = health_ratio * 5  # 最高5分
        
        quality_score = frequency_score + health_score
        
        return {
            'quality_score': quality_score,
            'pullback_count': pullback_count,
            'healthy_pullbacks': healthy_pullbacks,
            'frequency_score': frequency_score,
            'health_score': health_score
        }
    
    def calculate_intraday_volatility(self, df: pd.DataFrame) -> Dict:
        """
        计算日内波动特征
        
        Args:
            df: K线数据（5分钟）
            
        Returns:
            日内波动评估
        """
        if df.empty or len(df) < 20:
            return {'avg_range': 0, 'suitable': False}
        
        # 计算最近20根K线的平均波动幅度
        ranges = []
        check_count = min(20, len(df))
        
        for i in range(-check_count, 0):
            range_pct = (df['high'].iloc[i] - df['low'].iloc[i]) / df['close'].iloc[i]
            ranges.append(range_pct)
        
        avg_range = np.mean(ranges)
        
        # 日内交易理想波动范围：0.2%-0.8%
        suitable = 0.002 <= avg_range <= 0.008
        
        # 计算波动稳定性（标准差）
        std_range = np.std(ranges)
        stability = 1 / (1 + std_range * 100)  # 标准差越小，稳定性越高
        
        return {
            'avg_range': avg_range,
            'suitable': suitable,
            'stability': stability,
            'ranges': ranges
        }
    
    def evaluate_coin(self, symbol: str, ticker: Dict) -> Dict:
        """
        评估单个币种（针对日内顺势回调交易优化）
        
        Args:
            symbol: 交易对符号
            ticker: ticker数据
            
        Returns:
            评估结果
        """
        try:
            # 第一步：基础筛选 - 成交量
            volume_24h = ticker.get('quoteVolume', ticker.get('volume', 0))
            min_volume = self.config.get('min_volume_24h', 5000000)
            if volume_24h < min_volume:
                return {'symbol': symbol, 'passed': False, 'reason': 'low_volume'}
            
            # 第二步：获取多周期K线数据
            df_1h = self.data_fetcher.fetch_ohlcv_df(symbol, '1h', limit=50)
            if df_1h.empty or len(df_1h) < 20:
                return {'symbol': symbol, 'passed': False, 'reason': 'insufficient_data_1h'}
            
            df_15m = self.data_fetcher.fetch_ohlcv_df(symbol, '15m', limit=100)
            if df_15m.empty or len(df_15m) < 50:
                return {'symbol': symbol, 'passed': False, 'reason': 'insufficient_data_15m'}
            
            df_5m = self.data_fetcher.fetch_ohlcv_df(symbol, '5m', limit=100)
            if df_5m.empty or len(df_5m) < 20:
                return {'symbol': symbol, 'passed': False, 'reason': 'insufficient_data_5m'}
            
            # 第三步：趋势强度筛选（ADX）
            df_1h = technical_indicators.calculate_adx(df_1h)
            adx = df_1h['adx'].iloc[-1]
            plus_di = df_1h['plus_di'].iloc[-1]
            minus_di = df_1h['minus_di'].iloc[-1]
            
            min_adx = self.config.get('min_adx', 25)
            if pd.isna(adx) or adx < min_adx:
                return {'symbol': symbol, 'passed': False, 'reason': 'weak_trend'}
            
            # 第四步：趋势方向明确性（DI差值）
            if pd.isna(plus_di) or pd.isna(minus_di):
                return {'symbol': symbol, 'passed': False, 'reason': 'invalid_di'}
            
            di_diff = abs(plus_di - minus_di)
            if di_diff < 15:  # 趋势方向不够明确
                return {'symbol': symbol, 'passed': False, 'reason': 'unclear_trend_direction'}
            
            # 判断趋势方向
            trend_direction = 'up' if plus_di > minus_di else 'down'
            
            # 第五步：多周期EMA排列检查
            ema_1h = self.check_ema_alignment(df_1h)
            ema_15m = self.check_ema_alignment(df_15m)
            
            # 两个周期方向必须一致且排列清晰
            if not ema_1h['aligned'] or not ema_15m['aligned']:
                return {'symbol': symbol, 'passed': False, 'reason': 'ema_not_aligned'}
            
            if ema_1h['direction'] != ema_15m['direction']:
                return {'symbol': symbol, 'passed': False, 'reason': 'timeframe_conflict'}
            
            # 第六步：趋势持续性检查
            stability_1h = self.check_trend_stability(df_1h, trend_direction)
            if not stability_1h['stable']:
                return {'symbol': symbol, 'passed': False, 'reason': 'unstable_trend'}
            
            # 第七步：回调质量评估（最关键）
            pullback_quality = self.check_pullback_quality(df_15m, trend_direction)
            if pullback_quality['quality_score'] < 3:  # 最低3分
                return {'symbol': symbol, 'passed': False, 'reason': 'poor_pullback_quality'}
            
            # 第八步：日内波动特征检查
            intraday_vol = self.calculate_intraday_volatility(df_5m)
            if not intraday_vol['suitable']:
                return {'symbol': symbol, 'passed': False, 'reason': 'unsuitable_intraday_volatility'}
            
            # 第九步：流动性检查
            orderbook = self.data_fetcher.fetch_orderbook_analysis(symbol, limit=10)
            if not orderbook:
                return {'symbol': symbol, 'passed': False, 'reason': 'no_orderbook'}
            
            liquidity = orderbook.get('bid_depth', 0) + orderbook.get('ask_depth', 0)
            min_liquidity = self.config.get('liquidity_depth_threshold', 100000)
            if liquidity < min_liquidity:
                return {'symbol': symbol, 'passed': False, 'reason': 'low_liquidity'}
            
            # 第十步：综合评分（针对日内顺势回调交易）
            score = 0
            
            # 1. 趋势方向明确性（最高10分）
            trend_clarity_score = min(di_diff / 3, 10)
            score += trend_clarity_score
            
            # 2. 趋势强度（最高8分）
            trend_strength_score = min(adx / 5, 8)
            score += trend_strength_score
            
            # 3. 趋势持续性（最高8分）
            stability_score = (stability_1h['trend_bars'] / stability_1h['check_count']) * 8
            score += stability_score
            
            # 4. 回调质量（最高10分）⭐️ 权重最高
            score += pullback_quality['quality_score']
            
            # 5. 流动性（最高6分）
            liquidity_score = min(liquidity / 200000, 6)
            score += liquidity_score
            
            # 6. 成交量（最高6分）
            volume_score = min(volume_24h / 15000000, 6)
            score += volume_score
            
            # 7. 日内波动适中性（最高4分）
            volatility_score = 4 - abs(intraday_vol['avg_range'] - 0.004) * 1000
            volatility_score = max(0, volatility_score) * intraday_vol['stability']
            score += volatility_score
            
            return {
                'symbol': symbol,
                'passed': True,
                'score': score,
                'trend_direction': trend_direction,
                'trend_clarity': di_diff,
                'adx': adx,
                'stability': stability_1h['trend_bars'],
                'pullback_quality': pullback_quality['quality_score'],
                'pullback_count': pullback_quality['pullback_count'],
                'intraday_range': intraday_vol['avg_range'],
                'liquidity': liquidity,
                'volume_24h': volume_24h,
                'score_details': {
                    'trend_clarity': round(trend_clarity_score, 2),
                    'trend_strength': round(trend_strength_score, 2),
                    'stability': round(stability_score, 2),
                    'pullback': pullback_quality['quality_score'],
                    'liquidity': round(liquidity_score, 2),
                    'volume': round(volume_score, 2),
                    'volatility': round(volatility_score, 2),
                }
            }
        
        except Exception as e:
            system_logger.error(f"Error evaluating {symbol}: {e}")
            return {'symbol': symbol, 'passed': False, 'reason': 'error'}
    
    def select_coins(self) -> List[str]:
        """
        选择币种（针对日内顺势回调交易优化）
        
        Returns:
            选中的币种列表
        """
        system_logger.info("="*60)
        system_logger.info("Starting coin selection for INTRADAY TREND-PULLBACK trading")
        system_logger.info("="*60)
        
        # 获取所有USDT永续合约
        all_symbols = self.data_fetcher.get_usdt_perpetual_symbols()
        
        if not all_symbols:
            system_logger.warning("No symbols found")
            return []
        
        system_logger.info(f"Total USDT perpetual contracts: {len(all_symbols)}")
        
        # 获取所有ticker数据
        tickers = self.data_fetcher.fetch_all_tickers(all_symbols)
        
        # 统计筛选过程
        filter_stats = {
            'total': len(all_symbols),
            'low_volume': 0,
            'insufficient_data': 0,
            'weak_trend': 0,
            'unclear_direction': 0,
            'ema_not_aligned': 0,
            'timeframe_conflict': 0,
            'unstable_trend': 0,
            'poor_pullback': 0,
            'unsuitable_volatility': 0,
            'low_liquidity': 0,
            'error': 0,
            'passed': 0
        }
        
        # 评估每个币种
        candidates = []
        for i, symbol in enumerate(all_symbols, 1):
            if symbol not in tickers:
                continue
            
            # 显示进度
            if i % 10 == 0:
                system_logger.info(f"Progress: {i}/{len(all_symbols)} evaluated...")
            
            result = self.evaluate_coin(symbol, tickers[symbol])
            
            # 统计筛选原因
            if result['passed']:
                candidates.append(result)
                filter_stats['passed'] += 1
            else:
                reason = result.get('reason', 'unknown')
                if 'volume' in reason:
                    filter_stats['low_volume'] += 1
                elif 'insufficient_data' in reason:
                    filter_stats['insufficient_data'] += 1
                elif 'weak_trend' in reason:
                    filter_stats['weak_trend'] += 1
                elif 'unclear_trend_direction' in reason:
                    filter_stats['unclear_direction'] += 1
                elif 'ema_not_aligned' in reason:
                    filter_stats['ema_not_aligned'] += 1
                elif 'timeframe_conflict' in reason:
                    filter_stats['timeframe_conflict'] += 1
                elif 'unstable_trend' in reason:
                    filter_stats['unstable_trend'] += 1
                elif 'pullback' in reason:
                    filter_stats['poor_pullback'] += 1
                elif 'volatility' in reason:
                    filter_stats['unsuitable_volatility'] += 1
                elif 'liquidity' in reason:
                    filter_stats['low_liquidity'] += 1
                elif 'error' in reason:
                    filter_stats['error'] += 1
        
        # 输出筛选统计
        system_logger.info("")
        system_logger.info("Filtering Statistics:")
        system_logger.info(f"  Total contracts:          {filter_stats['total']}")
        system_logger.info(f"  ✗ Low volume:             {filter_stats['low_volume']}")
        system_logger.info(f"  ✗ Insufficient data:      {filter_stats['insufficient_data']}")
        system_logger.info(f"  ✗ Weak trend (ADX<25):    {filter_stats['weak_trend']}")
        system_logger.info(f"  ✗ Unclear direction:      {filter_stats['unclear_direction']}")
        system_logger.info(f"  ✗ EMA not aligned:        {filter_stats['ema_not_aligned']}")
        system_logger.info(f"  ✗ Timeframe conflict:     {filter_stats['timeframe_conflict']}")
        system_logger.info(f"  ✗ Unstable trend:         {filter_stats['unstable_trend']}")
        system_logger.info(f"  ✗ Poor pullback quality:  {filter_stats['poor_pullback']}")
        system_logger.info(f"  ✗ Unsuitable volatility:  {filter_stats['unsuitable_volatility']}")
        system_logger.info(f"  ✗ Low liquidity:          {filter_stats['low_liquidity']}")
        system_logger.info(f"  ✗ Errors:                 {filter_stats['error']}")
        system_logger.info(f"  ✓ Passed all filters:     {filter_stats['passed']}")
        system_logger.info("")
        
        # 按评分排序
        candidates.sort(key=lambda x: x['score'], reverse=True)
        
        # 选择Top N
        max_coins = self.config.get('max_selected_coins', 10)
        selected = candidates[:max_coins]
        
        self.selected_coins = [c['symbol'] for c in selected]
        self.last_update = datetime.now()
        
        # 记录日志
        system_logger.info(f"Selected {len(self.selected_coins)} coins for intraday trend-pullback trading")
        system_logger.info(f"Coins: {', '.join(self.selected_coins)}")
        
        for coin in selected:
            system_logger.info(
                f"  {coin['symbol']} (Score: {coin['score']:.2f}): "
                f"Trend={coin.get('trend_direction', 'N/A').upper()}, "
                f"ADX={coin['adx']:.1f}, "
                f"Clarity={coin.get('trend_clarity', 0):.1f}, "
                f"Pullback={coin.get('pullback_quality', 0):.1f}/10, "
                f"Stability={coin.get('stability', 0)}/10, "
                f"Volume={coin['volume_24h']/1000000:.1f}M"
            )
            
            # 详细评分
            if 'score_details' in coin:
                details = coin['score_details']
                system_logger.debug(
                    f"    Score breakdown: Clarity={details.get('trend_clarity', 0):.1f}, "
                    f"Strength={details.get('trend_strength', 0):.1f}, "
                    f"Stability={details.get('stability', 0):.1f}, "
                    f"Pullback={details.get('pullback', 0):.1f}, "
                    f"Liquidity={details.get('liquidity', 0):.1f}, "
                    f"Volume={details.get('volume', 0):.1f}, "
                    f"Volatility={details.get('volatility', 0):.1f}"
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

