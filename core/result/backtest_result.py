from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
import datetime
import pandas as pd


@dataclass
class BacktestMetadata:
    """回测基本信息"""
    stock_code: str  # 股票代码
    stock_name: str  # 股票名称
    market: str  # 市场类型 (e.g., 'HK', 'US', 'CN')
    start_date: datetime.date  # 回测开始日期
    end_date: datetime.date  # 回测结束日期
    initial_cash: float  # 初始资金
    strategy_name: str  # 策略名称
    strategy_params: Dict[str, Any] = field(default_factory=dict)  # 策略参数
    data_source: str = ""  # 数据来源
    backtest_id: str = ""  # 回测唯一标识
    run_time: datetime.datetime = field(default_factory=datetime.datetime.now)  # 回测运行时间


@dataclass
class StrategySignal:
    """策略信号详情"""
    date: datetime.date  # 信号日期
    signal_type: str  # 信号类型 (e.g., 'normal_buy', 'normal_sell', 'strong_buy', 'strong_sell')
    signal_description: str  # 信号描述
    price: float  # 信号产生时的价格
    indicators: Dict[str, float] = field(default_factory=dict)  # 信号产生时的指标值


@dataclass
class TradeRecord:
    """交易记录详情"""
    trade_id: str  # 交易唯一标识
    date: datetime.date  # 交易日期
    action: str  # 交易动作
    price: float  # 交易价格
    size: int  # 交易数量
    total_amount: float  # 交易总金额
    commission: float  # 佣金费用
    signal_type: str  # 触发交易的信号类型
    order_type: str = "market"  # 订单类型
    status: str = "completed"  # 订单状态


@dataclass
class PositionRecord:
    """持仓变化详情"""
    date: datetime.date  # 记录日期
    stock_code: str  # 股票代码
    shares: int  # 持仓数量
    avg_price: float  # 平均持仓价格
    current_price: float  # 当前价格
    market_value: float  # 市值
    profit_loss: float  # 盈亏金额
    profit_loss_percent: float  # 盈亏百分比


@dataclass
class AssetRecord:
    """账户资产详情"""
    date: datetime.date  # 记录日期
    total_assets: float  # 总资产
    cash: float  # 现金
    position_value: float  # 持仓市值
    daily_return: float  # 日收益率
    cumulative_return: float  # 累计收益率


@dataclass
class PerformanceMetrics:
    """回测性能指标"""
    total_return: float  # 总收益率
    max_drawdown: float  # 最大回撤
    sharpe_ratio: Optional[float] = None  # 夏普比率
    sortino_ratio: Optional[float] = None  # 索提诺比率
    calmar_ratio: Optional[float] = None  # 卡尔玛比率
    win_rate: float = 0.0  # 胜率
    total_trades: int = 0  # 总交易次数
    avg_trade_return: float = 0.0  # 平均每笔交易收益率
    profit_factor: float = 0.0  # 盈利因子


@dataclass
class BacktestResult:
    """回测结果主实体"""
    metadata: BacktestMetadata  # 回测基本信息
    signals: List[StrategySignal] = field(default_factory=list)  # 策略信号列表
    trades: List[TradeRecord] = field(default_factory=list)  # 交易记录列表
    positions: List[PositionRecord] = field(default_factory=list)  # 持仓记录列表
    assets: List[AssetRecord] = field(default_factory=list)  # 资产记录列表
    metrics: PerformanceMetrics = field(default_factory=PerformanceMetrics)  # 性能指标
    additional_info: Dict[str, Any] = field(default_factory=dict)  # 额外信息

    def add_signal(self, signal: StrategySignal):
        """添加策略信号"""
        self.signals.append(signal)

    def add_trade(self, trade: TradeRecord):
        """添加交易记录"""
        self.trades.append(trade)

    def add_position(self, position: PositionRecord):
        """添加持仓记录"""
        self.positions.append(position)

    def add_asset(self, asset: AssetRecord):
        """添加资产记录"""
        self.assets.append(asset)

    def to_dataframes(self) -> Dict[str, pd.DataFrame]:
        """将所有记录转换为DataFrame，便于分析和可视化"""
        result = {
            'metadata': pd.DataFrame([vars(self.metadata)]),
            'metrics': pd.DataFrame([vars(self.metrics)]),
            'signals': pd.DataFrame([vars(s) for s in self.signals]),
            'trades': pd.DataFrame([vars(t) for t in self.trades]),
            'positions': pd.DataFrame([vars(p) for p in self.positions]),
            'assets': pd.DataFrame([vars(a) for a in self.assets])
        }
        return result

    def save_to_csv(self, output_dir: str):
        """将所有记录保存为CSV文件"""
        import os
        os.makedirs(output_dir, exist_ok=True)

        # 保存元数据和指标
        pd.DataFrame([vars(self.metadata)]).to_csv(os.path.join(output_dir, 'metadata.csv'), index=False)
        pd.DataFrame([vars(self.metrics)]).to_csv(os.path.join(output_dir, 'metrics.csv'), index=False)

        # 保存详细记录
        if self.signals:
            pd.DataFrame([vars(s) for s in self.signals]).to_csv(os.path.join(output_dir, 'signals.csv'), index=False)
        if self.trades:
            pd.DataFrame([vars(t) for t in self.trades]).to_csv(os.path.join(output_dir, 'trades.csv'), index=False)
        if self.positions:
            pd.DataFrame([vars(p) for p in self.positions]).to_csv(os.path.join(output_dir, 'positions.csv'),
                                                                   index=False)
        if self.assets:
            pd.DataFrame([vars(a) for a in self.assets]).to_csv(os.path.join(output_dir, 'assets.csv'), index=False)

    @classmethod
    def load_from_csv(cls, input_dir: str) -> 'BacktestResult':
        """从CSV文件加载回测结果"""
        import os

        # 加载元数据
        metadata_df = pd.read_csv(os.path.join(input_dir, 'metadata.csv'))
        metadata_dict = metadata_df.iloc[0].to_dict()
        # 转换日期格式
        metadata_dict['start_date'] = pd.to_datetime(metadata_dict['start_date']).date()
        metadata_dict['end_date'] = pd.to_datetime(metadata_dict['end_date']).date()
        metadata_dict['run_time'] = pd.to_datetime(metadata_dict['run_time'])
        metadata = BacktestMetadata(**metadata_dict)

        # 加载指标
        metrics_df = pd.read_csv(os.path.join(input_dir, 'metrics.csv'))
        metrics = PerformanceMetrics(**metrics_df.iloc[0].to_dict())

        # 创建回测结果对象
        result = cls(metadata=metadata, metrics=metrics)

        # 加载详细记录
        if os.path.exists(os.path.join(input_dir, 'signals.csv')):
            signals_df = pd.read_csv(os.path.join(input_dir, 'signals.csv'))
            for _, row in signals_df.iterrows():
                row_dict = row.to_dict()
                row_dict['date'] = pd.to_datetime(row_dict['date']).date()
                result.add_signal(StrategySignal(**row_dict))

        if os.path.exists(os.path.join(input_dir, 'trades.csv')):
            trades_df = pd.read_csv(os.path.join(input_dir, 'trades.csv'))
            for _, row in trades_df.iterrows():
                row_dict = row.to_dict()
                row_dict['date'] = pd.to_datetime(row_dict['date']).date()
                result.add_trade(TradeRecord(**row_dict))

        if os.path.exists(os.path.join(input_dir, 'positions.csv')):
            positions_df = pd.read_csv(os.path.join(input_dir, 'positions.csv'))
            for _, row in positions_df.iterrows():
                row_dict = row.to_dict()
                row_dict['date'] = pd.to_datetime(row_dict['date']).date()
                result.add_position(PositionRecord(**row_dict))

        if os.path.exists(os.path.join(input_dir, 'assets.csv')):
            assets_df = pd.read_csv(os.path.join(input_dir, 'assets.csv'))
            for _, row in assets_df.iterrows():
                row_dict = row.to_dict()
                row_dict['date'] = pd.to_datetime(row_dict['date']).date()
                result.add_asset(AssetRecord(**row_dict))

        return result