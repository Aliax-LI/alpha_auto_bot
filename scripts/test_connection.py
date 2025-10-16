#!/usr/bin/env python3
"""测试交易所连接和配置"""
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.exchange_client import exchange_client
from src.core.data_fetcher import data_fetcher
from src.utils.config import config
from src.monitor.logger import system_logger


def test_config():
    """测试配置加载"""
    print("\n=== Testing Configuration ===")
    try:
        exchange_config = config.get_exchange_config()
        print(f"✓ Exchange: {exchange_config.get('name')}")
        print(f"✓ Sandbox mode: {exchange_config.get('sandbox_mode')}")
        print(f"✓ Proxy: {exchange_config.get('proxy')}")
        return True
    except Exception as e:
        print(f"✗ Config error: {e}")
        return False


def test_exchange_connection():
    """测试交易所连接"""
    print("\n=== Testing Exchange Connection ===")
    try:
        # 测试获取市场信息
        markets = exchange_client.fetch_markets()
        print(f"✓ Connected to exchange. Found {len(markets)} markets")
        
        # 测试获取余额
        balance = data_fetcher.fetch_account_balance()
        print(f"✓ Account balance: {balance.get('total', 0):.2f} USDT")
        
        return True
    except Exception as e:
        print(f"✗ Exchange connection error: {e}")
        return False


def test_data_fetching():
    """测试数据获取"""
    print("\n=== Testing Data Fetching ===")
    try:
        # 获取USDT永续合约
        symbols = data_fetcher.get_usdt_perpetual_symbols()
        print(f"✓ Found {len(symbols)} USDT perpetual contracts")
        
        if symbols:
            # 测试获取K线数据
            test_symbol = symbols[0]
            df = data_fetcher.fetch_ohlcv_df(test_symbol, '5m', limit=100)
            print(f"✓ Fetched {len(df)} candles for {test_symbol}")
            
            # 测试获取订单簿
            orderbook = data_fetcher.fetch_orderbook_analysis(test_symbol)
            if orderbook:
                print(f"✓ Orderbook depth: {orderbook.get('bid_depth', 0):.2f}")
        
        return True
    except Exception as e:
        print(f"✗ Data fetching error: {e}")
        return False


def test_indicators():
    """测试技术指标计算"""
    print("\n=== Testing Technical Indicators ===")
    try:
        from src.indicators.technical import technical_indicators
        
        # 获取测试数据
        symbols = data_fetcher.get_usdt_perpetual_symbols()
        if not symbols:
            print("✗ No symbols available for testing")
            return False
        
        test_symbol = symbols[0]
        df = data_fetcher.fetch_ohlcv_df(test_symbol, '5m', limit=100)
        
        if df.empty:
            print("✗ No data available")
            return False
        
        # 计算指标
        df = technical_indicators.calculate_all_indicators(df)
        
        # 检查指标是否计算成功
        indicators = ['ema_9', 'macd', 'rsi', 'adx', 'atr']
        success = all(col in df.columns for col in indicators)
        
        if success:
            print(f"✓ All indicators calculated successfully")
            print(f"  EMA(9): {df['ema_9'].iloc[-1]:.2f}")
            print(f"  RSI: {df['rsi'].iloc[-1]:.2f}")
            print(f"  ADX: {df['adx'].iloc[-1]:.2f}")
        else:
            print("✗ Some indicators missing")
            return False
        
        return True
    except Exception as e:
        print(f"✗ Indicator calculation error: {e}")
        return False


def test_database():
    """测试数据库"""
    print("\n=== Testing Database ===")
    try:
        from src.utils.database import database
        
        # 测试数据库连接
        session = database.get_session()
        session.close()
        print("✓ Database connection successful")
        
        # 测试查询
        open_trades = database.get_open_trades()
        print(f"✓ Open trades: {len(open_trades)}")
        
        return True
    except Exception as e:
        print(f"✗ Database error: {e}")
        return False


def main():
    """主测试函数"""
    print("=" * 60)
    print("OKX Trading System - Connection Test")
    print("=" * 60)
    
    results = []
    
    # 运行所有测试
    results.append(("Configuration", test_config()))
    results.append(("Exchange Connection", test_exchange_connection()))
    results.append(("Data Fetching", test_data_fetching()))
    results.append(("Technical Indicators", test_indicators()))
    results.append(("Database", test_database()))
    
    # 总结
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{name:.<30} {status}")
    
    print("=" * 60)
    print(f"Total: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed! System is ready to use.")
        return 0
    else:
        print("\n⚠️  Some tests failed. Please check the configuration.")
        return 1


if __name__ == '__main__':
    sys.exit(main())

