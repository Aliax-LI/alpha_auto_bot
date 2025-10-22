"""
测试数据获取功能
验证 BinanceClient 的配置和网络连接
"""
import sys
from loguru import logger
from src.utils.config_loader import ConfigLoader
from src.data.binance_client import BinanceClient

# 配置日志
logger.remove()
logger.add(
    sys.stdout,
    format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
    level="DEBUG"
)

def test_binance_client():
    """测试币安客户端"""
    try:
        # 1. 加载配置
        logger.info("=" * 60)
        logger.info("🧪 测试币安数据获取")
        logger.info("=" * 60)
        
        config_loader = ConfigLoader("../config/config.yaml")
        config = config_loader.load()
        
        exchange_config = config.get('exchange', {})
        logger.info(f"\n📋 配置信息:")
        logger.info(f"   交易所: {exchange_config.get('name')}")
        logger.info(f"   代理: {exchange_config.get('http_proxy', '未配置')}")
        logger.info(f"   测试网: {exchange_config.get('testnet', False)}")
        
        # 2. 初始化客户端
        logger.info(f"\n⚙️  初始化客户端...")
        client = BinanceClient(exchange_config)
        
        # 3. 测试获取K线数据
        symbol = config['trading']['symbol']
        timeframe = config['trading']['base_timeframe']
        
        logger.info(f"\n📊 测试获取K线数据:")
        logger.info(f"   交易对: {symbol}")
        logger.info(f"   时间框架: {timeframe}")
        logger.info(f"   数量: 10")
        
        df = client.fetch_ohlcv(symbol, timeframe, limit=10)
        
        if df is not None and not df.empty:
            logger.info(f"\n✅ 成功获取数据:")
            logger.info(f"   K线数量: {len(df)}")
            logger.info(f"   时间范围: {df['timestamp'].iloc[0]} → {df['timestamp'].iloc[-1]}")
            logger.info(f"   价格范围: {df['close'].min():.4f} - {df['close'].max():.4f}")
            logger.info(f"\n最新5根K线:")
            logger.info(df.tail().to_string())
        else:
            logger.error("❌ 未获取到数据")
            return False
        
        # 4. 测试获取更多数据
        logger.info(f"\n📊 测试获取更多K线数据 (500根)...")
        df_large = client.fetch_ohlcv(symbol, timeframe, limit=500)
        
        if df_large is not None and not df_large.empty:
            logger.info(f"✅ 成功获取 {len(df_large)} 根K线")
        else:
            logger.error("❌ 未获取到数据")
            return False
        
        logger.info("\n" + "=" * 60)
        logger.info("✅ 所有测试通过！")
        logger.info("=" * 60)
        return True
        
    except Exception as e:
        logger.error(f"\n❌ 测试失败: {e}", exc_info=True)
        return False

if __name__ == "__main__":
    success = test_binance_client()
    sys.exit(0 if success else 1)

