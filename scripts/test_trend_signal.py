#!/usr/bin/env python3
"""趋势信号分析测试类

支持两种运行方式:
1. 直接运行: python scripts/test_trend_signal.py ARB/USDT:USDT
2. pytest运行: pytest scripts/test_trend_signal.py -v
"""
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional
import pandas as pd
import pytest

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.strategy.trend_analyzer import trend_analyzer, TrendInfo
from src.strategy.signal_generator import SignalGenerator, TradingSignal
from src.core.data_fetcher import data_fetcher
from src.indicators.technical import technical_indicators
from src.indicators.support_resistance import support_resistance
from src.indicators.order_flow import order_flow_analyzer
from src.monitor.logger import system_logger
from loguru import logger


class TrendSignalAnalyzer:
    """趋势信号分析测试类"""
    
    def __init__(self, symbol: str):
        """
        初始化
        
        Args:
            symbol: 交易对符号
        """
        self.symbol = symbol
        self.signal_generator = SignalGenerator()
        
        # 数据存储
        self.data_5m = None
        self.data_15m = None
        self.data_1h = None
        
        # 分析结果
        self.trend_info = None
        self.signal = None
        
    def print_header(self, title: str, level: int = 1):
        """打印标题"""
        if level == 1:
            print("\n" + "=" * 80)
            print(f"  {title}")
            print("=" * 80)
        elif level == 2:
            print("\n" + "-" * 80)
            print(f"  {title}")
            print("-" * 80)
        else:
            print(f"\n{'  ' * (level-1)}▶ {title}")
    
    def fetch_data(self) -> bool:
        """
        获取多周期数据
        
        Returns:
            是否成功
        """
        self.print_header("1. 获取市场数据", level=1)
        
        try:
            logger.info(f"正在获取 {self.symbol} 的多周期数据...")
            
            # 获取5分钟数据
            self.data_5m = data_fetcher.fetch_ohlcv_df(self.symbol, '5m', limit=200)
            if self.data_5m.empty:
                logger.error("❌ 获取5分钟数据失败")
                return False
            logger.success(f"✅ 5分钟数据: {len(self.data_5m)} 根K线")
            
            # 获取15分钟数据
            self.data_15m = data_fetcher.fetch_ohlcv_df(self.symbol, '15m', limit=100)
            if self.data_15m.empty:
                logger.error("❌ 获取15分钟数据失败")
                return False
            logger.success(f"✅ 15分钟数据: {len(self.data_15m)} 根K线")
            
            # 获取1小时数据
            self.data_1h = data_fetcher.fetch_ohlcv_df(self.symbol, '1h', limit=100)
            if self.data_1h.empty:
                logger.error("❌ 获取1小时数据失败")
                return False
            logger.success(f"✅ 1小时数据: {len(self.data_1h)} 根K线")
            
            # 显示最新价格
            current_price = self.data_5m['close'].iloc[-1]
            logger.info(f"📊 当前价格: {current_price:.4f} USDT")
            
            # 显示24小时变化
            price_24h_ago = self.data_5m['close'].iloc[-288] if len(self.data_5m) >= 288 else self.data_5m['close'].iloc[0]
            change_24h = (current_price - price_24h_ago) / price_24h_ago * 100
            change_emoji = "📈" if change_24h > 0 else "📉"
            logger.info(f"{change_emoji} 24小时涨跌: {change_24h:+.2f}%")
            
            return True
            
        except Exception as e:
            logger.exception(f"❌ 获取数据失败: {e}")
            return False
    
    def analyze_trend(self) -> bool:
        """
        分析趋势
        
        Returns:
            是否成功
        """
        self.print_header("2. 多周期趋势分析", level=1)
        
        try:
            # 执行趋势分析
            logger.info("正在分析多周期趋势...")
            self.trend_info = trend_analyzer.analyze(
                self.data_5m,
                self.data_15m,
                self.data_1h
            )
            
            # 显示趋势信息
            self.print_header("趋势总览", level=2)
            logger.info(f"趋势方向: {self.trend_info.direction.upper()}")
            logger.info(f"趋势强度: {self.trend_info.strength:.2%}")
            logger.info(f"是否强趋势: {'✅ 是' if self.trend_info.is_strong else '❌ 否'}")
            
            # 5分钟周期分析
            self.print_header("5分钟周期分析", level=3)
            details_5m = self.trend_info.details['5m']
            self._print_timeframe_details(details_5m, '5m')
            
            # 15分钟周期分析
            self.print_header("15分钟周期分析", level=3)
            details_15m = self.trend_info.details['15m']
            self._print_timeframe_details(details_15m, '15m')
            
            # 1小时周期分析
            self.print_header("1小时周期分析", level=3)
            details_1h = self.trend_info.details['1h']
            self._print_timeframe_details(details_1h, '1h')
            
            # 共振分析
            self.print_header("多周期共振分析", level=2)
            resonance = self.trend_info.details['resonance']
            logger.info(f"共振度: {resonance}/3")
            if resonance >= 2:
                logger.success(f"✅ 多周期趋势共振良好")
            else:
                logger.warning(f"⚠️  多周期趋势共振较弱")
            
            return True
            
        except Exception as e:
            logger.exception(f"❌ 趋势分析失败: {e}")
            return False
    
    def _print_timeframe_details(self, details: Dict, timeframe: str):
        """打印周期详细信息"""
        direction_emoji = {
            'up': '📈',
            'down': '📉',
            'neutral': '➡️'
        }
        
        logger.info(f"{direction_emoji.get(details['direction'], '❓')} 方向: {details['direction'].upper()}")
        logger.info(f"💪 强度: {details['strength']:.2%}")
        logger.info(f"✓ 确认数: {details['confirmations']}/5")
        
        # EMA排列
        ema = details.get('ema', {})
        if ema.get('aligned'):
            logger.success(f"  ✅ EMA排列: {ema['direction'].upper()} (整齐)")
        else:
            logger.warning(f"  ⚠️  EMA排列: 混乱")
        
        # MACD
        macd = details.get('macd', {})
        macd_emoji = '🟢' if macd.get('signal') == 'bullish' else '🔴' if macd.get('signal') == 'bearish' else '⚪'
        logger.info(f"  {macd_emoji} MACD: {macd.get('signal', 'neutral')}")
        
        # ADX
        adx = details.get('adx', {})
        if adx.get('strong_trend'):
            logger.success(f"  ✅ ADX: {adx.get('value', 0):.1f} (强趋势)")
        else:
            logger.info(f"  ℹ️  ADX: {adx.get('value', 0):.1f} (弱趋势)")
        
        # SuperTrend
        st = details.get('supertrend', {})
        st_emoji = '🟢' if st.get('signal') == 'bullish' else '🔴' if st.get('signal') == 'bearish' else '⚪'
        logger.info(f"  {st_emoji} SuperTrend: {st.get('signal', 'neutral')}")
        
        # 成交量
        vol = details.get('volume', {})
        if vol.get('confirmation'):
            logger.success(f"  ✅ 成交量: 确认 ({vol.get('direction', 'N/A')})")
        else:
            logger.info(f"  ℹ️  成交量: 未确认")
    
    def analyze_indicators(self) -> bool:
        """
        分析技术指标
        
        Returns:
            是否成功
        """
        self.print_header("3. 技术指标详细分析", level=1)
        
        try:
            # 使用5分钟数据进行详细指标分析
            df = self.data_5m.copy()
            df = technical_indicators.calculate_all_indicators(df)
            
            current_price = df['close'].iloc[-1]
            
            # EMA分析
            self.print_header("移动平均线 (EMA)", level=2)
            ema_9 = df['ema_9'].iloc[-1]
            ema_21 = df['ema_21'].iloc[-1]
            ema_50 = df['ema_50'].iloc[-1]
            
            logger.info(f"EMA9:  {ema_9:.4f} USDT ({(current_price/ema_9-1)*100:+.2f}%)")
            logger.info(f"EMA21: {ema_21:.4f} USDT ({(current_price/ema_21-1)*100:+.2f}%)")
            logger.info(f"EMA50: {ema_50:.4f} USDT ({(current_price/ema_50-1)*100:+.2f}%)")
            
            if ema_9 > ema_21 > ema_50:
                logger.success("✅ 多头排列 (EMA9 > EMA21 > EMA50)")
            elif ema_9 < ema_21 < ema_50:
                logger.warning("📉 空头排列 (EMA9 < EMA21 < EMA50)")
            else:
                logger.info("➡️  排列混乱")
            
            # RSI分析
            self.print_header("相对强弱指标 (RSI)", level=2)
            rsi = df['rsi'].iloc[-1]
            logger.info(f"RSI(14): {rsi:.2f}")
            
            if rsi > 70:
                logger.warning("⚠️  超买区域 (RSI > 70)")
            elif rsi < 30:
                logger.success("✅ 超卖区域 (RSI < 30)")
            elif 40 <= rsi <= 60:
                logger.info("ℹ️  中性区域 (40-60)")
            else:
                logger.info(f"ℹ️  {'偏强' if rsi > 50 else '偏弱'}区域")
            
            # MACD分析
            self.print_header("MACD指标", level=2)
            macd = df['macd'].iloc[-1]
            macd_signal = df['macd_signal'].iloc[-1]
            macd_hist = df['macd_hist'].iloc[-1]
            
            logger.info(f"MACD: {macd:.6f}")
            logger.info(f"Signal: {macd_signal:.6f}")
            logger.info(f"Histogram: {macd_hist:.6f}")
            
            if macd > macd_signal and macd_hist > 0:
                logger.success("✅ 多头信号 (MACD > Signal, Hist > 0)")
            elif macd < macd_signal and macd_hist < 0:
                logger.warning("📉 空头信号 (MACD < Signal, Hist < 0)")
            else:
                logger.info("ℹ️  信号不明确")
            
            # KDJ分析
            self.print_header("KDJ指标", level=2)
            kdj_k = df['kdj_k'].iloc[-1]
            kdj_d = df['kdj_d'].iloc[-1]
            kdj_j = df['kdj_j'].iloc[-1]
            
            logger.info(f"K: {kdj_k:.2f}")
            logger.info(f"D: {kdj_d:.2f}")
            logger.info(f"J: {kdj_j:.2f}")
            
            if kdj_k > kdj_d and kdj_k < 80:
                logger.success("✅ 金叉且未超买")
            elif kdj_k < kdj_d and kdj_k > 20:
                logger.warning("⚠️  死叉且未超卖")
            elif kdj_j > 100:
                logger.warning("⚠️  超买 (J > 100)")
            elif kdj_j < 0:
                logger.success("✅ 超卖 (J < 0)")
            
            # ADX分析
            self.print_header("ADX趋势强度", level=2)
            adx = df['adx'].iloc[-1]
            plus_di = df['plus_di'].iloc[-1]
            minus_di = df['minus_di'].iloc[-1]
            
            logger.info(f"ADX: {adx:.2f}")
            logger.info(f"+DI: {plus_di:.2f}")
            logger.info(f"-DI: {minus_di:.2f}")
            logger.info(f"DI差值: {abs(plus_di - minus_di):.2f}")
            
            if adx > 25:
                trend_type = "上升" if plus_di > minus_di else "下降"
                logger.success(f"✅ 强趋势 (ADX > 25, {trend_type})")
            elif adx > 20:
                logger.info(f"ℹ️  中等趋势 (ADX > 20)")
            else:
                logger.warning(f"⚠️  弱趋势 (ADX < 20)")
            
            # 布林带分析
            self.print_header("布林带 (Bollinger Bands)", level=2)
            bb_upper = df['bb_upper'].iloc[-1]
            bb_middle = df['bb_middle'].iloc[-1]
            bb_lower = df['bb_lower'].iloc[-1]
            
            logger.info(f"上轨: {bb_upper:.4f} USDT")
            logger.info(f"中轨: {bb_middle:.4f} USDT")
            logger.info(f"下轨: {bb_lower:.4f} USDT")
            logger.info(f"当前价格: {current_price:.4f} USDT")
            
            bb_position = (current_price - bb_lower) / (bb_upper - bb_lower)
            logger.info(f"布林带位置: {bb_position:.1%}")
            
            if current_price > bb_upper:
                logger.warning("⚠️  价格突破上轨（可能超买）")
            elif current_price < bb_lower:
                logger.success("✅ 价格跌破下轨（可能超卖）")
            elif bb_position > 0.8:
                logger.info("ℹ️  价格接近上轨")
            elif bb_position < 0.2:
                logger.info("ℹ️  价格接近下轨")
            else:
                logger.info("ℹ️  价格在中间区域")
            
            # ATR波动率
            self.print_header("ATR波动率", level=2)
            atr = df['atr'].iloc[-1]
            atr_pct = atr / current_price * 100
            logger.info(f"ATR: {atr:.4f} USDT")
            logger.info(f"ATR百分比: {atr_pct:.2f}%")
            
            if atr_pct > 5:
                logger.warning("⚠️  高波动 (ATR > 5%)")
            elif atr_pct > 3:
                logger.info("ℹ️  中等波动 (ATR > 3%)")
            else:
                logger.info("ℹ️  低波动 (ATR < 3%)")
            
            return True
            
        except Exception as e:
            logger.exception(f"❌ 指标分析失败: {e}")
            return False
    
    def analyze_support_resistance(self) -> bool:
        """
        分析支撑阻力位
        
        Returns:
            是否成功
        """
        self.print_header("4. 支撑阻力位分析", level=1)
        
        try:
            df = self.data_5m.copy()
            current_price = df['close'].iloc[-1]
            
            # 识别关键价格位
            self.print_header("关键价格位", level=2)
            levels = support_resistance.identify_key_levels(df)
            
            support_levels = levels.get('support', [])
            resistance_levels = levels.get('resistance', [])
            
            logger.info(f"当前价格: {current_price:.4f} USDT")
            logger.info("")
            
            # 阻力位
            if resistance_levels:
                logger.info("🔴 阻力位:")
                for i, level in enumerate(resistance_levels[:5], 1):
                    distance = (level - current_price) / current_price * 100
                    logger.info(f"  R{i}: {level:.4f} USDT (+{distance:.2f}%)")
            else:
                logger.info("🔴 阻力位: 未识别到")
            
            logger.info("")
            
            # 支撑位
            if support_levels:
                logger.info("🟢 支撑位:")
                for i, level in enumerate(support_levels[:5], 1):
                    distance = (current_price - level) / current_price * 100
                    logger.info(f"  S{i}: {level:.4f} USDT (-{distance:.2f}%)")
            else:
                logger.info("🟢 支撑位: 未识别到")
            
            # 斐波那契回撤
            self.print_header("斐波那契回撤位", level=2)
            
            try:
                fib_levels = support_resistance.calculate_fibonacci_retracement(df)
            except Exception as e:
                logger.warning(f"⚠️  斐波那契回撤计算失败: {e}")
                fib_levels = None
            
            if fib_levels and isinstance(fib_levels, dict):
                # 根据趋势方向判断高低点
                trend = fib_levels.get('trend', 'up')
                level_0 = fib_levels.get('level_0', 0)
                level_100 = fib_levels.get('level_100', 0)
                
                if trend == 'up':
                    logger.info(f"区间低点: {level_0:.4f} USDT")
                    logger.info(f"区间高点: {level_100:.4f} USDT")
                else:
                    logger.info(f"区间高点: {level_0:.4f} USDT")
                    logger.info(f"区间低点: {level_100:.4f} USDT")
                
                logger.info(f"趋势方向: {trend.upper()}")
                logger.info("")
                logger.info("关键回撤位:")
                
                # 显示各个斐波那契水平
                fib_keys = [
                    ('level_236', '23.6%'),
                    ('level_382', '38.2%'),
                    ('level_500', '50.0%'),
                    ('level_618', '61.8%'),
                    ('level_786', '78.6%'),
                ]
                
                for level_key, level_label in fib_keys:
                    level_price = fib_levels.get(level_key)
                    if level_price:
                        distance = (current_price - level_price) / current_price * 100
                        symbol = "↑" if distance < 0 else "↓"
                        
                        # 标注当前价格是否接近该水平
                        if abs(distance) < 0.5:
                            proximity = " ⭐ 接近"
                        elif abs(distance) < 1.0:
                            proximity = " 👀 关注"
                        else:
                            proximity = ""
                        
                        logger.info(f"  {level_label}: {level_price:.4f} USDT ({symbol} {abs(distance):.2f}%){proximity}")
            else:
                logger.info("ℹ️  无斐波那契回撤数据")
            
            return True
            
        except Exception as e:
            logger.exception(f"❌ 支撑阻力分析失败: {e}")
            return False
    
    def generate_signal(self) -> bool:
        """
        生成交易信号
        
        Returns:
            是否成功
        """
        self.print_header("5. 交易信号生成", level=1)
        
        try:
            if not self.trend_info:
                logger.error("❌ 请先执行趋势分析")
                return False
            
            # 生成信号
            logger.info("正在生成交易信号...")
            self.signal = self.signal_generator.generate_signal(
                self.symbol,
                self.data_5m,
                self.trend_info
            )
            
            if not self.signal:
                logger.warning("⚠️  当前无交易信号")
                logger.info("可能原因:")
                logger.info("  - 趋势不够强")
                logger.info("  - 无明显回调")
                logger.info("  - 信号评分不足")
                return True
            
            # 显示信号信息
            self.print_header("信号详情", level=2)
            
            signal_emoji = "🟢" if self.signal.signal_type == 'long' else "🔴"
            logger.success(f"{signal_emoji} 交易方向: {self.signal.signal_type.upper()}")
            logger.info(f"📊 信号评分: {self.signal.score:.1f}/15")
            logger.info(f"💵 入场价格: {self.signal.entry_price:.4f} USDT")
            logger.info(f"🛑 止损价格: {self.signal.stop_loss:.4f} USDT")
            logger.info(f"🎯 止盈价格: {self.signal.take_profit:.4f} USDT")
            
            # 计算风险回报比
            if self.signal.signal_type == 'long':
                risk = self.signal.entry_price - self.signal.stop_loss
                reward = self.signal.take_profit - self.signal.entry_price
            else:
                risk = self.signal.stop_loss - self.signal.entry_price
                reward = self.signal.entry_price - self.signal.take_profit
            
            rr_ratio = reward / risk if risk > 0 else 0
            logger.info(f"⚖️  风险回报比: 1:{rr_ratio:.2f}")
            
            # 显示支撑阻力
            if self.signal.support_level:
                logger.info(f"🟢 支撑位: {self.signal.support_level:.4f} USDT")
            if self.signal.resistance_level:
                logger.info(f"🔴 阻力位: {self.signal.resistance_level:.4f} USDT")
            
            # 评分详情
            self.print_header("信号评分详情", level=2)
            score_details = self.signal.score_details
            
            logger.info(f"斐波那契回撤:   {score_details.get('fibonacci', {}).get('score', 0):.1f}/2")
            logger.info(f"支撑阻力位:     {score_details.get('support_resistance', {}).get('score', 0):.1f}/2")
            logger.info(f"RSI条件:        {score_details.get('rsi', {}).get('score', 0):.1f}/1")
            logger.info(f"KDJ金叉:        {score_details.get('kdj', {}).get('score', 0):.1f}/1")
            logger.info(f"MACD收敛:       {score_details.get('macd', {}).get('score', 0):.1f}/1")
            logger.info(f"K线形态:        {score_details.get('candlestick', {}).get('score', 0):.1f}/2")
            logger.info(f"成交量确认:     {score_details.get('volume', {}).get('score', 0):.1f}/2")
            logger.info(f"订单流:         {score_details.get('order_flow', {}).get('score', 0):.1f}/2")
            
            # 判断信号质量
            logger.info("")
            if self.signal.score >= 10:
                logger.success("🌟 高质量信号！建议重点关注")
            elif self.signal.score >= 7:
                logger.info("✅ 合格信号，可考虑入场")
            else:
                logger.warning("⚠️  信号较弱，建议观望")
            
            return True
            
        except Exception as e:
            logger.exception(f"❌ 信号生成失败: {e}")
            return False
    
    def run_full_analysis(self) -> bool:
        """
        运行完整分析
        
        Returns:
            是否成功
        """
        logger.info("=" * 80)
        logger.info(f"  {self.symbol} 趋势信号完整分析")
        logger.info("=" * 80)
        logger.info(f"分析时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # 执行分析步骤
        steps = [
            ("获取数据", self.fetch_data),
            ("趋势分析", self.analyze_trend),
            ("技术指标", self.analyze_indicators),
            ("支撑阻力", self.analyze_support_resistance),
            ("生成信号", self.generate_signal),
        ]
        
        for step_name, step_func in steps:
            if not step_func():
                logger.error(f"❌ {step_name}失败，分析终止")
                return False
        
        # 最终总结
        self.print_header("📊 分析总结", level=1)
        
        if self.trend_info:
            logger.info(f"趋势方向: {self.trend_info.direction.upper()}")
            logger.info(f"趋势强度: {self.trend_info.strength:.2%}")
            logger.info(f"是否强趋势: {'是' if self.trend_info.is_strong else '否'}")
        
        if self.signal:
            logger.success(f"\n✅ 发现交易信号: {self.signal.signal_type.upper()}")
            logger.info(f"信号评分: {self.signal.score:.1f}/15")
            logger.info(f"入场价格: {self.signal.entry_price:.4f} USDT")
        else:
            logger.info("\n⚠️  当前无交易信号，建议继续观望")
        
        logger.info("\n" + "=" * 80)
        logger.success("✅ 分析完成！")
        logger.info("=" * 80)
        
        return True


def main():
    """主函数"""
    import argparse
    
    # 解析命令行参数
    parser = argparse.ArgumentParser(
        description='趋势信号分析测试工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python scripts/test_trend_signal.py                    # 默认测试ARB/USDT:USDT
  python scripts/test_trend_signal.py BTC/USDT:USDT     # 测试BTC
  python scripts/test_trend_signal.py ETH/USDT:USDT     # 测试ETH
  
支持的币种格式:
  - ARB/USDT:USDT  (推荐，完整格式)
  - ARB            (自动转换为ARB/USDT:USDT)
  - ARB/USDT       (自动补充:USDT)
        """
    )
    parser.add_argument(
        'symbol',
        nargs='?',
        default='ARB/USDT:USDT',
        help='交易对符号 (默认: ARB/USDT:USDT)'
    )
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='显示详细日志'
    )
    
    args = parser.parse_args()
    
    # 处理币种格式
    symbol = args.symbol.upper()
    
    # 自动补全格式
    if '/' not in symbol:
        # 只有币种名称，如 "ARB"
        symbol = f"{symbol}/USDT:USDT"
    elif ':' not in symbol:
        # 有交易对但无合约类型，如 "ARB/USDT"
        symbol = f"{symbol}:USDT"
    
    try:
        logger.info(f"\n🔍 准备分析币种: {symbol}\n")
        
        analyzer = TrendSignalAnalyzer(symbol)
        success = analyzer.run_full_analysis()
        
        return 0 if success else 1
        
    except KeyboardInterrupt:
        logger.warning("\n\n⚠️  分析被用户中断")
        return 1
    except Exception as e:
        logger.exception(f"❌ 分析过程中出现错误: {e}")
        return 1


def test_arb_trend_signal():
    """Pytest测试函数 - 测试ARB/USDT:USDT趋势信号分析"""
    symbol = "ARB/USDT:USDT"
    analyzer = TrendSignalAnalyzer(symbol)
    
    # 测试数据获取
    assert analyzer.fetch_data(), "数据获取失败"
    assert analyzer.data_5m is not None, "5分钟数据为空"
    assert analyzer.data_15m is not None, "15分钟数据为空"
    assert analyzer.data_1h is not None, "1小时数据为空"
    
    # 测试趋势分析
    assert analyzer.analyze_trend(), "趋势分析失败"
    assert analyzer.trend_info is not None, "趋势信息为空"
    assert analyzer.trend_info.direction in ['up', 'down', 'neutral'], "趋势方向无效"
    
    # 测试指标分析
    assert analyzer.analyze_indicators(), "指标分析失败"
    
    # 测试支撑阻力分析
    assert analyzer.analyze_support_resistance(), "支撑阻力分析失败"
    
    # 测试信号生成（可能无信号）
    analyzer.generate_signal()
    # 信号可以为空，这是正常的
    
    logger.success(f"✅ {symbol} 测试完成！")


def test_multiple_symbols():
    """Pytest测试函数 - 测试多个币种"""
    symbols = ["BTC/USDT:USDT", "ETH/USDT:USDT"]
    
    for symbol in symbols:
        logger.info(f"\n{'='*60}")
        logger.info(f"测试币种: {symbol}")
        logger.info(f"{'='*60}\n")
        
        analyzer = TrendSignalAnalyzer(symbol)
        
        # 只测试数据获取和趋势分析
        if analyzer.fetch_data():
            analyzer.analyze_trend()
            logger.success(f"✅ {symbol} 基础分析完成")
        else:
            logger.warning(f"⚠️  {symbol} 数据获取失败，跳过")


if __name__ == '__main__':
    # 直接运行模式
    sys.exit(main())

