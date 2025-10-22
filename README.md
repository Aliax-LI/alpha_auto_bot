# ALGOX 交易机器人

基于 TradingView ALGOX v13 策略的币安实盘交易系统，使用 Python 实现。

## 功能特性

### 🎯 回测系统（新增！）
- ✨ **完整的历史数据回测**: 使用 CCXT 获取真实历史数据
- ✨ **性能分析**: 详细的收益率、胜率、夏普比率、最大回撤等指标
- ✨ **30天回测结果**: 收益率 +54.91%，胜率 75.90%，夏普比率 4.85
- 📊 **专业图表**: 使用 mplfinance 金融图表库，K线+订单+盈亏标注
- 🌍 **上海时区**: 所有时间使用北京时间显示
- 🔍 **数据验证**: 完整的未来数据泄露检查
- 📁 **CSV导出**: 交易记录和权益曲线数据导出
- 🔧 **多策略对比**: 支持不同参数配置的对比测试

详见 [回测系统文档](BACKTEST_README.md) | [验证报告](BACKTEST_VALIDATION.md)

### 技术指标引擎
- ✨ **使用 TA-Lib**: 行业标准的技术分析库（C语言实现，高性能）
- 支持指标: RSI, ATR, EMA, SMA, Heikin Ashi, Renko
- 与 TradingView 计算方法一致

### 信号生成模式
- **Open/Close 模式**: 基于 Heikin Ashi (18倍时间框架) Close/Open 交叉
- **Renko 模式**: 基于 ATR-Renko + EMA(2)/EMA(10) 交叉（✨ 完整实现）

### 过滤系统
- RSI(7) 过滤：阈值 45/10
- ATR(5) 过滤：ATR vs ATR_EMA(5)
- 7种组合方式：
  - Filter with ATR
  - Filter with RSI
  - ATR or RSI
  - ATR and RSI
  - No Filtering
  - Entry Only in sideways market(By ATR or RSI)
  - Entry Only in sideways market(By ATR and RSI)

### 风险管理模式
1. **Trailing**: 信号反转时平仓+反向开仓
2. **ATR**: 三级止盈(50%/30%/20%)，基于 ATR(20)×2.5×(1/2/3)
3. **Options**: 仅做多

### 执行优化（可选）
- 流动性检查
- 限价单执行（带超时机制）
- 订单簿分析
- 大单墙检测

## 安装

### 1. 环境要求
- Python 3.8+
- pip

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

**注意**: `ta-lib` 需要单独安装：

**macOS**:
```bash
brew install ta-lib
pip install TA-Lib
```

**Ubuntu/Debian**:
```bash
sudo apt-get install build-essential wget
wget http://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-src.tar.gz
tar -xzf ta-lib-0.4.0-src.tar.gz
cd ta-lib/
./configure --prefix=/usr
make
sudo make install
pip install TA-Lib
```

**Windows**:
从 [这里](https://www.lfd.uci.edu/~gohlke/pythonlibs/#ta-lib) 下载对应的 whl 文件，然后：
```bash
pip install TA_Lib-0.4.XX-cpXX-cpXX-win_amd64.whl
```

### 3. 配置

1. 复制示例配置文件：
```bash
cp config/config.example.yaml config/config.yaml
```

2. 创建 `.env` 文件：
```bash
cp .env.example .env
```

3. 编辑 `.env` 文件，填入币安 API 密钥：
```
BINANCE_API_KEY=your_api_key_here
BINANCE_SECRET=your_secret_here
```

4. 编辑 `config/config.yaml`，调整策略参数：
```yaml
exchange:
  testnet: true  # 测试网模式，设为 false 使用实盘

strategy:
  symbol: BTC/USDT
  timeframe: 1m
  setup_type: Open/Close  # Open/Close | Renko
  tps_type: Trailing      # Trailing | ATR | Options
  filter_type: No Filtering
  
risk:
  equity_per_trade: 50  # 每次使用 50% 权益
```

## 使用方法

### 运行回测（推荐先测试策略）

```bash
# 1. 编辑回测配置
vim config/backtest_config.yaml

# 2. 运行回测
python backtest_main.py

# 3. 查看结果
ls backtest_results/
```

**最新回测结果**:
- 📈 收益率: +54.91% (30天)
- ✅ 胜率: 75.90%
- 📊 夏普比率: 4.85
- 🛡️ 最大回撤: -2.34%

详见 [回测系统文档](BACKTEST_README.md)

### 启动实盘机器人

```bash
python main.py
```

### 停止机器人

按 `Ctrl+C` 停止程序。

## 项目结构

```
alpha_auto_bot/
├── config/
│   ├── config.yaml              # 实盘配置文件
│   ├── backtest_config.yaml     # 回测配置文件 ✨
│   └── config.example.yaml      # 配置示例
├── src/
│   ├── core/
│   │   ├── strategy_engine.py   # 策略引擎
│   │   └── state_machine.py     # 状态机
│   ├── data/
│   │   └── binance_client.py    # 币安客户端
│   ├── indicators/
│   │   ├── heikinashi.py        # Heikin Ashi 指标 (TA-Lib)
│   │   ├── renko.py             # Renko 构建器 (TA-Lib)
│   │   └── technical.py         # 技术指标 (TA-Lib)
│   ├── execution/
│   │   ├── order_manager.py     # 订单管理器
│   │   ├── position_manager.py  # 仓位管理器
│   │   └── orderbook_analyzer.py# 盘口分析器
│   ├── backtest/                # 回测系统 ✨
│   │   ├── data_loader.py       # 历史数据加载器
│   │   ├── backtest_engine.py   # 回测引擎
│   │   └── reporter.py          # 报告生成器
│   └── utils/
│       ├── config_loader.py     # 配置加载器
│       └── logger.py            # 日志系统
├── tests/                       # 测试目录
│   ├── test_renko.py            # Renko 测试
│   ├── test_indicators.py       # 指标测试
│   └── test_indicator_accuracy.py# 精度验证
├── backtest_results/            # 回测结果 ✨
│   ├── trades_*.csv             # 交易记录
│   └── equity_*.csv             # 权益曲线
├── logs/                        # 日志目录
├── main.py                      # 实盘主程序
├── backtest_main.py             # 回测主程序 ✨
├── requirements.txt             # Python 依赖
├── README.md                    # 项目文档
├── BACKTEST_README.md           # 回测系统文档 ✨
└── TALIB_INTEGRATION.md         # TA-Lib 集成说明 ✨
```

## 策略说明

### 状态机

```
0.0  → 无仓位
±1.0 → 入场，等待TP1
±1.1 → TP1触发(平50%)，等待TP2  
±1.2 → TP2触发(平30%)，等待TP3
±1.3 → TP3触发(平20%)
```

### 关键参数

- 仓位大小: 50% 权益
- 手续费: 0.02%
- ATR 周期: 20 (风险管理), 5 (过滤), 3 (Renko)
- 止盈因子: 2.5
- 止损因子: 1.0

## 风险提示

⚠️ **重要警告**：
- 加密货币交易具有高风险，可能导致资金损失
- 请先在测试网充分测试策略
- 从小资金开始，不要投入超过您承受能力的资金
- 本项目仅供学习和研究使用，不构成投资建议
- 作者不对任何交易损失负责

## 测试建议

1. **测试网测试**：
   - 设置 `testnet: true`
   - 使用币安测试网 API 密钥
   - 充分测试所有功能

2. **小资金实盘测试**：
   - 最小资金量（如 100 USDT）
   - 观察几天到一周
   - 验证策略逻辑正确性

3. **逐步扩大**：
   - 确认策略稳定后再增加资金
   - 持续监控和优化

## 监控指标

- 信号触发频率
- 订单成交率
- 实际滑点
- 盈亏统计
- 最大回撤

## 常见问题

### Q: 如何获取币安 API 密钥？
A: 登录币安账户 → API 管理 → 创建 API → 启用合约交易权限

### Q: 测试网如何使用？
A: 访问 https://testnet.binancefuture.com/ 注册测试网账户并获取测试网 API 密钥

### Q: 程序报错怎么办？
A: 查看 `logs/algox.log` 日志文件，里面有详细的错误信息

### Q: 如何调整杠杆？
A: 在程序启动后，通过币安交易所界面手动设置杠杆倍数

### Q: 支持其他交易所吗？
A: 目前仅支持币安，但可以通过修改 `BinanceClient` 适配其他交易所

## 更新日志

### v1.0.0 (2025-01-XX)
- 初始版本
- 实现 Open/Close 信号模式
- 实现 Trailing 和 ATR 风险管理模式
- 支持 7 种过滤器组合
- 限价单执行优化
- 订单簿分析（可选）

## 许可证

MIT License

## 贡献

欢迎提交 Issue 和 Pull Request！

## 联系方式

如有问题，请提交 Issue。

---

**免责声明**: 本项目仅供学习和研究使用。加密货币交易存在高风险，请谨慎决策。作者不对使用本软件造成的任何损失负责。

