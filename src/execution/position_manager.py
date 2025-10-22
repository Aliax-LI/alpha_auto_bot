"""
仓位管理器
跟踪和管理当前持仓
"""
from typing import Optional, Dict, Any
from loguru import logger


class PositionManager:
    """仓位管理器类"""
    
    def __init__(self):
        """初始化仓位管理器"""
        self.position = None
        self.entry_price = 0.0
        self.size = 0.0
        self.remaining_size = 0.0
        self.direction = None  # 'LONG' 或 'SHORT'
        self.pnl = 0.0
        self.realized_pnl = 0.0
        
    def open_position(
        self, 
        direction: str, 
        entry_price: float, 
        size: float
    ):
        """
        开仓
        
        Args:
            direction: 'LONG' 或 'SHORT'
            entry_price: 入场价格
            size: 仓位大小
        """
        self.direction = direction
        self.entry_price = entry_price
        self.size = size
        self.remaining_size = size
        self.pnl = 0.0
        
        logger.info(
            f"📊 开仓: {direction} @ {entry_price:.2f}, 数量={size:.4f}"
        )
    
    def close_position(self, exit_price: float, reason: str = ''):
        """
        平仓
        
        Args:
            exit_price: 平仓价格
            reason: 平仓原因
        """
        if not self.has_position():
            logger.warning("无持仓，无法平仓")
            return
        
        # 计算盈亏
        if self.direction == 'LONG':
            pnl = (exit_price - self.entry_price) * self.remaining_size
        else:
            pnl = (self.entry_price - exit_price) * self.remaining_size
        
        self.realized_pnl += pnl
        
        logger.info(
            f"📊 平仓: {self.direction} @ {exit_price:.2f}, "
            f"数量={self.remaining_size:.4f}, "
            f"盈亏={pnl:.2f} USDT {reason}"
        )
        
        # 重置仓位
        self.direction = None
        self.entry_price = 0.0
        self.size = 0.0
        self.remaining_size = 0.0
        self.pnl = 0.0
    
    def reduce_position(self, size: float, exit_price: float, reason: str = ''):
        """
        减仓（部分平仓）
        
        Args:
            size: 减仓数量
            exit_price: 平仓价格
            reason: 原因
        """
        if size > self.remaining_size:
            logger.warning(f"减仓数量 {size:.4f} 超过剩余仓位 {self.remaining_size:.4f}")
            size = self.remaining_size
        
        # 计算盈亏
        if self.direction == 'LONG':
            pnl = (exit_price - self.entry_price) * size
        else:
            pnl = (self.entry_price - exit_price) * size
        
        self.realized_pnl += pnl
        self.remaining_size -= size
        
        logger.info(
            f"📊 减仓: {self.direction} @ {exit_price:.2f}, "
            f"数量={size:.4f}, 剩余={self.remaining_size:.4f}, "
            f"盈亏={pnl:.2f} USDT {reason}"
        )
        
        # 如果仓位全部平完，重置
        if self.remaining_size <= 0:
            self.close_position(exit_price, reason)
    
    def update_pnl(self, current_price: float):
        """
        更新未实现盈亏
        
        Args:
            current_price: 当前价格
        """
        if not self.has_position():
            return
        
        if self.direction == 'LONG':
            self.pnl = (current_price - self.entry_price) * self.remaining_size
        else:
            self.pnl = (self.entry_price - current_price) * self.remaining_size
    
    def has_position(self) -> bool:
        """是否有持仓"""
        return self.direction is not None and self.remaining_size > 0
    
    def is_long(self) -> bool:
        """是否持有多头"""
        return self.direction == 'LONG' and self.remaining_size > 0
    
    def is_short(self) -> bool:
        """是否持有空头"""
        return self.direction == 'SHORT' and self.remaining_size > 0
    
    def get_position_info(self) -> Dict[str, Any]:
        """
        获取仓位信息
        
        Returns:
            仓位信息字典
        """
        return {
            'direction': self.direction,
            'entry_price': self.entry_price,
            'size': self.size,
            'remaining_size': self.remaining_size,
            'unrealized_pnl': self.pnl,
            'realized_pnl': self.realized_pnl,
            'total_pnl': self.pnl + self.realized_pnl
        }

