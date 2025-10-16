#!/bin/bash
# 系统初始化脚本

echo "=================================="
echo "OKX Trading System - Initialization"
echo "=================================="

# 检查Python版本
echo -e "\n[1/6] Checking Python version..."
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "Python version: $python_version"

# 创建必要的目录
echo -e "\n[2/6] Creating directories..."
mkdir -p data
mkdir -p logs
mkdir -p reports
mkdir -p data/backups
echo "✓ Directories created"

# 检查配置文件
echo -e "\n[3/6] Checking configuration..."
if [ ! -f "config/config.yaml" ]; then
    echo "⚠️  config.yaml not found"
    if [ -f "config/config.example.yaml" ]; then
        echo "Copying config.example.yaml to config.yaml..."
        cp config/config.example.yaml config/config.yaml
        echo "✓ Please edit config/config.yaml with your API credentials"
    else
        echo "✗ config.example.yaml not found"
        exit 1
    fi
else
    echo "✓ config.yaml found"
fi

# 安装Python依赖
echo -e "\n[4/6] Installing Python dependencies..."
if [ -f "requirements.txt" ]; then
    pip3 install -r requirements.txt
    echo "✓ Dependencies installed"
else
    echo "✗ requirements.txt not found"
    exit 1
fi

# 初始化数据库
echo -e "\n[5/6] Initializing database..."
python3 src/utils/database.py --init
if [ $? -eq 0 ]; then
    echo "✓ Database initialized"
else
    echo "✗ Database initialization failed"
    exit 1
fi

# 测试连接
echo -e "\n[6/6] Testing system..."
python3 scripts/test_connection.py
test_result=$?

echo -e "\n=================================="
if [ $test_result -eq 0 ]; then
    echo "✓ System initialization completed successfully!"
    echo ""
    echo "Next steps:"
    echo "1. Edit config/config.yaml with your API credentials"
    echo "2. Run: python3 scripts/test_connection.py"
    echo "3. Start trading: python3 main.py"
else
    echo "⚠️  System initialization completed with warnings"
    echo "Please check the errors above and fix them"
fi
echo "=================================="

