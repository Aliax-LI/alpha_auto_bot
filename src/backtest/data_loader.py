"""
历史数据加载器
使用 CCXT 获取历史 OHLCV 数据
"""
import ccxt
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from loguru import logger


class HistoricalDataLoader:
    """历史数据加载器"""
    
    def __init__(
        self,
        exchange_id: str = 'binance',
        proxy: Optional[str] = None,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None
    ):
        """
        初始化数据加载器
        
        Args:
            exchange_id: 交易所 ID
            proxy: 代理地址（可选）
            api_key: API Key（可选）
            api_secret: API Secret（可选）
        """
        self.exchange_id = exchange_id
        
        # 初始化交易所
        exchange_class = getattr(ccxt, exchange_id)
        config = {
            'timeout': 30000,
            'enableRateLimit': True,
        }
        
        # 设置代理
        if proxy:
            config['proxies'] = {
                'http': proxy,
                'https': proxy,
            }
            logger.info(f"🌐 使用代理: {proxy}")
        
        # 设置API密钥（如果提供）
        if api_key and api_secret:
            config['apiKey'] = api_key
            config['secret'] = api_secret
        
        # 初始化交易所
        self.exchange = exchange_class(config)
        
        # 设置为永续合约市场（重要！）
        if exchange_id == 'binance':
            try:
                self.exchange.set_sandbox_mode(False)  # 使用正式环境
                # 加载市场信息
                self.exchange.load_markets()
                logger.info(f"✅ 初始化交易所: {exchange_id} (永续合约)")
            except Exception as e:
                logger.warning(f"⚠️ 加载市场信息失败: {e}，继续使用默认配置")
                logger.info(f"✅ 初始化交易所: {exchange_id}")
        else:
            logger.info(f"✅ 初始化交易所: {exchange_id}")
    
    def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str = '1h',
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        limit: int = 1000
    ) -> pd.DataFrame:
        """
        获取 OHLCV 历史数据
        
        Args:
            symbol: 交易对（例如 'BTC/USDT:USDT'）
            timeframe: 时间框架（1m, 5m, 15m, 1h, 4h, 1d）
            since: 开始时间
            until: 结束时间
            limit: 每次请求的数据量
            
        Returns:
            包含 OHLCV 数据的 DataFrame
        """
        logger.info(f"📊 开始加载历史数据: {symbol} {timeframe}")
        
        all_ohlcv = []
        
        # 转换时间为时间戳
        if since:
            since_ts = int(since.timestamp() * 1000)
        else:
            # 默认获取最近 30 天数据
            since_ts = int((datetime.now() - timedelta(days=30)).timestamp() * 1000)
        
        if until:
            until_ts = int(until.timestamp() * 1000)
        else:
            until_ts = int(datetime.now().timestamp() * 1000)
        
        current_ts = since_ts
        
        # 分批获取数据
        while current_ts < until_ts:
            try:
                ohlcv = self.exchange.fetch_ohlcv(
                    symbol=symbol,
                    timeframe=timeframe,
                    since=current_ts,
                    limit=limit
                )
                
                if not ohlcv:
                    break
                
                all_ohlcv.extend(ohlcv)
                
                # 更新时间戳到最后一根K线之后
                current_ts = ohlcv[-1][0] + 1
                
                logger.debug(f"获取 {len(ohlcv)} 根K线，当前时间: {datetime.fromtimestamp(current_ts/1000)}")
                
                # 如果获取的数据少于 limit，说明已经到最新数据
                if len(ohlcv) < limit:
                    break
                
            except Exception as e:
                logger.error(f"❌ 获取数据失败: {e}")
                break
        
        # 转换为 DataFrame
        if not all_ohlcv:
            logger.warning("未获取到任何数据")
            return pd.DataFrame()
        
        df = pd.DataFrame(
            all_ohlcv,
            columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
        )
        
        # 转换时间戳为上海时区（东八区）
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms').dt.tz_localize('UTC').dt.tz_convert('Asia/Shanghai')
        
        # 去重（可能有重叠数据）
        df = df.drop_duplicates(subset=['timestamp']).reset_index(drop=True)
        
        # 格式化时间显示
        start_time = df['timestamp'].iloc[0].strftime('%Y-%m-%d %H:%M:%S')
        end_time = df['timestamp'].iloc[-1].strftime('%Y-%m-%d %H:%M:%S')
        
        logger.info(f"✅ 加载完成: {len(df)} 根K线")
        logger.info(f"   时间范围: {start_time} → {end_time} [上海时间]")
        logger.info(f"   价格范围: {df['close'].min():.2f} - {df['close'].max():.2f}")
        
        return df
    
    def get_multiple_timeframes(
        self,
        symbol: str,
        base_timeframe: str,
        multiplier: int,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None
    ) -> Dict[str, pd.DataFrame]:
        """
        获取多时间框架数据
        
        Args:
            symbol: 交易对
            base_timeframe: 基础时间框架
            multiplier: 倍数
            since: 开始时间
            until: 结束时间
            
        Returns:
            包含两个时间框架数据的字典
        """
        # 获取基础时间框架数据
        base_df = self.fetch_ohlcv(symbol, base_timeframe, since, until)
        
        # 计算高级时间框架
        htf_timeframe = self._calculate_htf(base_timeframe, multiplier)
        
        logger.info(f"📈 获取高级时间框架: {htf_timeframe} (= {multiplier} × {base_timeframe})")
        
        htf_df = self.fetch_ohlcv(symbol, htf_timeframe, since, until)
        
        return {
            'base': base_df,
            'htf': htf_df
        }
    
    def _calculate_htf(self, base_timeframe: str, multiplier: int) -> str:
        """
        计算高级时间框架
        
        Args:
            base_timeframe: 基础时间框架
            multiplier: 倍数
            
        Returns:
            高级时间框架字符串
        """
        # 解析时间框架
        unit = base_timeframe[-1]  # m, h, d
        value = int(base_timeframe[:-1])
        
        htf_value = value * multiplier
        
        # 转换单位
        if unit == 'm' and htf_value >= 60:
            htf_value = htf_value // 60
            unit = 'h'
        
        if unit == 'h' and htf_value >= 24:
            htf_value = htf_value // 24
            unit = 'd'
        
        return f"{htf_value}{unit}"

