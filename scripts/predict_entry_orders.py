#!/usr/bin/env python3
"""
智能挂单策略预测工具
根据市场状态预测最佳挂单买入价格
"""
import sys
from pathlib import Path
from typing import List, Dict

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.strategy.trend_analyzer import trend_analyzer
from src.strategy.signal_generator import SignalGenerator, EntryMode
from src.core.data_fetcher import data_fetcher
from src.indicators.technical import technical_indicators
from loguru import logger


class EntryOrderPredictor:
    """挂单策略预测器"""
    
    def __init__(self, symbol: str, leverage: int = None, account_balance: float = 1000, single_mode: bool = False):
        self.symbol = symbol
        self.signal_gen = SignalGenerator()
        self.data_5m = None
        self.data_15m = None
        self.data_1h = None
        self.trend_info = None
        self.entry_mode = None
        self.current_price = 0
        self.user_leverage = leverage  # 用户指定的杠杆
        self.recommended_leverage = None  # 推荐杠杆
        self.account_balance = account_balance  # 账户余额
        self.single_mode = single_mode  # 单一最优挂单模式
        
    def fetch_data(self) -> bool:
        """获取市场数据"""
        logger.info(f"📊 获取 {self.symbol} 市场数据...")
        
        self.data_5m = data_fetcher.fetch_ohlcv_df(self.symbol, '5m', limit=200)
        self.data_15m = data_fetcher.fetch_ohlcv_df(self.symbol, '15m', limit=100)
        self.data_1h = data_fetcher.fetch_ohlcv_df(self.symbol, '1h', limit=100)
        
        if self.data_5m.empty:
            logger.error("❌ 数据获取失败")
            return False
        
        self.current_price = self.data_5m['close'].iloc[-1]
        logger.success(f"✅ 当前价格: {self.current_price:.4f} USDT\n")
        return True
    
    def analyze_market(self) -> bool:
        """分析市场状态"""
        logger.info("🔍 分析市场状态...")
        
        # 趋势分析
        self.trend_info = trend_analyzer.analyze(self.data_5m, self.data_15m, self.data_1h)
        logger.info(f"   趋势方向: {self.trend_info.direction.upper()}")
        logger.info(f"   趋势强度: {self.trend_info.strength:.2%}")
        logger.info(f"   强趋势: {'是' if self.trend_info.is_strong else '否'}\n")
        
        if not self.trend_info.is_strong:
            logger.warning("⚠️  当前趋势不够强，不建议挂单")
            return False
        
        # 计算技术指标
        self.data_5m = technical_indicators.calculate_all_indicators(self.data_5m.copy())
        
        # 检测入场模式
        self.entry_mode = self.signal_gen.detect_entry_mode(self.data_5m, self.trend_info)
        logger.info(f"🎯 入场模式: {self.entry_mode.value.upper()}\n")
        
        return True
    
    def calculate_key_levels(self) -> Dict:
        """计算关键价格位"""
        logger.info("📍 计算关键价格位...")
        
        levels = {
            'fibonacci': {},
            'support_resistance': {},
            'ema': {},
            'bollinger': {},
            'psychological': []
        }
        
        # 1. 斐波那契回撤位
        fib_levels = self.signal_gen.sr.calculate_fibonacci_retracement(self.data_5m)
        if fib_levels and fib_levels.get('trend') != 'neutral':
            levels['fibonacci'] = {
                'trend': fib_levels.get('trend'),
                'level_0': fib_levels.get('level_0', 0),
                'level_236': fib_levels.get('level_236', 0),
                'level_382': fib_levels.get('level_382', 0),
                'level_500': fib_levels.get('level_500', 0),
                'level_618': fib_levels.get('level_618', 0),
                'level_100': fib_levels.get('level_100', 0),
            }
            logger.info("   ✅ 斐波那契回撤位已计算")
        
        # 2. 支撑阻力位
        sr_levels = self.signal_gen.sr.get_nearest_support_resistance(
            self.data_5m, self.current_price
        )
        if sr_levels:
            levels['support_resistance'] = {
                'nearest_support': sr_levels.get('nearest_support', 0),
                'nearest_resistance': sr_levels.get('nearest_resistance', 0),
            }
            logger.info("   ✅ 支撑阻力位已计算")
        
        # 3. EMA均线位
        if 'ema_9' in self.data_5m.columns:
            levels['ema'] = {
                'ema_9': self.data_5m['ema_9'].iloc[-1],
                'ema_21': self.data_5m['ema_21'].iloc[-1] if 'ema_21' in self.data_5m.columns else 0,
                'ema_50': self.data_5m['ema_50'].iloc[-1] if 'ema_50' in self.data_5m.columns else 0,
            }
            logger.info("   ✅ EMA均线位已计算")
        
        # 4. 布林带
        if 'bb_lower' in self.data_5m.columns:
            levels['bollinger'] = {
                'upper': self.data_5m['bb_upper'].iloc[-1],
                'middle': self.data_5m['bb_middle'].iloc[-1],
                'lower': self.data_5m['bb_lower'].iloc[-1],
            }
            logger.info("   ✅ 布林带已计算")
        
        # 5. 心理价位（整数关口）
        base = int(self.current_price * 10) / 10  # 保留1位小数
        levels['psychological'] = [
            round(base - 0.01, 4),
            round(base, 4),
            round(base + 0.01, 4),
        ]
        logger.info("   ✅ 心理价位已计算\n")
        
        return levels
    
    def _calculate_leverage_recommendation(self, score: float, risk_level: str) -> Dict:
        """
        根据评分计算建议杠杆倍数
        
        Args:
            score: 可行性评分
            risk_level: 风险等级 ('high', 'medium', 'low', 'very_low')
            
        Returns:
            杠杆建议字典
        """
        # 基础杠杆范围
        leverage_ranges = {
            'high': (10, 20),      # 高分：10-20倍
            'medium': (5, 10),     # 中分：5-10倍
            'low': (3, 5),         # 低分：3-5倍
            'very_low': (1, 3)     # 很低：1-3倍
        }
        
        min_lev, max_lev = leverage_ranges.get(risk_level, (5, 10))
        
        # 根据具体分数细化
        if score >= 85:
            recommended = max_lev
            aggressive = max_lev
            conservative = int(max_lev * 0.7)
        elif score >= 75:
            recommended = int((min_lev + max_lev) / 2) + 2
            aggressive = max_lev
            conservative = min_lev
        elif score >= 65:
            recommended = int((min_lev + max_lev) / 2)
            aggressive = max_lev
            conservative = min_lev
        elif score >= 55:
            recommended = int((min_lev + max_lev) / 2) - 1
            aggressive = int((min_lev + max_lev) / 2)
            conservative = min_lev
        elif score >= 45:
            recommended = min_lev
            aggressive = int((min_lev + max_lev) / 2)
            conservative = max(1, min_lev - 2)
        else:
            recommended = max(1, min_lev - 2)
            aggressive = min_lev
            conservative = 1
        
        return {
            'recommended': recommended,
            'conservative': conservative,
            'aggressive': aggressive,
            'range': f"{min_lev}-{max_lev}x",
            'description': self._get_leverage_description(risk_level)
        }
    
    def _get_leverage_description(self, risk_level: str) -> str:
        """获取杠杆描述"""
        descriptions = {
            'high': '市场条件优秀，可以使用较高杠杆',
            'medium': '市场条件一般，建议中等杠杆',
            'low': '市场条件不佳，应降低杠杆',
            'very_low': '市场条件很差，仅建议极低杠杆或不交易'
        }
        return descriptions.get(risk_level, '建议谨慎使用杠杆')
    
    def evaluate_order_feasibility(self) -> Dict:
        """评估挂单可行性"""
        logger.info("\n" + "=" * 80)
        logger.info("  🔍 挂单可行性评估")
        logger.info("=" * 80 + "\n")
        
        score = 0
        max_score = 100
        reasons = []
        warnings = []
        
        # 1. 趋势强度 (30分)
        trend_strength_score = self.trend_info.strength * 30
        score += trend_strength_score
        
        if self.trend_info.strength >= 0.8:
            reasons.append(f"✅ 趋势非常强 ({self.trend_info.strength:.0%}) +{trend_strength_score:.0f}分")
        elif self.trend_info.strength >= 0.6:
            reasons.append(f"✅ 趋势较强 ({self.trend_info.strength:.0%}) +{trend_strength_score:.0f}分")
        else:
            warnings.append(f"⚠️  趋势偏弱 ({self.trend_info.strength:.0%}) +{trend_strength_score:.0f}分")
        
        # 2. 入场模式明确性 (20分)
        mode_score = 0
        if self.entry_mode == EntryMode.PULLBACK:
            mode_score = 20
            reasons.append(f"✅ 回调入场模式明确 +{mode_score}分")
        elif self.entry_mode == EntryMode.REBOUND:
            mode_score = 18
            reasons.append(f"✅ 反弹模式明确 +{mode_score}分")
        elif self.entry_mode == EntryMode.BREAKOUT:
            mode_score = 15
            reasons.append(f"⚠️  突破模式不确定性高 +{mode_score}分")
        elif self.entry_mode == EntryMode.TREND_FOLLOWING:
            mode_score = 12
            warnings.append(f"⚠️  趋势跟随模式风险较高 +{mode_score}分")
        
        score += mode_score
        
        # 3. RSI状态 (15分)
        rsi = self.data_5m['rsi'].iloc[-1] if 'rsi' in self.data_5m.columns else 50
        rsi_score = 0
        
        if self.trend_info.direction == 'down':
            # 下跌趋势，RSI越低越好（超卖更安全）
            if rsi < 25:
                rsi_score = 15
                reasons.append(f"✅ RSI深度超卖 ({rsi:.1f}) +{rsi_score}分")
            elif rsi < 35:
                rsi_score = 12
                reasons.append(f"✅ RSI超卖 ({rsi:.1f}) +{rsi_score}分")
            elif rsi < 45:
                rsi_score = 8
                reasons.append(f"⚠️  RSI偏低 ({rsi:.1f}) +{rsi_score}分")
            else:
                rsi_score = 3
                warnings.append(f"⚠️  RSI不够低 ({rsi:.1f}) +{rsi_score}分")
        else:
            # 上涨趋势，RSI越高越好（超买更安全做空）
            if rsi > 75:
                rsi_score = 15
                reasons.append(f"✅ RSI深度超买 ({rsi:.1f}) +{rsi_score}分")
            elif rsi > 65:
                rsi_score = 12
                reasons.append(f"✅ RSI超买 ({rsi:.1f}) +{rsi_score}分")
            elif rsi > 55:
                rsi_score = 8
                reasons.append(f"⚠️  RSI偏高 ({rsi:.1f}) +{rsi_score}分")
            else:
                rsi_score = 3
                warnings.append(f"⚠️  RSI不够高 ({rsi:.1f}) +{rsi_score}分")
        
        score += rsi_score
        
        # 4. 关键价格位清晰度 (20分)
        levels = self.calculate_key_levels()
        price_levels_score = 0
        
        fib_levels = levels.get('fibonacci', {})
        sr_levels = levels.get('support_resistance', {})
        
        has_fib = bool(fib_levels.get('level_382') or fib_levels.get('level_500'))
        has_sr = bool(sr_levels.get('nearest_support') or sr_levels.get('nearest_resistance'))
        
        if has_fib and has_sr:
            price_levels_score = 20
            reasons.append(f"✅ 关键价格位清晰（斐波那契+支撑阻力） +{price_levels_score}分")
        elif has_fib or has_sr:
            price_levels_score = 12
            reasons.append(f"⚠️  有部分关键价格位 +{price_levels_score}分")
        else:
            price_levels_score = 0
            warnings.append(f"❌ 关键价格位不清晰 +{price_levels_score}分")
        
        score += price_levels_score
        
        # 5. 波动率合理性 (15分)
        if 'atr' in self.data_5m.columns:
            atr = self.data_5m['atr'].iloc[-1]
            atr_pct = atr / self.current_price
            
            if 0.01 <= atr_pct <= 0.05:  # 1%-5%波动率
                volatility_score = 15
                reasons.append(f"✅ 波动率适中 ({atr_pct:.2%}) +{volatility_score}分")
            elif atr_pct < 0.01:
                volatility_score = 8
                warnings.append(f"⚠️  波动率过低 ({atr_pct:.2%}) +{volatility_score}分")
            else:
                volatility_score = 5
                warnings.append(f"⚠️  波动率过高 ({atr_pct:.2%}) +{volatility_score}分")
            
            score += volatility_score
        else:
            score += 10  # 默认分
        
        # 6. 评估结论和杠杆建议
        if score >= 80:
            recommendation = "🟢 强烈建议挂单"
            action = "EXECUTE"
            self.recommended_leverage = self._calculate_leverage_recommendation(score, 'high')
        elif score >= 60:
            recommendation = "🟡 可以挂单，但需谨慎"
            action = "EXECUTE_WITH_CAUTION"
            self.recommended_leverage = self._calculate_leverage_recommendation(score, 'medium')
        elif score >= 40:
            recommendation = "🟠 不建议挂单，等待更好时机"
            action = "WAIT"
            self.recommended_leverage = self._calculate_leverage_recommendation(score, 'low')
        else:
            recommendation = "🔴 不要挂单，市场条件不佳"
            action = "NO_EXECUTE"
            self.recommended_leverage = self._calculate_leverage_recommendation(score, 'very_low')
        
        return {
            'score': score,
            'max_score': max_score,
            'percentage': score / max_score,
            'recommendation': recommendation,
            'action': action,
            'reasons': reasons,
            'warnings': warnings,
            'recommended_leverage': self.recommended_leverage
        }
    
    def predict_entry_orders(self) -> List[Dict]:
        """预测挂单策略（顺势回调交易）"""
        logger.info("=" * 80)
        logger.info("  🎯 顺势回调挂单策略分析")
        logger.info("=" * 80 + "\n")
        
        orders = []
        
        # 顺势回调交易逻辑 ⭐
        # 下跌趋势：等待反弹到阻力位 → 做空（顺势）
        # 上涨趋势：等待回调到支撑位 → 做多（顺势）
        if self.trend_info.direction == 'down':
            logger.info("📉 当前趋势：下跌 → 顺势做空策略\n")
            orders = self._predict_short_orders()  # 顺势做空
        else:
            logger.info("📈 当前趋势：上涨 → 顺势做多策略\n")
            orders = self._predict_long_orders()  # 顺势做多
        
        # 单一最优挂单模式：选择最佳的1个 ⭐
        if self.single_mode and len(orders) > 1:
            best_order = self._select_best_order(orders)
            logger.info(f"\n💡 单一最优挂单模式：已从 {len(orders)} 个候选中选择最优挂单\n")
            orders = [best_order]
        
        return orders
    
    def _select_best_order(self, orders: List[Dict]) -> Dict:
        """
        从多个挂单中选择最优的1个
        
        选择策略：
        1. 综合评分 = 触达概率 × 0.6 + 距离优势 × 0.4
        2. 触达概率越高越好
        3. 距离越近越好（但不能太近，至少要有1%回调空间）
        """
        best_order = None
        best_score = -1
        
        for order in orders:
            probability = order['probability']
            distance = order['distance_pct']
            
            # 综合评分
            # 触达概率权重60%，距离优势权重40%
            # 距离优势：假设最佳距离是1.5-2.5%，超出此范围扣分
            distance_score = 1.0
            if distance < 0.015:  # 太近（<1.5%），可能是假突破
                distance_score = 0.6
            elif distance > 0.03:  # 太远（>3%），不太可能触达
                distance_score = 0.7
            else:  # 1.5%-3%之间，最佳范围
                distance_score = 1.0
            
            # 综合评分
            score = probability * 0.6 + distance_score * 0.4
            
            if score > best_score:
                best_score = score
                best_order = order
        
        # 调整仓位为100%（单一挂单，全仓）
        if best_order:
            best_order['position_pct'] = 1.0
            logger.info(f"🎯 最优挂单选择：{best_order['reason']}")
            logger.info(f"   综合评分: {best_score:.2f}")
            logger.info(f"   触达概率: {best_order['probability']*100:.0f}%")
            logger.info(f"   距离: {best_order['distance_pct']*100:.2f}%")
            logger.info(f"   仓位调整: {best_order['position_pct']*100:.0f}% (全仓)")
        
        return best_order
    
    def _predict_long_orders(self) -> List[Dict]:
        """预测做多挂单（上涨趋势中等待回调到支撑位）"""
        logger.info("📈 做多挂单策略（上涨趋势回调做多 - 顺势）\n")
        
        levels = self.calculate_key_levels()
        orders = []
        
        rsi = self.data_5m['rsi'].iloc[-1] if 'rsi' in self.data_5m.columns else 50
        
        # 根据入场模式选择策略
        if self.entry_mode == EntryMode.REBOUND:
            logger.info("🔄 反弹入场模式 - 超卖反弹策略")
            orders = self._rebound_long_orders(levels, rsi)
            
        elif self.entry_mode == EntryMode.BREAKOUT:
            logger.info("🚀 突破入场模式 - 突破追涨策略")
            orders = self._breakout_long_orders(levels)
            
        elif self.entry_mode == EntryMode.TREND_FOLLOWING:
            logger.info("📊 趋势跟随模式 - 顺势加仓策略")
            orders = self._trend_long_orders(levels)
            
        else:  # PULLBACK
            logger.info("📉 回调入场模式 - 回调买入策略")
            orders = self._pullback_long_orders(levels)
        
        return orders
    
    def _rebound_long_orders(self, levels: Dict, rsi: float) -> List[Dict]:
        """反弹模式做多挂单"""
        orders = []
        
        # 策略：在支撑位附近分批挂单
        support = levels['support_resistance'].get('nearest_support', 0)
        fib_618 = levels['fibonacci'].get('level_618', 0)
        bb_lower = levels['bollinger'].get('lower', 0)
        
        # 挂单价格计算
        prices = []
        
        if support > 0:
            prices.append({
                'price': support * 0.995,  # 支撑位下方0.5%
                'reason': '支撑位下方',
                'probability': 0.7,
                'position_pct': 0.3
            })
        
        if fib_618 > 0 and fib_618 < self.current_price:
            prices.append({
                'price': fib_618,
                'reason': '斐波那契61.8%回撤',
                'probability': 0.6,
                'position_pct': 0.25
            })
        
        if bb_lower > 0 and bb_lower < self.current_price:
            prices.append({
                'price': bb_lower,
                'reason': '布林带下轨',
                'probability': 0.5,
                'position_pct': 0.25
            })
        
        # 如果RSI已经超卖，增加接近当前价的挂单
        if rsi < 30:
            prices.append({
                'price': self.current_price * 0.998,
                'reason': 'RSI超卖，接近当前价',
                'probability': 0.8,
                'position_pct': 0.2
            })
        
        # 排序并生成订单
        prices.sort(key=lambda x: x['price'], reverse=True)
        for i, p in enumerate(prices, 1):
            orders.append({
                'order_no': i,
                'price': p['price'],
                'reason': p['reason'],
                'probability': p['probability'],
                'position_pct': p['position_pct'],
                'distance_pct': abs(p['price'] - self.current_price) / self.current_price
            })
        
        return orders
    
    def _breakout_long_orders(self, levels: Dict) -> List[Dict]:
        """突破模式做多挂单"""
        orders = []
        
        resistance = levels['support_resistance'].get('nearest_resistance', 0)
        ema_9 = levels['ema'].get('ema_9', 0)
        
        if resistance > 0 and resistance > self.current_price:
            # 突破阻力位后追涨
            orders.append({
                'order_no': 1,
                'price': resistance * 1.002,
                'reason': '突破阻力位',
                'probability': 0.6,
                'position_pct': 0.5,
                'distance_pct': abs(resistance * 1.002 - self.current_price) / self.current_price
            })
        
        if ema_9 > 0 and ema_9 > self.current_price:
            # 突破EMA9
            orders.append({
                'order_no': 2,
                'price': ema_9 * 1.001,
                'reason': '突破EMA9',
                'probability': 0.7,
                'position_pct': 0.3,
                'distance_pct': abs(ema_9 * 1.001 - self.current_price) / self.current_price
            })
        
        # 保守挂单：当前价附近
        orders.append({
            'order_no': 3,
            'price': self.current_price * 1.001,
            'reason': '当前价小幅突破',
            'probability': 0.5,
            'position_pct': 0.2,
            'distance_pct': 0.001
        })
        
        return orders
    
    def _trend_long_orders(self, levels: Dict) -> List[Dict]:
        """趋势跟随做多挂单（上升趋势）"""
        orders = []
        
        ema_9 = levels['ema'].get('ema_9', 0)
        ema_21 = levels['ema'].get('ema_21', 0)
        
        # 策略：在均线附近挂单，顺势加仓
        if ema_9 > 0 and ema_9 < self.current_price:
            orders.append({
                'order_no': 1,
                'price': ema_9,
                'reason': '回踩EMA9',
                'probability': 0.6,
                'position_pct': 0.4,
                'distance_pct': abs(ema_9 - self.current_price) / self.current_price
            })
        
        if ema_21 > 0 and ema_21 < self.current_price:
            orders.append({
                'order_no': 2,
                'price': ema_21,
                'reason': '回踩EMA21',
                'probability': 0.5,
                'position_pct': 0.3,
                'distance_pct': abs(ema_21 - self.current_price) / self.current_price
            })
        
        # 激进挂单：当前价附近
        orders.append({
            'order_no': 3,
            'price': self.current_price * 0.999,
            'reason': '当前价小幅回调',
            'probability': 0.7,
            'position_pct': 0.3,
            'distance_pct': 0.001
        })
        
        return orders
    
    def _pullback_long_orders(self, levels: Dict) -> List[Dict]:
        """回调入场做多挂单"""
        orders = []
        
        fib_382 = levels['fibonacci'].get('level_382', 0)
        fib_500 = levels['fibonacci'].get('level_500', 0)
        fib_618 = levels['fibonacci'].get('level_618', 0)
        support = levels['support_resistance'].get('nearest_support', 0)
        
        # 策略：斐波那契关键位挂单
        if fib_382 > 0 and fib_382 < self.current_price:
            orders.append({
                'order_no': 1,
                'price': fib_382,
                'reason': '斐波那契38.2%',
                'probability': 0.7,
                'position_pct': 0.3,
                'distance_pct': abs(fib_382 - self.current_price) / self.current_price
            })
        
        if fib_500 > 0 and fib_500 < self.current_price:
            orders.append({
                'order_no': 2,
                'price': fib_500,
                'reason': '斐波那契50%',
                'probability': 0.6,
                'position_pct': 0.3,
                'distance_pct': abs(fib_500 - self.current_price) / self.current_price
            })
        
        if fib_618 > 0 and fib_618 < self.current_price:
            orders.append({
                'order_no': 3,
                'price': fib_618,
                'reason': '斐波那契61.8%',
                'probability': 0.5,
                'position_pct': 0.25,
                'distance_pct': abs(fib_618 - self.current_price) / self.current_price
            })
        
        if support > 0 and support < self.current_price:
            orders.append({
                'order_no': 4,
                'price': support,
                'reason': '关键支撑位',
                'probability': 0.65,
                'position_pct': 0.15,
                'distance_pct': abs(support - self.current_price) / self.current_price
            })
        
        return orders
    
    def _predict_short_orders(self) -> List[Dict]:
        """预测做空挂单（下跌趋势中等待反弹到阻力位）"""
        logger.info("📉 做空挂单策略（下跌趋势反弹做空 - 顺势）\n")
        
        levels = self.calculate_key_levels()
        orders = []
        
        # 根据入场模式选择策略
        if self.entry_mode == EntryMode.REBOUND:
            logger.info("🔄 反弹入场模式 - 超买回落策略")
            resistance = levels['support_resistance'].get('nearest_resistance', 0)
            fib_382 = levels['fibonacci'].get('level_382', 0)
            
            if resistance > 0 and resistance > self.current_price:
                orders.append({
                    'order_no': 1,
                    'price': resistance * 1.005,
                    'reason': '阻力位上方',
                    'probability': 0.7,
                    'position_pct': 0.4,
                    'distance_pct': abs(resistance * 1.005 - self.current_price) / self.current_price
                })
            
            if fib_382 > 0 and fib_382 > self.current_price:
                orders.append({
                    'order_no': 2,
                    'price': fib_382,
                    'reason': '斐波那契38.2%',
                    'probability': 0.6,
                    'position_pct': 0.3,
                    'distance_pct': abs(fib_382 - self.current_price) / self.current_price
                })
        
        elif self.entry_mode == EntryMode.PULLBACK:
            logger.info("📈 回调入场模式 - 反弹做空策略")
            fib_382 = levels['fibonacci'].get('level_382', 0)
            fib_500 = levels['fibonacci'].get('level_500', 0)
            fib_618 = levels['fibonacci'].get('level_618', 0)
            
            if fib_382 > 0 and fib_382 > self.current_price:
                orders.append({
                    'order_no': 1,
                    'price': fib_382,
                    'reason': '斐波那契38.2%',
                    'probability': 0.7,
                    'position_pct': 0.35,
                    'distance_pct': abs(fib_382 - self.current_price) / self.current_price
                })
            
            if fib_500 > 0 and fib_500 > self.current_price:
                orders.append({
                    'order_no': 2,
                    'price': fib_500,
                    'reason': '斐波那契50%',
                    'probability': 0.6,
                    'position_pct': 0.35,
                    'distance_pct': abs(fib_500 - self.current_price) / self.current_price
                })
            
            if fib_618 > 0 and fib_618 > self.current_price:
                orders.append({
                    'order_no': 3,
                    'price': fib_618,
                    'reason': '斐波那契61.8%',
                    'probability': 0.5,
                    'position_pct': 0.3,
                    'distance_pct': abs(fib_618 - self.current_price) / self.current_price
                })
        
        return orders
    
    def display_feasibility(self, feasibility: Dict):
        """展示可行性评估"""
        score = feasibility['score']
        max_score = feasibility['max_score']
        percentage = feasibility['percentage']
        
        logger.info(f"📊 可行性评分: {score:.0f}/{max_score} ({percentage:.0%})\n")
        
        # 显示评分原因
        logger.info("✅ 加分项：")
        for reason in feasibility['reasons']:
            logger.info(f"   {reason}")
        
        if feasibility['warnings']:
            logger.info("\n⚠️  警告项：")
            for warning in feasibility['warnings']:
                logger.warning(f"   {warning}")
        
        # 显示建议
        logger.info(f"\n{feasibility['recommendation']}\n")
        
        # 显示杠杆建议
        self._display_leverage_recommendation(feasibility)
        
        return feasibility['action']
    
    def _display_leverage_recommendation(self, feasibility: Dict):
        """显示杠杆建议"""
        lev_rec = feasibility.get('recommended_leverage', {})
        
        logger.info("=" * 80)
        logger.info("  ⚡ 杠杆建议")
        logger.info("=" * 80 + "\n")
        
        # 如果用户指定了杠杆
        if self.user_leverage:
            logger.info(f"🎯 您选择的杠杆: {self.user_leverage}x")
            
            # 评估用户杠杆是否合理
            recommended = lev_rec.get('recommended', 10)
            aggressive = lev_rec.get('aggressive', 15)
            conservative = lev_rec.get('conservative', 5)
            
            if self.user_leverage > aggressive:
                logger.error(f"   ⚠️  杠杆过高！建议范围: {lev_rec.get('range', 'N/A')}")
                logger.warning(f"   💡 推荐降低至: {aggressive}x 或更低")
            elif self.user_leverage > recommended:
                logger.warning(f"   ⚠️  杠杆偏高，建议: {recommended}x")
            elif self.user_leverage < conservative:
                logger.info(f"   ✅ 杠杆保守（当前市场适合使用 {conservative}-{recommended}x）")
            else:
                logger.success(f"   ✅ 杠杆合理！")
        else:
            logger.info("📊 根据当前市场条件的杠杆建议：\n")
            
            logger.info(f"   推荐杠杆范围: {lev_rec.get('range', 'N/A')}")
            logger.success(f"   ✅ 推荐: {lev_rec.get('recommended', 10)}x（平衡风险与收益）")
            logger.info(f"   🛡️  保守: {lev_rec.get('conservative', 5)}x（更安全）")
            logger.info(f"   ⚡ 激进: {lev_rec.get('aggressive', 15)}x（高风险高收益）")
            
            logger.info(f"\n   💡 {lev_rec.get('description', '')}")
        
        logger.info("\n")
    
    def display_orders(self, orders: List[Dict], action: str):
        """展示挂单建议"""
        if action in ['NO_EXECUTE', 'WAIT']:
            logger.warning("=" * 80)
            logger.warning("  ⛔ 不建议执行挂单")
            logger.warning("=" * 80)
            logger.info("\n💡 建议：")
            if action == 'NO_EXECUTE':
                logger.info("   1. 市场条件不佳，暂时观望")
                logger.info("   2. 等待趋势更明确或RSI到极值区")
                logger.info("   3. 关注关键价格位的形成")
            else:
                logger.info("   1. 等待更好的入场时机")
                logger.info("   2. 继续监控市场变化")
                logger.info("   3. 当评分达到60分以上再考虑挂单")
            logger.info("\n")
            return
        
        if not orders:
            logger.warning("⚠️  当前无法生成有效的挂单价格\n")
            return
        
        logger.info("=" * 80)
        if action == 'EXECUTE':
            logger.success("  ✅ 建议执行挂单")
        else:
            logger.warning("  ⚠️  谨慎执行挂单（降低仓位）")
        logger.info("=" * 80 + "\n")
        
        logger.info("📋 建议挂单列表：\n")
        
        # 表头
        header = f"{'序号':<6}{'价格':<12}{'距离':<10}{'触达概率':<12}{'仓位占比':<12}{'原因'}"
        logger.info(header)
        logger.info("-" * 80)
        
        # 订单详情
        for order in orders:
            order_line = (
                f"{order['order_no']:<6}"
                f"{order['price']:<12.4f}"
                f"{order['distance_pct']*100:<10.2f}%"
                f"{order['probability']*100:<12.0f}%"
                f"{order['position_pct']*100:<12.0f}%"
                f"{order['reason']}"
            )
            
            # 根据概率着色
            if order['probability'] >= 0.7:
                logger.success(order_line)
            elif order['probability'] >= 0.5:
                logger.info(order_line)
            else:
                logger.warning(order_line)
        
        logger.info("-" * 80 + "\n")
        
        # 统计信息
        total_position = sum(o['position_pct'] for o in orders)
        avg_probability = sum(o['probability'] for o in orders) / len(orders)
        
        logger.info("📊 统计信息：")
        logger.info(f"   总挂单数: {len(orders)} 个")
        logger.info(f"   总仓位占比: {total_position*100:.0f}%")
        
        # 根据action调整仓位建议
        if action == 'EXECUTE_WITH_CAUTION':
            adjusted_position = total_position * 0.5
            logger.warning(f"   建议调整至: {adjusted_position*100:.0f}% （降低50%）")
        
        logger.info(f"   平均触达概率: {avg_probability*100:.0f}%")
        
        # 计算预期收益
        self._calculate_expected_return(orders, action)
    
    def _calculate_smart_stop_levels(self, entry_price: float, direction: str, leverage: int) -> Dict:
        """
        基于K线和订单流智能计算止盈止损位
        
        Args:
            entry_price: 入场价格
            direction: 交易方向 ('up' 做多, 'down' 做空)
            leverage: 杠杆倍数
            
        Returns:
            {'stop_loss': float, 'take_profit': float, 'stop_loss_pct': float, 'take_profit_pct': float, 'reason': str}
        """
        # 1. 基础杠杆调整（作为最小值）
        if leverage >= 20:
            base_stop_pct = 0.005
            base_profit_pct = 0.015
        elif leverage >= 15:
            base_stop_pct = 0.007
            base_profit_pct = 0.02
        elif leverage >= 10:
            base_stop_pct = 0.01
            base_profit_pct = 0.03
        elif leverage >= 5:
            base_stop_pct = 0.015
            base_profit_pct = 0.045
        else:
            base_stop_pct = 0.02
            base_profit_pct = 0.06
        
        # 2. 基于ATR（真实波动范围）动态调整
        if 'atr' in self.data_5m.columns:
            atr = self.data_5m['atr'].iloc[-1]
            atr_pct = atr / entry_price
            
            # ATR作为止损参考（1-2倍ATR）
            atr_stop_pct = min(atr_pct * 1.5, base_stop_pct * 2)
            # 使用较大值（给足波动空间）
            dynamic_stop_pct = max(base_stop_pct, atr_stop_pct)
        else:
            dynamic_stop_pct = base_stop_pct
        
        # 3. 基于支撑阻力位优化
        sr_levels = self.signal_gen.sr.get_nearest_support_resistance(self.data_5m, entry_price)
        
        if direction == 'up':  # 做多
            # 止损：设在最近支撑位下方
            if sr_levels and sr_levels.get('nearest_support'):
                support = sr_levels['nearest_support']
                if support < entry_price:
                    sr_stop_pct = abs(support - entry_price) / entry_price
                    # 支撑位下方0.2%作为止损
                    sr_stop_pct = sr_stop_pct + 0.002
                    dynamic_stop_pct = max(dynamic_stop_pct, sr_stop_pct)
            
            # 止盈：设在最近阻力位附近
            if sr_levels and sr_levels.get('nearest_resistance'):
                resistance = sr_levels['nearest_resistance']
                if resistance > entry_price:
                    sr_profit_pct = abs(resistance - entry_price) / entry_price
                    # 阻力位前0.3%作为止盈
                    sr_profit_pct = sr_profit_pct - 0.003
                    
        else:  # 做空
            # 止损：设在最近阻力位上方
            if sr_levels and sr_levels.get('nearest_resistance'):
                resistance = sr_levels['nearest_resistance']
                if resistance > entry_price:
                    sr_stop_pct = abs(resistance - entry_price) / entry_price
                    sr_stop_pct = sr_stop_pct + 0.002
                    dynamic_stop_pct = max(dynamic_stop_pct, sr_stop_pct)
            
            # 止盈：设在最近支撑位附近
            if sr_levels and sr_levels.get('nearest_support'):
                support = sr_levels['nearest_support']
                if support < entry_price:
                    sr_profit_pct = abs(support - entry_price) / entry_price
                    sr_profit_pct = sr_profit_pct - 0.003
        
        # 4. 确保最小盈亏比1:1.68（黄金分割比例）
        min_profit_ratio = 1.68
        calculated_profit_pct = base_profit_pct
        
        # 如果基于支撑阻力计算的止盈存在且合理
        if 'sr_profit_pct' in locals() and sr_profit_pct > 0:
            calculated_profit_pct = max(base_profit_pct, sr_profit_pct)
        
        # 强制保证盈亏比≥1.68
        min_required_profit = dynamic_stop_pct * min_profit_ratio
        final_profit_pct = max(calculated_profit_pct, min_required_profit)
        
        # 5. 计算实际价格
        if direction == 'up':
            stop_loss = entry_price * (1 - dynamic_stop_pct)
            take_profit = entry_price * (1 + final_profit_pct)
            reason = "做多"
        else:
            stop_loss = entry_price * (1 + dynamic_stop_pct)
            take_profit = entry_price * (1 - final_profit_pct)
            reason = "做空"
        
        # 6. 计算实际盈亏比
        actual_ratio = final_profit_pct / dynamic_stop_pct
        
        return {
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'stop_loss_pct': dynamic_stop_pct,
            'take_profit_pct': final_profit_pct,
            'ratio': actual_ratio,
            'reason': f"{reason}（基于ATR+支撑阻力，盈亏比1:{actual_ratio:.2f}）"
        }
    
    def _calculate_expected_return(self, orders: List[Dict], action: str = 'EXECUTE'):
        """计算预期收益"""
        logger.info("\n💰 风险收益分析：\n")
        
        # 使用实例变量
        account_balance = self.account_balance
        
        # 确定使用的杠杆
        if self.user_leverage:
            leverage = self.user_leverage
            logger.info(f"使用杠杆: {leverage}x（用户指定）")
        elif self.recommended_leverage:
            leverage = self.recommended_leverage.get('recommended', 10)
            logger.info(f"使用杠杆: {leverage}x（系统推荐）")
        else:
            leverage = 10
            logger.info(f"使用杠杆: {leverage}x（默认）")
        
        logger.info(f"账户余额: {account_balance:.2f} USDT")
        logger.info(f"止盈止损策略: 基于K线ATR + 支撑阻力动态计算 ⭐\n")
        
        # 如果是谨慎执行，降低仓位
        position_multiplier = 0.5 if action == 'EXECUTE_WITH_CAUTION' else 1.0
        
        total_expected_return = 0
        total_max_loss = 0
        total_max_profit = 0
        
        for order in orders:
            # 计算仓位（应用调整系数）
            position_value = account_balance * order['position_pct'] * position_multiplier
            quantity = (position_value * leverage) / order['price']
            
            # 使用智能止盈止损计算（顺势回调）⭐
            # 下跌趋势做空 → direction='down'
            # 上涨趋势做多 → direction='up'
            direction = self.trend_info.direction  # 顺势交易，方向一致
            stop_levels = self._calculate_smart_stop_levels(order['price'], direction, leverage)
            
            stop_loss = stop_levels['stop_loss']
            take_profit = stop_levels['take_profit']
            stop_loss_pct = stop_levels['stop_loss_pct']
            take_profit_pct = stop_levels['take_profit_pct']
            profit_loss_ratio = stop_levels['ratio']
            
            # 最大亏损和盈利
            max_loss = position_value * stop_loss_pct * leverage
            max_profit = position_value * take_profit_pct * leverage
            
            expected_return = max_profit * order['probability'] - max_loss * (1-order['probability'])
            
            logger.info(f"订单 #{order['order_no']} - {order['reason']}")
            logger.info(f"   入场价: {order['price']:.4f}")
            logger.info(f"   仓位: {position_value:.2f} USDT ({order['position_pct']*100:.0f}% × {position_multiplier:.0%})")
            logger.info(f"   杠杆: {leverage}x")
            logger.info(f"   实际开仓: {position_value * leverage:.2f} USDT")
            logger.info(f"   数量: {quantity:.2f} 张")
            logger.info(f"   止损: {stop_loss:.4f} ({stop_loss_pct*100:.2f}%) {stop_levels['reason']}")
            logger.info(f"   止盈: {take_profit:.4f} ({take_profit_pct*100:.2f}%)")
            
            # 显示盈亏比
            if profit_loss_ratio >= 1.68:
                logger.success(f"   ✅ 盈亏比: 1:{profit_loss_ratio:.2f} （≥黄金分割1:1.68）")
            else:
                logger.info(f"   💡 盈亏比: 1:{profit_loss_ratio:.2f}")
            
            # 显示实际盈亏（价格波动 × 杠杆）
            actual_loss_pct = stop_loss_pct * leverage
            actual_profit_pct = take_profit_pct * leverage
            logger.info(f"   → 实际止损效果: -{actual_loss_pct*100:.1f}% 本金")
            logger.info(f"   → 实际止盈效果: +{actual_profit_pct*100:.1f}% 本金")
            
            logger.info(f"   最大亏损: -{max_loss:.2f} USDT ({max_loss/account_balance*100:.1f}% 本金)")
            logger.info(f"   最大盈利: +{max_profit:.2f} USDT ({max_profit/account_balance*100:.1f}% 本金)")
            logger.info(f"   期望收益: {expected_return:.2f} USDT ({expected_return/account_balance*100:.1f}% 本金)\n")
            
            total_expected_return += expected_return
            total_max_loss += max_loss
            total_max_profit += max_profit
        
        # 显示汇总信息
        logger.info("=" * 80)
        logger.info(f"📊 汇总（所有订单）")
        logger.info("=" * 80)
        logger.info(f"总期望收益: {total_expected_return:.2f} USDT ({total_expected_return/account_balance*100:.1f}% 本金)")
        logger.info(f"总最大亏损: -{total_max_loss:.2f} USDT ({total_max_loss/account_balance*100:.1f}% 本金)")
        logger.info(f"总最大盈利: +{total_max_profit:.2f} USDT ({total_max_profit/account_balance*100:.1f}% 本金)")
        
        # 风险收益比
        if total_max_loss > 0:
            risk_reward_ratio = total_max_profit / total_max_loss
            logger.info(f"风险收益比: 1:{risk_reward_ratio:.2f}")
            
            if risk_reward_ratio >= 3:
                logger.success(f"   ✅ 风险收益比优秀！")
            elif risk_reward_ratio >= 2:
                logger.info(f"   ✅ 风险收益比良好")
            else:
                logger.warning(f"   ⚠️  风险收益比偏低")
        
        # 杠杆风险提示
        logger.info("\n⚡ 杠杆风险提示：")
        if leverage >= 20:
            logger.error(f"   ⚠️  {leverage}x杠杆极高！价格波动{100/leverage:.1f}%即爆仓")
            logger.info(f"   💡 已自动调整止盈止损：止损0.5%，止盈1.5%")
        elif leverage >= 15:
            logger.warning(f"   ⚠️  {leverage}x杠杆较高，价格波动{100/leverage:.1f}%即爆仓")
            logger.info(f"   💡 已自动调整止盈止损：止损0.7%，止盈2%")
        elif leverage >= 10:
            logger.info(f"   💡 {leverage}x杠杆适中，价格波动{100/leverage:.1f}%即爆仓")
            logger.info(f"   💡 已自动调整止盈止损：止损1%，止盈3%")
        elif leverage >= 5:
            logger.success(f"   ✅ {leverage}x杠杆保守，价格波动{100/leverage:.1f}%即爆仓")
            logger.info(f"   💡 已自动调整止盈止损：止损1.5%，止盈4.5%")
        else:
            logger.success(f"   ✅ {leverage}x杠杆极低，价格波动{100/leverage:.1f}%即爆仓")
            logger.info(f"   💡 使用标准止盈止损：止损2%，止盈6%")
        
        logger.info("")
    
    def run(self):
        """运行预测"""
        logger.info("=" * 80)
        logger.info(f"  {self.symbol} 挂单策略分析")
        logger.info("=" * 80 + "\n")
        
        # 1. 获取数据
        if not self.fetch_data():
            return
        
        # 2. 分析市场
        if not self.analyze_market():
            return
        
        # 3. 评估挂单可行性 ⭐ 新增
        feasibility = self.evaluate_order_feasibility()
        action = self.display_feasibility(feasibility)
        
        # 4. 预测挂单（如果可行）
        orders = self.predict_entry_orders()
        
        # 5. 展示结果
        self.display_orders(orders, action)
        
        # 6. 风险提示
        logger.info("\n" + "=" * 80)
        logger.info("  ⚠️  风险提示")
        logger.info("=" * 80)
        logger.info("1. 以上分析仅供参考，不构成投资建议")
        logger.info("2. 请根据可行性评分决定是否挂单")
        logger.info("3. 市场瞬息万变，建议持续监控")
        logger.info("4. 务必设置止损，严格控制风险")
        
        if action in ['NO_EXECUTE', 'WAIT']:
            logger.warning("\n⛔ 当前不建议挂单，请等待更好时机！")
        elif action == 'EXECUTE_WITH_CAUTION':
            logger.warning("\n⚠️  可以挂单但需谨慎，建议降低50%仓位！")
        else:
            logger.success("\n✅ 可以按建议执行挂单！")
        
        logger.info("=" * 80 + "\n")


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='智能挂单策略预测',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 使用默认杠杆（系统推荐）
  python predict_entry_orders.py BTC
  
  # 指定杠杆倍数
  python predict_entry_orders.py BTC --leverage 15
  
  # 指定账户余额和杠杆
  python predict_entry_orders.py ARB -l 10 -b 5000
        """
    )
    parser.add_argument('symbol', nargs='?', default='BTC/USDT:USDT', 
                       help='交易对符号 (默认: BTC/USDT:USDT)')
    parser.add_argument('-l', '--leverage', type=int, default=20,
                        help='杠杆倍数 (不指定则使用系统推荐)')
    parser.add_argument('-b', '--balance', type=float, default=200,
                        help='账户余额 USDT (默认: 200)')
    parser.add_argument('-s', '--single', action='store_true', default=True,
                        help='只推荐1个最优挂单（默认推荐3个分批挂单）')
    args = parser.parse_args()
    
    # 标准化交易对格式
    symbol = args.symbol.upper()
    if ':' not in symbol and 'USDT' in symbol:
        if not symbol.endswith(':USDT'):
            symbol = symbol.replace('USDT', '/USDT:USDT')
    
    # 验证杠杆倍数
    if args.leverage:
        if args.leverage < 1:
            logger.error("❌ 杠杆倍数不能小于1")
            return 1
        if args.leverage > 125:
            logger.error("❌ 杠杆倍数过高（最大125x），请谨慎！")
            return 1
        if args.leverage > 20:
            logger.warning(f"⚠️  {args.leverage}x杠杆极高，风险巨大！")
    
    # 验证账户余额
    if args.balance <= 0:
        logger.error("❌ 账户余额必须大于0")
        return 1
    
    # 创建预测器（传递single_mode参数）
    predictor = EntryOrderPredictor(
        symbol, 
        leverage=args.leverage, 
        account_balance=args.balance,
        single_mode=args.single  # ⭐ 单一最优挂单模式
    )
    predictor.run()
    
    return 0


if __name__ == '__main__':
    import sys
    sys.exit(main())

