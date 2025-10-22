"""
回测可视化工具（使用 mplfinance 专业金融图表库）
参考官方文档优化版本
"""
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import mplfinance as mpf
from typing import List, Optional, Dict, Tuple
from datetime import datetime
import pytz
from loguru import logger


class BacktestVisualizer:
    """回测可视化工具（mplfinance 优化版）"""
    
    @staticmethod
    def plot_results(
        df: pd.DataFrame,
        trades: List,
        output_file: str = "backtest_chart.png",
        timezone: str = 'Asia/Shanghai'
    ):
        """
        使用 mplfinance 绘制专业的回测图表
        
        Args:
            df: OHLCV 数据（必须包含 timestamp 列）
            trades: 交易记录列表
            output_file: 输出文件路径
            timezone: 时区
        """
        logger.info(f"📊 开始绘制回测图表（mplfinance）...")
        
        # 1. 准备数据
        df = df.copy()
        
        # 确保时区一致
        tz = pytz.timezone(timezone)
        if df['timestamp'].dt.tz is None:
            df['timestamp'] = df['timestamp'].dt.tz_localize('UTC').dt.tz_convert(tz)
        else:
            df['timestamp'] = df['timestamp'].dt.tz_convert(tz)
        
        # 设置 timestamp 为索引（mplfinance 要求）
        mpf_df = df.set_index('timestamp')[['open', 'high', 'low', 'close', 'volume']].copy()
        
        # 2. 准备买卖信号标记
        buy_markers, sell_markers = BacktestVisualizer._prepare_trade_signals(
            mpf_df, trades, tz
        )
        
        # 4. 创建自定义样式
        mc = mpf.make_marketcolors(
            up='green', down='red',
            edge='inherit',
            wick={'up': 'green', 'down': 'red'},
            volume={'up': 'green', 'down': 'red'},
            alpha=0.9
        )
        
        style = mpf.make_mpf_style(
            marketcolors=mc,
            gridstyle=':',
            gridcolor='lightgray',
            gridaxis='both',
            facecolor='white',
            figcolor='white',
            y_on_right=False
        )
        
        # 5. 准备附加绘图
        apds = []
        
        # 添加买入信号（使用 NaN 填充，只在买入点显示标记）
        if not buy_markers.empty and buy_markers.notna().any():
            apds.append(
                mpf.make_addplot(buy_markers, type='scatter', markersize=200,
                                marker='^', color='lime', edgecolors='darkgreen',
                                secondary_y=False, panel=0, width=2)
            )
        
        # 添加卖出信号
        if not sell_markers.empty and sell_markers.notna().any():
            apds.append(
                mpf.make_addplot(sell_markers, type='scatter', markersize=200,
                                marker='v', color='gold', edgecolors='darkred',
                                secondary_y=False, panel=0, width=2)
            )
        
        # 6. 绘制主图表
        try:
            fig, axes = mpf.plot(
                mpf_df,
                type='candle',
                style=style,
                title=f'\nALGOX Strategy Backtest Results ({timezone})',
                ylabel='Price (USDT)',
                volume=True,
                ylabel_lower='Volume',
                figsize=(24, 14),
                addplot=apds if apds else None,
                returnfig=True,
                datetime_format='%m-%d %H:%M',
                xrotation=45,
                panel_ratios=(3, 1),
                tight_layout=True
            )
            
            # 7. 在主图上添加交易连接线和盈亏标注
            ax_main = axes[0]  # 主价格图
            BacktestVisualizer._add_trade_lines_and_annotations(ax_main, mpf_df, trades, tz)
            
            # 8. 优化图表外观
            ax_main.grid(True, alpha=0.3, linestyle=':', linewidth=0.5)
            
            # 9. 保存图表
            fig.savefig(output_file, dpi=150, bbox_inches='tight', facecolor='white')
            logger.info(f"✅ 图表已保存: {output_file}")
            
            plt.close(fig)
            
        except Exception as e:
            logger.error(f"❌ 绘图失败: {e}")
            import traceback
            traceback.print_exc()
            raise
    
    @staticmethod
    def _prepare_trade_signals(
        mpf_df: pd.DataFrame,
        trades: List,
        tz
    ) -> Tuple[pd.Series, pd.Series]:
        """
        准备买卖信号标记
        返回与 mpf_df 索引对齐的 Series，使用 NaN 填充非信号点
        """
        # 创建全 NaN 的 Series
        buy_markers = pd.Series(index=mpf_df.index, dtype=float)
        sell_markers = pd.Series(index=mpf_df.index, dtype=float)
        
        for trade in trades:
            try:
                # 转换时区
                entry_time = trade.entry_time
                if entry_time.tzinfo is None:
                    entry_time = pytz.utc.localize(entry_time).astimezone(tz)
                else:
                    entry_time = entry_time.astimezone(tz)
                
                # 找到最接近的索引（使用 get_indexer 方法）
                if entry_time in mpf_df.index:
                    buy_markers.loc[entry_time] = trade.entry_price
                else:
                    # 找最近的时间索引
                    idx = mpf_df.index.get_indexer([entry_time], method='nearest')[0]
                    if idx >= 0 and idx < len(mpf_df):
                        actual_time = mpf_df.index[idx]
                        buy_markers.loc[actual_time] = trade.entry_price
                
                # 处理卖出信号
                if trade.exit_time:
                    exit_time = trade.exit_time
                    if exit_time.tzinfo is None:
                        exit_time = pytz.utc.localize(exit_time).astimezone(tz)
                    else:
                        exit_time = exit_time.astimezone(tz)
                    
                    if exit_time in mpf_df.index:
                        sell_markers.loc[exit_time] = trade.exit_price
                    else:
                        idx = mpf_df.index.get_indexer([exit_time], method='nearest')[0]
                        if idx >= 0 and idx < len(mpf_df):
                            actual_time = mpf_df.index[idx]
                            sell_markers.loc[actual_time] = trade.exit_price
                            
            except Exception as e:
                logger.warning(f"⚠️ 处理交易标记时出错: {e}")
                continue
        
        return buy_markers, sell_markers
    
    @staticmethod
    def _add_trade_lines_and_annotations(ax, mpf_df: pd.DataFrame, trades: List, tz):
        """在主图上添加交易连接线和盈亏百分比标注"""
        for trade in trades:
            if not trade.exit_time:
                continue
            
            try:
                # 转换时区
                entry_time = trade.entry_time
                exit_time = trade.exit_time
                
                if entry_time.tzinfo is None:
                    entry_time = pytz.utc.localize(entry_time).astimezone(tz)
                else:
                    entry_time = entry_time.astimezone(tz)
                
                if exit_time.tzinfo is None:
                    exit_time = pytz.utc.localize(exit_time).astimezone(tz)
                else:
                    exit_time = exit_time.astimezone(tz)
                
                # 检查时间是否在数据范围内
                if entry_time < mpf_df.index[0] or exit_time > mpf_df.index[-1]:
                    continue
                
                # 盈亏颜色
                line_color = '#10AC84' if trade.pnl > 0 else '#EE5A6F'
                
                # 1. 绘制连接线
                ax.plot(
                    [entry_time, exit_time],
                    [trade.entry_price, trade.exit_price],
                    color=line_color,
                    linestyle='--',
                    linewidth=2,
                    alpha=0.7,
                    zorder=3
                )
                
                # 2. 计算标注位置（交易中点）
                mid_time = entry_time + (exit_time - entry_time) / 2
                mid_price = (trade.entry_price + trade.exit_price) / 2
                
                # 3. 盈亏文本
                pnl_text = f"{trade.pnl_pct*100:+.2f}%"
                
                # 4. 添加标注
                ax.annotate(
                    pnl_text,
                    xy=(mid_time, mid_price),
                    xytext=(0, 25), 
                    textcoords='offset points',
                    fontsize=11,
                    color='white',
                    fontweight='bold',
                    bbox=dict(
                        boxstyle='round,pad=0.6',
                        facecolor=line_color,
                        edgecolor=line_color,
                        alpha=0.9,
                        linewidth=2
                    ),
                    ha='center',
                    va='bottom',
                    zorder=5
                )
                
            except Exception as e:
                logger.warning(f"⚠️ 添加交易线和标注时出错: {e}")
                continue
    
    @staticmethod
    def plot_equity_curve(
        equity_df: pd.DataFrame,
        output_file: str = "equity_curve.png",
        timezone: str = 'Asia/Shanghai'
    ):
        """
        绘制权益曲线（保持原有逻辑）
        
        Args:
            equity_df: 权益曲线数据
            output_file: 输出文件路径
            timezone: 时区
        """
        logger.info(f"📈 开始绘制权益曲线...")
        
        # 转换时区
        tz = pytz.timezone(timezone)
        equity_df = equity_df.copy()
        if equity_df['timestamp'].dt.tz is None:
            equity_df['timestamp'] = equity_df['timestamp'].dt.tz_localize('UTC').dt.tz_convert(tz)
        else:
            equity_df['timestamp'] = equity_df['timestamp'].dt.tz_convert(tz)
        
        # 创建图表
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(18, 11),
                                        gridspec_kw={'height_ratios': [2, 1]})
        
        # 1. 权益曲线
        ax1.plot(equity_df['timestamp'], equity_df['equity'],
                linewidth=2.5, color='#2E86DE', label='Equity', alpha=0.9)
        
        # 初始资金线
        initial_equity = equity_df['equity'].iloc[0]
        ax1.axhline(y=initial_equity, color='gray', 
                   linestyle='--', linewidth=1.5, label='Initial Capital', alpha=0.7)
        
        # 填充盈利/亏损区域
        ax1.fill_between(equity_df['timestamp'], 
                        initial_equity, 
                        equity_df['equity'],
                        where=(equity_df['equity'] >= initial_equity),
                        interpolate=True, alpha=0.25, color='#10AC84',
                        label='Profit')
        ax1.fill_between(equity_df['timestamp'],
                        initial_equity,
                        equity_df['equity'],
                        where=(equity_df['equity'] < initial_equity),
                        interpolate=True, alpha=0.25, color='#EE5A6F',
                        label='Loss')
        
        ax1.set_title('Equity Curve', fontsize=16, fontweight='bold', pad=15)
        ax1.set_ylabel('Equity (USDT)', fontsize=13, fontweight='bold')
        ax1.legend(loc='upper left', fontsize=11, framealpha=0.9)
        ax1.grid(True, alpha=0.3, linestyle=':', linewidth=0.5)
        
        # 2. 回撤
        running_max = equity_df['equity'].cummax()
        drawdown = (equity_df['equity'] - running_max) / running_max * 100
        
        ax2.fill_between(equity_df['timestamp'], 0, drawdown,
                        color='#EE5A6F', alpha=0.6)
        ax2.plot(equity_df['timestamp'], drawdown,
                color='#C23616', linewidth=1.5, alpha=0.9)
        
        ax2.set_title('Drawdown', fontsize=14, fontweight='bold', pad=10)
        ax2.set_xlabel(f'Time ({timezone})', fontsize=13, fontweight='bold')
        ax2.set_ylabel('Drawdown (%)', fontsize=13, fontweight='bold')
        ax2.grid(True, alpha=0.3, linestyle=':', linewidth=0.5)
        
        # 格式化时间轴
        import matplotlib.dates as mdates
        for ax in [ax1, ax2]:
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
            plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha='right')
        
        plt.tight_layout()
        plt.savefig(output_file, dpi=150, bbox_inches='tight', facecolor='white')
        logger.info(f"✅ 权益曲线已保存: {output_file}")
        
        plt.close()
