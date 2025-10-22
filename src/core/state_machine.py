"""
状态机管理器
管理交易的不同状态和状态转换
"""
from enum import Enum
from typing import Optional, Dict, Any
from loguru import logger


class TradingState:
    """交易状态枚举"""
    # 无仓位
    NO_POSITION = 0.0
    
    # 多头状态
    LONG_ENTRY = 1.0      # 入场，等待TP1
    LONG_TP1_HIT = 1.1    # TP1触发，等待TP2
    LONG_TP2_HIT = 1.2    # TP2触发，等待TP3
    LONG_TP3_HIT = 1.3    # TP3触发
    
    # 空头状态
    SHORT_ENTRY = -1.0    # 入场，等待TP1
    SHORT_TP1_HIT = -1.1  # TP1触发，等待TP2
    SHORT_TP2_HIT = -1.2  # TP2触发，等待TP3
    SHORT_TP3_HIT = -1.3  # TP3触发


class StateMachine:
    """交易状态机"""
    
    def __init__(self):
        """初始化状态机"""
        self.state = TradingState.NO_POSITION
        self.entry_price = 0.0
        self.position_size = 0.0
        self.remaining_size = 0.0
        self.tp_levels = {}
        self.sl_level = 0.0
        
    def reset(self):
        """重置状态机"""
        self.state = TradingState.NO_POSITION
        self.entry_price = 0.0
        self.position_size = 0.0
        self.remaining_size = 0.0
        self.tp_levels = {}
        self.sl_level = 0.0
        logger.info("🔄 状态机已重置")
    
    def enter_long(self, entry_price: float, size: float, tp_sl_levels: Dict[str, float]):
        """
        进入多头仓位
        
        Args:
            entry_price: 入场价格
            size: 仓位大小
            tp_sl_levels: 止盈止损价格字典 {'tp1', 'tp2', 'tp3', 'sl'}
        """
        self.state = TradingState.LONG_ENTRY
        self.entry_price = entry_price
        self.position_size = size
        self.remaining_size = size
        self.tp_levels = tp_sl_levels
        self.sl_level = tp_sl_levels.get('sl', 0.0)
        
        logger.info(
            f"📈 进入多头: 价格={entry_price:.2f}, 数量={size:.4f}, "
            f"TP1={tp_sl_levels.get('tp1', 0):.2f}, "
            f"SL={self.sl_level:.2f}"
        )
    
    def enter_short(self, entry_price: float, size: float, tp_sl_levels: Dict[str, float]):
        """
        进入空头仓位
        
        Args:
            entry_price: 入场价格
            size: 仓位大小
            tp_sl_levels: 止盈止损价格字典
        """
        self.state = TradingState.SHORT_ENTRY
        self.entry_price = entry_price
        self.position_size = size
        self.remaining_size = size
        self.tp_levels = tp_sl_levels
        self.sl_level = tp_sl_levels.get('sl', 0.0)
        
        logger.info(
            f"📉 进入空头: 价格={entry_price:.2f}, 数量={size:.4f}, "
            f"TP1={tp_sl_levels.get('tp1', 0):.2f}, "
            f"SL={self.sl_level:.2f}"
        )
    
    def update_state(self, new_state: float):
        """
        更新状态
        
        Args:
            new_state: 新状态值
        """
        old_state = self.state
        self.state = new_state
        logger.info(f"🔄 状态变更: {old_state} -> {new_state}")
    
    def reduce_position(self, size: float, tp_level: str):
        """
        减少仓位（部分止盈）
        
        Args:
            size: 减少的数量
            tp_level: 触发的止盈级别
        """
        self.remaining_size -= size
        logger.info(
            f"💰 部分止盈 {tp_level}: 平仓 {size:.4f}, "
            f"剩余 {self.remaining_size:.4f}"
        )
    
    def is_long(self) -> bool:
        """是否持有多头仓位"""
        return self.state > 0
    
    def is_short(self) -> bool:
        """是否持有空头仓位"""
        return self.state < 0
    
    def has_position(self) -> bool:
        """是否有持仓"""
        return self.state != TradingState.NO_POSITION
    
    def get_state_description(self) -> str:
        """获取状态描述"""
        state_map = {
            TradingState.NO_POSITION: "无仓位",
            TradingState.LONG_ENTRY: "多头入场",
            TradingState.LONG_TP1_HIT: "多头TP1",
            TradingState.LONG_TP2_HIT: "多头TP2",
            TradingState.LONG_TP3_HIT: "多头TP3",
            TradingState.SHORT_ENTRY: "空头入场",
            TradingState.SHORT_TP1_HIT: "空头TP1",
            TradingState.SHORT_TP2_HIT: "空头TP2",
            TradingState.SHORT_TP3_HIT: "空头TP3",
        }
        return state_map.get(self.state, f"未知状态({self.state})")

