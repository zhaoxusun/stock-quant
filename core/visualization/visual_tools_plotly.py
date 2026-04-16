import os
from datetime import datetime
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from common.logger import create_log
from common.time_key import get_current_time
from common.util_csv import load_stock_data
from core.visualization.visual_demo import get_sample_signal_records, get_sample_trade_records, get_sample_asset_records
from settings import stock_data_root, html_root

logger = create_log('visual_tools_plotly')

try:
    from settings import chart_show_switch

    switch = chart_show_switch
except ImportError:
    switch = False
    logger.info("未导入chart_show_switch，设为False, 执行回测后浏览器不显示标的回测结果图表，请手动查看结果")


def prepare_continuous_dates(df):
    """
    创建连续的日期范围，确保K线图不间断显示

    参数:
        df: 原始股票数据DataFrame

    返回:
        包含连续日期的DataFrame
    """
    # 获取数据的最小和最大日期
    min_date = df.index.min()
    max_date = df.index.max()
    # 创建包含所有日期的连续索引（包括周末和节假日）
    continuous_dates = pd.date_range(start=min_date, end=max_date, freq='D')
    # 使用reindex将原始数据填充到连续日期索引中，非交易日数据为NaN
    df_continuous = df.reindex(continuous_dates)
    return df_continuous


def filter_valid_dates(df, records):
    """
    筛选有效的日期，确保记录中的日期在股票数据中存在

    参数:
        df: 股票数据DataFrame
        records: 记录DataFrame（信号或交易）

    返回:
        有效的记录DataFrame
    """
    # 检查records是否为空或是否包含'date'列
    if records is None or records.empty:
        logger.warning("警告：记录为空，无法筛选有效日期")
        return pd.DataFrame()

    if 'date' not in records.columns:
        logger.warning("警告：记录中不包含'date'列，无法筛选有效日期")
        # 尝试查找可能的日期列
        date_like_columns = [col for col in records.columns if 'date' in col.lower()]
        if date_like_columns:
            date_column = date_like_columns[0]
            logger.info(f"使用列'{date_column}'作为日期列")
            valid_dates = df.index  # 股票数据中所有存在的日期
            valid_records = records[records[date_column].isin(valid_dates)].copy()
            return valid_records
        return records  # 如果没有找到类似日期的列，返回原始记录

    valid_dates = df.index  # 股票数据中所有存在的日期
    valid_records = records[records['date'].isin(valid_dates)].copy()

    # 提示缺失的日期
    missing_dates = records[~records['date'].isin(valid_dates)]['date']
    if not missing_dates.empty:
        logger.info(f"警告：以下日期在股票数据中不存在，已跳过：{missing_dates.dt.strftime('%Y-%m-%d').tolist()}")

    return valid_records


def calculate_holdings(df_continuous, valid_trades, initial_capital):
    """
    计算持仓量变化、总资产、持仓成本变化

    参数:
        df_continuous: 连续日期的股票数据
        valid_trades: 有效的交易记录
        initial_capital: 初始资金

    返回:
        包含持仓量和总资产和持仓成本的DataFrame
    """
    holdings_data = pd.DataFrame(index=df_continuous.index)
    holdings_data['holdings'] = 0  # 持仓量
    holdings_data['adjusted_cost'] = 0.0  # 持仓成本

    # 检查valid_trades是否为空或不包含'date'列
    if valid_trades is None or valid_trades.empty or 'date' not in valid_trades.columns:
        # 如果没有有效的交易记录，总资产始终为初始资金
        holdings_data['total_assets'] = initial_capital
        return holdings_data

    # 初始化持仓量和资金
    total_holdings = 0  # 当前持仓量
    capital = initial_capital  # 剩余资金
    holdings_value = 0
    total_cost = 0.0  # 总持仓成本
    adjusted_cost = 0.0  # 持仓成本

    # 计算持仓量变化和总资产变化
    holdings_history = []
    asset_history = []
    adjusted_cost_history = []

    for date in df_continuous.index:
        # 检查该日期是否有交易
        day_trades = valid_trades[valid_trades['date'] == date]
        for _, trade in day_trades.iterrows():
            if trade['action'] == 'B':
                # 买入，持仓量增加
                if date in df_continuous.index.dropna():
                    buy_price = trade['price']
                    buy_size = trade['size']
                    commission = trade['commission']
                    current_cost = buy_size * buy_price + commission
                    total_cost += current_cost
                    capital -= current_cost
                    total_holdings += buy_size
                    adjusted_cost = total_cost / total_holdings
            elif trade['action'] == 'S':
                # 卖出，持仓量减少
                if date in df_continuous.index.dropna():
                    sell_price = trade['price']
                    sell_size = trade['size']
                    commission = trade['commission']
                    current_cost = sell_size * sell_price - commission
                    total_cost -= current_cost
                    capital += current_cost
                    total_holdings -= sell_size
                    # 如果全部卖出，重置持仓成本
                    if total_holdings <= 0:
                        adjusted_cost = 0.0
                        total_cost = 0.0
                        total_holdings = 0
                    else:
                        adjusted_cost = total_cost / total_holdings

        # 保存当日持仓量
        holdings_history.append(total_holdings)
        adjusted_cost_history.append(adjusted_cost)

        # 计算总资产（现金+持仓市值）
        if date in df_continuous.index.dropna():
            current_price = df_continuous.loc[date, 'close']
            holdings_value = total_holdings * current_price
        total_assets = capital + holdings_value
        asset_history.append(total_assets)

    # 添加持仓量和总资产数据到DataFrame
    holdings_data['holdings'] = holdings_history
    holdings_data['total_assets'] = asset_history
    holdings_data['adjusted_cost'] = adjusted_cost_history

    return holdings_data


def calculate_performance_metrics(strategy, initial_capital, df):
    """
    计算绩效指标

    参数:
        strategy: 策略实例
        initial_capital: 初始资金
        df: 股票数据

    返回:
        包含绩效指标的字典
    """
    metrics = {}

    # 收益情况
    try:
        total_return = list(strategy.analyzers.total_return.get_analysis().values())[0] * 100
        final_cash = strategy.broker.getvalue()
        # 计算年化收益
        start_date = df.index[0]
        end_date = df.index[-1]
        days = (end_date - start_date).days
        annual_return = (pow((1 + total_return / 100), 365 / days) - 1) * 100 if days > 0 else 0
        metrics['total_return'] = total_return
        metrics['annual_return'] = annual_return
        metrics['final_cash'] = final_cash
    except Exception as e:
        logger.warning(f"计算收益指标失败：{str(e)}")
        metrics['total_return'] = 0
        metrics['annual_return'] = 0
        metrics['final_cash'] = initial_capital

    # 风险指标
    try:
        max_dd = strategy.analyzers.drawdown.get_analysis()["max"]["drawdown"]
        # 计算Calmar比率
        try:
            calmar_ratio = metrics['annual_return'] / max_dd if max_dd > 0 else 0
        except:
            calmar_ratio = 0
        metrics['max_drawdown'] = max_dd
        metrics['calmar_ratio'] = calmar_ratio
    except Exception as e:
        logger.warning(f"计算风险指标失败：{str(e)}")
        metrics['max_drawdown'] = 0
        metrics['calmar_ratio'] = 0

    # 交易统计
    try:
        trade_stats = strategy.analyzers.trade_analyzer.get_analysis()
        total_trades = trade_stats["total"]["total"]
        won_trades = trade_stats.get("won", {}).get("total", 0)
        lost_trades = trade_stats.get("lost", {}).get("total", 0)
        win_rate = (won_trades / total_trades) * 100 if total_trades > 0 else 0
        # 计算盈亏比
        try:
            avg_win = trade_stats.get("won", {}).get("pnl", {}).get("average", 0)
            avg_loss = abs(trade_stats.get("lost", {}).get("pnl", {}).get("average", 1))
            profit_factor = avg_win / avg_loss if avg_loss > 0 else 0
        except:
            profit_factor = 0
        metrics['total_trades'] = total_trades

        metrics['won_trades'] = won_trades
        metrics['lost_trades'] = lost_trades
        metrics['win_rate'] = win_rate
        metrics['profit_factor'] = profit_factor
    except Exception as e:
        logger.warning(f"计算交易统计失败：{str(e)}")
        metrics['total_trades'] = 0
        metrics['won_trades'] = 0
        metrics['lost_trades'] = 0
        metrics['win_rate'] = 0
        metrics['profit_factor'] = 0

    # 夏普比率
    try:
        sharpe_ratio = strategy.analyzers.sharpe_ratio.get_analysis().get("sharperatio", 0)
        # 确保sharpe_ratio不是None
        sharpe_ratio = sharpe_ratio if sharpe_ratio is not None else 0
        metrics['sharpe_ratio'] = sharpe_ratio
    except Exception as e:
        logger.warning(f"计算夏普比率失败：{str(e)}")
        metrics['sharpe_ratio'] = 0

    # 信号统计
    try:
        metrics['buy_signals_count'] = strategy.buy_signals_count
        metrics['sell_signals_count'] = strategy.sell_signals_count
        metrics['executed_buys_count'] = strategy.executed_buys_count
        metrics['executed_sells_count'] = strategy.executed_sells_count
    except Exception as e:
        logger.warning(f"计算信号统计失败：{str(e)}")
        metrics['buy_signals_count'] = 0
        metrics['sell_signals_count'] = 0
        metrics['executed_buys_count'] = 0
        metrics['executed_sells_count'] = 0

    return metrics


def create_trading_chart(chart_title_prefix, df, valid_signals, valid_trades, holdings_data, initial_capital):
    """
    创建包含K线、信号和交易记录的图表

    参数:
        chart_title_prefix: 图表标题前缀
        df: 原始股票数据处理后得到连续日期的股票数据
        valid_signals: 有效的信号记录
        valid_trades: 有效的交易记录
        holdings_data: 持仓量和总资产数据
        initial_capital: 初始资金

    返回:
        Plotly图表对象
    """
    # 数据清理：处理NaN值
    df = df.copy()
    df = df.ffill().fillna(0)  # 前向填充再用0填充剩余NaN值

    # 持仓数据清理
    holdings_data = holdings_data.copy()
    holdings_data = holdings_data.ffill().fillna(0)

    # 创建五个垂直排列的图表
    fig = make_subplots(
        rows=6, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.07,
        subplot_titles=(
            'K线图与交易信号',
            '全景K图',  # 全景K线视图，用于时间范围选择，方便其他图联动
            '成交量',
            '持仓量变化',
            '总资产变化',
            '持仓成本'
        ),
        row_heights=[0.35, 0.1, 0.15, 0.15, 0.15, 0.15]
    )

    # 1. 添加K线图
    fig.add_trace(
        go.Candlestick(
            x=df.index,
            open=df['open'],
            high=df['high'],
            low=df['low'],
            close=df['close'],
            name='K线',
            increasing_line_color='red',  # 上涨为红色
            decreasing_line_color='green'  # 下跌为绿色
        ),
        row=1, col=1
    )

    # 2. 添加全景视图占位图（第二行）- 不显示实际数据
    fig.add_trace(
        go.Bar(
            x=df.index,
            y=df['volume'],
            name='全景K图',
            marker=dict(
                color=['red' if close >= open else 'green' for open, close in zip(df['open'], df['close'])]
            ),
        ),
        row=2, col=1
    )

    # 3. 添加成交量柱状图
    fig.add_trace(
        go.Bar(
            x=df.index,
            y=df['volume'],
            name='成交量',
            marker=dict(
                color=['red' if close >= open else 'green' for open, close in zip(df['open'], df['close'])],
                opacity=0.8  # 增加不透明度，使颜色更鲜艳
            ),
        ),
        row=3, col=1
    )

    # 4. 添加持仓量变化曲线
    # 处理NaN值
    holdings_clean = holdings_data['holdings'].ffill().fillna(0)
    fig.add_trace(
        go.Scatter(
            x=holdings_data.index,
            y=holdings_clean,
            mode='lines',
            name='持仓量',
            line=dict(color='blue', width=2)
        ),
        row=4, col=1
    )

    # 5. 添加总资产变化曲线和初始资金参考线
    # 处理NaN值
    assets_clean = holdings_data['total_assets'].ffill().fillna(0)
    fig.add_trace(
        go.Scatter(
            x=holdings_data.index,
            y=assets_clean,
            mode='lines',
            name='总资产',
            line=dict(color='purple', width=2),
            connectgaps=True
        ),
        row=5, col=1
    )

    # 添加初始资金参考线
    fig.add_hline(
        y=initial_capital,
        line_dash="dash",
        line_color="gray",
        annotation_text=f"初始资金: {initial_capital}",
        annotation_position="bottom right",
        row=5, col=1
    )

    # 6. 添加持仓成本变化曲线
    # 处理NaN值
    cost_clean = holdings_data['adjusted_cost'].ffill().fillna(0)
    fig.add_trace(
        go.Scatter(
            x=holdings_data.index,
            y=cost_clean,
            mode='lines',
            name='持仓成本',
            line=dict(color='orange', width=2)
        ),
        row=6, col=1
    )

    # 6. 添加信号点标记
    # 首先检查valid_signals是否有效
    if valid_signals is not None and not valid_signals.empty and all(
            col in valid_signals.columns for col in ['date', 'signal_type', 'signal_description']):
        # 清理信号数据中的NaN值
        valid_signals = valid_signals.dropna(subset=['date']).copy()
        # 只保留日期在df索引范围内的信号
        valid_signals = valid_signals[valid_signals['date'].isin(df.index)]

        # 强买入信号（绿色，圆形）
        strong_buy_signals = valid_signals[valid_signals['signal_type'] == 'strong_buy']
        if not strong_buy_signals.empty:
            fig.add_trace(
                go.Scatter(
                    x=strong_buy_signals['date'],
                    y=df.loc[strong_buy_signals['date'], 'low'] * 0.95,
                    mode='markers+text',
                    name='强买入信号',
                    marker=dict(
                        symbol='circle',
                        color='green',
                        size=10,
                        line=dict(width=1, color='black')
                    ),
                    text=['强多' for _ in range(len(strong_buy_signals))],
                    textposition='bottom center',
                    texttemplate='%{text}',
                    textfont=dict(family="SimHei, Arial", size=12, color="darkgreen", weight="bold"),
                    hovertemplate='日期: %{x}<br>信号: %{customdata[0]}<extra></extra>',
                    customdata=strong_buy_signals[['signal_description']].values,
                    showlegend=True
                ), row=1, col=1
            )

        # 买入信号（浅绿色，圆形）
        buy_signals = valid_signals[valid_signals['signal_type'] == 'normal_buy']
        if not buy_signals.empty:
            fig.add_trace(
                go.Scatter(
                    x=buy_signals['date'],
                    y=df.loc[buy_signals['date'], 'low'] * 0.95,
                    mode='markers+text',
                    name='买入信号',
                    marker=dict(
                        symbol='circle',
                        color='lightgreen',
                        size=10,
                        line=dict(width=1, color='black')
                    ),
                    text=['多' for _ in range(len(buy_signals))],
                    textposition='bottom center',
                    texttemplate='%{text}',
                    textfont=dict(family="SimHei, Arial", size=12, color="darkgreen", weight="bold"),
                    hovertemplate='日期: %{x}<br>信号: %{customdata[0]}<extra></extra>',
                    customdata=buy_signals[['signal_description']].values,
                    showlegend=True
                ), row=1, col=1
            )

        # 强卖出信号（红色，圆形）
        strong_sell_signals = valid_signals[valid_signals['signal_type'] == 'strong_sell']
        if not strong_sell_signals.empty:
            fig.add_trace(
                go.Scatter(
                    x=strong_sell_signals['date'],
                    y=df.loc[strong_sell_signals['date'], 'high'] * 1.05,
                    mode='markers+text',
                    name='强卖出信号',
                    marker=dict(
                        symbol='circle',
                        color='red',
                        size=10,
                        line=dict(width=1, color='black')
                    ),
                    text=['强空' for _ in range(len(strong_sell_signals))],
                    textposition='top center',
                    texttemplate='%{text}',
                    textfont=dict(family="SimHei, Arial", size=12, color="darkred", weight="bold"),
                    hovertemplate='日期: %{x}<br>信号: %{customdata[0]}<extra></extra>',
                    customdata=strong_sell_signals[['signal_description']].values,
                    showlegend=True
                ), row=1, col=1
            )

        # 卖出信号（浅红色，圆形）
        sell_signals = valid_signals[valid_signals['signal_type'] == 'normal_sell']
        if not sell_signals.empty:
            fig.add_trace(
                go.Scatter(
                    x=sell_signals['date'],
                    y=df.loc[sell_signals['date'], 'high'] * 1.05,
                    mode='markers+text',
                    name='卖出信号',
                    marker=dict(
                        symbol='circle',
                        color='lightcoral',
                        size=10,
                        line=dict(width=1, color='black')
                    ),
                    text=['空' for _ in range(len(sell_signals))],
                    textposition='top center',
                    texttemplate='%{text}',
                    textfont=dict(family="SimHei, Arial", size=12, color="darkred", weight="bold"),
                    hovertemplate='日期: %{x}<br>信号: %{customdata[0]}<extra></extra>',
                    customdata=sell_signals[['signal_description']].values,
                    showlegend=True
                ), row=1, col=1
            )
    else:
        logger.warning("警告：信号记录为空或不包含必要的列，无法添加信号标记")

    # 7. 添加实际交易点标记
    # 首先检查valid_trades是否有效
    if valid_trades is not None and not valid_trades.empty and all(
            col in valid_trades.columns for col in ['date', 'action', 'size']):
        # 清理交易数据中的NaN值
        valid_trades = valid_trades.dropna(subset=['date']).copy()
        # 只保留日期在df索引范围内的交易
        valid_trades = valid_trades[valid_trades['date'].isin(df.index)]

        # 买入操作（B，上三角形，绿色，K线下方）
        buy_trades = valid_trades[valid_trades['action'] == 'B']
        if not buy_trades.empty:
            fig.add_trace(
                go.Scatter(
                    x=buy_trades['date'],
                    y=df.loc[buy_trades['date'], 'close'] * 0.90,
                    mode='markers+text',
                    name='买入操作(B)',
                    marker=dict(
                        symbol='triangle-up',
                        color='green',
                        size=12,
                        line=dict(width=1, color='black')
                    ),
                    text=['B' for _ in range(len(buy_trades))],
                    textposition='bottom center',
                    texttemplate='%{text}',
                    textfont=dict(family="SimHei, Arial", size=12, color="darkgreen", weight="bold"),
                    hovertemplate='日期: %{x}<br>操作: 买入(B)<br>数量: %{customdata[0]}股<br>价格: %{y:.2f}<extra></extra>',
                    customdata=buy_trades[['size']].values
                ), row=1, col=1
            )

        # 卖出操作（S，下三角形，红色，K线上方）
        sell_trades = valid_trades[valid_trades['action'] == 'S']
        if not sell_trades.empty:
            fig.add_trace(
                go.Scatter(
                    x=sell_trades['date'],
                    y=df.loc[sell_trades['date'], 'close'] * 1.10,
                    mode='markers+text',
                    name='卖出操作(S)',
                    marker=dict(
                        symbol='triangle-down',
                        color='red',
                        size=12,
                        line=dict(width=1, color='black')
                    ),
                    text=['S' for _ in range(len(sell_trades))],
                    textposition='top center',
                    texttemplate='%{text}',
                    textfont=dict(family="SimHei, Arial", size=12, color="darkred", weight="bold"),
                    hovertemplate='日期: %{x}<br>操作: 卖出(S)<br>数量: %{customdata[0]}股<br>价格: %{y:.2f}<extra></extra>',
                    customdata=sell_trades[['size']].values
                ), row=1, col=1
            )
    else:
        logger.warning("警告：交易记录为空或不包含必要的列，无法添加交易标记")

    # 8. 设置图表布局
    fig.update_layout(
        title=dict(
            text=f'{chart_title_prefix} - 股票交易策略回测分析',
            font=dict(family="SimHei, Arial", size=20, color="black", weight="bold"),
            x=0.5,
            y=0.99,
            xanchor='center',
            yanchor='top'  # 设置yanchor为top，确保y值从标题顶部开始计算
        ),
        height=1800,  # 调整高度，因为指标表格现在在图表下方
        width=1600,
        margin=dict(l=120, r=80, t=120, b=80),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            font=dict(family="SimHei, Arial", size=12)
        ),
        hovermode='x unified',
        font=dict(family="SimHei, Arial", size=12)
    )

    # 设置X轴
    fig.update_xaxes(
        title_text="日期",
        showgrid=True,
        gridwidth=1,
        gridcolor='LightGray',
        tickfont=dict(family="SimHei, Arial", size=12)
    )

    # 设置Y轴
    # K线图Y轴
    fig.update_yaxes(
        title_text="价格",
        showgrid=True,
        gridwidth=1,
        gridcolor='LightGray',
        tickfont=dict(family="SimHei, Arial", size=12),
        row=1, col=1
    )

    # 全景视图Y轴 - 隐藏Y轴标签和刻度
    fig.update_yaxes(
        title_text="全景K图",
        showgrid=True,
        showticklabels=False,  # 隐藏刻度标签
        showline=False,  # 隐藏轴线
        gridwidth=1,
        gridcolor='LightGray',
        tickfont=dict(family="SimHei, Arial", size=12),
        row=2, col=1
    )

    # 成交量Y轴
    fig.update_yaxes(
        title_text="成交量",
        showgrid=True,
        gridwidth=1,
        gridcolor='LightGray',
        tickfont=dict(family="SimHei, Arial", size=12),
        row=3, col=1
    )

    # 持仓量Y轴
    fig.update_yaxes(
        title_text="持仓量(股)",
        showgrid=True,
        gridwidth=1,
        gridcolor='LightGray',
        tickfont=dict(family="SimHei, Arial", size=12),
        row=4, col=1
    )

    # 总资产Y轴
    fig.update_yaxes(
        title_text="总资产",
        showgrid=True,
        gridwidth=1,
        gridcolor='LightGray',
        tickfont=dict(family="SimHei, Arial", size=12),
        row=5, col=1
    )

    # 添加持仓成本Y轴
    fig.update_yaxes(
        title_text="持仓成本",
        showgrid=True,
        gridwidth=1,
        gridcolor='LightGray',
        tickfont=dict(family="SimHei, Arial", size=12),
        row=6, col=1
    )

    return fig


def save_and_show_chart(fig, file_name, output_dir=None, metrics=None):
    """
    保存图表并在浏览器中显示

    参数:
        fig: Plotly图表对象
        output_dir: 输出目录路径（可选）
        metrics: 绩效指标字典（可选）

    返回:
        保存的文件路径
    """

    # 如果指定了输出目录，则使用该目录
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        file_path = os.path.join(output_dir, file_name)
    else:
        file_path = file_name

    # 生成指标表格HTML
    metrics_table = ""
    if metrics:
        metrics_table = f"""
        <div class="card" style="margin: 20px 0;">
            <div class="card-header">
                <h3 style="margin: 0; font-size: 1.2em;">策略绩效指标</h3>
            </div>
            <div class="card-body">
                <table class="table">
                    <thead>
                        <tr>
                            <th style="text-align: left;">指标</th>
                            <th style="text-align: right;">值</th>
                            <th style="text-align: left;">说明</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr>
                            <td>总收益率</td>
                            <td style="text-align: right;">{metrics['total_return']:.2f}%</td>
                            <td>策略整体盈利或亏损的百分比</td>
                        </tr>
                        <tr>
                            <td>年化收益</td>
                            <td style="text-align: right;">{metrics['annual_return']:.2f}%</td>
                            <td>按年计算的平均收益率</td>
                        </tr>
                        <tr>
                            <td>最终资金</td>
                            <td style="text-align: right;">{metrics['final_cash']:,.2f} 港元</td>
                            <td>回测结束时的资金总额</td>
                        </tr>
                        <tr>
                            <td>最大回撤</td>
                            <td style="text-align: right;">{metrics['max_drawdown']:.2f}%</td>
                            <td>策略历史上最大的亏损幅度</td>
                        </tr>
                        <tr>
                            <td>Calmar比率</td>
                            <td style="text-align: right;">{metrics['calmar_ratio']:.2f}</td>
                            <td>年化收益与最大回撤的比值，衡量风险调整后的收益</td>
                        </tr>
                        <tr>
                            <td>夏普比率</td>
                            <td style="text-align: right;">{metrics.get('sharpe_ratio', 0):.2f}</td>
                            <td>超额收益与波动率的比值，衡量风险调整后的收益</td>
                        </tr>
                        <tr>
                            <td>总交易次数</td>
                            <td style="text-align: right;">{metrics['total_trades']}</td>
                            <td>所有已平仓完整订单</td>
                        </tr>
                        <tr>
                            <td>胜率</td>
                            <td style="text-align: right;">{metrics['win_rate']:.2f}%</td>
                            <td>平仓后净利润＞0 的交易占总交易次数的百分比</td>
                        </tr>
                        <tr>
                            <td>盈亏比</td>
                            <td style="text-align: right;">{metrics['profit_factor']:.2f}</td>
                            <td>平均盈利与平均亏损的比值</td>
                        </tr>
                        <tr>
                            <td>买入信号</td>
                            <td style="text-align: right;">{metrics['buy_signals_count']}</td>
                            <td>策略生成的买入信号数量</td>
                        </tr>
                        <tr>
                            <td>卖出信号</td>
                            <td style="text-align: right;">{metrics['sell_signals_count']}</td>
                            <td>策略生成的卖出信号数量</td>
                        </tr>
                        <tr>
                            <td>实际买入</td>
                            <td style="text-align: right;">{metrics['executed_buys_count']}</td>
                            <td>实际执行的买入交易次数</td>
                        </tr>
                        <tr>
                            <td>实际卖出</td>
                            <td style="text-align: right;">{metrics['executed_sells_count']}</td>
                            <td>实际执行的卖出交易次数</td>
                        </tr>
                    </tbody>
                </table>
            </div>
        </div>
        """

    # 生成完整的HTML文件
    chart_html = fig.to_html(full_html=False, include_plotlyjs='cdn')
    full_html = f"""
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>股票交易策略回测分析</title>
        <style>
            :root {{
                --primary-color: #0a4b78; /* 深蓝色主色调 */
                --secondary-color: #165d8c; /* 辅助蓝色 */
                --accent-color: #2980b9; /* 强调蓝色 */
                --success-color: #2ecc71; /* 绿色（上涨） */
                --danger-color: #e74c3c; /* 红色（下跌） */
                --warning-color: #f39c12; /* 黄色（警告） */
                --info-color: #3498db; /* 信息蓝色 */
                --text-color: #e0e0e0; /* 主要文本颜色 */
                --text-secondary: #a0a0a0; /* 次要文本颜色 */
                --background-color: #121212; /* 深色背景 */
                --surface-color: #1e1e1e; /* 表面颜色 */
                --card-bg: #252525; /* 卡片背景 */
                --border-color: #333333; /* 边框颜色 */
                --hover-color: #353535; /* 悬停颜色 */
            }}

            * {{
                box-sizing: border-box;
                margin: 0;
                padding: 0;
            }}

            body {{
                font-family: "Segoe UI", "Microsoft YaHei", "Arial", sans-serif;
                background-color: var(--background-color);
                color: var(--text-color);
                line-height: 1.6;
                font-size: 14px;
            }}

            .container {{
                max-width: 1600px;
                margin: 20px auto;
                padding: 0 20px;
            }}

            .chart-container {{
                background-color: var(--card-bg);
                border-radius: 6px;
                padding: 20px;
                margin: 20px 0;
                box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
            }}

            .metrics-container {{
                margin-top: 20px;
            }}

            .card {{
                background-color: var(--card-bg);
                color: var(--text-color);
                border: 1px solid var(--border-color);
                border-radius: 6px;
                box-shadow: 0 4px 12px rgba(0, 0, 0, 0.25);
                transition: all 0.3s ease;
                overflow: hidden;
            }}

            .card-header {{
                background-color: var(--primary-color);
                color: white;
                font-weight: 600;
                padding: 15px 20px;
                border-bottom: 1px solid var(--border-color);
                display: flex;
                align-items: center;
                justify-content: space-between;
            }}

            .card-body {{
                padding: 20px;
            }}

            .table {{
                background-color: var(--card-bg);
                border-radius: 6px;
                overflow: hidden;
                box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
                border-collapse: collapse;
                width: 100%;
            }}

            .table thead {{
                background-color: var(--primary-color);
                color: white;
            }}

            .table th, .table td {{
                padding: 12px 15px;
                text-align: left;
                border-bottom: 1px solid var(--border-color);
            }}

            .table tbody tr {{
                transition: background-color 0.2s ease;
            }}

            .table tbody tr:hover {{
                background-color: var(--hover-color);
            }}

            .table tbody tr:last-child td {{
                border-bottom: none;
            }}

            h1 {{
                color: var(--text-color);
                text-align: center;
                margin: 20px 0;
                font-size: 2em;
            }}
        </style>
    </head>
    <body class="result-viewer">
        <div class="container">
            <h1>股票交易策略回测分析</h1>
            <div class="chart-container">
                {chart_html}
            </div>
            <div class="metrics-container">
                {metrics_table}
            </div>
        </div>
    </body>
    </html>
    """

    # 保存完整的HTML文件
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(full_html)

    # 在浏览器中显示图表
    if switch:
        import webbrowser
        webbrowser.open('file://' + file_path)

    return file_path


def plotly_draw(kline_csv_path, strategy, initial_capital, html_file_name, html_file_path):
    signal_record_manager = strategy.indicator.signal_record_manager
    signals_df = signal_record_manager.transform_to_dataframe()
    trade_record_manager = strategy.trade_record_manager
    trades_df = trade_record_manager.transform_to_dataframe()
    # 1. 加载股票数据
    df = load_stock_data(kline_csv_path)

    # 2. 准备连续日期数据
    df_continuous = prepare_continuous_dates(df)

    # 3. 获取信号记录和交易记录和资产记录
    if signals_df is None:
        signals_df = get_sample_signal_records()
    if trades_df is None:
        trades_df = get_sample_trade_records()
    logger.debug(f"买/卖信号记录：")
    logger.debug(f"\n{signals_df}")
    logger.debug(f"交易记录：")
    logger.debug(f"\n{trades_df}")

    # 4. 筛选有效的日期
    valid_signals = filter_valid_dates(df, signals_df)
    valid_trades = filter_valid_dates(df, trades_df)

    # 5. 计算持仓量和资产变化
    holdings_data = calculate_holdings(df_continuous, valid_trades, initial_capital)

    # 6. 计算绩效指标
    metrics = calculate_performance_metrics(strategy, initial_capital, df)
    # 在控制台输出绩效指标
    logger.info("策略绩效指标:")
    logger.info(f"总收益率: {metrics['total_return']:.2f}% (策略整体盈利或亏损的百分比)")
    logger.info(f"年化收益: {metrics['annual_return']:.2f}% (按年计算的平均收益率)")
    logger.info(f"最终资金: {metrics['final_cash']:,.2f} 港元 (回测结束时的资金总额)")
    logger.info(f"最大回撤: {metrics['max_drawdown']:.2f}% (策略历史上最大的亏损幅度)")
    logger.info(f"Calmar比率: {metrics['calmar_ratio']:.2f} (年化收益与最大回撤的比值，衡量风险调整后的收益)")
    logger.info(f"夏普比率: {metrics.get('sharpe_ratio', 0):.2f} (超额收益与波动率的比值，衡量风险调整后的收益)")
    logger.info(f"总交易次数: {metrics['total_trades']} (实际成交的买入次数+卖出次数)")
    logger.info(f"胜率: {metrics['win_rate']:.2f}% (盈利交易次数占总交易次数的百分比)")
    logger.info(f"盈亏比: {metrics['profit_factor']:.2f} (平均盈利与平均亏损的比值)")
    logger.info(f"买入信号: {metrics['buy_signals_count']} (策略生成的买入信号数量)")
    logger.info(f"卖出信号: {metrics['sell_signals_count']} (策略生成的卖出信号数量)")
    logger.info(f"实际买入: {metrics['executed_buys_count']} (实际执行的买入交易次数)")
    logger.info(f"实际卖出: {metrics['executed_sells_count']} (实际执行的卖出交易次数)")

    # 7. 创建图表
    # 从CSV路径中提取股票代码和名称
    file_name = os.path.basename(str(kline_csv_path))
    parts = file_name.split('_')
    stock_info = ""
    if len(parts) >= 2:
        stock_code = parts[0]
        stock_name = parts[1]
        stock_info = f"{stock_code} {stock_name}"

    fig = create_trading_chart(stock_info, df_continuous, valid_signals, valid_trades, holdings_data, initial_capital)
    # 8. 保存和显示图表
    output_path = save_and_show_chart(fig, html_file_name, html_file_path, metrics)

    return output_path