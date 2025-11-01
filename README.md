[English](./README.md) | [简体中文](./README_zh-CN.md)

---
# Stock Quant - Local Backtest
## Environment Dependencies Installation
- Python3 [官网](https://www.python.org/downloads/macos/)
```
MacOS: Download the Python3 installation package from the official website and install directly. You can also configure multiple Python3 environments to support free switching.
For switching methods, see the Environment Initialization section.
```

## Environment initialization
- Python3.13（Recommended）
```
python3.13 -m venv venv13 
source venv13/bin/activate
pip install -r requirements-13.txt
```

- Python3.7（Not yet tested）
```
python3.7 -m venv venv7 
source venv7/bin/activate
pip install -r requirements-7.txt
```
- Python Environment Switching
```
- deactivate
```

## Quick Start
### 1. Historical K-line Data Preparation
```
Run core/stock/manager_xxxx to obtain K-line data
```
### 2. Backtest Execution
```
from common.logger import create_log
from core.quant.quant_manage import run_backtest_enhanced_volume_strategy, run_backtest_enhanced_volume_strategy_multi
from core.strategy.trading.volume.trading_strategy_volume import EnhancedVolumeStrategy
from settings import stock_data_root

logger = create_log('test_strategy')

if __name__ == "__main__":
    # 启动回测-单个股票
    kline_csv_path = stock_data_root / "futu/HK.00175_吉利汽车_20211028_20251027.csv"
    run_backtest_enhanced_volume_strategy(kline_csv_path, EnhancedVolumeStrategy)
    # 启动回测-批量股票
    kline_csv_path_folder = stock_data_root / "akshare"
    run_backtest_enhanced_volume_strategy_multi(kline_csv_path_folder, EnhancedVolumeStrategy)
```
### 3. Backtest Result Analysis
```
Backtest logs will be output to the logs directory

Backtest charts will be output to the html directory (historical K-line, strategy trigger signals, 
strategy trading records, position records, fund records)
```
![demo_result](./resource/img/result/demo_result_tencent_stock.png)
### 4. Strategy Parameter Adjustment
```
Adjust strategy signal parameters (only mark trading signals, no trading): Modify trading strategy-related 
parameters in the settings file

Adjust strategy buying and selling parameters (execute trades based on trading signals): Modify trading 
commission-related parameters in the settings file

Adjust initial principal: Modify trading principal parameters in the settings file
```

Disclaimer: The strategy is for learning and research purposes only. It is not recommended for use 
in real trading. We do not assume any trading risks, and all consequences are at your own risk.