"""仓位管理模块"""
import pandas as pd
from typing import Dict
from ..core.data_fetcher import data_fetcher
from ..utils.config import config
from ..monitor.logger import system_logger


class PositionSizer:
    """仓位计算类"""
    
    def __init__(self):
        """初始化"""
        self.trading_config = config.get_trading_config()
        self.data_fetcher = data_fetcher
    
    def calculate_position_size(self,
                               symbol: str,
                               signal,
                               account_balance: float) -> Dict:
        """
        计算仓位大小
        
        Args:
            symbol: 交易对
            signal: 交易信号
            account_balance: 账户余额
            
        Returns:
            仓位信息
        """
        risk_per_trade = self.trading_config.get('risk_per_trade', 0.10)
        leverage_range = self.trading_config.get('leverage_range', [10, 20])
        
        entry_price = signal.entry_price
        stop_loss = signal.stop_loss
        
        # 计算止损距离百分比
        stop_distance_pct = abs(entry_price - stop_loss) / entry_price
        
        # 根据止损距离动态调整杠杆
        # 止损距离越大，杠杆越小
        if stop_distance_pct > 0.03:  # 止损超过3%
            leverage = leverage_range[0]  # 使用最小杠杆
        elif stop_distance_pct < 0.015:  # 止损小于1.5%
            leverage = leverage_range[1]  # 使用最大杠杆
        else:
            # 线性插值
            leverage = int(leverage_range[0] + 
                          (leverage_range[1] - leverage_range[0]) * 
                          (0.03 - stop_distance_pct) / 0.015)
        
        # 计算风险金额
        risk_amount = account_balance * risk_per_trade
        
        # 计算仓位大小（USDT）
        # 仓位 = 风险金额 / 止损距离百分比
        position_size_usdt = risk_amount / stop_distance_pct
        
        # 限制最大仓位（不超过账户余额 * 杠杆 * 0.8）
        max_position = account_balance * leverage * 0.8
        position_size_usdt = min(position_size_usdt, max_position)
        
        # 计算合约数量
        contracts = position_size_usdt / entry_price
        
        # 计算实际使用的保证金
        margin_required = position_size_usdt / leverage
        
        return {
            'symbol': symbol,
            'contracts': contracts,
            'position_size_usdt': position_size_usdt,
            'leverage': leverage,
            'margin_required': margin_required,
            'risk_amount': risk_amount,
            'risk_pct': risk_per_trade,
            'stop_distance_pct': stop_distance_pct,
        }
    
    def calculate(self, signal, risk_per_trade: float = None) -> Dict:
        """
        计算仓位（简化接口）
        
        Args:
            signal: 交易信号
            risk_per_trade: 单笔风险比例
            
        Returns:
            仓位信息
        """
        # 获取账户余额
        balance_info = self.data_fetcher.fetch_account_balance()
        account_balance = balance_info.get('free', 0)
        
        if account_balance <= 0:
            system_logger.error("Insufficient account balance")
            return None
        
        if risk_per_trade:
            # 临时覆盖配置
            original_risk = self.trading_config.get('risk_per_trade')
            self.trading_config['risk_per_trade'] = risk_per_trade
            result = self.calculate_position_size(signal.symbol, signal, account_balance)
            self.trading_config['risk_per_trade'] = original_risk
            return result
        
        return self.calculate_position_size(signal.symbol, signal, account_balance)


# 全局仓位计算器实例
position_sizer = PositionSizer()

