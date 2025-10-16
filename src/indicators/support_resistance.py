"""支撑阻力位计算模块"""
import pandas as pd
import numpy as np
from typing import List, Tuple, Dict
from scipy.signal import argrelextrema
from ..monitor.logger import system_logger


class SupportResistance:
    """支撑阻力位计算类"""
    
    def __init__(self):
        """初始化"""
        pass
    
    def find_local_extrema(self, df: pd.DataFrame, order: int = 5) -> Tuple[List[float], List[float]]:
        """
        查找局部高低点
        
        Args:
            df: K线数据
            order: 比较的邻近点数
            
        Returns:
            (支撑位列表, 阻力位列表)
        """
        if len(df) < order * 2:
            return [], []
        
        # 找局部最低点（支撑）
        local_min_indices = argrelextrema(df['low'].values, np.less, order=order)[0]
        supports = df['low'].iloc[local_min_indices].tolist()
        
        # 找局部最高点（阻力）
        local_max_indices = argrelextrema(df['high'].values, np.greater, order=order)[0]
        resistances = df['high'].iloc[local_max_indices].tolist()
        
        return supports, resistances
    
    def cluster_levels(self, levels: List[float], tolerance: float = 0.02) -> List[float]:
        """
        聚类相近的价格水平
        
        Args:
            levels: 价格水平列表
            tolerance: 容差（百分比）
            
        Returns:
            聚类后的价格水平
        """
        if not levels:
            return []
        
        levels = sorted(levels)
        clusters = []
        current_cluster = [levels[0]]
        
        for level in levels[1:]:
            # 如果在容差范围内，加入当前簇
            if (level - current_cluster[-1]) / current_cluster[-1] <= tolerance:
                current_cluster.append(level)
            else:
                # 否则，保存当前簇的平均值，开始新簇
                clusters.append(np.mean(current_cluster))
                current_cluster = [level]
        
        # 添加最后一个簇
        clusters.append(np.mean(current_cluster))
        
        return clusters
    
    def identify_key_levels(self, df: pd.DataFrame, num_levels: int = 5) -> Dict[str, List[float]]:
        """
        识别关键支撑阻力位
        
        Args:
            df: K线数据
            num_levels: 返回的关键水平数量
            
        Returns:
            {'support': [...], 'resistance': [...]}
        """
        # 查找局部极值
        supports, resistances = self.find_local_extrema(df, order=5)
        
        # 聚类
        supports = self.cluster_levels(supports)
        resistances = self.cluster_levels(resistances)
        
        # 按照距离当前价格的远近排序，取最近的几个
        current_price = df['close'].iloc[-1]
        
        supports = sorted(supports, key=lambda x: abs(current_price - x))[:num_levels]
        resistances = sorted(resistances, key=lambda x: abs(current_price - x))[:num_levels]
        
        # 过滤：支撑要在当前价格下方，阻力要在当前价格上方
        supports = [s for s in supports if s < current_price]
        resistances = [r for r in resistances if r > current_price]
        
        return {
            'support': sorted(supports, reverse=True),  # 从高到低
            'resistance': sorted(resistances)  # 从低到高
        }
    
    def calculate_fibonacci_retracement(self, 
                                        df: pd.DataFrame, 
                                        lookback: int = 50) -> Dict[str, float]:
        """
        计算斐波那契回撤位
        
        Args:
            df: K线数据
            lookback: 回看周期
            
        Returns:
            斐波那契水平字典
        """
        if len(df) < lookback:
            lookback = len(df)
        
        recent_df = df.tail(lookback)
        
        # 找到最高点和最低点
        high = recent_df['high'].max()
        low = recent_df['low'].min()
        
        diff = high - low
        
        # 判断趋势方向
        high_idx = recent_df['high'].idxmax()
        low_idx = recent_df['low'].idxmin()
        
        if high_idx > low_idx:
            # 上升趋势，从低点向高点计算
            levels = {
                'level_0': low,
                'level_236': low + 0.236 * diff,
                'level_382': low + 0.382 * diff,
                'level_500': low + 0.5 * diff,
                'level_618': low + 0.618 * diff,
                'level_786': low + 0.786 * diff,
                'level_100': high,
                'trend': 'up'
            }
        else:
            # 下降趋势，从高点向低点计算
            levels = {
                'level_0': high,
                'level_236': high - 0.236 * diff,
                'level_382': high - 0.382 * diff,
                'level_500': high - 0.5 * diff,
                'level_618': high - 0.618 * diff,
                'level_786': high - 0.786 * diff,
                'level_100': low,
                'trend': 'down'
            }
        
        return levels
    
    def find_round_numbers(self, current_price: float, num_levels: int = 3) -> List[float]:
        """
        查找附近的整数关口
        
        Args:
            current_price: 当前价格
            num_levels: 返回的关口数量
            
        Returns:
            整数关口列表
        """
        # 根据价格大小确定步长
        if current_price < 1:
            step = 0.1
        elif current_price < 10:
            step = 0.5
        elif current_price < 100:
            step = 5
        elif current_price < 1000:
            step = 50
        elif current_price < 10000:
            step = 500
        else:
            step = 1000
        
        # 找到附近的整数关口
        base = round(current_price / step) * step
        
        levels = []
        for i in range(-num_levels, num_levels + 1):
            level = base + i * step
            if level > 0 and abs(level - current_price) / current_price < 0.1:  # 在10%范围内
                levels.append(level)
        
        return sorted(levels)
    
    def calculate_volume_profile(self, df: pd.DataFrame, num_bins: int = 20) -> Dict:
        """
        计算成交密集区（Volume Profile）
        
        Args:
            df: K线数据
            num_bins: 价格区间数量
            
        Returns:
            成交密集区信息
        """
        if df.empty:
            return {}
        
        # 价格范围
        price_min = df['low'].min()
        price_max = df['high'].max()
        
        # 创建价格区间
        bins = np.linspace(price_min, price_max, num_bins + 1)
        
        # 计算每个区间的成交量
        volume_at_price = np.zeros(num_bins)
        
        for i, row in df.iterrows():
            # 找到价格所在的区间
            bin_idx = np.digitize(row['close'], bins) - 1
            if 0 <= bin_idx < num_bins:
                volume_at_price[bin_idx] += row['volume']
        
        # 找到成交量最大的区间（POC - Point of Control）
        poc_idx = np.argmax(volume_at_price)
        poc_price = (bins[poc_idx] + bins[poc_idx + 1]) / 2
        
        # 找到高成交量区域（超过平均成交量的1.5倍）
        avg_volume = np.mean(volume_at_price)
        high_volume_zones = []
        
        for i in range(num_bins):
            if volume_at_price[i] > avg_volume * 1.5:
                price = (bins[i] + bins[i + 1]) / 2
                high_volume_zones.append({
                    'price': price,
                    'volume': volume_at_price[i]
                })
        
        return {
            'poc_price': poc_price,
            'poc_volume': volume_at_price[poc_idx],
            'high_volume_zones': high_volume_zones,
        }
    
    def get_nearest_support_resistance(self, 
                                       df: pd.DataFrame, 
                                       current_price: float = None) -> Dict[str, float]:
        """
        获取最近的支撑阻力位
        
        Args:
            df: K线数据
            current_price: 当前价格，默认为最新收盘价
            
        Returns:
            {'nearest_support': float, 'nearest_resistance': float}
        """
        if current_price is None:
            current_price = df['close'].iloc[-1]
        
        # 获取所有关键水平
        levels = self.identify_key_levels(df)
        fib_levels = self.calculate_fibonacci_retracement(df)
        
        all_supports = levels['support']
        all_resistances = levels['resistance']
        
        # 添加斐波那契水平
        for key, value in fib_levels.items():
            if key.startswith('level_') and isinstance(value, (int, float)):
                if value < current_price:
                    all_supports.append(value)
                elif value > current_price:
                    all_resistances.append(value)
        
        # 找到最近的支撑和阻力
        nearest_support = max(all_supports) if all_supports else current_price * 0.98
        nearest_resistance = min(all_resistances) if all_resistances else current_price * 1.02
        
        return {
            'nearest_support': nearest_support,
            'nearest_resistance': nearest_resistance,
            'all_supports': sorted(all_supports, reverse=True)[:3],
            'all_resistances': sorted(all_resistances)[:3],
        }


# 全局支撑阻力计算实例
support_resistance = SupportResistance()

