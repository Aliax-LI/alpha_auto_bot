"""风险管理模块"""
from datetime import datetime, timedelta
from typing import Dict, List
from ..utils.config import config
from ..utils.database import database
from ..monitor.logger import system_logger, TradingLogger


class RiskManager:
    """风险管理类"""
    
    def __init__(self):
        """初始化"""
        self.risk_config = config.get_risk_config()
        self.trading_config = config.get_trading_config()
        self.db = database
        
        # 状态跟踪
        self.consecutive_losses = 0
        self.trading_paused = False
        self.pause_until = None
        self.position_size_multiplier = 1.0
    
    def can_open_position(self) -> bool:
        """
        检查是否可以开仓
        
        Returns:
            是否允许开仓
        """
        # 1. 检查是否暂停交易
        if self.trading_paused:
            if self.pause_until and datetime.now() < self.pause_until:
                remaining = (self.pause_until - datetime.now()).total_seconds() / 3600
                system_logger.warning(f"Trading paused. Resume in {remaining:.1f} hours")
                return False
            else:
                # 暂停期结束，恢复交易
                self.trading_paused = False
                self.pause_until = None
                system_logger.info("Trading pause ended. Resuming trading.")
        
        # 2. 检查持仓数量
        open_trades = self.db.get_open_trades()
        max_positions = self.trading_config.get('max_positions', 3)
        
        if len(open_trades) >= max_positions:
            system_logger.warning(f"Maximum positions reached: {len(open_trades)}/{max_positions}")
            return False
        
        # 3. 检查日内亏损限制
        if not self.check_daily_loss_limit():
            return False
        
        # 4. 检查周亏损限制
        if not self.check_weekly_loss_limit():
            return False
        
        return True
    
    def check_daily_loss_limit(self) -> bool:
        """
        检查日内亏损限制
        
        Returns:
            是否在限制内
        """
        daily_max_loss = self.risk_config.get('daily_max_loss', 0.20)
        
        # 获取今日交易
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_trades = self.db.get_trades_by_date(today_start)
        
        # 计算今日盈亏
        total_pnl = sum(t.pnl for t in today_trades if t.pnl is not None)
        
        # 获取账户余额（简化处理，实际应该用起始余额）
        from ..core.data_fetcher import data_fetcher
        balance_info = data_fetcher.fetch_account_balance()
        account_balance = balance_info.get('total', 0)
        
        if account_balance <= 0:
            return False
        
        loss_pct = abs(total_pnl) / account_balance if total_pnl < 0 else 0
        
        if loss_pct >= daily_max_loss:
            TradingLogger.log_risk_alert(
                'daily_loss_limit',
                f'Daily loss limit reached: {loss_pct:.2%}',
                total_loss=total_pnl,
                limit=daily_max_loss
            )
            self.pause_trading(24)  # 暂停24小时
            return False
        
        return True
    
    def check_weekly_loss_limit(self) -> bool:
        """
        检查周亏损限制
        
        Returns:
            是否在限制内
        """
        weekly_max_loss = self.risk_config.get('weekly_max_loss', 0.35)
        
        # 获取本周交易
        week_start = datetime.now() - timedelta(days=datetime.now().weekday())
        week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
        week_trades = self.db.get_trades_by_date(week_start)
        
        # 计算本周盈亏
        total_pnl = sum(t.pnl for t in week_trades if t.pnl is not None)
        
        # 获取账户余额
        from ..core.data_fetcher import data_fetcher
        balance_info = data_fetcher.fetch_account_balance()
        account_balance = balance_info.get('total', 0)
        
        if account_balance <= 0:
            return False
        
        loss_pct = abs(total_pnl) / account_balance if total_pnl < 0 else 0
        
        if loss_pct >= weekly_max_loss:
            TradingLogger.log_risk_alert(
                'weekly_loss_limit',
                f'Weekly loss limit reached: {loss_pct:.2%}',
                total_loss=total_pnl,
                limit=weekly_max_loss
            )
            self.pause_trading(72)  # 暂停3天
            return False
        
        return True
    
    def on_trade_closed(self, trade_pnl: float):
        """
        交易结束后的风控处理
        
        Args:
            trade_pnl: 交易盈亏
        """
        if trade_pnl < 0:
            # 连续亏损计数
            self.consecutive_losses += 1
            
            consecutive_limit = self.risk_config.get('consecutive_loss_limit', 3)
            
            # 连续3次止损，降低仓位
            if self.consecutive_losses >= consecutive_limit:
                self.position_size_multiplier = 0.5
                TradingLogger.log_risk_alert(
                    'consecutive_losses',
                    f'Consecutive losses: {self.consecutive_losses}. Reducing position size to 50%',
                    consecutive_losses=self.consecutive_losses
                )
            
            # 连续5次止损，暂停交易
            if self.consecutive_losses >= 5:
                self.pause_trading(24)
                TradingLogger.log_risk_alert(
                    'consecutive_losses_pause',
                    f'Consecutive losses: {self.consecutive_losses}. Pausing trading for 24 hours',
                    consecutive_losses=self.consecutive_losses
                )
        else:
            # 盈利则重置计数
            if self.consecutive_losses > 0:
                system_logger.info(f"Profitable trade. Resetting consecutive losses from {self.consecutive_losses}")
                self.consecutive_losses = 0
                self.position_size_multiplier = 1.0
    
    def pause_trading(self, hours: int):
        """
        暂停交易
        
        Args:
            hours: 暂停小时数
        """
        self.trading_paused = True
        self.pause_until = datetime.now() + timedelta(hours=hours)
        system_logger.warning(f"Trading paused for {hours} hours until {self.pause_until}")
    
    def check_drawdown(self) -> Dict:
        """
        检查回撤
        
        Returns:
            回撤信息
        """
        # 获取所有历史交易
        all_trades = self.db.get_trades_by_date(datetime.now() - timedelta(days=90))
        
        if not all_trades:
            return {'max_drawdown': 0, 'current_drawdown': 0}
        
        # 计算权益曲线
        equity_curve = []
        cumulative_pnl = 0
        
        for trade in all_trades:
            if trade.pnl:
                cumulative_pnl += trade.pnl
                equity_curve.append(cumulative_pnl)
        
        if not equity_curve:
            return {'max_drawdown': 0, 'current_drawdown': 0}
        
        # 计算最大回撤
        peak = equity_curve[0]
        max_drawdown = 0
        
        for equity in equity_curve:
            if equity > peak:
                peak = equity
            drawdown = (peak - equity) / peak if peak > 0 else 0
            max_drawdown = max(max_drawdown, drawdown)
        
        # 当前回撤
        current_peak = max(equity_curve)
        current_equity = equity_curve[-1]
        current_drawdown = (current_peak - current_equity) / current_peak if current_peak > 0 else 0
        
        # 检查回撤告警
        max_dd_alert = self.risk_config.get('max_drawdown_alert', 0.30)
        if current_drawdown >= max_dd_alert:
            TradingLogger.log_risk_alert(
                'max_drawdown',
                f'Drawdown alert: {current_drawdown:.2%}',
                current_drawdown=current_drawdown,
                threshold=max_dd_alert
            )
        
        return {
            'max_drawdown': max_drawdown,
            'current_drawdown': current_drawdown,
        }
    
    def get_position_size_multiplier(self) -> float:
        """
        获取仓位倍数
        
        Returns:
            仓位倍数
        """
        return self.position_size_multiplier
    
    def validate_order(self, symbol: str, side: str, amount: float, leverage: int) -> bool:
        """
        验证订单参数
        
        Args:
            symbol: 交易对
            side: 方向
            amount: 数量
            leverage: 杠杆
            
        Returns:
            是否合法
        """
        # 检查杠杆
        max_leverage = self.trading_config.get('leverage_range', [10, 20])[1]
        if leverage > max_leverage:
            system_logger.error(f"Leverage {leverage} exceeds maximum {max_leverage}")
            return False
        
        # 检查数量
        if amount <= 0:
            system_logger.error(f"Invalid amount: {amount}")
            return False
        
        return True


# 全局风控管理器实例
risk_manager = RiskManager()

