# Release Notes

## 2026-04-16 v2.0.0

### New Features

#### Frontend Interface Redesign
- Complete modern UI with dark theme
- Unified styling system with CSS extracted from HTML files

#### Signal Analysis Page
- New signal analysis feature page
- Multi-dimensional filtering (time, stock, strategy, signal type)
- Signal distribution statistics chart
- Support batch selection of signal files for analysis

#### Background Music Player
- New standalone music player window
- Playlist management support
- Volume control

#### Scheduled Task Execution Records
- New task execution history tracking
- Paginated display
- Records execution status, duration, and processing results
- Real-time execution progress refresh

#### Enterprise WeChat Notifications
- New Webhook notification feature
- Automatically send reports to enterprise WeChat group after task completion

### Architecture Optimization

#### Modular Refactoring
- New `core/ai/` module - AI analysis features
- New `core/notification/` module - Notification features
- New `core/signal/` module - Signal processing features
- New `core/task/` module - Scheduled task features
- Strategy module split into indicator and trading submodules

#### Visualization Enhancement
- Reimplemented charts using Plotly
- Interactive chart operations
- Optimized chart loading performance

### Dependency Updates
- Python 3.13 support
- New requirements-13.txt

## 2026-04-01 v1.0.5
- Added AI analysis
  - Support model selection: gpt-4o-mini, gpt-4o, DeepSeek-R1 (without context)

## 2026-03-04 v1.0.3
- Refactored navbar for reuse
- Added background music configuration

## 2025-11-21 v1.0.2
- Added scheduled task feature (supports target list, backtest parameters, task execution time)
  - Configure scheduled tasks
  - View scheduled tasks
  - Enable/disable scheduled tasks
- Fixed startup bug

## 2025-11-15 v1.0.1
- Added strategy viewing feature with auto-registration
  - View trading strategies
  - View signal strategies

## 2025-11-12 v1.0.0
- Initial release
  - Data acquisition
    - Support CSV import
    - Support data from specified sources
      - akshare
      - baostock
      - futu (requires account for SDK)
  - Backtest execution
    - Single stock backtest
      - Specify backtest data
      - Specify initial capital
      - Specify trading commission (in settings file)
      - Specify trading slippage (in settings file)
    - Multi-stock batch backtest
      - Specify backtest data
      - Specify initial capital
      - Specify trading commission (in settings file)
      - Specify trading slippage (in settings file)
    - Historical backtest results with visualization
      - Price, volume and other basic data
      - Trading records
      - Position records
      - Trading signals
      - Total asset changes
    - Trading signal visualization
      - Aggregated by signal type
      - Filter by time, stock, signal type
      - Export to HTML
