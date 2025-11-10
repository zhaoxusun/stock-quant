import os
import sys
import futu as ft
from datetime import datetime
import pandas as pd
from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_cors import CORS
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from core.stock import manager_baostock, manager_akshare, manager_futu
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
# 导入数据获取相关模块

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
                for stock_dir in os.listdir(source_path):
                    # 应用股票筛选
                    if stock_filter and stock_filter.lower() not in stock_dir.lower():
                        continue

                    stock_path = source_path / stock_dir
                    if os.path.isdir(stock_path):
                        for strategy_dir in os.listdir(stock_path):
                            # 应用策略筛选
                            if strategy_filter and strategy_dir != strategy_filter:
                                continue

                            strategy_path = stock_path / strategy_dir
                            if os.path.isdir(strategy_path):
                                for result_file in os.listdir(strategy_path):
                                    if result_file.endswith('.html'):
                                        # 获取文件创建时间
                                        file_path = strategy_path / result_file
                                        run_time = datetime.fromtimestamp(os.path.getctime(file_path)).strftime('%Y-%m-%d %H:%M:%S')

                                        # 应用日期筛选
                                        if date_filter and not run_time.startswith(date_filter):
                                            continue

                                        # 构建结果路径
                                        relative_path = f"{source}/{stock_dir}/{strategy_dir}/{result_file}"

                                        results.append({
                                            'stock': stock_dir,
                                            'source': source,
                                            'strategy': strategy_dir,
                                            'run_time': run_time,
                                            'path': relative_path
                                        })

        # 按运行时间降序排序
        results.sort(key=lambda x: x['run_time'], reverse=True)

        # 计算总页数
        total = len(results)
        total_pages = (total + page_size - 1) // page_size

        # 分页
        paginated_results = results[start_idx:start_idx + page_size]

        return jsonify({
            'results': paginated_results,
            'page': page,
            'total_pages': total_pages,
            'total': total
        })

    except Exception as e:
        logger.error(f"Error getting backtest results: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/show_result/<path:result_path>')
def show_result(result_path):
    """显示回测结果图表"""
    try:
        # 获取实际文件路径
        actual_path = os.path.join(html_root, result_path)
        if not os.path.exists(actual_path):
            return jsonify({'error': 'Result file not found'}), 404

        # 读取HTML文件内容
        with open(actual_path, 'r', encoding='utf-8') as f:
            html_content = f.read()

        return render_template('result_viewer.html', html_content=html_content, file_path=result_path)

    except Exception as e:
        logger.error(f"Error showing result: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/static/<path:filename>')
def serve_static(filename):
    """提供静态文件服务"""
    return send_from_directory('static', filename)


@app.route('/html/<path:filename>')
def serve_html(filename):
    """提供HTML结果文件服务"""
    return send_from_directory('../html', filename)


@app.route('/acquire_stock_data', methods=['POST'])
def acquire_stock_data():
    """获取股票历史数据"""
    try:
        data = request.json
        market = data.get('market')
        data_source = data.get('data_source')
        stock_code = data.get('stock_code')
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        adjust_type = data.get('adjust_type', 'qfq')

        # 参数验证
        if not all([market, data_source, stock_code, start_date, end_date]):
            return jsonify({'error': '缺少必要参数'}), 400

        if data_source not in DATA_SOURCES:
            return jsonify({'error': f'不支持的数据源: {data_source}'}), 400

        logger.info(f"开始获取数据: 市场={market}, 数据源={data_source}, 股票代码={stock_code}")

        # 根据市场和数据源调用不同的数据获取函数
        success = False
        if data_source == 'akshare':
            if market == 'hk':
                if not stock_code.startswith('HK') :
                    return jsonify({'error': f'{market}股票代码请保证前缀HK: {stock_code}'}), 400
                stock_code = stock_code.replace('HK.', '')
                success = manager_akshare.get_single_hk_stock_history(
                    stock_code=stock_code,
                    start_date=start_date,
                    end_date=end_date,
                    adjust_type=adjust_type,
                    output_dir=data_source
                )
            elif market == 'us':
                if not stock_code.startswith('US') :
                    return jsonify({'error': f'{market}股票代码请保证前缀US: {stock_code}'}), 400
                stock_code = stock_code.replace('US.', '')
                success = manager_akshare.get_single_us_history(
                    stock_code=stock_code,
                    start_date=start_date,
                    end_date=end_date,
                    output_dir=data_source
                )
            else:
                return jsonify({'error': f'暂不支持的市场: {market}'}), 400
        elif data_source == 'baostock':
            if adjust_type == 'qfq':
                adjust_type = '2'
            elif adjust_type == 'hfq':
                adjust_type = '3'
            elif adjust_type == 'bfq':
                adjust_type = '1'
            else:
                return jsonify({'error': f'不支持的调整类型: {adjust_type}'}), 400
            if market == 'cn':
                if not stock_code.startswith('SH') and not stock_code.startswith('SZ'):
                    return jsonify({'error': f'{market}股票代码请保证前缀SH或SZ: {stock_code}'}), 400
                stock_code = stock_code.replace('SH.', 'sh.')
                stock_code = stock_code.replace('SZ.', 'sz.')
                success = manager_baostock.get_single_cn_stock_history(
                    stock_code=stock_code,
                    start_date=start_date,
                    end_date=end_date,
                    adjust_type=adjust_type,
                    output_dir=data_source
                )
            else:
                return jsonify({'error': f'暂不支持的市场: {market}'}), 400
        elif data_source == 'futu':
            if adjust_type == 'qfq':
                pass
            elif adjust_type == 'hfq':
                pass
            elif adjust_type == 'bfq':
                adjust_type = 'None'
            else:
                return jsonify({'error': f'不支持的调整类型: {adjust_type}'}), 400
            if market == 'cn':
                if not stock_code.startswith('SH') and not stock_code.startswith('SZ'):
                    return jsonify({'error': f'{market}股票代码请保证前缀SH或SZ: {stock_code}'}), 400
                success = manager_futu.get_single_cn_stock_history(
                    stock_code=stock_code,
                    start_date=start_date,
                    end_date=end_date,
                    adjust_type=adjust_type,
                    output_dir=data_source
                )
            elif market == 'hk':
                if not stock_code.startswith('HK') :
                    return jsonify({'error': f'{market}股票代码请保证前缀HK: {stock_code}'}), 400
                success = manager_futu.get_single_hk_stock_history(
                    stock_code=stock_code,
                    start_date=start_date,
                    end_date=end_date,
                    adjust_type=adjust_type,
                    output_dir=data_source
                )
            else:
                return jsonify({'error': f'暂不支持的市场: {market}'}), 400
        else:
            return jsonify({'error': f'数据源 {data_source} 的数据获取功能尚未实现'}), 400

        if success:
            return jsonify({
                'success': True,
                'message': f'股票数据获取成功！股票代码: {stock_code}'
            })
        else:
            return jsonify({
                'error': f'股票数据获取失败，请检查股票代码是否正确或稍后重试'
            }), 500

    except Exception as e:
        logger.error(f"获取股票数据时出错: {str(e)}")
        return jsonify({'error': f'获取数据时发生错误: {str(e)}'}), 500


if __name__ == '__main__':
    # 在开发环境中运行，生产环境应使用WSGI服务器
    app.run(debug=True, host='0.0.0.0', port=5000)