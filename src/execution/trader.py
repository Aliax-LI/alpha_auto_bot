"""交易执行器模块"""
import time
from typing import Dict, Optional
from datetime import datetime
from ..core.order_manager import order_manager
from ..core.exchange_client import exchange_client
from ..risk.risk_manager import risk_manager
from ..risk.stop_loss import stop_loss_manager
from ..strategy.position_sizer import position_sizer
from ..utils.database import database
from ..monitor.logger import system_logger, TradingLogger


class Trader:
    """交易执行器类"""
    
    def __init__(self):
        """初始化"""
        self.order_manager = order_manager
        self.exchange = exchange_client
        self.risk_manager = risk_manager
        self.stop_manager = stop_loss_manager
        self.position_sizer = position_sizer
        self.db = database
    
    def open_position(self,
                     symbol: str,
                     signal_type: str,
                     position_info: Dict,
                     entry_price: float,
                     stop_loss: float,
                     take_profit: float) -> Optional[str]:
        """
        开仓
        
        Args:
            symbol: 交易对
            signal_type: 信号类型 (long/short)
            position_info: 仓位信息
            entry_price: 入场价
            stop_loss: 止损价
            take_profit: 止盈价
            
        Returns:
            订单ID
        """
        try:
            contracts = position_info['contracts']
            leverage = position_info['leverage']
            
            # 验证订单参数
            order_side = 'buy' if signal_type == 'long' else 'sell'
            if not self.risk_manager.validate_order(symbol, order_side, contracts, leverage):
                return None
            
            # 设置杠杆
            try:
                self.exchange.set_leverage(leverage, symbol)
                system_logger.info(f"Leverage set to {leverage}x for {symbol}")
            except Exception as e:
                system_logger.warning(f"Failed to set leverage: {e}")
            
            # 创建市价单开仓
            order = self.order_manager.create_market_order(
                symbol=symbol,
                side=order_side,
                amount=contracts,
                params={'leverage': leverage}
            )
            
            if not order:
                system_logger.error(f"Failed to create order for {symbol}")
                return None
            
            order_id = order['id']
            
            # 等待订单成交
            if not self.order_manager.wait_for_order_fill(order_id, symbol, timeout=30):
                system_logger.error(f"Order not filled: {order_id}")
                # 尝试取消订单
                self.order_manager.cancel_order(order_id, symbol)
                return None
            
            # 获取实际成交价
            final_order = self.order_manager.get_order_status(order_id, symbol)
            actual_entry = final_order.get('average', entry_price)
            
            # 初始化止损止盈管理
            self.stop_manager.initialize_position(
                order_id=order_id,
                symbol=symbol,
                side=signal_type,
                entry_price=actual_entry,
                stop_loss=stop_loss,
                take_profit=take_profit,
                amount=contracts
            )
            
            # 记录到数据库
            self.db.add_trade({
                'order_id': order_id,
                'symbol': symbol,
                'side': signal_type,
                'action': 'open',
                'entry_price': actual_entry,
                'stop_loss': stop_loss,
                'take_profit': take_profit,
                'amount': contracts,
                'leverage': leverage,
                'status': 'open',
                'open_time': datetime.now(),
            })
            
            # 记录日志
            TradingLogger.log_trade(
                symbol=symbol,
                side=signal_type,
                action='open',
                price=actual_entry,
                amount=contracts,
                order_id=order_id,
                leverage=leverage,
                stop_loss=stop_loss,
                take_profit=take_profit
            )
            
            system_logger.info(
                f"Position opened: {order_id} {symbol} {signal_type} "
                f"{contracts} @ {actual_entry} (leverage={leverage}x)"
            )
            
            return order_id
        
        except Exception as e:
            system_logger.error(f"Error opening position: {e}")
            return None
    
    def close_position(self,
                      order_id: str,
                      reason: str,
                      partial_ratio: float = 1.0) -> bool:
        """
        平仓
        
        Args:
            order_id: 订单ID
            reason: 平仓原因
            partial_ratio: 平仓比例（0-1）
            
        Returns:
            是否成功
        """
        try:
            # 从数据库获取持仓信息
            session = self.db.get_session()
            trade = session.query(database.Trade).filter_by(order_id=order_id).first()
            session.close()
            
            if not trade or trade.status != 'open':
                system_logger.warning(f"Position not found or already closed: {order_id}")
                return False
            
            # 获取持仓信息
            position = self.stop_manager.get_position(order_id)
            if not position:
                system_logger.error(f"Position not found in stop manager: {order_id}")
                return False
            
            symbol = trade.symbol
            side = trade.side
            amount = position['amount'] * partial_ratio
            
            # 获取当前价格
            ticker = self.exchange.fetch_ticker(symbol)
            current_price = ticker['last']
            
            # 平仓
            close_order = self.order_manager.close_position(
                symbol=symbol,
                side=side,
                amount=amount
            )
            
            if not close_order:
                system_logger.error(f"Failed to close position: {order_id}")
                return False
            
            # 等待成交
            if not self.order_manager.wait_for_order_fill(close_order['id'], symbol, timeout=30):
                system_logger.error(f"Close order not filled: {close_order['id']}")
                return False
            
            # 获取实际成交价
            final_order = self.order_manager.get_order_status(close_order['id'], symbol)
            exit_price = final_order.get('average', current_price)
            
            # 计算盈亏
            if side == 'long':
                pnl_pct = (exit_price - trade.entry_price) / trade.entry_price
            else:
                pnl_pct = (trade.entry_price - exit_price) / trade.entry_price
            
            pnl = pnl_pct * trade.entry_price * amount
            
            # 更新数据库
            if partial_ratio < 1.0:
                # 部分平仓，更新数量
                self.stop_manager.update_position_amount(order_id, position['amount'] * (1 - partial_ratio))
            else:
                # 全部平仓
                self.db.update_trade(order_id, {
                    'exit_price': exit_price,
                    'close_time': datetime.now(),
                    'status': 'closed',
                    'close_reason': reason,
                    'pnl': pnl,
                    'pnl_percentage': pnl_pct * 100,
                })
                
                # 移除持仓
                self.stop_manager.remove_position(order_id)
                
                # 通知风控
                self.risk_manager.on_trade_closed(pnl)
            
            # 记录日志
            TradingLogger.log_trade(
                symbol=symbol,
                side=side,
                action='close',
                price=exit_price,
                amount=amount,
                order_id=close_order['id'],
                pnl=pnl,
                reason=reason,
                partial=partial_ratio < 1.0
            )
            
            system_logger.info(
                f"Position closed: {order_id} {symbol} @ {exit_price} "
                f"PNL: {pnl:.2f} ({pnl_pct:.2%}) Reason: {reason}"
            )
            
            return True
        
        except Exception as e:
            system_logger.error(f"Error closing position: {e}")
            return False
    
    def monitor_position(self, order_id: str):
        """
        监控持仓
        
        Args:
            order_id: 订单ID
        """
        try:
            # 获取持仓信息
            position = self.stop_manager.get_position(order_id)
            if not position:
                return
            
            symbol = position['symbol']
            
            # 获取当前价格
            ticker = self.exchange.fetch_ticker(symbol)
            current_price = ticker['last']
            
            # 更新止损止盈
            self.stop_manager.update_stops(order_id, current_price)
            
            # 检查止损
            stop_check = self.stop_manager.check_stop_loss(order_id, current_price)
            if stop_check['triggered']:
                system_logger.warning(
                    f"Stop loss triggered for {order_id}: {stop_check['reason']}"
                )
                self.close_position(order_id, stop_check['reason'])
                return
            
            # 检查止盈
            profit_check = self.stop_manager.check_take_profit(order_id, current_price)
            if profit_check['triggered']:
                system_logger.info(
                    f"Take profit triggered for {order_id}: {profit_check['reason']}"
                )
                close_ratio = profit_check.get('close_ratio', 1.0)
                self.close_position(order_id, profit_check['reason'], close_ratio)
                return
        
        except Exception as e:
            system_logger.error(f"Error monitoring position {order_id}: {e}")
    
    def monitor_all_positions(self):
        """监控所有持仓"""
        positions = self.stop_manager.get_all_positions()
        
        for order_id in list(positions.keys()):
            self.monitor_position(order_id)


# 全局交易执行器实例
trader = Trader()

