# Release Note - English

## 2025-11-21 v1.0.2
- Add scheduled task function（support configuring list of target stocks, backtest parameters, task execution time, etc.）
  - Support configuring scheduled tasks
  - Support viewing scheduled tasks
  - Support enabling/disabling scheduled tasks
- Fix bug of startup

## 2025-11-15 v1.0.1
- Add strategy viewer function, support automatic registration of strategies
  - Support viewing transaction strategies
  - Support viewing signal strategies

## 2025-11-12 v1.0.0
- Initial version release
    - Data acquisition
      - Support reading from csv file
      - Support fetching data from specified data sources
        - akshare
        - baostock
        - futu, need to apply for account to use sdk
    - Backtesting execution
      - Single stock backtesting
        - Support specifying backtest data
        - Support specifying initial capital
        - Support specifying transaction fee（set in settings file）
        - Support specifying transaction slippage（set in settings file）
      - Batch backtesting of multiple stocks
        - Support specifying backtest data
        - Support specifying initial capital
        - Support specifying transaction fee（set in settings file）
        - Support specifying transaction slippage（set in settings file）
      - Historical backtest results viewing and visualization charts
        - Basic data such as stock price, volume, etc.
        - Transaction records
        - Position records
        - Transaction signals
        - Total asset changes
      - Transaction signal visualization chart
        - Aggregate by signal type, support filtering by time, stock, signal type
        - Support exporting HTML
