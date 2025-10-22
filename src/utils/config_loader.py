"""
配置加载器
从 YAML 文件加载配置，支持环境变量替换
"""
import os
import yaml
from pathlib import Path
from dotenv import load_dotenv
from typing import Dict, Any


class ConfigLoader:
    """配置加载器类"""
    
    def __init__(self, config_path: str = 'config/config.yaml'):
        """
        初始化配置加载器
        
        Args:
            config_path: 配置文件路径
        """
        self.config_path = Path(config_path)
        load_dotenv()  # 加载 .env 文件
        
    def load(self) -> Dict[str, Any]:
        """
        加载配置文件
        
        Returns:
            配置字典
        """
        if not self.config_path.exists():
            raise FileNotFoundError(f"配置文件不存在: {self.config_path}")
        
        with open(self.config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        # 替换环境变量
        config = self._replace_env_vars(config)
        
        return config
    
    def _replace_env_vars(self, config: Any) -> Any:
        """
        递归替换配置中的环境变量
        
        Args:
            config: 配置对象
            
        Returns:
            替换后的配置对象
        """
        if isinstance(config, dict):
            return {k: self._replace_env_vars(v) for k, v in config.items()}
        elif isinstance(config, list):
            return [self._replace_env_vars(item) for item in config]
        elif isinstance(config, str) and config.startswith('${') and config.endswith('}'):
            # 提取环境变量名
            env_var = config[2:-1]
            value = os.getenv(env_var)
            if value is None:
                raise ValueError(f"环境变量未设置: {env_var}")
            return value
        else:
            return config


def load_config(config_path: str = 'config/config.yaml') -> Dict[str, Any]:
    """
    加载配置的便捷函数
    
    Args:
        config_path: 配置文件路径
        
    Returns:
        配置字典
    """
    loader = ConfigLoader(config_path)
    return loader.load()

