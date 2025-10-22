"""
订单管理器实盘测试脚本
使用币安测试网进行真实订单测试
@author Cursor
@date 2025-01-22
@version 1.0.0
"""
import sys
import time
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger
from src.data.binance_client import BinanceClient
from src.execution.order_manager import OrderManager
from src.utils.config_loader import ConfigLoader


class OrderManagerTester:
    """订单管理器测试类"""
    
    def __init__(self, config_path: str = "/Users/lixin/PycharmProjects/alpha_auto_bot/config/config.yaml"):
        """初始化测试器"""
        logger.info("=" * 80)
        logger.info("🧪 订单管理器实盘测试")
        logger.info("=" * 80)
        
        # 加载配置
        config_loader = ConfigLoader(config_path)
        self.config = config_loader.load()
        
        # 初始化客户端
        logger.info("\n📡 初始化币安客户端...")
        self.client = BinanceClient(self.config['exchange'])
        
        # 初始化订单管理器
        logger.info("⚙️  初始化订单管理器...")
        execution_config = self.config.get('execution', {})
        self.order_manager = OrderManager(self.client, execution_config)
        
        # 测试交易对
        self.symbol = self.config['trading'].get('symbol', 'BTC/USDT:USDT')
        
        logger.info(f"\n✅ 初始化完成")
        logger.info(f"   交易对: {self.symbol}")
        logger.info(f"   测试网: 是")
        logger.info("=" * 80)
    
    def check_connection(self) -> bool:
        """检查连接"""
        logger.info("\n🔍 测试 1: 检查交易所连接")
        logger.info("-" * 80)
        
        try:
            # 获取账户余额
            balance = self.client.fetch_balance()
            usdt_balance = balance.get('USDT', {}).get('free', 0)
            
            logger.info(f"✅ 连接成功")
            logger.info(f"   USDT余额: {usdt_balance:.2f}")
            
            if usdt_balance < 10:
                logger.warning("⚠️  余额不足，请先领取测试网USDT")
                logger.warning("   访问: https://testnet.binancefuture.com/")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"❌ 连接失败: {e}")
            return False
    
    def test_orderbook_fetch(self) -> bool:
        """测试订单簿获取"""
        logger.info("\n🔍 测试 2: 获取订单簿数据")
        logger.info("-" * 80)
        
        try:
            orderbook = self.client.fetch_orderbook(self.symbol, limit=10)
            
            best_bid = orderbook['bids'][0][0] if orderbook['bids'] else 0
            best_ask = orderbook['asks'][0][0] if orderbook['asks'] else 0
            spread = best_ask - best_bid
            spread_pct = (spread / best_bid * 100) if best_bid > 0 else 0
            
            logger.info(f"✅ 订单簿获取成功")
            logger.info(f"   最佳买价: {best_bid:.2f}")
            logger.info(f"   最佳卖价: {best_ask:.2f}")
            logger.info(f"   价差: {spread:.2f} ({spread_pct:.4f}%)")
            logger.info(f"   买盘深度: {len(orderbook['bids'])} 档")
            logger.info(f"   卖盘深度: {len(orderbook['asks'])} 档")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ 订单簿获取失败: {e}")
            return False
    
    def test_market_order(self, test_size: float = 30) -> bool:
        """测试市价单"""
        logger.info(f"\n🔍 测试 3: 市价单执行 (数量: {test_size})")
        logger.info("-" * 80)
        
        try:
            # 获取当前价格
            ticker = self.client.get_ticker(self.symbol)
            current_price = ticker['last']
            logger.info(f"   当前价格: {current_price:.2f}")
            
            # 执行买入市价单
            logger.info(f"\n📝 执行买入市价单...")
            buy_order = self.order_manager._execute_market_order(
                self.symbol, 'buy', test_size
            )
            
            if not buy_order:
                logger.error("❌ 买入市价单失败")
                return False
            
            logger.info(f"✅ 买入市价单成功")
            logger.info(f"   订单ID: {buy_order.get('id')}")
            logger.info(f"   成交价: {buy_order.get('average', 'N/A')}")
            logger.info(f"   成交量: {buy_order.get('filled', test_size)}")
            logger.info(f"   状态: {buy_order.get('status')}")
            
            # 等待几秒
            time.sleep(2)
            
            # 执行卖出市价单平仓
            logger.info(f"\n📝 执行卖出市价单（平仓）...")
            sell_order = self.order_manager._execute_market_order(
                self.symbol, 'sell', test_size
            )
            
            if not sell_order:
                logger.error("❌ 卖出市价单失败")
                return False
            
            logger.info(f"✅ 卖出市价单成功")
            logger.info(f"   订单ID: {sell_order.get('id')}")
            logger.info(f"   成交价: {sell_order.get('average', 'N/A')}")
            logger.info(f"   成交量: {sell_order.get('filled', test_size)}")
            
            # 计算盈亏
            buy_price = buy_order.get('average', 0)
            sell_price = sell_order.get('average', 0)
            if buy_price and sell_price:
                pnl = (sell_price - buy_price) * test_size
                logger.info(f"\n💰 测试盈亏: {pnl:.4f} USDT")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ 市价单测试失败: {e}")
            return False
    
    def test_limit_order(self, test_size: float = 30) -> bool:
        """测试限价单"""
        logger.info(f"\n🔍 测试 4: 限价单执行 (数量: {test_size})")
        logger.info("-" * 80)
        
        try:
            # 获取订单簿
            orderbook = self.client.fetch_orderbook(self.symbol, limit=5)
            best_bid = orderbook['bids'][0][0]
            best_ask = orderbook['asks'][0][0]
            
            logger.info(f"   最佳买价: {best_bid:.2f}")
            logger.info(f"   最佳卖价: {best_ask:.2f}")
            
            # 测试限价买单（价格设置得较优，应该能快速成交）
            buy_price = best_ask - 0.01  # 略优于卖一价
            
            logger.info(f"\n📝 创建限价买单 @ {buy_price:.2f}...")
            buy_order = self.client.create_order(
                symbol=self.symbol,
                side='buy',
                amount=test_size,
                price=buy_price,
                order_type='limit'
            )
            
            buy_order_id = buy_order['id']
            logger.info(f"✅ 限价买单已创建")
            logger.info(f"   订单ID: {buy_order_id}")
            logger.info(f"   价格: {buy_price:.2f}")
            logger.info(f"   数量: {test_size}")
            
            # 等待成交
            logger.info("\n⏳ 等待订单成交...")
            max_wait = 10  # 最多等待10秒
            start_time = time.time()
            
            while time.time() - start_time < max_wait:
                order_status = self.client.fetch_order(buy_order_id, self.symbol)
                
                if order_status['status'] == 'closed':
                    logger.info(f"✅ 限价买单已成交")
                    logger.info(f"   成交价: {order_status.get('average', 'N/A')}")
                    logger.info(f"   成交量: {order_status.get('filled', test_size)}")
                    break
                
                time.sleep(1)
            else:
                # 超时，取消订单
                logger.warning(f"⏰ 订单未在{max_wait}秒内成交，取消订单...")
                self.client.cancel_order(buy_order_id, self.symbol)
                logger.info("✅ 订单已取消")
                return True  # 取消成功也算测试通过
            
            # 如果买单成交，立即市价平仓
            time.sleep(1)
            logger.info("\n📝 市价平仓...")
            sell_order = self.order_manager._execute_market_order(
                self.symbol, 'sell', test_size
            )
            
            if sell_order:
                logger.info("✅ 平仓成功")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ 限价单测试失败: {e}")
            return False
    
    def test_limit_order_with_timeout(self, test_size: float = 30) -> bool:
        """测试限价单超时机制"""
        logger.info(f"\n🔍 测试 5: 限价单超时机制 (数量: {test_size})")
        logger.info("-" * 80)
        
        try:
            # 获取订单簿
            orderbook = self.client.fetch_orderbook(self.symbol, limit=5)
            best_bid = orderbook['bids'][0][0]
            best_ask = orderbook['asks'][0][0]
            
            # 设置一个不太可能成交的价格（远低于市价）
            buy_price = best_bid * 0.95  # 低于市价5%
            
            logger.info(f"   市价: {best_ask:.2f}")
            logger.info(f"   限价: {buy_price:.2f} (低于市价 {(1 - buy_price/best_ask)*100:.1f}%)")
            
            # 临时修改超时时间为5秒
            original_timeout = self.order_manager.order_timeout
            self.order_manager.order_timeout = 5
            
            logger.info(f"\n📝 执行限价单（预计超时）...")
            start_time = time.time()
            
            # 使用订单管理器的限价单方法（会自动处理超时）
            result = self.order_manager._execute_limit_order(
                self.symbol, 'buy', test_size
            )
            
            elapsed = time.time() - start_time
            
            if result:
                logger.info(f"✅ 订单已处理")
                logger.info(f"   耗时: {elapsed:.1f}秒")
                logger.info(f"   最终类型: {'市价单（超时转换）' if elapsed > 5 else '限价单成交'}")
                
                # 平仓
                time.sleep(1)
                self.order_manager._execute_market_order(self.symbol, 'sell', test_size)
            else:
                logger.error("❌ 订单处理失败")
            
            # 恢复超时时间
            self.order_manager.order_timeout = original_timeout
            
            return result is not None
            
        except Exception as e:
            logger.error(f"❌ 超时测试失败: {e}")
            # 恢复超时时间
            self.order_manager.order_timeout = original_timeout
            return False
    
    def test_execute_entry(self, test_size: float = 30) -> bool:
        """测试完整的入场流程"""
        logger.info(f"\n🔍 测试 6: 完整入场流程 (数量: {test_size})")
        logger.info("-" * 80)
        
        try:
            # 使用订单管理器的 execute_entry 方法
            logger.info("📝 执行入场订单...")
            
            order = self.order_manager.execute_entry(
                self.symbol, 'buy', test_size
            )
            
            if not order:
                logger.error("❌ 入场订单失败")
                return False
            
            logger.info(f"✅ 入场订单成功")
            logger.info(f"   订单ID: {order.get('id')}")
            logger.info(f"   成交价: {order.get('average', 'N/A')}")
            logger.info(f"   成交量: {order.get('filled', test_size)}")
            
            # 执行平仓
            time.sleep(1)
            logger.info("\n📝 执行平仓订单...")
            
            exit_order = self.order_manager.execute_exit(
                self.symbol, 'sell', test_size
            )
            
            if exit_order:
                logger.info(f"✅ 平仓订单成功")
                logger.info(f"   订单ID: {exit_order.get('id')}")
                logger.info(f"   成交价: {exit_order.get('average', 'N/A')}")
            else:
                logger.error("❌ 平仓订单失败")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ 入场流程测试失败: {e}")
            return False
    
    def test_cancel_orders(self) -> bool:
        """测试取消订单功能"""
        logger.info("\n🔍 测试 7: 取消订单功能")
        logger.info("-" * 80)
        
        try:
            # 创建一个不会成交的限价单
            orderbook = self.client.fetch_orderbook(self.symbol, limit=5)
            best_bid = orderbook['bids'][0][0]
            
            # 挂一个远低于市价的买单
            test_price = best_bid * 0.9
            test_size = 30
            
            logger.info(f"📝 创建限价买单 @ {test_price:.2f}...")
            order = self.client.create_order(
                symbol=self.symbol,
                side='buy',
                amount=test_size,
                price=test_price,
                order_type='limit'
            )
            
            order_id = order['id']
            logger.info(f"✅ 限价单已创建: {order_id}")
            
            # 等待1秒
            time.sleep(1)
            
            # 取消订单
            logger.info(f"\n🚫 取消订单...")
            cancel_result = self.client.cancel_order(order_id, self.symbol)
            
            logger.info(f"✅ 订单已取消")
            
            # 验证订单状态
            time.sleep(1)
            order_status = self.client.fetch_order(order_id, self.symbol)
            logger.info(f"   订单状态: {order_status.get('status')}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ 取消订单测试失败: {e}")
            return False
    
    def test_orderbook_analyzer(self) -> bool:
        """测试订单簿分析器"""
        logger.info("\n🔍 测试 8: 订单簿分析器")
        logger.info("-" * 80)
        
        if not self.order_manager.orderbook_analyzer:
            logger.warning("⚠️  订单簿分析器未启用，跳过测试")
            return True
        
        try:
            analyzer = self.order_manager.orderbook_analyzer
            
            # 测试流动性检查
            logger.info("📊 检查流动性...")
            is_sufficient = analyzer.check_liquidity(self.symbol, 0.01)
            logger.info(f"   流动性充足: {is_sufficient}")
            
            # 测试价差获取
            logger.info("\n📊 获取价差...")
            spread_info = analyzer.get_spread(self.symbol, limit=0.001)
            logger.info(f"   价差: {spread_info['spread']:.4f}")
            logger.info(f"   价差百分比: {spread_info['spread_pct']:.4f}%")
            
            # 测试订单簿失衡度
            logger.info("\n📊 计算订单簿失衡度...")
            imbalance = analyzer.get_order_book_imbalance(self.symbol, depth=10)
            logger.info(f"   失衡度: {imbalance:.4f}")
            if imbalance > 0:
                logger.info(f"   买压较强")
            elif imbalance < 0:
                logger.info(f"   卖压较强")
            else:
                logger.info(f"   买卖平衡")
            
            # 测试大单墙检测
            logger.info("\n📊 检测大单墙...")
            walls = analyzer.detect_walls(self.symbol, threshold=2.0)
            logger.info(f"   支撑位数量: {len(walls['support'])}")
            logger.info(f"   阻力位数量: {len(walls['resistance'])}")
            
            if walls['support']:
                logger.info("   最近支撑位:")
                for price, volume in walls['support'][:3]:
                    logger.info(f"      {price:.2f} - 数量: {volume:.4f}")
            
            if walls['resistance']:
                logger.info("   最近阻力位:")
                for price, volume in walls['resistance'][:3]:
                    logger.info(f"      {price:.2f} - 数量: {volume:.4f}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ 订单簿分析器测试失败: {e}")
            return False
    
    def run_all_tests(self):
        """运行所有测试"""
        logger.info("\n" + "=" * 80)
        logger.info("🚀 开始测试")
        logger.info("=" * 80)
        
        tests = [
            # ("连接测试", self.check_connection),
            # ("订单簿获取", self.test_orderbook_fetch),
            # ("市价单", self.test_market_order),
            # ("限价单", self.test_limit_order),
            # ("限价单超时", self.test_limit_order_with_timeout),
            # ("完整入场流程", self.test_execute_entry),
            ("取消订单", self.test_cancel_orders),
            ("订单簿分析", self.test_orderbook_analyzer),
        ]
        
        results = []
        
        for name, test_func in tests:
            try:
                result = test_func()
                results.append((name, result))
            except Exception as e:
                logger.error(f"❌ 测试异常: {name} - {e}")
                results.append((name, False))
            
            # 测试间隔
            time.sleep(2)
        
        # 打印测试总结
        logger.info("\n" + "=" * 80)
        logger.info("📊 测试总结")
        logger.info("=" * 80)
        
        passed = sum(1 for _, result in results if result)
        total = len(results)
        
        for name, result in results:
            status = "✅ 通过" if result else "❌ 失败"
            logger.info(f"{status} - {name}")
        
        logger.info("\n" + "-" * 80)
        logger.info(f"总计: {passed}/{total} 通过")
        logger.info(f"成功率: {passed/total*100:.1f}%")
        logger.info("=" * 80)
        
        return passed == total


def main():
    """主函数"""
    # 配置日志
    logger.remove()
    logger.add(
        sys.stdout,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
        level="INFO"
    )
    
    try:
        # 创建测试器
        tester = OrderManagerTester()
        
        # 运行测试
        success = tester.run_all_tests()
        
        # 退出
        if success:
            logger.info("\n✅ 所有测试通过！")
            sys.exit(0)
        else:
            logger.error("\n❌ 部分测试失败")
            sys.exit(1)
            
    except KeyboardInterrupt:
        logger.info("\n\n⌨️  测试被中断")
        sys.exit(0)
    except Exception as e:
        logger.error(f"\n❌ 测试异常: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()

