# stock-quant 本地量化
## 环境依赖安装
- Python3 [官网](https://www.python.org/downloads/macos/)
```
MacOS:官网下载python3安装包，直接安装即可，也可以配置多个版本的python3环境，支持自由切换，
切换方式查看环境初始化部分
```

## 环境初始化
- Python3.13（推荐）
```
python3.13 -m venv venv13 
source venv13/bin/activate
pip install -r requirements-13.txt

```
- Python3.7（暂未测试）
```
python3.7 -m venv venv7 
source venv7/bin/activate
pip install -r requirements-7.txt
```
- Python环境切换
```
- deactivate
```

## 快速开始
### 1. 历史k线数据准备
```
运行core/stock/manager_xxxx，获取k线数据
```
### 2. 回测运行
```
from common.logger import create_log
from core.quant.quant_manage import run_backtest_enhanced_volume_strategy
from settings import stock_data_root

logger = create_log('test_strategy')

if __name__ == "__main__":
    # 设置csv路径
    kline_csv_path = stock_data_root / "futu/HK.00700_腾讯控股_20210104_20250127.csv"
    # 设置初始资金
    init_cash = 5000000
    # 启动回测
    run_backtest_enhanced_volume_strategy(kline_csv_path,init_cash)
```
### 3. 回测结果分析
```
回测日志会输出到logs目录下，
回测图表会输出到html目录下（历史k线、策略触发信号、策略交易记录、持仓记录、资金记录）
```
### 4. 策略参数调整
```
可以在core/strategy/indicator/indicator_strategy_common.py中调整策略信号参数（只标记交易信号，不交易）
可以在core/strategy/trader/trader_strategy_common.py中调整策略买卖参数（根据交易信号执行交易）
```

注：目前策略只有一个，对应futu中指标广场TREND策略
