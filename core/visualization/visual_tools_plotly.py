import os
from datetime import datetime
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from common.logger import create_log
from common.util_csv import load_stock_data
from core.visualization.visual_demo import get_sample_signal_records, get_sample_trade_records, get_sample_asset_records
from settings import stock_data_root, html_root
logger = create_log('visual_tools_plotly')


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
    计算持仓量变化和总资产变化

    参数:
        df_continuous: 连续日期的股票数据
        valid_trades: 有效的交易记录
        initial_capital: 初始资金

    返回:
        包含持仓量和总资产和平均持仓成本的DataFrame
    """
    holdings_data = pd.DataFrame(index=df_continuous.index)
    holdings_data['holdings'] = 0   # 持仓量
    holdings_data['avg_cost'] = 0.0  # 平均持仓成本

    # 检查valid_trades是否为空或不包含'date'列
    if valid_trades is None or valid_trades.empty or 'date' not in valid_trades.columns:
        # 如果没有有效的交易记录，总资产始终为初始资金
        holdings_data['total_assets'] = initial_capital
        return holdings_data

    # 初始化持仓量和资金
    total_holdings = 0
    capital = initial_capital
    holdings_value = 0
    total_cost = 0.0  # 总持仓成本
    avg_cost = 0.0    # 平均持仓成本

    # 计算持仓量变化和总资产变化
    holdings_history = []
    asset_history = []
    avg_cost_history = []


    for date in df_continuous.index:
        # 检查该日期是否有交易
        day_trades = valid_trades[valid_trades['date'] == date]
        for _, trade in day_trades.iterrows():
            commission = trade['commission']
            if trade['action'] == 'B':
                # 买入，持仓量增加
                if date in df_continuous.index.dropna():
                    buy_price = trade['price']
                    total_cost = (total_holdings * avg_cost + trade['size'] * buy_price) \
                        if total_holdings > 0 else trade['size'] * buy_price
                    total_holdings += trade['size']
                    # 重新计算平均持仓成本
                    avg_cost = total_cost / total_holdings
                    # 从资金中扣除买入金额
                    capital -= trade['size'] * buy_price + commission
            elif trade['action'] == 'S':
                # 卖出，持仓量减少
                if date in df_continuous.index.dropna():
                    sell_price = trade['price']
                    sell_size = trade['size']  # 卖出数量
                    cost_to_reduce = avg_cost * sell_size
                    total_holdings -= sell_size
                    total_cost -= cost_to_reduce

                    # 如果全部卖出，重置平均持仓成本
                    if total_holdings <= 0:
                        avg_cost = 0.0
                        total_cost = 0.0
                        total_holdings = 0
                    else:
                        avg_cost = total_cost / total_holdings
                    capital += trade['size'] * sell_price - commission

        # 保存当日持仓量
        holdings_history.append(total_holdings)
        avg_cost_history.append(avg_cost)

        # 计算总资产（现金+持仓市值）
        if date in df_continuous.index.dropna():
            current_price = df_continuous.loc[date, 'close']
            holdings_value = total_holdings * current_price
        total_assets = capital + holdings_value
        asset_history.append(total_assets)

    # 添加持仓量和总资产数据到DataFrame
    holdings_data['holdings'] = holdings_history
    holdings_data['total_assets'] = asset_history
    holdings_data['avg_cost'] = avg_cost_history

    return holdings_data


def create_trading_chart(df, valid_signals, valid_trades, holdings_data, initial_capital):
    """
    创建包含K线、信号和交易记录的图表

    参数:
        df_continuous: 连续日期的股票数据
        df: 原始股票数据
        valid_signals: 有效的信号记录
        valid_trades: 有效的交易记录
        holdings_data: 持仓量和总资产数据
        initial_capital: 初始资金

    返回:
        Plotly图表对象
    """
    # 创建四个垂直排列的图表
    fig = make_subplots(
        rows=5, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.05,
        subplot_titles=(
            'K线图与交易信号',
            '成交量',
            '持仓量变化',
            '总资产变化',
            '平均持仓成本'
        ),
        row_heights=[0.4, 0.15, 0.2, 0.25, 0.2]
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

    # 2. 添加成交量柱状图
    fig.add_trace(
        go.Bar(
            x=df.index,
            y=df['volume'],
            name='成交量',
            marker_color=['red' if close >= open else 'green' for open, close in zip(df['open'], df['close'])],
            opacity=0.7
        ),
        row=2, col=1
    )

    # 3. 添加持仓量变化曲线
    fig.add_trace(
        go.Scatter(
            x=holdings_data.index,
            y=holdings_data['holdings'],
            mode='lines',
            name='持仓量',
            line=dict(color='blue', width=2)
        ),
        row=3, col=1
    )

    # 4. 添加总资产变化曲线和初始资金参考线
    fig.add_trace(
        go.Scatter(
            x=holdings_data.index,
            y=holdings_data['total_assets'],
            mode='lines',
            name='总资产',
            line=dict(color='purple', width=2),
            connectgaps=True
        ),
        row=4, col=1
    )

    # 添加初始资金参考线
    fig.add_hline(
        y=initial_capital,
        line_dash="dash",
        line_color="gray",
        annotation_text=f"初始资金: {initial_capital}",
        annotation_position="bottom right",
        row=4, col=1
    )

    # 5. 添加平均持仓成本变化曲线
    fig.add_trace(
        go.Scatter(
            x=holdings_data.index,
            y=holdings_data['avg_cost'],
            mode='lines',
            name='平均持仓成本',
            line=dict(color='orange', width=2)
        ),
        row=5, col=1
    )

    # 6. 添加信号点标记
    # 首先检查valid_signals是否有效
    if valid_signals is not None and not valid_signals.empty and all(col in valid_signals.columns for col in ['date', 'signal_type', 'signal_description']):
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
    if valid_trades is not None and not valid_trades.empty and all(col in valid_trades.columns for col in ['date', 'action', 'size']):
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
            text=f'股票交易策略回测分析',
            font=dict(family="SimHei, Arial", size=20, color="black", weight="bold"),
            x=0.5,
            y=0.99,
            xanchor='center',
            yanchor='top'  # 设置yanchor为top，确保y值从标题顶部开始计算
        ),
        height=1500,
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

    # 成交量Y轴
    fig.update_yaxes(
        title_text="成交量",
        showgrid=True,
        gridwidth=1,
        gridcolor='LightGray',
        tickfont=dict(family="SimHei, Arial", size=12),
        row=2, col=1
    )

    # 持仓量Y轴
    fig.update_yaxes(
        title_text="持仓量(股)",
        showgrid=True,
        gridwidth=1,
        gridcolor='LightGray',
        tickfont=dict(family="SimHei, Arial", size=12),
        row=3, col=1
    )

    # 总资产Y轴
    fig.update_yaxes(
        title_text="总资产(元)",
        showgrid=True,
        gridwidth=1,
        gridcolor='LightGray',
        tickfont=dict(family="SimHei, Arial", size=12),
        row=4, col=1
    )

    # 添加平均持仓成本Y轴
    fig.update_yaxes(
        title_text="平均持仓成本(元)",
        showgrid=True,
        gridwidth=1,
        gridcolor='LightGray',
        tickfont=dict(family="SimHei, Arial", size=12),
        row=5, col=1
    )

    return fig


def save_and_show_chart(fig, output_dir=None):
    """
    保存图表并在浏览器中显示

    参数:
        fig: Plotly图表对象
        output_dir: 输出目录路径（可选）

    返回:
        保存的文件路径
    """
    # 获取当前时间作为文件名的一部分
    current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_name = f"stock_with_trades_{current_time}.html"

    # 如果指定了输出目录，则使用该目录
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        file_path = os.path.join(output_dir, file_name)
    else:
        file_path = file_name

    # 保存图表
    fig.write_html(file_path)

    # 在浏览器中显示图表
    fig.show()

    return file_path


def plotly_draw(kline_csv_path, strategy, initial_capital):
    asset_record_manager = strategy.asset_record_manager
    asset_records_df = asset_record_manager.transform_to_dataframe()
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
    if asset_records_df is None:
        asset_records_df = get_sample_asset_records()
    logger.debug(f"买/卖信号记录：")
    logger.debug(f"\n{signals_df}")
    logger.debug(f"交易记录：")
    logger.debug(f"\n{trades_df}")
    logger.debug(f"资产记录：")
    logger.debug(f"\n{asset_records_df}")

    # 4. 筛选有效的日期
    valid_signals = filter_valid_dates(df, signals_df)
    valid_trades = filter_valid_dates(df, trades_df)
    valid_assets = filter_valid_dates(df, asset_records_df)

    # 5. 计算持仓量和资产变化
    holdings_data = calculate_holdings(df_continuous, valid_trades, initial_capital)

    # 6. 创建图表
    # 从CSV路径中提取股票代码和名称
    file_name = os.path.basename(str(kline_csv_path))
    parts = file_name.split('_')
    stock_info = ""
    if len(parts) >= 2:
        stock_code = parts[0]
        stock_name = parts[1]
        stock_info = f"{stock_code} {stock_name}"

    # fig = create_trading_chart(df_continuous, df, valid_signals, valid_trades, holdings_data, valid_assets, initial_capital)
    fig = create_trading_chart(df_continuous, valid_signals, valid_trades, holdings_data, initial_capital)
    if stock_info:
        current_title = fig.layout.title.text
        fig.update_layout(
            title=dict(
                text=f'{stock_info} - {current_title}',
                font=dict(family="SimHei, Arial", size=20, color="black", weight="bold"),
                x=0.5,
                y=0.99,
                xanchor='center',
                yanchor='top'
            )
        )
    # 7. 保存和显示图表
    relative_path = str(kline_csv_path).replace(str(stock_data_root) + '/', '')
    html_file_path = html_root /relative_path.rsplit('.', 1)[0]
    logger.info(f"回测可视化图表将保存至：{html_file_path}，对应股票数据：{kline_csv_path}")
    output_path = save_and_show_chart(fig,html_file_path)

    return output_path
