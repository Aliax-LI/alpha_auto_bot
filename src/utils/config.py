"""配置管理模块"""
import os
import yaml
from typing import Any, Dict
from pathlib import Path


class Config:
    """配置管理类"""
    
    _instance = None
    _config = None
    
    def __new__(cls):
        """单例模式"""
        if cls._instance is None:
            cls._instance = super(Config, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        """初始化配置"""
        if self._config is None:
            self.load_config()
    
    def load_config(self, config_path: str = None):
        """
        加载配置文件
        
        Args:
            config_path: 配置文件路径，默认为config/config.yaml
        """
        if config_path is None:
            # 获取项目根目录
            root_dir = Path(__file__).parent.parent.parent
            config_path = root_dir / "config" / "config.yaml"
        
        with open(config_path, 'r', encoding='utf-8') as f:
            self._config = yaml.safe_load(f)
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        获取配置项
        
        Args:
            key: 配置键，支持点号分隔的多级键，如 'exchange.api_key'
            default: 默认值
            
        Returns:
            配置值
        """
        keys = key.split('.')
        value = self._config
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
    
    def set(self, key: str, value: Any):
        """
        设置配置项
        
        Args:
            key: 配置键
            value: 配置值
        """
        keys = key.split('.')
        config = self._config
        
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        
        config[keys[-1]] = value
    
    def get_exchange_config(self) -> Dict[str, Any]:
        """获取交易所配置"""
        return self._config.get('exchange', {})
    
    def get_trading_config(self) -> Dict[str, Any]:
        """获取交易配置"""
        return self._config.get('trading', {})
    
    def get_risk_config(self) -> Dict[str, Any]:
        """获取风控配置"""
        return self._config.get('risk_management', {})
    
    def get_signal_config(self) -> Dict[str, Any]:
        """获取信号配置"""
        return self._config.get('signal_scoring', {})
    
    def get_indicator_config(self) -> Dict[str, Any]:
        """获取指标配置"""
        return self._config.get('indicators', {})
    
    def get_monitoring_config(self) -> Dict[str, Any]:
        """获取监控配置"""
        return self._config.get('monitoring', {})
    
    def get_database_config(self) -> Dict[str, Any]:
        """获取数据库配置"""
        return self._config.get('database', {})
    
    def get_system_config(self) -> Dict[str, Any]:
        """获取系统配置"""
        return self._config.get('system', {})
    
    @property
    def all(self) -> Dict[str, Any]:
        """获取所有配置"""
        return self._config


# 全局配置实例
config = Config()

