"""数据存储模块"""
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Boolean, Text, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from ..utils.config import config

Base = declarative_base()


class Trade(Base):
    """交易记录表"""
    __tablename__ = 'trades'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(String(100), unique=True, nullable=False)
    symbol = Column(String(50), nullable=False)
    side = Column(String(10), nullable=False)  # long/short
    action = Column(String(10), nullable=False)  # open/close
    
    entry_price = Column(Float)
    exit_price = Column(Float)
    stop_loss = Column(Float)
    take_profit = Column(Float)
    
    amount = Column(Float, nullable=False)
    leverage = Column(Float, nullable=False)
    
    fee = Column(Float, default=0)
    pnl = Column(Float)
    pnl_percentage = Column(Float)
    
    open_time = Column(DateTime)
    close_time = Column(DateTime)
    
    status = Column(String(20))  # open/closed/cancelled
    close_reason = Column(String(50))  # stop_loss/take_profit/manual/time_stop
    
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class Signal(Base):
    """信号记录表"""
    __tablename__ = 'signals'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(50), nullable=False)
    signal_type = Column(String(10), nullable=False)  # long/short
    score = Column(Float, nullable=False)
    
    # 评分明细
    score_details = Column(JSON)
    
    # 价格信息
    price = Column(Float)
    support_level = Column(Float)
    resistance_level = Column(Float)
    
    # 是否执行
    executed = Column(Boolean, default=False)
    not_executed_reason = Column(String(200))
    
    # 关联的订单ID
    order_id = Column(String(100))
    
    created_at = Column(DateTime, default=datetime.now)


class MarketData(Base):
    """市场数据表"""
    __tablename__ = 'market_data'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(50), nullable=False)
    timeframe = Column(String(10), nullable=False)
    
    timestamp = Column(DateTime, nullable=False)
    open = Column(Float, nullable=False)
    high = Column(Float, nullable=False)
    low = Column(Float, nullable=False)
    close = Column(Float, nullable=False)
    volume = Column(Float, nullable=False)
    
    # 技术指标
    indicators = Column(JSON)
    
    created_at = Column(DateTime, default=datetime.now)


class SystemLog(Base):
    """系统日志表"""
    __tablename__ = 'system_logs'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    level = Column(String(20), nullable=False)  # INFO/WARNING/ERROR
    category = Column(String(50))  # trade/signal/risk/system
    message = Column(Text, nullable=False)
    details = Column(JSON)
    
    created_at = Column(DateTime, default=datetime.now)


class Database:
    """数据库管理类"""
    
    _instance = None
    _engine = None
    _session_maker = None
    
    def __new__(cls):
        """单例模式"""
        if cls._instance is None:
            cls._instance = super(Database, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        """初始化数据库"""
        if self._engine is None:
            self._init_database()
    
    def _init_database(self):
        """初始化数据库连接"""
        db_config = config.get_database_config()
        db_type = db_config.get('type', 'sqlite')
        
        if db_type == 'sqlite':
            # 创建数据目录
            root_dir = Path(__file__).parent.parent.parent
            data_dir = root_dir / "data"
            data_dir.mkdir(exist_ok=True)
            
            db_path = root_dir / db_config.get('path', 'data/trading.db')
            db_url = f"sqlite:///{db_path}"
        else:
            raise ValueError(f"Unsupported database type: {db_type}")
        
        self._engine = create_engine(db_url, echo=False)
        self._session_maker = sessionmaker(bind=self._engine)
        
        # 创建所有表
        Base.metadata.create_all(self._engine)
    
    def get_session(self) -> Session:
        """获取数据库会话"""
        return self._session_maker()
    
    def add_trade(self, trade_data: Dict[str, Any]) -> Trade:
        """
        添加交易记录
        
        Args:
            trade_data: 交易数据
            
        Returns:
            交易记录对象
        """
        session = self.get_session()
        try:
            trade = Trade(**trade_data)
            session.add(trade)
            session.commit()
            session.refresh(trade)
            return trade
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
    
    def update_trade(self, order_id: str, update_data: Dict[str, Any]) -> Optional[Trade]:
        """
        更新交易记录
        
        Args:
            order_id: 订单ID
            update_data: 更新数据
            
        Returns:
            更新后的交易记录
        """
        session = self.get_session()
        try:
            trade = session.query(Trade).filter(Trade.order_id == order_id).first()
            if trade:
                for key, value in update_data.items():
                    setattr(trade, key, value)
                session.commit()
                session.refresh(trade)
            return trade
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
    
    def get_open_trades(self) -> List[Trade]:
        """获取所有未平仓交易"""
        session = self.get_session()
        try:
            return session.query(Trade).filter(Trade.status == 'open').all()
        finally:
            session.close()
    
    def get_trades_by_date(self, start_date: datetime, end_date: datetime = None) -> List[Trade]:
        """
        获取指定日期范围的交易
        
        Args:
            start_date: 开始日期
            end_date: 结束日期，默认为当前时间
            
        Returns:
            交易记录列表
        """
        if end_date is None:
            end_date = datetime.now()
        
        session = self.get_session()
        try:
            return session.query(Trade).filter(
                Trade.created_at >= start_date,
                Trade.created_at <= end_date
            ).all()
        finally:
            session.close()
    
    def add_signal(self, signal_data: Dict[str, Any]) -> Signal:
        """添加信号记录"""
        session = self.get_session()
        try:
            signal = Signal(**signal_data)
            session.add(signal)
            session.commit()
            session.refresh(signal)
            return signal
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
    
    def add_market_data(self, market_data: Dict[str, Any]) -> MarketData:
        """添加市场数据"""
        session = self.get_session()
        try:
            data = MarketData(**market_data)
            session.add(data)
            session.commit()
            session.refresh(data)
            return data
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
    
    def add_log(self, level: str, category: str, message: str, details: Dict = None):
        """添加系统日志"""
        session = self.get_session()
        try:
            log = SystemLog(
                level=level,
                category=category,
                message=message,
                details=details
            )
            session.add(log)
            session.commit()
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
    
    def backup(self):
        """备份数据库"""
        db_config = config.get_database_config()
        if db_config.get('type') == 'sqlite':
            import shutil
            root_dir = Path(__file__).parent.parent.parent
            db_path = root_dir / db_config.get('path', 'data/trading.db')
            backup_dir = root_dir / "data" / "backups"
            backup_dir.mkdir(exist_ok=True, parents=True)
            
            backup_file = backup_dir / f"trading_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
            shutil.copy2(db_path, backup_file)


# 全局数据库实例
database = Database()


# 命令行工具
if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--init':
        print("Initializing database...")
        db = Database()
        print("Database initialized successfully!")

