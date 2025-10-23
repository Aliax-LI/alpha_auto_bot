"""
币安交易所客户端
封装 ccxt 提供统一的数据和交易接口
"""
import ccxt
import pandas as pd
from typing import Optional, Dict, Any, List
from loguru import logger


class BinanceClient:
    """币安交易所客户端类"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化币安客户端
        
        Args:
            config: 交易所配置字典，包含 api_key, secret, testnet 等
        """
        self.config = config
        
        # 构建 ccxt 配置
        ccxt_config = {
            'apiKey': config.get('api_key', ''),
            'secret': config.get('secret', ''),
            'timeout': 30000,  # 30秒超时（与回测保持一致）
            'enableRateLimit': True,
            'options': {
                'defaultType': 'swap',  # 使用合约交易
                'adjustForTimeDifference': True
            }
        }
        
        # 设置代理（如果配置了）
        http_proxy = config.get('http_proxy')
        if http_proxy:
            ccxt_config['proxies'] = {
                'http': http_proxy,
                'https': http_proxy,
            }
            logger.info(f"🌐 使用代理: {http_proxy}")
        
        # 初始化 ccxt 交易所对象
        self.exchange = ccxt.binance(ccxt_config)
        
        # 设置测试网
        if config.get('testnet', False):
            self.exchange.set_sandbox_mode(True)
            logger.info("🧪 使用币安测试网")
        else:
            logger.warning("⚠️  使用币安实盘交易")
        
        # 加载市场信息
        try:
            self.exchange.load_markets()
            logger.info(f"✅ 成功连接到币安交易所（永续合约）")
                
        except Exception as e:
            logger.error(f"❌ 连接币安交易所失败: {e}")
            logger.warning("⚠️  将在首次请求时重试加载市场信息")
            # 不抛出异常，允许在首次API调用时重试
    
    def fetch_ohlcv(
        self, 
        symbol: str, 
        timeframe: str, 
        limit: int = 500,
        since: Optional[int] = None
    ) -> pd.DataFrame:
        """
        获取 OHLCV K线数据
        
        Args:
            symbol: 交易对符号，如 'BTC/USDT'
            timeframe: 时间周期，如 '1m', '5m', '1h'
            limit: 返回的K线数量
            since: 起始时间戳（毫秒）
            
        Returns:
            包含 OHLCV 数据的 DataFrame
        """
        try:
            logger.debug(f"📊 请求K线数据: {symbol} {timeframe} (limit={limit})")
            
            ohlcv = self.exchange.fetch_ohlcv(
                symbol, 
                timeframe, 
                since=since,
                limit=limit
            )
            
            if not ohlcv:
                logger.warning(f"⚠️  未获取到任何K线数据: {symbol} {timeframe}")
                return pd.DataFrame()
            
            df = pd.DataFrame(
                ohlcv, 
                columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
            )
            # 转换为上海时区（东八区）
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms').dt.tz_localize('UTC').dt.tz_convert('Asia/Shanghai')
            
            # 格式化时间显示（去掉时区标识）
            start_time = df['timestamp'].iloc[0].strftime('%Y-%m-%d %H:%M:%S')
            end_time = df['timestamp'].iloc[-1].strftime('%Y-%m-%d %H:%M:%S')
            
            logger.debug(
                f"✅ 获取 {symbol} {timeframe} K线数据: {len(df)} 条 "
                f"({start_time} → {end_time}) [上海时间]"
            )
            
            return df
            
        except ccxt.NetworkError as e:
            logger.error(f"❌ 网络错误，无法获取K线数据: {e}")
            logger.info("💡 提示：请检查网络连接和代理设置")
            raise
        except ccxt.ExchangeError as e:
            logger.error(f"❌ 交易所错误: {e}")
            raise
        except Exception as e:
            logger.error(f"❌ 获取K线数据失败: {e}")
            raise
    
    def fetch_orderbook(self, symbol: str, limit: int = 20) -> Dict[str, Any]:
        """
        获取订单簿数据
        
        Args:
            symbol: 交易对符号
            limit: 返回的深度档位数量
            
        Returns:
            订单簿字典，包含 bids 和 asks
        """
        try:
            orderbook = self.exchange.fetch_order_book(symbol, limit=limit)
            logger.debug(f"获取 {symbol} 订单簿: {limit} 档")
            return orderbook
        except Exception as e:
            logger.error(f"❌ 获取订单簿失败: {e}")
            raise
    
    def fetch_balance(self) -> Dict[str, Any]:
        """
        获取账户余额
        
        Returns:
            账户余额字典
        """
        try:
            balance = self.exchange.fetch_balance()
            logger.debug("获取账户余额")
            return balance
        except Exception as e:
            logger.error(f"❌ 获取余额失败: {e}")
            raise
    
    def fetch_positions(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        获取持仓信息
        
        Args:
            symbol: 交易对符号，None 则返回所有持仓
            
        Returns:
            持仓列表
        """
        try:
            positions = self.exchange.fetch_positions([symbol] if symbol else None)
            # 过滤掉零仓位
            active_positions = [
                pos for pos in positions 
                if float(pos.get('contracts', 0)) != 0
            ]
            logger.debug(f"获取持仓: {len(active_positions)} 个")
            return active_positions
        except Exception as e:
            logger.error(f"❌ 获取持仓失败: {e}")
            raise
    
    def create_order(
        self,
        symbol: str,
        side: str,
        amount: float,
        price: Optional[float] = None,
        order_type: str = 'market',
        params: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        创建订单
        
        Args:
            symbol: 交易对符号
            side: 'buy' 或 'sell'
            amount: 订单数量
            price: 限价单价格
            order_type: 订单类型 'market' 或 'limit'
            params: 额外参数
            
        Returns:
            订单信息字典
        """
        try:
            if params is None:
                params = {}
            
            # 对于期货合约，设置持仓方向
            # 双向持仓模式：需要指定 LONG 或 SHORT
            # 单向持仓模式：使用 BOTH
            if 'positionSide' not in params:
                # 默认只做多（LONG），不做空
                # buy = 开多仓, sell = 平多仓
                params['positionSide'] = 'LONG'
            
            order = self.exchange.create_order(
                symbol=symbol,
                type=order_type,
                side=side,
                amount=amount,
                price=price,
                params=params
            )
            
            logger.info(
                f"📝 创建订单: {side.upper()} {amount} {symbol} "
                f"@ {price if price else 'MARKET'} ({order_type})"
            )
            
            return order
            
        except Exception as e:
            logger.error(f"❌ 创建订单失败: {e}")
            raise
    
    def fetch_order(self, order_id: str, symbol: str) -> Dict[str, Any]:
        """
        查询订单状态
        
        Args:
            order_id: 订单ID
            symbol: 交易对符号
            
        Returns:
            订单信息字典
        """
        try:
            order = self.exchange.fetch_order(order_id, symbol)
            logger.debug(f"查询订单 {order_id}: {order.get('status')}")
            return order
        except Exception as e:
            logger.error(f"❌ 查询订单失败: {e}")
            raise
    
    def cancel_order(self, order_id: str, symbol: str) -> Dict[str, Any]:
        """
        取消订单
        
        Args:
            order_id: 订单ID
            symbol: 交易对符号
            
        Returns:
            取消结果字典
        """
        try:
            result = self.exchange.cancel_order(order_id, symbol)
            logger.info(f"🚫 取消订单: {order_id}")
            return result
        except Exception as e:
            logger.error(f"❌ 取消订单失败: {e}")
            raise
    
    def set_leverage(self, leverage: int, symbol: str) -> Dict[str, Any]:
        """
        设置杠杆倍数
        
        Args:
            leverage: 杠杆倍数
            symbol: 交易对符号
            
        Returns:
            设置结果
        """
        try:
            result = self.exchange.set_leverage(leverage, symbol)
            logger.info(f"⚙️  设置杠杆: {symbol} {leverage}x")
            return result
        except Exception as e:
            logger.error(f"❌ 设置杠杆失败: {e}")
            raise
    
    def set_margin_mode(self, margin_mode: str, symbol: str) -> Dict[str, Any]:
        """
        设置保证金模式
        
        Args:
            margin_mode: 'cross' 全仓 或 'isolated' 逐仓
            symbol: 交易对符号
            
        Returns:
            设置结果
        """
        try:
            result = self.exchange.set_margin_mode(margin_mode, symbol)
            logger.info(f"⚙️  设置保证金模式: {symbol} {margin_mode}")
            return result
        except Exception as e:
            logger.error(f"❌ 设置保证金模式失败: {e}")
            raise
    
    def get_ticker(self, symbol: str) -> Dict[str, Any]:
        """
        获取行情信息
        
        Args:
            symbol: 交易对符号
            
        Returns:
            行情字典
        """
        try:
            ticker = self.exchange.fetch_ticker(symbol)
            return ticker
        except Exception as e:
            logger.error(f"❌ 获取行情失败: {e}")
            raise

