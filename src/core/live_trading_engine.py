"""
实盘交易引擎
基于回测引擎的策略逻辑，实现实时交易
@author Cursor
@date 2025-01-22
@version 1.0.0
@copyright (C) 2025 Belle Information Technology Co.,Ltd 
All Rights Reserved.  
The software for the belle technology development, without the 
company's written consent, and any other individuals and 
organizations shall not be used, Copying, Modify or distribute 
the software.
"""
import time
import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from loguru import logger

from ..data.binance_client import BinanceClient
from ..execution.order_manager import OrderManager
from ..execution.position_manager import PositionManager
from ..indicators.heikinashi import HeikinAshi
from ..indicators.technical import TechnicalIndicators as TI
from ..indicators.renko import ATRRenkoBuilder, RenkoSignalGenerator


class LivePosition:
    """实盘持仓类（对应回测的Trade类）"""

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
        tp1_percent: float = 0.5,
        tp2_percent: float = 0.3
    ):
        self.entry_time = entry_time
        self.entry_price = entry_price
        self.direction = direction
        self.initial_size = size
        self.size = size
        self.closed_size = 0.0

        # 止盈止损价格
        self.stop_loss = stop_loss
        self.take_profit = take_profit
        self.trailing_stop = stop_loss

        # 分批止盈
        self.tp1_price = tp1_price
        self.tp2_price = tp2_price
        self.tp1_percent = tp1_percent
        self.tp2_percent = tp2_percent
        self.tp1_triggered = False
        self.tp2_triggered = False

        # 风险指标
        self.max_profit = 0.0
        self.max_drawdown = 0.0
        self.partial_exits: List[Dict] = []

    def update_metrics(self, current_price: float):
        """更新持仓指标"""
        if self.direction == 'LONG':
            unrealized_pnl_pct = (current_price - self.entry_price) / self.entry_price
        else:
            unrealized_pnl_pct = (self.entry_price - current_price) / self.entry_price

        self.max_profit = max(self.max_profit, unrealized_pnl_pct)
        self.max_drawdown = min(self.max_drawdown, unrealized_pnl_pct)

    def update_trailing_stop(self, current_price: float, atr_value: float, stop_factor: float):
        """更新追踪止损"""
        if self.direction == 'LONG':
            new_stop = current_price - atr_value * stop_factor
            if self.trailing_stop is None or new_stop > self.trailing_stop:
                self.trailing_stop = new_stop
                logger.debug(f"🔄 追踪止损更新: {new_stop:.6f}")
        else:
            new_stop = current_price + atr_value * stop_factor
            if self.trailing_stop is None or new_stop < self.trailing_stop:
                self.trailing_stop = new_stop
                logger.debug(f"🔄 追踪止损更新: {new_stop:.6f}")

    def check_partial_exits(self, current_high: float, current_low: float) -> Optional[Dict]:
        """检查分批止盈"""
        if self.direction == 'LONG':
            if not self.tp1_triggered and self.tp1_price and current_high >= self.tp1_price:
                return {'action': 'tp1', 'price': self.tp1_price}
            if not self.tp2_triggered and self.tp2_price and current_high >= self.tp2_price:
                return {'action': 'tp2', 'price': self.tp2_price}
        else:
            if not self.tp1_triggered and self.tp1_price and current_low <= self.tp1_price:
                return {'action': 'tp1', 'price': self.tp1_price}
            if not self.tp2_triggered and self.tp2_price and current_low <= self.tp2_price:
                return {'action': 'tp2', 'price': self.tp2_price}
        return None

    def check_exit(self, current_high: float, current_low: float) -> Optional[str]:
        """检查止盈止损触发"""
        if self.direction == 'LONG':
            if self.stop_loss and current_low <= self.stop_loss:
                return 'stop_loss'
            if self.trailing_stop and current_low <= self.trailing_stop:
                return 'trailing_stop'
            if self.take_profit and current_high >= self.take_profit:
                return 'take_profit'
        else:
            if self.stop_loss and current_high >= self.stop_loss:
                return 'stop_loss'
            if self.trailing_stop and current_high >= self.trailing_stop:
                return 'trailing_stop'
            if self.take_profit and current_low <= self.take_profit:
                return 'take_profit'
        return None

    def get_unrealized_pnl(self, current_price: float) -> float:
        """计算未实现盈亏"""
        if self.direction == 'LONG':
            return (current_price - self.entry_price) * self.size
        else:
            return (self.entry_price - current_price) * self.size


class LiveTradingEngine:
    """实盘交易引擎"""

    def __init__(self, config: Dict[str, Any]):
        """
        初始化实盘交易引擎

        Args:
            config: 完整配置字典（包含交易所、策略、风控等配置）
        """
        self.config = config

        # 交易所配置
        exchange_config = config.get('exchange', {})
        self.client = BinanceClient(exchange_config)
        
        # 交易参数
        trading_config = config.get('trading', {})
        self.symbol = trading_config.get('symbol', 'BTC/USDT')
        self.base_timeframe = trading_config.get('base_timeframe', '5m')
        self.leverage = trading_config.get('leverage', 1.0)
        
        # 策略参数（与回测引擎保持一致）
        strategy_config = config.get('strategy', {})
        self.setup_type = strategy_config.get('setup_type', 'Open/Close')
        self.filter_type = strategy_config.get('filter_type', 'No Filtering')
        self.tps_type = strategy_config.get('tps_type', 'Trailing')
        
        # 指标参数
        self.rsi_period = strategy_config.get('rsi_period', 7)
        self.rsi_high = strategy_config.get('rsi_high', 45)
        self.rsi_low = strategy_config.get('rsi_low', 10)
        
        self.atr_filter_period = strategy_config.get('atr_filter_period', 5)
        self.atr_filter_ma_period = strategy_config.get('atr_filter_ma_period', 5)
        
        # 风险管理参数
        self.atr_risk_period = strategy_config.get('atr_risk_period', 20)
        self.profit_factor = strategy_config.get('profit_factor', 2.5)
        self.stop_factor = strategy_config.get('stop_factor', 10.0)
        
        # 分批止盈设置
        self.enable_partial_exits = strategy_config.get('enable_partial_exits', False)
        self.tp1_factor = strategy_config.get('tp1_factor', 1.5)
        self.tp2_factor = strategy_config.get('tp2_factor', 2.0)
        self.tp1_percent = strategy_config.get('tp1_percent', 0.5)
        self.tp2_percent = strategy_config.get('tp2_percent', 0.3)
        
        # 时间框架倍数
        self.htf_multiplier = strategy_config.get('htf_multiplier', 18)
        
        # 风控参数
        risk_config = config.get('risk_management', {})
        self.position_size_pct = risk_config.get('position_size', 0.95)
        self.max_drawdown_percent = risk_config.get('max_drawdown_percent', 10)
        self.max_daily_loss = risk_config.get('max_daily_loss', 20)  # 每日最大亏损%
        
        # 订单管理和仓位管理
        execution_config = config.get('execution', {})
        self.order_manager = OrderManager(self.client, execution_config)
        self.position_manager = PositionManager()
        
        # 当前持仓对象
        self.current_position: Optional[LivePosition] = None
        
        # Renko构建器（如需要）
        if self.setup_type == 'Renko':
            self.renko_builder = ATRRenkoBuilder(atr_period=3)
            self.renko_signal_gen = RenkoSignalGenerator(ema_fast=2, ema_slow=10)
        else:
            self.renko_builder = None
            self.renko_signal_gen = None
        
        # 统计信息
        self.daily_pnl = 0.0
        self.total_trades = 0
        self.winning_trades = 0
        self.exit_stats = {
            'signal': 0,
            'stop_loss': 0,
            'take_profit': 0,
            'trailing_stop': 0,
            'max_drawdown': 0,
            'tp1': 0,
            'tp2': 0
        }
        
        # 运行状态
        self.is_running = False
        self.last_check_time = None
        
        logger.info("=" * 60)
        logger.info("🚀 实盘交易引擎初始化完成")
        logger.info(f"   交易对: {self.symbol}")
        logger.info(f"   策略模式: {self.setup_type}")
        logger.info(f"   过滤器: {self.filter_type}")
        logger.info(f"   止盈止损: {self.tps_type}")
        logger.info(f"   分批止盈: {'启用' if self.enable_partial_exits else '禁用'}")
        logger.info(f"   最大回撤限制: {self.max_drawdown_percent}%")
        logger.info("=" * 60)

    def start(self):
        """启动交易引擎"""
        logger.info("\n🎬 启动实盘交易引擎...")
        
        # 1. 检查账户余额
        balance = self.client.fetch_balance()
        usdt_balance = balance.get('USDT', {}).get('free', 0)
        logger.info(f"💰 账户余额: {usdt_balance:.2f} USDT")
        
        if usdt_balance < 10:
            logger.error("❌ 账户余额不足，无法启动交易")
            return
        
        # 2. 设置杠杆和保证金模式（从配置读取）
        trading_config = self.config.get('trading', {})
        leverage = trading_config.get('leverage', 1)
        margin_mode = trading_config.get('margin_mode', 'cross')
        
        if leverage > 1:
            try:
                self.client.set_leverage(leverage, self.symbol)
                logger.info(f"⚙️  设置杠杆: {leverage}x")
            except Exception as e:
                logger.warning(f"⚠️  设置杠杆失败（可能已设置）: {e}")
        
        if margin_mode:
            try:
                self.client.set_margin_mode(margin_mode, self.symbol)
                logger.info(f"⚙️  设置保证金模式: {margin_mode}")
            except Exception as e:
                logger.warning(f"⚠️  设置保证金模式失败（可能已设置）: {e}")
        
        # 3. 检查现有持仓
        self._sync_positions()
        
        # 4. 启动主循环
        self.is_running = True
        self._run_loop()

    def stop(self):
        """停止交易引擎"""
        logger.info("\n🛑 停止实盘交易引擎...")
        self.is_running = False
        
        # 平掉所有持仓
        if self.current_position:
            logger.warning("⚠️ 引擎停止，强制平仓")
            self._close_position('forced_stop')

    def _run_loop(self):
        """主交易循环"""
        logger.info("🔄 进入交易循环...")
        
        while self.is_running:
            try:
                # 1. 获取最新数据
                df = self._fetch_latest_data()
                
                if df is None or len(df) < 100:
                    logger.warning("数据不足，等待下一周期")
                    time.sleep(30)
                    continue
                
                # 2. 更新持仓状态
                if self.current_position:
                    self._update_position_status(df)
                
                # 3. 检查止盈止损
                if self.current_position:
                    exit_reason = self._check_exit_conditions(df)
                    if exit_reason:
                        self._close_position(exit_reason)
                        continue
                
                # 4. 检查分批止盈
                if self.current_position and self.enable_partial_exits:
                    self._check_partial_exits(df)
                
                # 5. 检查最大回撤保护
                if self.current_position:
                    if self._check_max_drawdown():
                        self._close_position('max_drawdown')
                        continue
                
                # 6. 生成交易信号
                if not self.current_position:
                    signal = self._generate_signal(df)
                    
                    if signal == 'BUY':
                        self._open_position('LONG', df)
                    elif signal == 'SELL' and self.current_position:
                        self._close_position('signal')
                
                # 7. 检查风控限制
                if not self._check_risk_limits():
                    logger.warning("⚠️ 触发风控限制，暂停交易")
                    if self.current_position:
                        self._close_position('risk_limit')
                    time.sleep(3600)  # 暂停1小时
                    continue
                
                # 8. 打印状态
                self._log_status(df)
                
                # 9. 等待下一周期
                sleep_time = self._get_sleep_time()
                logger.debug(f"⏰ 等待 {sleep_time}s...")
                time.sleep(sleep_time)
                
            except KeyboardInterrupt:
                logger.info("\n⌨️  收到中断信号，退出...")
                self.stop()
                break
            except Exception as e:
                logger.error(f"❌ 交易循环异常: {e}", exc_info=True)
                time.sleep(60)

    def _fetch_latest_data(self) -> Optional[pd.DataFrame]:
        """获取最新K线数据"""
        try:
            # 获取足够的历史数据（至少100根K线）
            df = self.client.fetch_ohlcv(
                self.symbol,
                self.base_timeframe,
                limit=500
            )
            
            if df is None or df.empty:
                logger.warning(f"⚠️  未获取到K线数据")
                return None
            
            logger.debug(f"📊 获取数据: {len(df)} 根K线")
            return df
            
        except Exception as e:
            logger.error(f"❌ 获取数据失败: {e}")
            logger.info("💡 提示：30秒后将自动重试")
            return None

    def _generate_signal(self, df: pd.DataFrame) -> Optional[str]:
        """
        生成交易信号（与回测引擎逻辑一致）
        
        Args:
            df: K线数据
            
        Returns:
            'BUY', 'SELL' 或 None
        """
        if len(df) < max(50, self.htf_multiplier * 2):
            return None
        
        # 重采样到高时间框架
        htf_df = self._resample_htf(df)
        
        if htf_df is None or len(htf_df) < 2:
            return None
        
        # 生成基础信号
        if self.setup_type == 'Open/Close':
            ha_df = HeikinAshi.calculate(htf_df)
            signal = HeikinAshi.detect_crossover(ha_df)
        elif self.setup_type == 'Renko' and self.renko_builder and self.renko_signal_gen:
            renko_df = self.renko_builder.build(htf_df)
            signal = self.renko_signal_gen.generate_signal(renko_df)
        else:
            signal = None
        
        # 应用过滤器
        if signal and self.filter_type != 'No Filtering':
            if not self._check_filters(df):
                signal = None
        
        if signal:
            logger.info(f"🎯 信号生成: {signal}")
        
        return signal

    def _resample_htf(self, df: pd.DataFrame) -> Optional[pd.DataFrame]:
        """重采样到高时间框架"""
        try:
            df_copy = df.copy()
            df_copy = df_copy.set_index('timestamp')
            
            resample_rule = f'{self.htf_multiplier}min'
            htf_df = df_copy.resample(resample_rule).agg({
                'open': 'first',
                'high': 'max',
                'low': 'min',
                'close': 'last',
                'volume': 'sum'
            }).dropna()
            
            return htf_df
            
        except Exception as e:
            logger.error(f"❌ 重采样失败: {e}")
            return None

    def _check_filters(self, df: pd.DataFrame) -> bool:
        """检查过滤条件（与回测引擎一致）"""
        rsi = TI.rsi(df['close'], self.rsi_period)
        current_rsi = rsi.iloc[-1]
        
        rsi_filter = self.rsi_low < current_rsi < self.rsi_high
        
        atr = TI.atr(df, self.atr_filter_period)
        atr_ema = TI.ema(atr.dropna(), self.atr_filter_ma_period)
        
        atr_filter = atr.iloc[-1] < atr_ema.iloc[-1]
        
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
            sideways_atr = atr.iloc[-1] >= atr_ema.iloc[-1]
            sideways_rsi = not rsi_filter
            
            if 'or' in self.filter_type:
                return sideways_atr or sideways_rsi
            else:
                return sideways_atr and sideways_rsi
        
        return True

    def _open_position(self, direction: str, df: pd.DataFrame):
        """
        开仓
        
        Args:
            direction: 'LONG' 或 'SHORT'
            df: 当前K线数据
        """
        try:
            # 1. 获取当前价格
            current_price = df['close'].iloc[-1]
            
            # 2. 计算止盈止损
            stop_loss, take_profit, tp1_price, tp2_price = self._calculate_sl_tp(
                df, current_price, direction
            )
            
            # 3. 计算仓位大小
            balance = self.client.fetch_balance()
            usdt_balance = balance.get('USDT', {}).get('free', 0)
            position_value = usdt_balance * self.position_size_pct * self.leverage
            size = position_value / current_price
            logger.debug(f"可用余额: {usdt_balance}, 杠杆倍数：{self.leverage}, 开仓金额：{position_value}, 开仓数量：{size}")
            # 4. 执行开仓订单
            side = 'buy' if direction == 'LONG' else 'sell'
            order = self.order_manager.execute_entry(self.symbol, side, size)
            
            if not order:
                logger.error("❌ 开仓失败")
                return
            
            # 5. 记录持仓
            actual_price = order.get('average', current_price)
            actual_size = order.get('filled', size)
            
            self.current_position = LivePosition(
                entry_time=datetime.now(),
                entry_price=actual_price,
                direction=direction,
                size=actual_size,
                stop_loss=stop_loss,
                take_profit=take_profit,
                tp1_price=tp1_price,
                tp2_price=tp2_price,
                tp1_percent=self.tp1_percent,
                tp2_percent=self.tp2_percent
            )
            
            self.position_manager.open_position(direction, actual_price, actual_size)
            
            logger.info("=" * 60)
            logger.info(f"📈 开仓成功: {direction}")
            logger.info(f"   价格: {actual_price:.6f}")
            logger.info(f"   数量: {actual_size:.4f}")
            if stop_loss:
                logger.info(f"   止损: {stop_loss:.6f}")
            if take_profit:
                logger.info(f"   止盈: {take_profit:.6f}")
            if self.enable_partial_exits and tp1_price:
                logger.info(f"   TP1: {tp1_price:.6f} ({self.tp1_percent*100:.0f}%)")
                logger.info(f"   TP2: {tp2_price:.6f} ({self.tp2_percent*100:.0f}%)")
            logger.info("=" * 60)
            
        except Exception as e:
            logger.error(f"❌ 开仓异常: {e}", exc_info=True)

    def _close_position(self, reason: str):
        """
        平仓
        
        Args:
            reason: 平仓原因
        """
        try:
            if not self.current_position:
                return
            
            # 1. 获取当前价格
            ticker = self.client.get_ticker(self.symbol)
            current_price = ticker['last']
            
            # 2. 执行平仓订单
            side = 'sell' if self.current_position.direction == 'LONG' else 'buy'
            order = self.order_manager.execute_exit(
                self.symbol, 
                side, 
                self.current_position.size
            )
            
            if not order:
                logger.error("❌ 平仓失败")
                return
            
            # 3. 计算盈亏
            exit_price = order.get('average', current_price)
            
            if self.current_position.direction == 'LONG':
                pnl = (exit_price - self.current_position.entry_price) * self.current_position.size
            else:
                pnl = (self.current_position.entry_price - exit_price) * self.current_position.size
            
            pnl_pct = pnl / (self.current_position.entry_price * self.current_position.initial_size) * 100
            
            # 4. 更新统计
            self.total_trades += 1
            if pnl > 0:
                self.winning_trades += 1
            
            self.daily_pnl += pnl
            self.exit_stats[reason] = self.exit_stats.get(reason, 0) + 1
            
            # 5. 记录日志
            logger.info("=" * 60)
            logger.info(f"📉 平仓: {reason}")
            logger.info(f"   方向: {self.current_position.direction}")
            logger.info(f"   开仓价: {self.current_position.entry_price:.2f}")
            logger.info(f"   平仓价: {exit_price:.2f}")
            logger.info(f"   数量: {self.current_position.size:.4f}")
            logger.info(f"   盈亏: {pnl:.2f} USDT ({pnl_pct:+.2f}%)")
            logger.info(f"   今日盈亏: {self.daily_pnl:.2f} USDT")
            logger.info(f"   胜率: {self.winning_trades}/{self.total_trades}")
            logger.info("=" * 60)
            
            # 6. 重置持仓
            self.position_manager.close_position(exit_price, reason)
            self.current_position = None
            
        except Exception as e:
            logger.error(f"❌ 平仓异常: {e}", exc_info=True)

    def _calculate_sl_tp(
        self,
        df: pd.DataFrame,
        entry_price: float,
        direction: str
    ) -> tuple[Optional[float], Optional[float], Optional[float], Optional[float]]:
        """
        计算止盈止损
        
        Returns:
            (止损价, 止盈价, TP1价格, TP2价格)
        """
        # 计算ATR
        atr = TI.atr(df, self.atr_risk_period)
        if len(atr) == 0:
            return None, None, None, None
        
        current_atr = atr.iloc[-1]
        
        if pd.isna(current_atr):
            return None, None, None, None
        
        # 计算止盈止损
        if direction == 'LONG':
            stop_loss = entry_price - current_atr * self.stop_factor
            take_profit = entry_price + current_atr * self.profit_factor
        else:
            stop_loss = entry_price + current_atr * self.stop_factor
            take_profit = entry_price - current_atr * self.profit_factor
        
        # 计算分批止盈
        tp1_price = None
        tp2_price = None
        if self.enable_partial_exits:
            if direction == 'LONG':
                tp1_price = entry_price + current_atr * self.tp1_factor
                tp2_price = entry_price + current_atr * self.tp2_factor
            else:
                tp1_price = entry_price - current_atr * self.tp1_factor
                tp2_price = entry_price - current_atr * self.tp2_factor
        
        return stop_loss, take_profit, tp1_price, tp2_price

    def _update_position_status(self, df: pd.DataFrame):
        """更新持仓状态"""
        if not self.current_position:
            return
        
        current_price = df['close'].iloc[-1]
        
        # 更新指标
        self.current_position.update_metrics(current_price)
        
        # 更新追踪止损
        if self.tps_type == 'Trailing':
            atr = TI.atr(df, self.atr_risk_period)
            if len(atr) > 0:
                current_atr = atr.iloc[-1]
                self.current_position.update_trailing_stop(
                    current_price, 
                    current_atr, 
                    self.stop_factor
                )
        
        # 更新仓位管理器
        self.position_manager.update_pnl(current_price)

    def _check_exit_conditions(self, df: pd.DataFrame) -> Optional[str]:
        """检查退出条件"""
        if not self.current_position:
            return None
        
        current_high = df['high'].iloc[-1]
        current_low = df['low'].iloc[-1]
        
        return self.current_position.check_exit(current_high, current_low)

    def _check_partial_exits(self, df: pd.DataFrame):
        """检查分批止盈"""
        if not self.current_position:
            return
        
        current_high = df['high'].iloc[-1]
        current_low = df['low'].iloc[-1]
        
        partial_exit = self.current_position.check_partial_exits(current_high, current_low)
        
        if not partial_exit:
            return
        
        action = partial_exit['action']
        exit_price = partial_exit['price']
        
        try:
            if action == 'tp1' and not self.current_position.tp1_triggered:
                # 第一止盈
                close_size = self.current_position.initial_size * self.tp1_percent
                side = 'sell' if self.current_position.direction == 'LONG' else 'buy'
                
                order = self.order_manager.execute_exit(self.symbol, side, close_size)
                
                if order:
                    self.current_position.size -= close_size
                    self.current_position.tp1_triggered = True
                    self.exit_stats['tp1'] += 1
                    
                    logger.info(f"🎯 TP1触发: 平仓 {self.tp1_percent*100:.0f}%, 剩余 {self.current_position.size:.4f}")
            
            elif action == 'tp2' and not self.current_position.tp2_triggered:
                # 第二止盈
                close_size = self.current_position.initial_size * self.tp2_percent
                side = 'sell' if self.current_position.direction == 'LONG' else 'buy'
                
                order = self.order_manager.execute_exit(self.symbol, side, close_size)
                
                if order:
                    self.current_position.size -= close_size
                    self.current_position.tp2_triggered = True
                    self.exit_stats['tp2'] += 1
                    
                    logger.info(f"🎯 TP2触发: 平仓 {self.tp2_percent*100:.0f}%, 剩余 {self.current_position.size:.4f}")
        
        except Exception as e:
            logger.error(f"❌ 分批止盈执行失败: {e}")

    def _check_max_drawdown(self) -> bool:
        """检查最大回撤保护"""
        if not self.current_position:
            return False
        
        current_drawdown_pct = abs(self.current_position.max_drawdown * 100)
        
        if current_drawdown_pct > self.max_drawdown_percent:
            logger.warning(f"⚠️ 触发最大回撤保护: {current_drawdown_pct:.2f}% > {self.max_drawdown_percent}%")
            return True
        
        return False

    def _check_risk_limits(self) -> bool:
        """检查风控限制"""
        # 检查每日最大亏损
        if self.daily_pnl < -self.max_daily_loss:
            logger.warning(f"⚠️ 触发每日最大亏损限制: {self.daily_pnl:.2f} USDT")
            return False
        
        return True

    def _sync_positions(self):
        """同步现有持仓"""
        try:
            positions = self.client.fetch_positions(self.symbol)
            
            for pos in positions:
                contracts = float(pos.get('contracts', 0))
                if contracts > 0:
                    logger.warning(f"⚠️ 检测到现有持仓: {contracts} {self.symbol}")
                    
                    # TODO: 决定是否接管现有持仓或强制平仓
                    # 目前策略：忽略现有持仓，仅管理引擎创建的持仓
            
        except Exception as e:
            logger.error(f"❌ 同步持仓失败: {e}")

    def _log_status(self, df: pd.DataFrame):
        """打印状态信息"""
        current_price = df['close'].iloc[-1]
        current_time = datetime.now()
        
        # 每5分钟打印一次状态
        if self.last_check_time is None or (current_time - self.last_check_time).seconds >= 300:
            logger.info("-" * 60)
            logger.info(f"⏰ {current_time.strftime('%Y-%m-%d %H:%M:%S')}")
            logger.info(f"💹 {self.symbol}: {current_price:.6f}")
            
            if self.current_position:
                unrealized_pnl = self.current_position.get_unrealized_pnl(current_price)
                pnl_pct = unrealized_pnl / (self.current_position.entry_price * self.current_position.initial_size) * 100
                
                logger.info(f"📊 持仓: {self.current_position.direction}")
                logger.info(f"   开仓价: {self.current_position.entry_price:.6f}")
                logger.info(f"   数量: {self.current_position.size:.4f}")
                logger.info(f"   浮盈: {unrealized_pnl:.2f} USDT ({pnl_pct:+.2f}%)")
                logger.info(f"   最大盈利: {self.current_position.max_profit*100:.2f}%")
                logger.info(f"   最大回撤: {self.current_position.max_drawdown*100:.2f}%")
            else:
                logger.info("📊 无持仓")
            
            logger.info(f"💰 今日盈亏: {self.daily_pnl:.2f} USDT")
            logger.info(f"📈 总交易: {self.total_trades}, 胜率: {self.winning_trades}/{self.total_trades}")
            logger.info("-" * 60)
            
            self.last_check_time = current_time

    def _get_sleep_time(self) -> int:
        """
        计算等待时间（秒）
        根据时间框架动态调整
        """
        timeframe_map = {
            '1m': 30,
            '5m': 60,
            '15m': 180,
            '1h': 300
        }
        return timeframe_map.get(self.base_timeframe, 60)

    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            'total_trades': self.total_trades,
            'winning_trades': self.winning_trades,
            'win_rate': self.winning_trades / self.total_trades if self.total_trades > 0 else 0,
            'daily_pnl': self.daily_pnl,
            'exit_stats': self.exit_stats,
            'current_position': self.position_manager.get_position_info() if self.current_position else None
        }

