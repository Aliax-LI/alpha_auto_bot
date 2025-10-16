"""止盈止损管理模块"""
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, Optional
from ..utils.config import config
from ..monitor.logger import system_logger


class StopLossManager:
    """止盈止损管理类"""
    
    def __init__(self):
        """初始化"""
        self.risk_config = config.get_risk_config()
        self.positions = {}  # 持仓信息缓存
    
    def initialize_position(self, 
                          order_id: str,
                          symbol: str,
                          side: str,
                          entry_price: float,
                          stop_loss: float,
                          take_profit: float,
                          amount: float):
        """
        初始化持仓止损止盈
        
        Args:
            order_id: 订单ID
            symbol: 交易对
            side: 方向
            entry_price: 入场价
            stop_loss: 止损价
            take_profit: 止盈价
            amount: 数量
        """
        self.positions[order_id] = {
            'order_id': order_id,
            'symbol': symbol,
            'side': side,
            'entry_price': entry_price,
            'entry_time': datetime.now(),
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'amount': amount,
            'initial_amount': amount,
            'highest_price': entry_price if side == 'long' else entry_price,
            'lowest_price': entry_price if side == 'short' else entry_price,
            'trailing_stop_active': False,
        }
        
        system_logger.info(
            f"Position initialized: {order_id} {symbol} {side} "
            f"entry={entry_price} sl={stop_loss} tp={take_profit}"
        )
    
    def update_stops(self, order_id: str, current_price: float) -> Dict:
        """
        更新止损止盈
        
        Args:
            order_id: 订单ID
            current_price: 当前价格
            
        Returns:
            更新后的止损止盈
        """
        if order_id not in self.positions:
            return {}
        
        position = self.positions[order_id]
        side = position['side']
        entry_price = position['entry_price']
        
        # 更新最高价/最低价
        if side == 'long':
            position['highest_price'] = max(position['highest_price'], current_price)
        else:
            position['lowest_price'] = min(position['lowest_price'], current_price)
        
        # 计算盈亏百分比
        if side == 'long':
            pnl_pct = (current_price - entry_price) / entry_price
        else:
            pnl_pct = (entry_price - current_price) / entry_price
        
        # 移动止损逻辑
        if pnl_pct > 0 and not position['trailing_stop_active']:
            # 盈利后，移动止损到入场价（保本）
            if side == 'long':
                position['stop_loss'] = max(position['stop_loss'], entry_price)
            else:
                position['stop_loss'] = min(position['stop_loss'], entry_price)
            
            position['trailing_stop_active'] = True
            system_logger.info(f"Trailing stop activated for {order_id}")
        
        # 每涨1%，止损上移0.5%
        if position['trailing_stop_active']:
            if side == 'long':
                # 根据最高价计算应该的止损位
                target_stop = entry_price + (position['highest_price'] - entry_price) * 0.5
                position['stop_loss'] = max(position['stop_loss'], target_stop)
            else:
                # 做空：根据最低价计算
                target_stop = entry_price - (entry_price - position['lowest_price']) * 0.5
                position['stop_loss'] = min(position['stop_loss'], target_stop)
        
        return {
            'stop_loss': position['stop_loss'],
            'take_profit': position['take_profit'],
            'trailing_active': position['trailing_stop_active'],
        }
    
    def check_stop_loss(self, order_id: str, current_price: float) -> Dict:
        """
        检查是否触发止损
        
        Args:
            order_id: 订单ID
            current_price: 当前价格
            
        Returns:
            止损检查结果
        """
        if order_id not in self.positions:
            return {'triggered': False}
        
        position = self.positions[order_id]
        side = position['side']
        stop_loss = position['stop_loss']
        entry_price = position['entry_price']
        entry_time = position['entry_time']
        
        # 1. 固定止损/技术止损
        if side == 'long' and current_price <= stop_loss:
            return {
                'triggered': True,
                'reason': 'stop_loss',
                'price': current_price,
                'stop_price': stop_loss,
            }
        elif side == 'short' and current_price >= stop_loss:
            return {
                'triggered': True,
                'reason': 'stop_loss',
                'price': current_price,
                'stop_price': stop_loss,
            }
        
        # 2. 时间止损（持仓超过4小时无盈利）
        time_stop_hours = self.risk_config.get('time_stop_hours', 4)
        elapsed_hours = (datetime.now() - entry_time).total_seconds() / 3600
        
        if elapsed_hours >= time_stop_hours:
            if side == 'long':
                pnl_pct = (current_price - entry_price) / entry_price
            else:
                pnl_pct = (entry_price - current_price) / entry_price
            
            if pnl_pct <= 0:
                return {
                    'triggered': True,
                    'reason': 'time_stop',
                    'price': current_price,
                    'elapsed_hours': elapsed_hours,
                }
        
        # 3. 突发止损（瞬间逆向突破3%）
        emergency_stop = self.risk_config.get('emergency_stop_loss', 0.03)
        if side == 'long':
            loss_pct = (entry_price - current_price) / entry_price
        else:
            loss_pct = (current_price - entry_price) / entry_price
        
        if loss_pct >= emergency_stop:
            return {
                'triggered': True,
                'reason': 'emergency_stop',
                'price': current_price,
                'loss_pct': loss_pct,
            }
        
        return {'triggered': False}
    
    def check_take_profit(self, order_id: str, current_price: float) -> Dict:
        """
        检查是否触发止盈
        
        Args:
            order_id: 订单ID
            current_price: 当前价格
            
        Returns:
            止盈检查结果
        """
        if order_id not in self.positions:
            return {'triggered': False}
        
        position = self.positions[order_id]
        side = position['side']
        entry_price = position['entry_price']
        take_profit = position['take_profit']
        
        # 计算盈利百分比
        if side == 'long':
            profit_pct = (current_price - entry_price) / entry_price
        else:
            profit_pct = (entry_price - current_price) / entry_price
        
        # 分批止盈
        partial_tp = self.risk_config.get('partial_take_profit', [0.03, 0.06])
        current_amount = position['amount']
        initial_amount = position['initial_amount']
        
        # 第一次止盈（3%）
        if profit_pct >= partial_tp[0] and current_amount == initial_amount:
            return {
                'triggered': True,
                'reason': 'partial_profit_1',
                'price': current_price,
                'profit_pct': profit_pct,
                'close_ratio': 0.5,  # 平仓50%
            }
        
        # 第二次止盈（6%）或到达目标止盈
        if profit_pct >= partial_tp[1] or (
            side == 'long' and current_price >= take_profit
        ) or (
            side == 'short' and current_price <= take_profit
        ):
            return {
                'triggered': True,
                'reason': 'take_profit',
                'price': current_price,
                'profit_pct': profit_pct,
                'close_ratio': 1.0,  # 全部平仓
            }
        
        return {'triggered': False}
    
    def update_position_amount(self, order_id: str, new_amount: float):
        """
        更新持仓数量（分批平仓后）
        
        Args:
            order_id: 订单ID
            new_amount: 新数量
        """
        if order_id in self.positions:
            self.positions[order_id]['amount'] = new_amount
            system_logger.info(f"Position amount updated: {order_id} amount={new_amount}")
    
    def remove_position(self, order_id: str):
        """
        移除持仓
        
        Args:
            order_id: 订单ID
        """
        if order_id in self.positions:
            del self.positions[order_id]
            system_logger.info(f"Position removed: {order_id}")
    
    def get_position(self, order_id: str) -> Optional[Dict]:
        """
        获取持仓信息
        
        Args:
            order_id: 订单ID
            
        Returns:
            持仓信息
        """
        return self.positions.get(order_id)
    
    def get_all_positions(self) -> Dict:
        """
        获取所有持仓
        
        Returns:
            所有持仓字典
        """
        return self.positions.copy()


# 全局止损管理器实例
stop_loss_manager = StopLossManager()

