[English](README_en.md) | [简体中文](README.md)

---
# 股票量化 - 本地回测

![演示动图](https://zhaoxusun.github.io/stock-quant/resource/img/usage.gif)
如果演示视频没加载出来，可以查看[这里](https://zhaoxusun.github.io/stock-quant/resource/img/usage.gif)

## 环境依赖安装
- Python3 [下载](https://www.python.org/downloads/macos/)
```
MacOS/Windows/Linux:官网下载python3安装包，直接安装即可，也可以配置多个版本的python3环境，支持自由切换，
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

#### 1.1 准备数据（csv格式，该步骤可选，自行准备数据，或者通过前端页面获取数据）
```
csv数据格式
A股数据格式
date,open,high,low,close,volume,amount,stock_code,stock_name,market
2021-11-01,0.81,0.82,0.81,0.82,54463399,54086664.0,SH.510210,上证指数ETF,CN
2021-11-02,0.82,0.82,0.8,0.81,71456299,70368907.0,SH.510210,上证指数ETF,CN
2021-11-03,0.81,0.81,0.8,0.8,36854399,36085912.0,SH.510210,上证指数ETF,CN
2021-11-04,0.81,0.81,0.8,0.81,47489699,46692877.0,SH.510210,上证指数ETF,CN

港股数据格式
date,open,high,low,close,volume,amount,stock_code,stock_name,market
2021-11-01,432.36,432.75,421.29,425.76,22649546,10654645504.0,00700,港股00700,HK
2021-11-02,434.49,437.79,416.64,420.32,33005998,15457739520.0,00700,港股00700,HK
2021-11-03,418.38,426.15,414.3,425.18,19362664,8976079360.0,00700,港股00700,HK
2021-11-04,431.19,437.6,429.84,436.63,16440685,7856704512.0,00700,港股00700,HK
2021-11-05,428.09,430.22,421.49,423.62,20019234,9394663936.0,00700,港股00700,HK
2021-11-08,416.44,420.32,410.04,420.13,22340751,10272692480.0,00700,港股00700,HK

美股数据格式
date,open,high,low,close,volume,amount,stock_code,stock_name,market
2021-11-01,434.07,434.46,431.96,433.88,2914779.0,,US.IVV,IVV,US
2021-11-02,434.02,435.99,433.86,435.7,3282790.0,,US.IVV,IVV,US
2021-11-03,435.08,438.91,434.62,438.55,2916130.0,,US.IVV,IVV,US
2021-11-04,439.15,440.8,438.78,440.69,3039933.0,,US.IVV,IVV,US
```

### 2 运行回测（两种方式）

#### 2.1 带前端页面
- 启动前端页面
  - frontend/frontend_app.py
- 前端页面上执行回测
  - 获取目标股票的历史k线数据（支持A股、港股、美股）
  - 选择要回测的股票（支持A股、港股、美股）
  - 选择要回测的策略（当前代码中策略你可以在core/strategy/trading/volume/trading_strategy_volume.py中查看）
    - 或者通过代码添加你的策略（参考core/strategy/trading/volume/trading_strategy_volume.py中的EnhancedVolumeStrategy类）
  - 点击“回测”按钮，即可执行回测
  - ![index_page](https://zhaoxusun.github.io/stock-quant/resource/img/index.png)
  - 回测结果会在前端页面上展示
  - ![result_page](https://zhaoxusun.github.io/stock-quant/resource/img/backtest_result_1.png)
  - ![result_page](https://zhaoxusun.github.io/stock-quant/resource/img/backtest_result_2.png)

#### 2.2 直接运行代码（不带前端页面）
- 代码启动回测
  - 参考如下代码

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

### 3. 回测结果分析
#### 3.1 分析回测结果
```
回测日志会输出到logs目录下
回测图表会输出到html目录下（历史k线、策略触发信号、策略交易记录、持仓记录、资金记录）
```
![demo_result](https://zhaoxusun.github.io/stock-quant/resource/img/result/demo_result_tencent_stock.png)

#### 3.2 分析交易信号结果（回测产生的交易信号，不是交易记录）
```
回测后会产生交易信号，交易信号按照信号纬度聚合，聚合后支持按照策略、股票名称、时间、信号类型筛选，支持下载html
```
![demo_signal](https://zhaoxusun.github.io/stock-quant/resource/img/signal_result.png)

### 4. 策略参数调整
```
调整策略信号参数（只标记交易信号，不交易）：settings文件中修改交易策略相关参数
调整策略买卖参数（根据交易信号执行交易）：settings文件中修改交易佣金相关参数
调整初始本金：settings文件中修改交易本金参数
```

[![Star History Chart](https://api.star-history.com/svg?repos=zhaoxusun/stock-quant&type=date&legend=top-left)](https://www.star-history.com/#zhaoxusun/stock-quant&type=date&legend=top-left)

声明：策略仅用于学习和研究，不建议在真实交易中使用，不承担任何交易风险，后果自负