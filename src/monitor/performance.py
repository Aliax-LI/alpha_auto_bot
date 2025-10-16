"""绩效监控模块"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List
from pathlib import Path
from ..utils.database import database
from ..utils.config import config
from ..monitor.logger import system_logger


class PerformanceMonitor:
    """绩效监控类"""
    
    def __init__(self):
        """初始化"""
        self.db = database
        self.config = config
    
    def calculate_metrics(self, trades: List) -> Dict:
        """
        计算绩效指标
        
        Args:
            trades: 交易列表
            
        Returns:
            绩效指标字典
        """
        if not trades:
            return {
                'total_trades': 0,
                'win_rate': 0,
                'profit_factor': 0,
                'total_pnl': 0,
            }
        
        # 总交易次数
        total_trades = len(trades)
        
        # 盈利和亏损交易
        profitable_trades = [t for t in trades if t.pnl and t.pnl > 0]
        losing_trades = [t for t in trades if t.pnl and t.pnl < 0]
        
        # 胜率
        win_rate = len(profitable_trades) / total_trades if total_trades > 0 else 0
        
        # 总盈亏
        total_profit = sum(t.pnl for t in profitable_trades)
        total_loss = abs(sum(t.pnl for t in losing_trades))
        total_pnl = sum(t.pnl for t in trades if t.pnl)
        
        # 盈亏比
        profit_factor = total_profit / total_loss if total_loss > 0 else 0
        
        # 平均盈利/亏损
        avg_profit = total_profit / len(profitable_trades) if profitable_trades else 0
        avg_loss = total_loss / len(losing_trades) if losing_trades else 0
        
        # 最大单笔盈利/亏损
        max_profit = max((t.pnl for t in trades if t.pnl), default=0)
        max_loss = min((t.pnl for t in trades if t.pnl), default=0)
        
        # 总手续费
        total_fee = sum(t.fee for t in trades if t.fee)
        
        # 平均持仓时间
        durations = []
        for t in trades:
            if t.open_time and t.close_time:
                duration = (t.close_time - t.open_time).total_seconds() / 3600
                durations.append(duration)
        avg_duration = np.mean(durations) if durations else 0
        
        return {
            'total_trades': total_trades,
            'profitable_trades': len(profitable_trades),
            'losing_trades': len(losing_trades),
            'win_rate': win_rate,
            'profit_factor': profit_factor,
            'total_pnl': total_pnl,
            'total_profit': total_profit,
            'total_loss': total_loss,
            'avg_profit': avg_profit,
            'avg_loss': avg_loss,
            'max_profit': max_profit,
            'max_loss': max_loss,
            'total_fee': total_fee,
            'avg_duration_hours': avg_duration,
        }
    
    def calculate_coin_performance(self, trades: List) -> Dict[str, Dict]:
        """
        计算各币种表现
        
        Args:
            trades: 交易列表
            
        Returns:
            各币种绩效字典
        """
        coin_trades = {}
        
        for trade in trades:
            if trade.symbol not in coin_trades:
                coin_trades[trade.symbol] = []
            coin_trades[trade.symbol].append(trade)
        
        coin_performance = {}
        for symbol, symbol_trades in coin_trades.items():
            coin_performance[symbol] = self.calculate_metrics(symbol_trades)
        
        return coin_performance
    
    def generate_daily_report(self, date: datetime = None) -> str:
        """
        生成日终复盘报告
        
        Args:
            date: 日期，默认为今天
            
        Returns:
            报告文本
        """
        if date is None:
            date = datetime.now()
        
        # 获取当日交易
        day_start = date.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)
        trades = self.db.get_trades_by_date(day_start, day_end)
        
        # 计算指标
        metrics = self.calculate_metrics(trades)
        coin_performance = self.calculate_coin_performance(trades)
        
        # 生成报告
        report_lines = []
        report_lines.append("=" * 80)
        report_lines.append(f"Daily Trading Report - {date.strftime('%Y-%m-%d')}")
        report_lines.append("=" * 80)
        report_lines.append("")
        
        # 1. 交易概览
        report_lines.append("### Trading Overview ###")
        report_lines.append(f"Total Trades: {metrics['total_trades']}")
        report_lines.append(f"Profitable: {metrics['profitable_trades']} | Losing: {metrics['losing_trades']}")
        report_lines.append(f"Win Rate: {metrics['win_rate']:.2%}")
        report_lines.append(f"Profit Factor: {metrics['profit_factor']:.2f}")
        report_lines.append(f"Total P&L: {metrics['total_pnl']:.2f} USDT")
        report_lines.append(f"Total Profit: {metrics['total_profit']:.2f} USDT")
        report_lines.append(f"Total Loss: {metrics['total_loss']:.2f} USDT")
        report_lines.append(f"Total Fees: {metrics['total_fee']:.2f} USDT")
        report_lines.append(f"Max Profit: {metrics['max_profit']:.2f} USDT")
        report_lines.append(f"Max Loss: {metrics['max_loss']:.2f} USDT")
        report_lines.append(f"Avg Duration: {metrics['avg_duration_hours']:.1f} hours")
        report_lines.append("")
        
        # 2. 币种表现
        if coin_performance:
            report_lines.append("### Performance by Symbol ###")
            for symbol, perf in sorted(coin_performance.items(), key=lambda x: x[1]['total_pnl'], reverse=True):
                report_lines.append(f"{symbol}:")
                report_lines.append(f"  Trades: {perf['total_trades']}, Win Rate: {perf['win_rate']:.2%}, P&L: {perf['total_pnl']:.2f}")
            report_lines.append("")
        
        # 3. 风控统计
        report_lines.append("### Risk Management ###")
        from ..risk.risk_manager import risk_manager
        drawdown_info = risk_manager.check_drawdown()
        report_lines.append(f"Max Drawdown: {drawdown_info['max_drawdown']:.2%}")
        report_lines.append(f"Current Drawdown: {drawdown_info['current_drawdown']:.2%}")
        report_lines.append(f"Consecutive Losses: {risk_manager.consecutive_losses}")
        report_lines.append(f"Position Size Multiplier: {risk_manager.position_size_multiplier:.0%}")
        report_lines.append("")
        
        # 4. 信号统计
        report_lines.append("### Signal Performance ###")
        # 获取信号数据
        session = self.db.get_session()
        signals = session.query(database.Signal).filter(
            database.Signal.created_at >= day_start,
            database.Signal.created_at < day_end
        ).all()
        session.close()
        
        total_signals = len(signals)
        executed_signals = len([s for s in signals if s.executed])
        
        report_lines.append(f"Total Signals: {total_signals}")
        report_lines.append(f"Executed: {executed_signals}")
        report_lines.append(f"Execution Rate: {executed_signals/total_signals:.2%}" if total_signals > 0 else "Execution Rate: N/A")
        report_lines.append("")
        
        # 5. 优化建议
        report_lines.append("### Suggestions ###")
        if metrics['win_rate'] < 0.4:
            report_lines.append("- Win rate is low. Consider tightening entry criteria.")
        if metrics['profit_factor'] < 1.5:
            report_lines.append("- Profit factor is low. Review risk/reward ratio.")
        if drawdown_info['current_drawdown'] > 0.15:
            report_lines.append("- Current drawdown is high. Consider reducing position size.")
        if risk_manager.consecutive_losses >= 2:
            report_lines.append("- Consecutive losses detected. Review recent trades for patterns.")
        
        report_lines.append("")
        report_lines.append("=" * 80)
        
        report_text = "\n".join(report_lines)
        
        # 保存报告
        root_dir = Path(__file__).parent.parent.parent
        report_dir = root_dir / "reports"
        report_dir.mkdir(exist_ok=True)
        
        report_file = report_dir / f"daily_report_{date.strftime('%Y%m%d')}.txt"
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report_text)
        
        system_logger.info(f"Daily report saved to {report_file}")
        print(report_text)
        
        return report_text


# 全局绩效监控实例
performance_monitor = PerformanceMonitor()

