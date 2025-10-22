"""
实盘交易引擎测试
验证核心功能是否正常工作
"""
import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

from src.core.live_trading_engine import LiveTradingEngine, LivePosition


class TestLivePosition:
    """测试LivePosition类"""
    
    def test_position_initialization(self):
        """测试持仓初始化"""
        pos = LivePosition(
            entry_time=datetime.now(),
            entry_price=42000.0,
            direction='LONG',
            size=0.1,
            stop_loss=41000.0,
            take_profit=44000.0
        )
        
        assert pos.direction == 'LONG'
        assert pos.entry_price == 42000.0
        assert pos.size == 0.1
        assert pos.stop_loss == 41000.0
        assert pos.take_profit == 44000.0
    
    def test_update_metrics(self):
        """测试指标更新"""
        pos = LivePosition(
            entry_time=datetime.now(),
            entry_price=42000.0,
            direction='LONG',
            size=0.1
        )
        
        # 价格上涨
        pos.update_metrics(43000.0)
        assert pos.max_profit > 0
        
        # 价格回落
        pos.update_metrics(42500.0)
        assert pos.max_drawdown < pos.max_profit
    
    def test_check_exit_long(self):
        """测试多头止盈止损检查"""
        pos = LivePosition(
            entry_time=datetime.now(),
            entry_price=42000.0,
            direction='LONG',
            size=0.1,
            stop_loss=41000.0,
            take_profit=44000.0
        )
        
        # 触发止损
        result = pos.check_exit(42000.0, 40900.0)
        assert result == 'stop_loss'
        
        # 触发止盈
        result = pos.check_exit(44100.0, 43000.0)
        assert result == 'take_profit'
        
        # 未触发
        result = pos.check_exit(43000.0, 42500.0)
        assert result is None
    
    def test_check_exit_short(self):
        """测试空头止盈止损检查"""
        pos = LivePosition(
            entry_time=datetime.now(),
            entry_price=42000.0,
            direction='SHORT',
            size=0.1,
            stop_loss=43000.0,
            take_profit=40000.0
        )
        
        # 触发止损
        result = pos.check_exit(43100.0, 42000.0)
        assert result == 'stop_loss'
        
        # 触发止盈
        result = pos.check_exit(41000.0, 39900.0)
        assert result == 'take_profit'
    
    def test_partial_exits(self):
        """测试分批止盈"""
        pos = LivePosition(
            entry_time=datetime.now(),
            entry_price=42000.0,
            direction='LONG',
            size=0.1,
            tp1_price=43000.0,
            tp2_price=44000.0,
            tp1_percent=0.5,
            tp2_percent=0.3
        )
        
        # 触发TP1
        result = pos.check_partial_exits(43100.0, 42500.0)
        assert result['action'] == 'tp1'
        assert result['price'] == 43000.0
        
        # 标记TP1已触发
        pos.tp1_triggered = True
        
        # 触发TP2
        result = pos.check_partial_exits(44100.0, 43500.0)
        assert result['action'] == 'tp2'
        assert result['price'] == 44000.0
    
    def test_unrealized_pnl(self):
        """测试未实现盈亏计算"""
        # 多头
        pos_long = LivePosition(
            entry_time=datetime.now(),
            entry_price=42000.0,
            direction='LONG',
            size=0.1
        )
        pnl = pos_long.get_unrealized_pnl(43000.0)
        assert pnl == (43000.0 - 42000.0) * 0.1
        
        # 空头
        pos_short = LivePosition(
            entry_time=datetime.now(),
            entry_price=42000.0,
            direction='SHORT',
            size=0.1
        )
        pnl = pos_short.get_unrealized_pnl(41000.0)
        assert pnl == (42000.0 - 41000.0) * 0.1


class TestLiveTradingEngine:
    """测试LiveTradingEngine类"""
    
    @pytest.fixture
    def mock_config(self):
        """模拟配置"""
        return {
            'exchange': {
                'api_key': 'test_key',
                'secret': 'test_secret',
                'testnet': True
            },
            'trading': {
                'symbol': 'BTC/USDT',
                'base_timeframe': '5m'
            },
            'strategy': {
                'setup_type': 'Open/Close',
                'filter_type': 'No Filtering',
                'tps_type': 'Trailing',
                'rsi_period': 7,
                'rsi_high': 45,
                'rsi_low': 10,
                'atr_filter_period': 5,
                'atr_filter_ma_period': 5,
                'atr_risk_period': 20,
                'profit_factor': 2.5,
                'stop_factor': 10.0,
                'enable_partial_exits': True,
                'tp1_factor': 1.5,
                'tp2_factor': 2.0,
                'tp1_percent': 0.5,
                'tp2_percent': 0.3,
                'htf_multiplier': 18
            },
            'risk_management': {
                'position_size': 0.95,
                'max_drawdown_percent': 10,
                'max_daily_loss': 500.0
            },
            'execution': {
                'use_limit_orders': True,
                'order_timeout': 30,
                'price_tick_offset': 0.01,
                'enable_orderbook_analysis': False
            }
        }
    
    @pytest.fixture
    def mock_df(self):
        """模拟K线数据"""
        dates = pd.date_range(start='2024-01-01', periods=200, freq='5min')
        
        # 生成模拟价格数据
        close_prices = 42000 + np.cumsum(np.random.randn(200) * 100)
        
        df = pd.DataFrame({
            'timestamp': dates,
            'open': close_prices - np.random.rand(200) * 50,
            'high': close_prices + np.random.rand(200) * 100,
            'low': close_prices - np.random.rand(200) * 100,
            'close': close_prices,
            'volume': np.random.rand(200) * 1000
        })
        
        return df
    
    @patch('src.core.live_trading_engine.BinanceClient')
    @patch('src.core.live_trading_engine.OrderManager')
    def test_engine_initialization(self, mock_order_mgr, mock_client, mock_config):
        """测试引擎初始化"""
        engine = LiveTradingEngine(mock_config)
        
        assert engine.symbol == 'BTC/USDT'
        assert engine.base_timeframe == '5m'
        assert engine.setup_type == 'Open/Close'
        assert engine.enable_partial_exits == True
        assert engine.is_running == False
    
    @patch('src.core.live_trading_engine.BinanceClient')
    @patch('src.core.live_trading_engine.OrderManager')
    def test_resample_htf(self, mock_order_mgr, mock_client, mock_config, mock_df):
        """测试高时间框架重采样"""
        engine = LiveTradingEngine(mock_config)
        
        htf_df = engine._resample_htf(mock_df)
        
        assert htf_df is not None
        assert len(htf_df) < len(mock_df)
        assert 'open' in htf_df.columns
        assert 'high' in htf_df.columns
        assert 'low' in htf_df.columns
        assert 'close' in htf_df.columns
    
    @patch('src.core.live_trading_engine.BinanceClient')
    @patch('src.core.live_trading_engine.OrderManager')
    def test_calculate_sl_tp(self, mock_order_mgr, mock_client, mock_config, mock_df):
        """测试止盈止损计算"""
        engine = LiveTradingEngine(mock_config)
        
        entry_price = 42000.0
        sl, tp, tp1, tp2 = engine._calculate_sl_tp(mock_df, entry_price, 'LONG')
        
        # 多头：止损低于入场价，止盈高于入场价
        assert sl < entry_price
        assert tp > entry_price
        
        if engine.enable_partial_exits:
            assert tp1 < tp
            assert tp2 < tp
            assert tp1 < tp2
    
    @patch('src.core.live_trading_engine.BinanceClient')
    @patch('src.core.live_trading_engine.OrderManager')
    def test_check_filters(self, mock_order_mgr, mock_client, mock_config, mock_df):
        """测试过滤器"""
        engine = LiveTradingEngine(mock_config)
        engine.filter_type = 'No Filtering'
        
        # 无过滤应该总是通过
        result = engine._check_filters(mock_df)
        assert result == True
    
    @patch('src.core.live_trading_engine.BinanceClient')
    @patch('src.core.live_trading_engine.OrderManager')
    def test_check_max_drawdown(self, mock_order_mgr, mock_client, mock_config):
        """测试最大回撤检查"""
        engine = LiveTradingEngine(mock_config)
        
        # 创建持仓
        engine.current_position = LivePosition(
            entry_time=datetime.now(),
            entry_price=42000.0,
            direction='LONG',
            size=0.1
        )
        
        # 设置最大回撤
        engine.current_position.max_drawdown = -0.05  # -5%
        
        # 未超过限制
        result = engine._check_max_drawdown()
        assert result == False
        
        # 超过限制
        engine.current_position.max_drawdown = -0.15  # -15%
        result = engine._check_max_drawdown()
        assert result == True
    
    @patch('src.core.live_trading_engine.BinanceClient')
    @patch('src.core.live_trading_engine.OrderManager')
    def test_check_risk_limits(self, mock_order_mgr, mock_client, mock_config):
        """测试风控限制"""
        engine = LiveTradingEngine(mock_config)
        
        # 未超过每日亏损
        engine.daily_pnl = -300.0
        result = engine._check_risk_limits()
        assert result == True
        
        # 超过每日亏损
        engine.daily_pnl = -600.0
        result = engine._check_risk_limits()
        assert result == False
    
    @patch('src.core.live_trading_engine.BinanceClient')
    @patch('src.core.live_trading_engine.OrderManager')
    def test_get_statistics(self, mock_order_mgr, mock_client, mock_config):
        """测试统计信息"""
        engine = LiveTradingEngine(mock_config)
        
        # 设置一些统计数据
        engine.total_trades = 10
        engine.winning_trades = 6
        engine.daily_pnl = 150.0
        
        stats = engine.get_statistics()
        
        assert stats['total_trades'] == 10
        assert stats['winning_trades'] == 6
        assert stats['win_rate'] == 0.6
        assert stats['daily_pnl'] == 150.0


def test_integration_workflow():
    """集成测试：完整工作流"""
    # TODO: 实现完整的工作流集成测试
    # 包括：初始化 -> 获取数据 -> 生成信号 -> 执行订单 -> 管理持仓 -> 平仓
    pass


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

