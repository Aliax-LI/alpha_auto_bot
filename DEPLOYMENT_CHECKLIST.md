# 部署检查清单

## 部署前准备

### 1. 环境检查

- [ ] Python 3.8+ 已安装
- [ ] TA-Lib C库已安装
- [ ] 系统有稳定的网络连接
- [ ] （如在国内）代理已配置

### 2. 账户准备

- [ ] OKX账户已注册
- [ ] 已完成KYC验证
- [ ] 账户有足够余额（建议100-1000 USDT测试）
- [ ] 了解合约交易规则

### 3. API密钥配置

- [ ] 已创建OKX API密钥
- [ ] 已记录 API Key
- [ ] 已记录 Secret Key
- [ ] 已记录 Passphrase
- [ ] API权限仅包含「交易」，不包含「提现」
- [ ] （推荐）已绑定IP白名单

## 安装步骤

### Step 1: 克隆/下载项目

```bash
cd /path/to/your/projects
# 如果是git仓库
git clone <repository_url>
cd alpha_auto_bot
```

- [ ] 项目文件已下载
- [ ] 进入项目目录

### Step 2: 安装TA-Lib

**macOS:**
```bash
brew install ta-lib
```

**Ubuntu/Debian:**
```bash
sudo apt-get install ta-lib
```

- [ ] TA-Lib C库安装成功

### Step 3: 运行初始化脚本

```bash
chmod +x scripts/init_system.sh
./scripts/init_system.sh
```

- [ ] 目录创建成功（data/, logs/, reports/）
- [ ] Python依赖安装成功
- [ ] 数据库初始化成功

### Step 4: 配置API密钥

编辑 `config/config.yaml`:

```yaml
exchange:
  api_key: YOUR_ACTUAL_API_KEY
  secret: YOUR_ACTUAL_SECRET
  password: YOUR_ACTUAL_PASSWORD
  proxy: http://127.0.0.1:7890  # 根据实际情况设置
  sandbox_mode: true  # 首次测试必须为true
```

- [ ] API Key已填写
- [ ] Secret已填写
- [ ] Password已填写
- [ ] 代理已配置（如需要）
- [ ] sandbox_mode设为true

### Step 5: 参数配置

根据您的风险偏好调整 `config/config.yaml`:

```yaml
trading:
  leverage_range: [10, 20]     # 杠杆范围
  max_positions: 3             # 最大持仓数
  risk_per_trade: 0.10         # 单笔风险

risk_management:
  fixed_stop_loss: 0.02        # 固定止损
  daily_max_loss: 0.20         # 日最大亏损
```

- [ ] 交易参数已审核
- [ ] 风控参数已审核
- [ ] 确认参数符合您的风险承受能力

### Step 6: 测试连接

```bash
python3 scripts/test_connection.py
```

检查输出：
- [ ] ✓ Configuration test passed
- [ ] ✓ Exchange Connection test passed
- [ ] ✓ Data Fetching test passed
- [ ] ✓ Technical Indicators test passed
- [ ] ✓ Database test passed

**如果任何测试失败，请先解决问题再继续！**

## 沙盒环境测试

### Step 7: 首次启动（沙盒模式）

```bash
python3 main.py
```

观察系统运行：

- [ ] 系统成功启动
- [ ] 选币模块正常运行
- [ ] 数据获取正常
- [ ] 日志正常输出
- [ ] 无严重错误

运行时长建议：**至少24小时**

### Step 8: 检查沙盒测试结果

查看日志：
```bash
tail -f logs/trading.log
```

查看交易记录：
```bash
tail -f logs/trades.log
```

查看日报：
```bash
cat reports/daily_report_*.txt
```

检查项：
- [ ] 系统稳定运行24小时以上
- [ ] 选币逻辑正常
- [ ] 信号生成正常
- [ ] 订单执行正常（沙盒环境）
- [ ] 止损止盈正常触发
- [ ] 风控机制正常工作
- [ ] 日报生成正常

### Step 9: 分析沙盒结果

从日报中分析：
- [ ] 胜率是否 > 35%
- [ ] 盈亏比是否 > 2
- [ ] 最大回撤是否 < 30%
- [ ] 风控是否有效（连续亏损保护等）

**如果以上任何指标不符合预期，请调整策略参数后重新测试！**

## 实盘部署

### ⚠️ 重要提醒

在进入实盘前，请确认：
- [ ] 已在沙盒环境测试至少1周
- [ ] 沙盒测试结果符合预期
- [ ] 充分理解系统的风险
- [ ] 准备好可承受损失的资金
- [ ] 不会影响正常生活

### Step 10: 切换到实盘模式

编辑 `config/config.yaml`:

```yaml
exchange:
  sandbox_mode: false  # 改为false
  testnet: false       # 确保为false
```

- [ ] sandbox_mode已改为false
- [ ] 再次确认API密钥正确
- [ ] 再次确认账户有足够余额

### Step 11: 小资金实盘测试

建议初始资金：100-1000 USDT

```bash
python3 main.py
```

实盘监控：
- [ ] 系统运行正常
- [ ] 实盘订单执行成功
- [ ] 止损止盈正常工作
- [ ] 实时监控日志

运行时长建议：**至少1周**

### Step 12: 每日检查

每天执行：
- [ ] 查看日志是否有异常
- [ ] 查看日报
- [ ] 检查持仓情况
- [ ] 检查账户余额
- [ ] 评估策略表现

### Step 13: 每周评估

每周执行：
- [ ] 计算周胜率
- [ ] 计算周收益率
- [ ] 分析亏损原因
- [ ] 评估是否需要调整参数
- [ ] 决定是否继续运行

## 持续运维

### 日常监控

建议使用screen或tmux保持后台运行：

```bash
# 使用screen
screen -S trading
python3 main.py
# 按 Ctrl+A, D 退出但保持运行

# 重新连接
screen -r trading
```

- [ ] 后台运行已配置
- [ ] 知道如何查看运行状态

### 定期维护

**每天**:
- [ ] 查看交易日志
- [ ] 检查系统告警
- [ ] 查看日报

**每周**:
- [ ] 分析周报
- [ ] 备份数据库
- [ ] 评估策略表现
- [ ] 决定是否调整参数

**每月**:
- [ ] 全面性能评估
- [ ] 策略优化
- [ ] 更新系统（如有）

### 异常处理

系统异常时：
1. [ ] 立即停止系统（Ctrl+C）
2. [ ] 查看错误日志
3. [ ] 手动检查持仓
4. [ ] 必要时手动平仓
5. [ ] 分析问题原因
6. [ ] 修复后重启

### 停止条件

出现以下情况应立即停止系统：

- [ ] 周胜率 < 30%
- [ ] 连续5天亏损
- [ ] 回撤超过30%
- [ ] 系统频繁报错
- [ ] API连接不稳定
- [ ] 市场出现极端行情

## 优化建议

### 参数优化方向

如果表现不佳：

**胜率低（<35%）**:
- [ ] 提高信号评分阈值（7→8分）
- [ ] 增加趋势确认条件
- [ ] 调整时间周期

**盈亏比低（<2）**:
- [ ] 扩大止盈目标（6%→8%）
- [ ] 优化移动止损
- [ ] 延长持仓时间

**频繁止损**:
- [ ] 扩大止损距离（2%→3%）
- [ ] 优化入场点位
- [ ] 减少交易频率

## 安全检查

### 最后确认

部署前最后检查：

- [ ] API密钥已妥善保管
- [ ] 只给了交易权限，没有提现权限
- [ ] 配置文件已加入.gitignore
- [ ] 了解系统所有风险
- [ ] 准备好可承受损失的资金
- [ ] 设置了账户告警通知
- [ ] 知道如何紧急停止系统
- [ ] 知道如何手动平仓

### 风险声明确认

我已经：
- [ ] 阅读并理解所有文档
- [ ] 了解高杠杆交易的巨大风险
- [ ] 知道可能会损失全部投入资金
- [ ] 仅使用可承受损失的资金
- [ ] 不会因为亏损影响正常生活
- [ ] 对自己的交易决策负责
- [ ] 接受作者不承担任何责任

**最终确认签名**: ___________________  
**日期**: ___________________

---

## 紧急联系方式

系统相关：
- 项目文档：README.md
- 快速指南：QUICKSTART.md
- 问题反馈：提交Issue

OKX相关：
- OKX帮助中心：https://www.okx.com/support
- API文档：https://www.okx.com/docs-v5

---

**祝您交易顺利！但请永远记住：风险管理是第一位的！**

