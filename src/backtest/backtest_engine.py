"""
回测引擎
包含未来数据泄露检查和时区处理
"""
import pandas as pd
import numpy as np
import pytz
from typing import Dict, Any, List, Optional
from datetime import datetime
from loguru import logger

from ..indicators.heikinashi import HeikinAshi
from ..indicators.technical import TechnicalIndicators as TI
from ..indicators.renko import ATRRenkoBuilder, RenkoSignalGenerator


class Trade:
    """交易记录"""

    def __init__(
        self,
        entry_time: datetime,
        entry_price: float,
        direction: str,  # 'LONG' or 'SHORT'
        size: float = 1.0,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        tp1_price: Optional[float] = None,
        tp2_price: Optional[float] = None,
        tp1_percent: float = 0.5,  # 第一止盈平仓50%
        tp2_percent: float = 0.3   # 第二止盈平仓30%
    ):
        self.entry_time = entry_time
        self.entry_price = entry_price
        self.direction = direction
        self.initial_size = size  # 初始仓位
        self.size = size  # 当前剩余仓位
        self.closed_size = 0.0  # 已平仓位

        # ⚡ 止盈止损价格（在开仓时计算并固定，持仓期间不会被修改）
        self.stop_loss = stop_loss          # 固定止损价格
        self.take_profit = take_profit      # 固定止盈价格
        self.trailing_stop = stop_loss      # 追踪止损价格（动态调整）
        
        # 分批止盈（价格固定，触发后标记为True）
        self.tp1_price = tp1_price          # 第一止盈价格（固定）
        self.tp2_price = tp2_price          # 第二止盈价格（固定）
        self.tp1_percent = tp1_percent
        self.tp2_percent = tp2_percent
        self.tp1_triggered = False
        self.tp2_triggered = False

        self.exit_time: Optional[datetime] = None
        self.exit_price: Optional[float] = None
        self.exit_reason: Optional[str] = None  # 'signal', 'stop_loss', 'take_profit', 'trailing_stop', 'tp1', 'tp2'
        self.pnl: Optional[float] = None
        self.pnl_pct: Optional[float] = None
        self.max_profit: float = 0.0
        self.max_drawdown: float = 0.0
        
        # 分批平仓记录
        self.partial_exits: List[Dict] = []

    def partial_close(self, exit_time: datetime, exit_price: float, close_percent: float, reason: str):
        """
        部分平仓
        
        Args:
            exit_time: 平仓时间
            exit_price: 平仓价格
            close_percent: 平仓比例（0-1）
            reason: 平仓原因
        """
        close_size = self.initial_size * close_percent
        
        if self.direction == 'LONG':
            partial_pnl = (exit_price - self.entry_price) * close_size
        else:
            partial_pnl = (self.entry_price - exit_price) * close_size
        
        self.partial_exits.append({
            'time': exit_time,
            'price': exit_price,
            'size': close_size,
            'percent': close_percent,
            'pnl': partial_pnl,
            'reason': reason
        })
        
        self.size -= close_size
        self.closed_size += close_size
        
    def close(self, exit_time: datetime, exit_price: float, exit_reason: str = 'signal'):
        """完全平仓"""
        self.exit_time = exit_time
        self.exit_price = exit_price
        self.exit_reason = exit_reason

        # 计算总盈亏（包括已部分平仓的）
        total_pnl = sum([exit['pnl'] for exit in self.partial_exits])
        
        if self.size > 0:  # 还有剩余仓位
            if self.direction == 'LONG':
                total_pnl += (exit_price - self.entry_price) * self.size
            else:
                total_pnl += (self.entry_price - exit_price) * self.size
        
        self.pnl = total_pnl
        self.pnl_pct = total_pnl / (self.entry_price * self.initial_size)

    def check_partial_exits(self, current_high: float, current_low: float) -> Optional[Dict]:
        """
        检查是否触发分批止盈
        
        Args:
            current_high: 当前K线最高价
            current_low: 当前K线最低价
            
        Returns:
            {'action': 'tp1' or 'tp2', 'price': float} 或 None
        """
        if self.direction == 'LONG':
            # 多头检查
            if not self.tp1_triggered and self.tp1_price and current_high >= self.tp1_price:
                return {'action': 'tp1', 'price': self.tp1_price}
            if not self.tp2_triggered and self.tp2_price and current_high >= self.tp2_price:
                return {'action': 'tp2', 'price': self.tp2_price}
        else:
            # 空头检查
            if not self.tp1_triggered and self.tp1_price and current_low <= self.tp1_price:
                return {'action': 'tp1', 'price': self.tp1_price}
            if not self.tp2_triggered and self.tp2_price and current_low <= self.tp2_price:
                return {'action': 'tp2', 'price': self.tp2_price}
        
        return None
    
    def update_metrics(self, current_price: float):
        """更新交易指标（基于剩余仓位）"""
        if self.direction == 'LONG':
            unrealized_pnl_pct = (current_price - self.entry_price) / self.entry_price
        else:
            unrealized_pnl_pct = (self.entry_price - current_price) / self.entry_price

        self.max_profit = max(self.max_profit, unrealized_pnl_pct)
        self.max_drawdown = min(self.max_drawdown, unrealized_pnl_pct)

    def update_trailing_stop(self, current_price: float, atr_value: float, stop_factor: float):
        """
        更新追踪止损价格
        
        Args:
            current_price: 当前价格
            atr_value: ATR值
            stop_factor: 止损倍数
        """
        if self.direction == 'LONG':
            # 多头：止损价格向上追踪
            new_stop = current_price - atr_value * stop_factor
            if self.trailing_stop is None or new_stop > self.trailing_stop:
                self.trailing_stop = new_stop
        else:
            # 空头：止损价格向下追踪
            new_stop = current_price + atr_value * stop_factor
            if self.trailing_stop is None or new_stop < self.trailing_stop:
                self.trailing_stop = new_stop

    def check_exit(self, current_high: float, current_low: float) -> Optional[str]:
        """
        检查是否触发止盈止损
        
        Args:
            current_high: 当前K线最高价
            current_low: 当前K线最低价
            
        Returns:
            退出原因: 'stop_loss', 'take_profit', 'trailing_stop' 或 None
        """
        if self.direction == 'LONG':
            # 多头检查
            if self.stop_loss and current_low <= self.stop_loss:
                return 'stop_loss'
            if self.trailing_stop and current_low <= self.trailing_stop:
                return 'trailing_stop'
            if self.take_profit and current_high >= self.take_profit:
                return 'take_profit'
        else:
            # 空头检查
            if self.stop_loss and current_high >= self.stop_loss:
                return 'stop_loss'
            if self.trailing_stop and current_high >= self.trailing_stop:
                return 'trailing_stop'
            if self.take_profit and current_low <= self.take_profit:
                return 'take_profit'
        
        return None


class BacktestEngine:
    """回测引擎（含未来数据泄露检查）"""

    def __init__(self, config: Dict[str, Any], timezone: str = 'Asia/Shanghai'):
        """
        初始化回测引擎

        Args:
            config: 策略配置
            timezone: 时区（默认上海时区）
        """
        self.config = config
        self.timezone = pytz.timezone(timezone)

        # 策略参数
        self.setup_type = config.get('setup_type', 'Open/Close')
        self.filter_type = config.get('filter_type', 'No Filtering')
        self.tps_type = config.get('tps_type', 'Trailing')

        # 指标参数
        self.rsi_period = config.get('rsi_period', 7)
        self.rsi_high = config.get('rsi_high', 45)
        self.rsi_low = config.get('rsi_low', 10)

        # ATR过滤参数
        self.atr_filter_period = config.get('atr_filter_period', 5)
        self.atr_filter_ma_period = config.get('atr_filter_ma_period', 5)

        # 风险管理ATR参数（用于止盈止损）
        self.atr_risk_period = config.get('atr_risk_period', 20)
        self.profit_factor = config.get('profit_factor', 2.5)  # 止盈倍数
        self.stop_factor = config.get('stop_factor', 10.0)  # 止损倍数
        
        # 分批止盈设置
        self.enable_partial_exits = config.get('enable_partial_exits', False)
        self.tp1_factor = config.get('tp1_factor', 1.5)
        self.tp2_factor = config.get('tp2_factor', 2.0)
        self.tp1_percent = config.get('tp1_percent', 0.5)
        self.tp2_percent = config.get('tp2_percent', 0.3)

        # 时间框架
        self.htf_multiplier = config.get('htf_multiplier', 18)

        # 初始资金
        self.initial_capital = config.get('initial_capital', 10000.0)
        self.position_size = config.get('position_size', 0.95)  # 95% 资金

        # 风险控制
        self.max_drawdown_percent = config.get('max_drawdown_percent', 10)  # 最大回撤百分比

        # 交易记录
        self.trades: List[Trade] = []
        self.current_trade: Optional[Trade] = None
        self.equity_curve = []

        # 数据验证标记
        self.lookahead_checks = []

        # 统计信息
        self.exit_stats = {
            'signal': 0,
            'stop_loss': 0,
            'take_profit': 0,
            'trailing_stop': 0,
            'max_drawdown': 0,  # 最大回撤强制平仓
            'tp1': 0,  # 第一止盈
            'tp2': 0   # 第二止盈
        }

        partial_exits_str = f", 分批止盈 ({self.tp1_percent*100:.0f}%/{self.tp2_percent*100:.0f}%)" if self.enable_partial_exits else ""
        logger.info(f"✅ 回测引擎初始化: {self.setup_type} 模式, {self.tps_type} 止盈止损{partial_exits_str}, "
                   f"最大回撤限制 {self.max_drawdown_percent}% ({timezone})")

    def run(
        self,
        base_df: pd.DataFrame,
        htf_df: Optional[pd.DataFrame] = None
    ) -> Dict[str, Any]:
        """
        运行回测

        Args:
            base_df: 基础时间框架数据
            htf_df: 高级时间框架数据（可选）

        Returns:
            回测结果
        """
        logger.info("=" * 60)
        logger.info("开始回测")
        logger.info("=" * 60)

        # 转换时区
        base_df = self._convert_timezone(base_df)
        if htf_df is not None:
            htf_df = self._convert_timezone(htf_df)

        # 验证数据完整性
        self._validate_data(base_df, htf_df)

        # 重置状态
        self.trades = []
        self.current_trade = None
        self.equity_curve = []
        self.lookahead_checks = []
        current_capital = self.initial_capital

        # 如果使用 Renko 模式，需要构建 Renko 数据
        if self.setup_type == 'Renko' and htf_df is not None:
            renko_builder = ATRRenkoBuilder(atr_period=3)
            renko_df = renko_builder.build(htf_df)
            renko_signal_gen = RenkoSignalGenerator(ema_fast=2, ema_slow=10)
        else:
            renko_df = None
            renko_signal_gen = None

        # 遍历每根K线
        for i in range(max(50, self.htf_multiplier * 2), len(base_df)):
            current_time = base_df['timestamp'].iloc[i]
            current_price = base_df['close'].iloc[i]
            current_high = base_df['high'].iloc[i]
            current_low = base_df['low'].iloc[i]

            # 获取历史数据片段
            hist_base = base_df.iloc[:i+1]

            # 如果有 HTF 数据，找到对应的片段
            if htf_df is not None:
                htf_idx = htf_df[htf_df['timestamp'] <= current_time].index[-1] if len(htf_df[htf_df['timestamp'] <= current_time]) > 0 else 0
                hist_htf = htf_df.iloc[:htf_idx+1]
            else:
                hist_htf = None

            # 生成信号
            signal = self._generate_signal(hist_base, hist_htf, renko_df, renko_signal_gen)

            # 更新当前持仓的指标
            if self.current_trade:
                self.current_trade.update_metrics(current_price)
                
                # 检查分批止盈
                if self.enable_partial_exits:
                    partial_exit = self.current_trade.check_partial_exits(current_high, current_low)
                    if partial_exit:
                        action = partial_exit['action']
                        exit_price = partial_exit['price']
                        
                        if action == 'tp1' and not self.current_trade.tp1_triggered:
                            # 第一止盈：平仓50%
                            self.current_trade.partial_close(current_time, exit_price, self.tp1_percent, 'tp1')
                            self.current_trade.tp1_triggered = True
                            self.exit_stats['tp1'] += 1
                            logger.info(
                                f"🎯 TP1触发: {current_time} @ {exit_price:.2f}, "
                                f"平仓 {self.tp1_percent*100:.0f}%, 剩余 {self.current_trade.size:.4f}"
                            )
                        
                        elif action == 'tp2' and not self.current_trade.tp2_triggered:
                            # 第二止盈：平仓30%
                            self.current_trade.partial_close(current_time, exit_price, self.tp2_percent, 'tp2')
                            self.current_trade.tp2_triggered = True
                            self.exit_stats['tp2'] += 1
                            logger.info(
                                f"🎯 TP2触发: {current_time} @ {exit_price:.2f}, "
                                f"平仓 {self.tp2_percent*100:.0f}%, 剩余 {self.current_trade.size:.4f}"
                            )
                
                # 检查是否超过最大回撤限制
                current_drawdown_pct = abs(self.current_trade.max_drawdown * 100)
                if current_drawdown_pct > self.max_drawdown_percent:
                    # 强制平仓：超过最大回撤
                    self.current_trade.close(current_time, current_price, 'max_drawdown')
                    current_capital += self.current_trade.pnl
                    self.trades.append(self.current_trade)
                    self.exit_stats['max_drawdown'] += 1
                    
                    logger.warning(
                        f"⚠️ 最大回撤平仓: {current_time} @ {current_price:.2f}, "
                        f"回撤: {current_drawdown_pct:.2f}%, PnL: {self.current_trade.pnl:.2f}"
                    )
                    self.current_trade = None
                    signal = None  # 清除信号，避免立即重新开仓

            # 处理信号
            if signal == 'BUY' and not self.current_trade:
                # ⚡ 重要：止损止盈价格在开仓时立即计算并固定
                # 这些价格在持仓期间不会被重新计算或修改（除了trailing_stop会动态调整）
                stop_loss, take_profit, tp1_price, tp2_price = self._calculate_sl_tp(hist_base, current_price, 'LONG')
                
                # 开多
                position_value = current_capital * self.position_size
                size = position_value / current_price
                
                # 创建Trade对象时，将预先计算好的止损止盈价格传入
                self.current_trade = Trade(
                    current_time, 
                    current_price, 
                    'LONG', 
                    size,
                    stop_loss,      # 固定止损价格
                    take_profit,    # 固定止盈价格
                    tp1_price,      # 第一止盈价格
                    tp2_price,      # 第二止盈价格
                    self.tp1_percent,
                    self.tp2_percent
                )
                
                tp_info = f", TP1: {tp1_price:.2f}, TP2: {tp2_price:.2f}" if self.enable_partial_exits and tp1_price else ""
                sl_tp_info = f", SL: {stop_loss:.2f}, TP: {take_profit:.2f}" if stop_loss or take_profit else ""
                logger.debug(f"📈 开多: {current_time} @ {current_price:.2f}{sl_tp_info}{tp_info}")

            elif signal == 'SELL':
                if self.current_trade and self.current_trade.direction == 'LONG':
                    # 平多（信号退出）
                    self.current_trade.close(current_time, current_price, 'signal')
                    current_capital += self.current_trade.pnl
                    self.trades.append(self.current_trade)
                    self.exit_stats['signal'] += 1
                    logger.debug(f"📉 平多: {current_time} @ {current_price:.2f}, PnL: {self.current_trade.pnl:.2f}")
                    self.current_trade = None

                # 如果策略允许做空（当前策略不做空）
                # if not self.current_trade:
                #     position_value = current_capital * self.position_size
                #     size = position_value / current_price
                #     self.current_trade = Trade(current_time, current_price, 'SHORT', size)

            # 记录权益曲线
            equity = current_capital
            if self.current_trade:
                if self.current_trade.direction == 'LONG':
                    equity += (current_price - self.current_trade.entry_price) * self.current_trade.size
                else:
                    equity += (self.current_trade.entry_price - current_price) * self.current_trade.size

            self.equity_curve.append({
                'timestamp': current_time,
                'equity': equity,
                'price': current_price
            })

        # 如果还有持仓，强制平仓
        if self.current_trade:
            last_price = base_df['close'].iloc[-1]
            last_time = base_df['timestamp'].iloc[-1]
            self.current_trade.close(last_time, last_price, 'forced')
            current_capital += self.current_trade.pnl
            self.trades.append(self.current_trade)
            self.exit_stats['signal'] += 1  # 强制平仓计入信号退出
            logger.info(f"⚠️ 强制平仓: {last_time} @ {last_price:.2f}")
            self.current_trade = None

        # 计算性能指标
        results = self._calculate_metrics(current_capital)

        logger.info("=" * 60)
        logger.info("回测完成")
        logger.info("=" * 60)

        return results

    def _generate_signal(
        self,
        base_df: pd.DataFrame,
        htf_df: Optional[pd.DataFrame],
        renko_df: Optional[pd.DataFrame],
        renko_signal_gen: Optional[RenkoSignalGenerator]
    ) -> Optional[str]:
        """生成交易信号"""

        if self.setup_type == 'Open/Close' and htf_df is not None:
            # Heikin Ashi Open/Close 交叉
            ha_df = HeikinAshi.calculate(htf_df)
            signal = HeikinAshi.detect_crossover(ha_df)

        elif self.setup_type == 'Renko' and renko_df is not None and renko_signal_gen is not None:
            # Renko EMA 交叉
            signal = renko_signal_gen.generate_signal(renko_df)

        else:
            signal = None

        # 应用过滤器
        if signal and self.filter_type != 'No Filtering':
            if not self._check_filters(base_df):
                signal = None

        return signal

    def _calculate_sl_tp(
        self,
        df: pd.DataFrame,
        entry_price: float,
        direction: str
    ) -> tuple[Optional[float], Optional[float], Optional[float], Optional[float]]:
        """
        计算止盈止损价格

        Args:
            df: 历史数据
            entry_price: 入场价格
            direction: 交易方向 ('LONG' or 'SHORT')

        Returns:
            (止损价, 止盈价, TP1价格, TP2价格)
        """
        # 调试信息
        logger.debug(f"🔍 _calculate_sl_tp 调用: tps_type={self.tps_type} (type={type(self.tps_type)}), enable_partial_exits={self.enable_partial_exits}")
        
        # if self.tps_type == 'No' and not self.enable_partial_exits:
        #     logger.debug("❌ 返回None: tps_type=='No' 且 enable_partial_exits=False")
        #     return None, None, None, None

        # 计算ATR
        atr = TI.atr(df, self.atr_risk_period)
        if len(atr) == 0:
            logger.debug("❌ 返回None: ATR长度为0")
            return None, None, None, None

        current_atr = atr.iloc[-1]

        if pd.isna(current_atr):
            logger.debug(f"❌ 返回None: current_atr is NaN")
            return None, None, None, None
        
        logger.debug(f"✅ ATR计算成功: {current_atr:.2f}")

        # 计算基础止盈止损
        if direction == 'LONG':
            stop_loss = entry_price - current_atr * self.stop_factor
            take_profit = entry_price + current_atr * self.profit_factor
        else:  # SHORT
            stop_loss = entry_price + current_atr * self.stop_factor
            take_profit = entry_price - current_atr * self.profit_factor

        # 计算分批止盈价格
        tp1_price = None
        tp2_price = None
        if self.enable_partial_exits:
            if direction == 'LONG':
                tp1_price = entry_price + current_atr * self.tp1_factor
                tp2_price = entry_price + current_atr * self.tp2_factor
            else:  # SHORT
                tp1_price = entry_price - current_atr * self.tp1_factor
                tp2_price = entry_price - current_atr * self.tp2_factor

        return stop_loss, take_profit, tp1_price, tp2_price

    def _get_current_atr(self, df: pd.DataFrame) -> Optional[float]:
        """
        获取当前ATR值（用于追踪止损）

        Args:
            df: 历史数据

        Returns:
            当前ATR值
        """
        atr = TI.atr(df, self.atr_risk_period)
        if len(atr) == 0:
            return None
        return atr.iloc[-1]

    def _check_filters(self, df: pd.DataFrame) -> bool:
        """检查过滤条件"""

        # RSI 过滤
        rsi = TI.rsi(df['close'], self.rsi_period)
        current_rsi = rsi.iloc[-1]

        rsi_filter = self.rsi_low < current_rsi < self.rsi_high

        # ATR 过滤（使用atr_filter_period）
        atr = TI.atr(df, self.atr_filter_period)
        atr_ema = TI.ema(atr.dropna(), self.atr_filter_ma_period)

        atr_filter = atr.iloc[-1] < atr_ema.iloc[-1]  # 非横盘

        # 根据过滤类型判断
        if self.filter_type == 'Filter with ATR':
            return atr_filter
        elif self.filter_type == 'Filter with RSI':
            return rsi_filter
        elif self.filter_type == 'ATR or RSI':
            return atr_filter or rsi_filter
        elif self.filter_type == 'ATR and RSI':
            return atr_filter and rsi_filter
        elif self.filter_type in ['Entry Only in sideways market(By ATR or RSI)',
                                   'Entry Only in sideways market(By ATR and RSI)']:
            # 横盘市场（反向逻辑）
            sideways_atr = atr.iloc[-1] >= atr_ema.iloc[-1]
            sideways_rsi = not rsi_filter

            if 'or' in self.filter_type:
                return sideways_atr or sideways_rsi
            else:
                return sideways_atr and sideways_rsi

        return True

    def _calculate_metrics(self, final_capital: float) -> Dict[str, Any]:
        """计算回测指标"""

        if not self.trades:
            logger.warning("⚠️ 没有完成的交易")
            return {
                'total_trades': 0,
                'win_rate': 0,
                'total_return': 0,
                'sharpe_ratio': 0,
                'max_drawdown': 0,
            }

        # 基本统计
        total_trades = len(self.trades)
        winning_trades = [t for t in self.trades if t.pnl > 0]
        losing_trades = [t for t in self.trades if t.pnl <= 0]

        win_rate = len(winning_trades) / total_trades if total_trades > 0 else 0

        # 收益统计
        total_return = (final_capital - self.initial_capital) / self.initial_capital
        total_return_pct = total_return * 100

        avg_win = np.mean([t.pnl for t in winning_trades]) if winning_trades else 0
        avg_loss = np.mean([t.pnl for t in losing_trades]) if losing_trades else 0

        # 最大回撤
        equity_df = pd.DataFrame(self.equity_curve)
        running_max = equity_df['equity'].cummax()
        drawdown = (equity_df['equity'] - running_max) / running_max
        max_drawdown = drawdown.min()
        max_drawdown_pct = max_drawdown * 100

        # Sharpe Ratio（假设无风险利率为 0）
        equity_returns = equity_df['equity'].pct_change().dropna()
        if len(equity_returns) > 0 and equity_returns.std() > 0:
            sharpe_ratio = (equity_returns.mean() / equity_returns.std()) * np.sqrt(252 * 24)  # 年化
        else:
            sharpe_ratio = 0

        # 盈亏比
        profit_factor = abs(avg_win / avg_loss) if avg_loss != 0 else float('inf')

        # 交易持续时间
        durations = [(t.exit_time - t.entry_time).total_seconds() / 3600 for t in self.trades]
        avg_duration = np.mean(durations) if durations else 0

        # 退出原因统计
        exit_by_signal = self.exit_stats.get('signal', 0)
        exit_by_max_drawdown = self.exit_stats.get('max_drawdown', 0)
        exit_by_tp1 = self.exit_stats.get('tp1', 0)
        exit_by_tp2 = self.exit_stats.get('tp2', 0)

        results = {
            'initial_capital': self.initial_capital,
            'final_capital': final_capital,
            'total_return': total_return,
            'total_return_pct': total_return_pct,
            'total_trades': total_trades,
            'winning_trades': len(winning_trades),
            'losing_trades': len(losing_trades),
            'win_rate': win_rate,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'profit_factor': profit_factor,
            'max_drawdown': max_drawdown,
            'max_drawdown_pct': max_drawdown_pct,
            'sharpe_ratio': sharpe_ratio,
            'avg_duration_hours': avg_duration,
            # 退出原因统计
            'exit_by_signal': exit_by_signal,
            'exit_by_max_drawdown': exit_by_max_drawdown,
            'exit_by_tp1': exit_by_tp1,
            'exit_by_tp2': exit_by_tp2,
            'exit_stats': self.exit_stats,
            'trades': self.trades,
            'equity_curve': equity_df,
            'lookahead_checks': self.lookahead_checks,
        }

        return results

    def _convert_timezone(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        转换时区到上海时区

        Args:
            df: 数据框

        Returns:
            转换后的数据框
        """
        df = df.copy()
        if 'timestamp' in df.columns:
            if df['timestamp'].dt.tz is None:
                # 假设原始数据是 UTC
                df['timestamp'] = df['timestamp'].dt.tz_localize('UTC').dt.tz_convert(self.timezone)
                logger.debug(f"✅ 已将时区从 UTC 转换到 {self.timezone}")
            else:
                df['timestamp'] = df['timestamp'].dt.tz_convert(self.timezone)
                logger.debug(f"✅ 已转换时区到 {self.timezone}")
        return df

    def _validate_data(self, base_df: pd.DataFrame, htf_df: Optional[pd.DataFrame]):
        """
        验证数据完整性和时间顺序

        Args:
            base_df: 基础时间框架数据
            htf_df: 高级时间框架数据
        """
        logger.info("\n🔍 数据完整性检查")
        logger.info("-" * 60)

        # 1. 检查数据是否按时间排序
        if not base_df['timestamp'].is_monotonic_increasing:
            logger.error("❌ 基础数据时间顺序不正确！")
            raise ValueError("数据必须按时间顺序排列")
        else:
            logger.info("✅ 基础数据时间顺序正确")

        if htf_df is not None and not htf_df['timestamp'].is_monotonic_increasing:
            logger.error("❌ HTF数据时间顺序不正确！")
            raise ValueError("HTF数据必须按时间顺序排列")
        elif htf_df is not None:
            logger.info("✅ HTF数据时间顺序正确")

        # 2. 检查是否有缺失值
        null_counts = base_df[['open', 'high', 'low', 'close']].isnull().sum()
        if null_counts.sum() > 0:
            logger.warning(f"⚠️ 发现缺失值: {null_counts.to_dict()}")
        else:
            logger.info("✅ 无缺失值")

        # 3. 检查价格逻辑
        invalid_prices = base_df[
            (base_df['high'] < base_df['low']) |
            (base_df['high'] < base_df['open']) |
            (base_df['high'] < base_df['close']) |
            (base_df['low'] > base_df['open']) |
            (base_df['low'] > base_df['close'])
        ]

        if len(invalid_prices) > 0:
            logger.error(f"❌ 发现 {len(invalid_prices)} 根K线价格逻辑错误！")
            logger.error(f"错误时间: {invalid_prices['timestamp'].tolist()[:5]}")
        else:
            logger.info("✅ 价格逻辑正确")

        # 4. 记录数据范围
        logger.info(f"\n📊 数据范围:")
        logger.info(f"   基础框架: {len(base_df)} 根K线")
        logger.info(f"   时间范围: {base_df['timestamp'].iloc[0]} → {base_df['timestamp'].iloc[-1]}")
        logger.info(f"   价格范围: {base_df['close'].min():.2f} - {base_df['close'].max():.2f}")

        if htf_df is not None:
            logger.info(f"   HTF框架: {len(htf_df)} 根K线")
            logger.info(f"   HTF范围: {htf_df['timestamp'].iloc[0]} → {htf_df['timestamp'].iloc[-1]}")

        logger.info("\n" + "=" * 60)