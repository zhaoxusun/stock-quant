import os
import sys
from datetime import datetime
import pandas as pd
from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_cors import CORS
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from core.strategy.strategy_manager import global_strategy_manager

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 导入项目模块
from common.logger import create_log
from core.quant.quant_manage import run_backtest_enhanced_volume_strategy, run_backtest_enhanced_volume_strategy_multi
from core.strategy.trading.volume.enhanced_volume import EnhancedVolumeStrategy
from settings import stock_data_root, html_root
from core.visualization.visual_tools_plotly import prepare_continuous_dates, filter_valid_dates, calculate_holdings
from common.util_csv import load_stock_data

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

# 初始化Flask应用
app = Flask(__name__)
CORS(app)
logger = create_log('quant_frontend')

# 支持的数据源
DATA_SOURCES = ['akshare', 'baostock', 'futu']


@app.route('/')
def index():
    """主页，显示数据源和股票选择界面"""
    strategies = global_strategy_manager.get_strategy_names()
    return render_template('index.html', data_sources=DATA_SOURCES, strategies=strategies)


@app.route('/get_stocks/<source>')
def get_stocks(source):
    """获取指定数据源下的所有股票文件"""
    if source not in DATA_SOURCES:
        return jsonify({'error': 'Invalid data source'}), 400

    source_path = stock_data_root / source
    if not os.path.exists(source_path):
        return jsonify({'error': 'Source directory not found'}), 404

    stocks = []
    try:
        for file in os.listdir(source_path):
            if file.endswith('.csv'):
                # 解析文件名获取股票信息
                parts = file.split('_')
                if len(parts) >= 2:
                    stock_code = parts[0]
                    stock_name = parts[1]
                    stocks.append({
                        'file': file,
                        'code': stock_code,
                        'name': stock_name
                    })
    except Exception as e:
        logger.error(f"Error reading stocks: {str(e)}")
        return jsonify({'error': str(e)}), 500

    return jsonify(stocks)


@app.route('/run_backtest', methods=['POST'])
def run_backtest():
    """运行回测"""
    try:
        data = request.json
        source = data.get('source')
        stock_file = data.get('stock_file')
        is_batch = data.get('is_batch', False)
        init_cash = float(data.get('init_cash', 5000000))
        strategy_name = data.get('strategy')

        # 验证策略名称
        strategy_class = global_strategy_manager.get_strategy(strategy_name)
        if not strategy_class:
            return jsonify({'error': f'Invalid strategy: {strategy_name}'}), 400

        if source not in DATA_SOURCES:
            return jsonify({'error': 'Invalid data source'}), 400

        if is_batch:
            # 批量回测
            folder_path = stock_data_root / source
            run_backtest_enhanced_volume_strategy_multi(str(folder_path), strategy_class, init_cash)
            return jsonify({'success': True, 'message': 'Batch backtest completed'})
        else:
            # 单个股票回测
            if not stock_file:
                return jsonify({'error': 'Stock file is required'}), 400

            file_path = stock_data_root / source / stock_file
            run_backtest_enhanced_volume_strategy(str(file_path), strategy_class, init_cash)

            # 构建回测结果的HTML路径，添加策略名称作为最后一层
            relative_path = f"{source}/{stock_file.rsplit('.', 1)[0]}/{strategy_class.__name__}"
            # 查找最新的回测结果文件
            result_dir = html_root / source / stock_file.rsplit('.', 1)[0] / strategy_class.__name__
            if os.path.exists(result_dir):
                files = sorted(os.listdir(result_dir), reverse=True)
                if files:
                    latest_file = files[0]
                    result_path = f"{relative_path}/{latest_file}"
                    return jsonify({
                        'success': True,
                        'message': 'Backtest completed',
                        'result_path': result_path
                    })

            return jsonify({'success': True, 'message': 'Backtest completed, but no result file found'})

    except Exception as e:
        logger.error(f"Error running backtest: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/get_backtest_results')
def get_backtest_results():
    """获取所有回测结果"""
    results = []
    try:
        # 获取分页和筛选参数
        page = int(request.args.get('page', 1))
        page_size = int(request.args.get('page_size', 20))
        start_idx = (page - 1) * page_size

        # 获取筛选参数
        stock_filter = request.args.get('stock', '')
        source_filter = request.args.get('source', '')
        date_filter = request.args.get('date', '')
        strategy_filter = request.args.get('strategy', '')  # 新增：获取策略筛选参数

        # 遍历所有数据源
        for source in DATA_SOURCES:
            # 应用数据源筛选
            if source_filter and source != source_filter:
                continue

            source_path = html_root / source
            if os.path.exists(source_path):
                # 遍历每个股票的回测结果
                for stock_folder in os.listdir(source_path):
                    # 应用股票名称筛选
                    if stock_filter and stock_filter.lower() not in stock_folder.lower():
                        continue

                    stock_path = source_path / stock_folder
                    if os.path.isdir(stock_path):
                        # 新增：遍历策略文件夹
                        for strategy_folder in os.listdir(stock_path):
                            # 应用策略筛选
                            if strategy_filter and strategy_filter.lower() not in strategy_folder.lower():
                                continue

                            strategy_path = stock_path / strategy_folder
                            if os.path.isdir(strategy_path):
                                # 在策略文件夹中查找回测结果文件
                                for file in os.listdir(strategy_path):
                                    if file.startswith('stock_with_trades_') and file.endswith('.html'):
                                        # 解析文件名获取时间信息
                                        timestamp_part = file.replace('stock_with_trades_', '').replace('.html', '')
                                        try:
                                            run_time = datetime.strptime(timestamp_part, '%Y%m%d_%H%M%S')

                                            # 应用日期筛选（精确到天）
                                            if date_filter:
                                                result_date = run_time.strftime('%Y-%m-%d')
                                                if result_date != date_filter:
                                                    continue

                                            results.append({
                                                'source': source,
                                                'stock': stock_folder,
                                                'file': file,
                                                'strategy': strategy_folder,  # 新增：添加策略名称
                                                'run_time': run_time.strftime('%Y-%m-%d %H:%M:%S'),
                                                'path': f"{source}/{stock_folder}/{strategy_folder}/{file}"
                                                # 更新：路径包含策略名称
                                            })
                                        except ValueError:
                                            continue

        # 按运行时间排序
        results.sort(key=lambda x: x['run_time'], reverse=True)

        # 分页处理
        total_results = len(results)
        paginated_results = results[start_idx:start_idx + page_size]

        # 返回分页结果和元数据
        return jsonify({
            'results': paginated_results,
            'total': total_results,
            'page': page,
            'page_size': page_size,
            'total_pages': (total_results + page_size - 1) // page_size
        })

    except Exception as e:
        logger.error(f"Error getting backtest results: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/show_result/<path:file_path>')
def show_result(file_path):
    """显示回测结果图表"""
    try:
        # 获取实际文件路径
        actual_path = os.path.join(html_root, file_path)
        if not os.path.exists(actual_path):
            return jsonify({'error': 'Result file not found'}), 404

        # 读取HTML文件内容
        with open(actual_path, 'r', encoding='utf-8') as f:
            html_content = f.read()

        return render_template('result_viewer.html', html_content=html_content, file_path=file_path)

    except Exception as e:
        logger.error(f"Error showing result: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/static/<path:filename>')
def serve_static(filename):
    """提供静态文件"""
    return send_from_directory('static', filename)


if __name__ == '__main__':
    # 确保templates和static目录存在
    for dir_name in ['templates', 'static']:
        dir_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), dir_name)
        if not os.path.exists(dir_path):
            os.makedirs(dir_path)

    # 启动Flask应用
    app.run(host='0.0.0.0', port=5000, debug=True)