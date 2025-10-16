# 快速启动指南

## 1. 安装TA-Lib

### macOS
```bash
brew install ta-lib
```

### Ubuntu/Debian
```bash
wget http://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-src.tar.gz
tar -xzf ta-lib-0.4.0-src.tar.gz
cd ta-lib/
./configure --prefix=/usr
make
sudo make install
```

### Windows
从 https://www.lfd.uci.edu/~gohlke/pythonlibs/#ta-lib 下载对应版本的whl文件，然后：
```bash
pip install TA_Lib-0.4.xx-cpxx-cpxxm-win_amd64.whl
```

## 2. 运行初始化脚本

```bash
chmod +x scripts/init_system.sh
./scripts/init_system.sh
```

这个脚本会：
- 创建必要的目录
- 复制配置文件模板
- 安装Python依赖
- 初始化数据库
- 测试系统连接

## 3. 配置API密钥

编辑 `config/config.yaml`：

```yaml
exchange:
  api_key: YOUR_API_KEY
  secret: YOUR_SECRET
  password: YOUR_PASSWORD
  sandbox_mode: true  # 建议先用沙盒模式测试
```

### 如何获取OKX API密钥：

1. 登录 OKX 网站
2. 进入「个人中心」 -> 「API管理」
3. 创建API密钥，记录以下信息：
   - API Key
   - Secret Key
   - Passphrase（密码）
4. 设置API权限（需要「交易」权限）
5. 绑定IP白名单（推荐）

⚠️ **重要**：首次使用请开启沙盒模式测试！

## 4. 测试连接

```bash
python3 scripts/test_connection.py
```

如果所有测试通过，会看到：
```
🎉 All tests passed! System is ready to use.
```

## 5. 启动交易系统

```bash
python3 main.py
```

系统会：
- 每小时更新币种池
- 每5分钟扫描交易机会
- 自动执行交易和风控
- 每日20:00生成复盘报告

## 6. 监控系统

### 查看实时日志
```bash
tail -f logs/trading.log
```

### 查看交易记录
```bash
tail -f logs/trades.log
```

### 查看日报
```bash
cat reports/daily_report_20241016.txt
```

## 7. 停止系统

按 `Ctrl+C` 优雅退出

## 常见问题

### Q1: TA-Lib安装失败
**A**: 参考 https://github.com/mrjbq7/ta-lib 的详细安装文档

### Q2: API连接失败
**A**: 
- 检查代理设置（如在国内需要设置proxy）
- 确认API密钥正确
- 检查API权限是否包含「交易」

### Q3: 没有交易信号
**A**:
- 市场可能无明显趋势
- 信号评分未达到阈值（默认7分）
- 检查日志了解具体原因

### Q4: 数据库错误
**A**:
```bash
rm data/trading.db
python3 src/utils/database.py --init
```

## 安全建议

1. ✅ 先在沙盒环境测试
2. ✅ 实盘使用小资金（100-1000 USDT）
3. ✅ 不要修改风控参数
4. ✅ 定期检查策略表现
5. ✅ 保管好API密钥
6. ✅ 设置API IP白名单
7. ✅ 只给API「交易」权限，不要给「提现」权限

## 参数调优

根据回测和实盘表现，可以调整 `config/config.yaml` 中的参数：

- `risk_per_trade`: 单笔风险比例（默认10%）
- `leverage_range`: 杠杆范围（默认10-20倍）
- `min_score`: 最低信号评分（默认7分）
- `daily_max_loss`: 日最大亏损（默认20%）

**建议**：每次只调整一个参数，观察至少一周后再做下一步调整。

## 获取帮助

- 查看详细文档：`README.md`
- 系统日志：`logs/trading.log`
- 错误日志：`logs/trading_error.log`

---

**祝交易顺利！记住：风险管理永远是第一位的！**

