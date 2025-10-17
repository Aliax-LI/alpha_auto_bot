# OKX合约日内顺势回调交易系统

基于CCXT和TA-Lib的OKX合约自动化交易系统，专注于5分钟周期的日内顺势回调策略。

## ⚠️ 重要警告

**此系统使用10-20倍高杠杆，风险极高！**

- 仅用于学习和研究目的
- 建议先在沙盒环境测试
- 实盘请使用小资金（100-1000 USDT）
- 严格遵守风控规则
- 市场极端波动可能导致超额亏损
- 请充分理解风险后再使用

## 系统特点

### 核心功能

1. **智能选币**：专为日内回调交易优化，10维度精准筛选（趋势方向明确性、多周期共振、回调质量评估⭐、日内波动特征等）
2. **多周期分析**：5分钟/15分钟/1小时三周期共振确认趋势
3. **🆕 多模式入场**：智能识别4种入场模式（回调/突破/趋势跟随/反弹），动态评分，全面覆盖交易机会
4. **🆕 智能挂单预测**：100分制可行性评估+智能杠杆计算+动态止盈止损（基于ATR和支撑阻力），确保盈亏比≥1:1.68
5. **精准入场**：结合斐波那契回撤、支撑阻力、技术指标识别最佳买入点
6. **订单流分析**：实时监控大单成交、盘口深度、主动买卖比
7. **智能止损止盈**：固定/技术/移动止损，分批止盈
8. **多层级风控**：订单、账户、策略、技术级别全方位风险管理
9. **绩效复盘**：自动生成日终报告，统计分析交易表现

### 技术指标

- **趋势类**：EMA(9/21/50)、MACD、ADX、SuperTrend
- **震荡类**：RSI、KDJ
- **波动类**：ATR、布林带
- **成交量**：OBV、Volume SMA
- **形态识别**：锤子线、吞没形态、启明星等

## 系统架构

```
src/
├── core/           # 核心功能（交易所客户端、数据获取、订单管理）
├── strategy/       # 策略模块（选币、趋势分析、信号生成、仓位管理）
├── indicators/     # 技术指标（TA-Lib封装、支撑阻力、订单流）
├── risk/          # 风控模块（风险管理、止盈止损）
├── execution/     # 执行模块（交易执行器）
├── monitor/       # 监控模块（日志、绩效）
└── utils/         # 工具模块（配置、数据库）
```

## 安装部署

### 1. 环境要求

- Python 3.8+
- TA-Lib库（需要先安装C库）
- Loguru（彩色日志库，自动安装）

### 2. 安装TA-Lib

**macOS:**
```bash
brew install ta-lib
```

**Ubuntu/Debian:**
```bash
sudo apt-get install ta-lib
```

**Windows:**
下载预编译包：https://www.lfd.uci.edu/~gohlke/pythonlibs/#ta-lib

### 3. 安装Python依赖

```bash
pip install -r requirements.txt
```

### 4. 配置系统

编辑 `config/config.yaml`：

```yaml
exchange:
  api_key: YOUR_API_KEY        # OKX API Key
  secret: YOUR_SECRET           # OKX Secret
  password: YOUR_PASSWORD       # OKX Password
  proxy: http://127.0.0.1:7890 # 代理（如需要）
  sandbox_mode: true            # 沙盒模式（建议先开启）

trading:
  leverage_range: [10, 20]      # 杠杆范围
  max_positions: 3              # 最大持仓数
  risk_per_trade: 0.10          # 单笔风险10%

risk_management:
  fixed_stop_loss: 0.02         # 固定止损2%
  daily_max_loss: 0.20          # 日最大亏损20%
  consecutive_loss_limit: 3     # 连续止损限制
```

### 5. 初始化数据库

```bash
python src/utils/database.py --init
```

### 6. 测试各模块（可选）

在启动完整系统前，可以先测试各个模块：

```bash
# 快速测试选币策略（推荐，只测试几个币种）
python3 scripts/test_coin_selector_quick.py

# 完整测试选币策略（扫描所有市场，需要几分钟）
python3 scripts/test_coin_selector.py

# 测试彩色日志
python3 scripts/test_colored_log.py
```

### 7. 启动系统

```bash
python main.py
```

## 使用指南

### 交易流程

1. **系统启动**：加载配置，初始化各模块
2. **选币筛选**：每小时自动筛选Top 5-10优质币种
3. **多周期扫描**：每5分钟扫描所有选中币种
4. **趋势确认**：三周期共振确认强趋势
5. **信号生成**：多重确认机制生成交易信号（评分≥7分）
6. **订单流验证**：检查大单和盘口是否支持
7. **风控检查**：验证是否符合开仓条件
8. **仓位计算**：基于风险比例和止损距离计算仓位
9. **执行交易**：开仓并设置止损止盈
10. **持仓监控**：实时监控，触发止损/止盈自动平仓
11. **日终复盘**：每日20:00生成绩效报告

### 查看日志

系统支持**彩色日志输出**，不同类型的日志使用不同颜色：
- 🔵 **DEBUG** - 青色
- 🟢 **INFO** - 绿色  
- 🟡 **WARNING** - 黄色
- 🔴 **ERROR** - 红色
- 💙 **TRADE** - 亮蓝色（粗体）
- 💠 **SIGNAL** - 亮青色
- 🚨 **RISK_ALERT** - 亮红色（粗体）

```bash
# 实时查看交易日志（带颜色）
tail -f logs/trading.log

# 查看错误日志
tail -f logs/trading_error.log

# 查看交易记录
tail -f logs/trades.log

# 测试彩色日志效果
python3 scripts/test_colored_log.py
```

### 查看报告

每日报告保存在 `reports/` 目录：

```bash
cat reports/daily_report_20241016.txt
```

## 风控机制

### 订单级别

- 单笔最大亏损：10%账户净值
- 杠杆上限：20倍
- 止损必设置，不允许裸单

### 账户级别

- 日最大亏损：20%（触发暂停24小时）
- 周最大亏损：35%（触发暂停72小时）
- 最大持仓数：3个

### 策略级别

- 连续3次止损：降低仓位至50%
- 连续5次止损：暂停交易24小时
- 回撤超过30%：告警并建议人工审核

### 技术级别

- API请求失败重试3次
- 网络超时5秒熔断
- 订单状态轮询确认

## 策略优化建议

1. **回测验证**：先用历史数据回测策略有效性
2. **小资金测试**：实盘先用100-1000 USDT测试
3. **参数调优**：根据市场情况和回测结果调整参数
4. **风控严格**：不要擅自修改风控参数
5. **定期检查**：每周检查策略表现，不佳时暂停

## 常见问题

### 1. TA-Lib安装失败

参考官方文档：https://github.com/mrjbq7/ta-lib

### 2. API连接失败

- 检查代理设置
- 确认API密钥正确
- 检查API权限（需要交易权限）

### 3. 选币测试没有找到任何币种

可能是筛选条件太严格。尝试调整配置参数：

```yaml
# config/config.yaml
coin_selection:
  min_volume_24h: 2000000        # 降低成交量要求（200万）
  volatility_range: [0.02, 0.25] # 放宽波动率范围（2%-25%）
  min_adx: 20                    # 降低ADX要求
  liquidity_depth_threshold: 50000 # 降低流动性要求（5万）
```

### 4. 无交易信号

- 市场可能无明显趋势
- 信号评分未达到7分阈值
- 风控限制（达到亏损限额）
- 没有选中合适的币种

### 5. 系统运行缓慢

- 减少选币数量
- 增加循环间隔
- 检查网络延迟

## 📚 详细文档

### 核心文档
- [选币策略优化总结](docs/COIN_SELECTOR_OPTIMIZATION.md) ⭐ **新增** - 日内顺势回调交易选币策略详解
- [趋势信号分析指南](docs/TREND_SIGNAL_TESTING.md) ⭐ **新增** - 单币种深度技术分析工具
- [彩色日志使用说明](docs/COLORED_LOGS.md) - 日志系统配置和使用
- [测试指南](docs/TESTING.md) - 系统测试说明

### 技术指标文档
- [Ta-Lib中文文档](docs/Ta-Lib中文文档/) - 包含趋势、动量、震荡、成交量等各类指标
- [CCXT官方文档](docs/CCXT官方文档.md) - 交易所API文档

### 测试脚本
```bash
# 测试交易所连接
python scripts/test_connection.py

# 测试选币策略（包含新功能）
python scripts/test_coin_selector.py

# 趋势信号分析（单币种深度分析）⭐ 新增
python scripts/test_trend_signal.py ARB/USDT:USDT
python scripts/test_trend_signal.py BTC  # 自动补全格式

# 信号诊断工具（持续监控模式）⭐ 新增
python scripts/diagnose_signal.py ARB --watch  # 每1分钟自动检查

# 智能挂单策略预测 ⭐ 新增
python scripts/predict_entry_orders.py ARB  # 使用系统推荐杠杆
python scripts/predict_entry_orders.py ARB -l 10 -b 5000  # 指定杠杆和余额
```

---

## 免责声明

本系统仅供学习研究使用。作者不对使用本系统造成的任何损失负责。加密货币交易存在高风险，请谨慎投资。

## 许可证

MIT License

## 联系方式

如有问题，请提交Issue。

---

**再次提醒：高杠杆高风险，请谨慎使用！**

