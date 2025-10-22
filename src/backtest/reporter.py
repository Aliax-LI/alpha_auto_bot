"""
回测报告生成器
"""
import pandas as pd
from typing import Dict, Any
from loguru import logger


class BacktestReporter:
    """回测报告生成器"""
    
    @staticmethod
    def print_results(results: Dict[str, Any], config: Dict[str, Any]):
        """打印回测结果"""
        
        logger.info("\n" + "=" * 80)
        logger.info("                           回测结果报告")
        logger.info("=" * 80)
        
        # 策略配置
        logger.info("\n📋 策略配置")
        logger.info("-" * 80)
        logger.info(f"  信号模式:       {config.get('setup_type', 'N/A')}")
        logger.info(f"  过滤类型:       {config.get('filter_type', 'N/A')}")
        logger.info(f"  止盈止损模式:   {config.get('tps_type', 'N/A')}")
        logger.info(f"  初始资金:       ${results['initial_capital']:,.2f}")
        logger.info(f"  仓位大小:       {config.get('position_size', 0.95)*100:.0f}%")
        
        # 总体表现
        logger.info("\n💰 总体表现")
        logger.info("-" * 80)
        logger.info(f"  最终资金:       ${results['final_capital']:,.2f}")
        logger.info(f"  总收益:         ${results['final_capital'] - results['initial_capital']:,.2f}")
        logger.info(f"  总收益率:       {results['total_return_pct']:+.2f}%")
        logger.info(f"  最大回撤:       {results['max_drawdown_pct']:.2f}%")
        logger.info(f"  夏普比率:       {results['sharpe_ratio']:.2f}")
        
        # 交易统计
        logger.info("\n📊 交易统计")
        logger.info("-" * 80)
        logger.info(f"  总交易次数:     {results['total_trades']}")
        logger.info(f"  盈利交易:       {results['winning_trades']}")
        logger.info(f"  亏损交易:       {results['losing_trades']}")
        logger.info(f"  胜率:           {results['win_rate']*100:.2f}%")
        logger.info(f"  平均盈利:       ${results['avg_win']:,.2f}")
        logger.info(f"  平均亏损:       ${results['avg_loss']:,.2f}")
        logger.info(f"  盈亏比:         {results['profit_factor']:.2f}")
        logger.info(f"  平均持仓时间:   {results['avg_duration_hours']:.1f} 小时")
        
        # 止盈止损统计
        if results.get('exit_stats'):
            logger.info("\n🎯 退出原因统计")
            logger.info("-" * 80)
            logger.info(f"  信号退出:       {results.get('exit_by_signal', 0)} 次")
            logger.info(f"  止损退出:       {results.get('exit_by_stop_loss', 0)} 次")
            logger.info(f"  止盈退出:       {results.get('exit_by_take_profit', 0)} 次")
            logger.info(f"  追踪止损退出:   {results.get('exit_by_trailing_stop', 0)} 次")
            logger.info(f"  最大回撤平仓:   {results.get('exit_by_max_drawdown', 0)} 次 ⚠️")
            
            # 分批止盈统计
            tp1_count = results.get('exit_by_tp1', 0)
            tp2_count = results.get('exit_by_tp2', 0)
            if tp1_count > 0 or tp2_count > 0:
                logger.info(f"\n📈 分批止盈统计")
                logger.info("-" * 80)
                logger.info(f"  TP1触发次数:    {tp1_count} 次")
                logger.info(f"  TP2触发次数:    {tp2_count} 次")
        
        # 详细交易记录（前10笔和后10笔）
        if results['trades']:
            logger.info("\n📝 交易记录（前 10 笔）")
            logger.info("-" * 80)
            BacktestReporter._print_trades(results['trades'][:10])
            
            if len(results['trades']) > 20:
                logger.info("\n📝 交易记录（后 10 笔）")
                logger.info("-" * 80)
                BacktestReporter._print_trades(results['trades'][-10:])
        
        logger.info("\n" + "=" * 80)
    
    @staticmethod
    def _print_trades(trades, max_display=10):
        """打印交易记录"""
        for i, trade in enumerate(trades[:max_display], 1):
            direction_emoji = "📈" if trade.direction == "LONG" else "📉"
            pnl_emoji = "✅" if trade.pnl > 0 else "❌"
            
            # 退出原因标识
            exit_reason_map = {
                'signal': '📊',
                'stop_loss': '🛑',
                'take_profit': '🎯',
                'trailing_stop': '📉',
                'max_drawdown': '⚠️'
            }
            exit_emoji = exit_reason_map.get(trade.exit_reason, '❓')
            
            logger.info(f"{direction_emoji} #{i:3d} | "
                       f"入场: {trade.entry_time.strftime('%Y-%m-%d %H:%M')} @ {trade.entry_price:8.2f} | "
                       f"出场: {trade.exit_time.strftime('%Y-%m-%d %H:%M')} @ {trade.exit_price:8.2f} | "
                       f"{pnl_emoji} PnL: {trade.pnl_pct*100:+6.2f}% {exit_emoji}")
    
    @staticmethod
    def save_to_csv(results: Dict[str, Any], filename: str = "backtest_results.csv"):
        """保存交易记录到 CSV"""
        if not results['trades']:
            logger.warning("没有交易记录可保存")
            return
        
        trades_data = []
        for trade in results['trades']:
            # 基础信息
            trade_info = {
                'entry_time': trade.entry_time,
                'entry_price': trade.entry_price,
                'exit_time': trade.exit_time,
                'exit_price': trade.exit_price,
                'exit_reason': trade.exit_reason,
                'direction': trade.direction,
                'initial_size': trade.initial_size,
                'remaining_size': trade.size,
                'closed_size': trade.closed_size,
                # 止盈止损
                'stop_loss': trade.stop_loss,
                'take_profit': trade.take_profit,
                'tp1_price': trade.tp1_price,
                'tp2_price': trade.tp2_price,
                'tp1_triggered': trade.tp1_triggered,
                'tp2_triggered': trade.tp2_triggered,
                # 盈亏信息
                'pnl': trade.pnl,
                'pnl_pct': trade.pnl_pct * 100,
                'max_profit_pct': trade.max_profit * 100,
                'max_drawdown_pct': trade.max_drawdown * 100,
            }
            
            # 添加分批平仓详情
            if hasattr(trade, 'partial_exits') and trade.partial_exits:
                for i, partial in enumerate(trade.partial_exits, 1):
                    trade_info[f'partial_{i}_time'] = partial['time']
                    trade_info[f'partial_{i}_price'] = partial['price']
                    trade_info[f'partial_{i}_size'] = partial['size']
                    trade_info[f'partial_{i}_percent'] = partial['percent'] * 100
                    trade_info[f'partial_{i}_pnl'] = partial['pnl']
                    trade_info[f'partial_{i}_reason'] = partial['reason']
            
            trades_data.append(trade_info)
        
        df = pd.DataFrame(trades_data)
        df.to_csv(filename, index=False)
        logger.info(f"✅ 交易记录已保存到: {filename}")
    
    @staticmethod
    def save_equity_curve(results: Dict[str, Any], filename: str = "equity_curve.csv"):
        """保存权益曲线到 CSV"""
        if results['equity_curve'].empty:
            logger.warning("没有权益曲线数据可保存")
            return
        
        results['equity_curve'].to_csv(filename, index=False)
        logger.info(f"✅ 权益曲线已保存到: {filename}")
    
    @staticmethod
    def generate_summary(results: Dict[str, Any]) -> Dict[str, Any]:
        """生成摘要统计"""
        return {
            '总收益率': f"{results['total_return_pct']:.2f}%",
            '胜率': f"{results['win_rate']*100:.2f}%",
            '总交易次数': results['total_trades'],
            '盈亏比': f"{results['profit_factor']:.2f}",
            '最大回撤': f"{results['max_drawdown_pct']:.2f}%",
            '夏普比率': f"{results['sharpe_ratio']:.2f}",
        }

