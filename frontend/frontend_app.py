import os
import sys


# 首先设置系统路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)
import multiprocessing

import secrets
from datetime import datetime
from functools import wraps

from core.signal.signal_handler import signal_get, signals_analyze
from core.task.task_timer import schedule_tasks
from core.strategy.indicator_manager import global_indicator_manager
from core.task.task_manager import TaskManager
from flask import Flask, render_template, request, send_from_directory
from flask_cors import CORS
from flask import make_response
import json
from common.util_csv import combine_data, read_data
from common.util_html import signals_to_html
from core.stock import manager_baostock, manager_akshare, manager_futu
from core.strategy.strategy_manager import global_strategy_manager
from common.logger import create_log
from core.quant.quant_manage import run_backtest_enhanced_volume_strategy, run_backtest_enhanced_volume_strategy_multi
from settings import stock_data_root, html_root, signals_root

# 初始化Flask应用
app = Flask(__name__)
app.secret_key = secrets.token_hex(32)
CORS(app)
logger = create_log('quant_frontend')
task_manager = TaskManager()
# 支持的数据源
DATA_SOURCES = ['akshare', 'baostock', 'futu']


def log_request_details(f):
    """
    记录请求详情的装饰器
    """

    @wraps(f)
    def decorated_function(*args, **kwargs):
        # 记录请求开始
        request_id = secrets.token_hex(8)
        start_time = datetime.now()

        # 获取请求详情
        method = request.method
        url = request.url
        path = request.path

        # 获取请求参数
        query_params = dict(request.args)

        # 获取请求体（对于POST请求等）
        request_body = None
        if request.is_json:
            try:
                request_body = request.get_json()
            except Exception as e:
                logger.warning(f"Request ID: {request_id} - Failed to parse JSON body: {str(e)}")

        # 记录请求详情（不记录过大的请求体）
        log_data = {
            'request_id': request_id,
            'method': method,
            'path': path,
            'query_params': query_params,
            'client_ip': request.remote_addr,
            'user_agent': request.headers.get('User-Agent', ''),
        }

        # 只记录较小的请求体，避免日志过大
        if request_body and len(str(request_body)) < 10000:
            log_data['request_body'] = request_body
        elif request_body:
            log_data['request_body_size'] = len(str(request_body))

        logger.info(f"Request received: {json.dumps(log_data, ensure_ascii=False)}")

        try:
            # 执行原始函数
            response = f(*args, **kwargs)

            # 记录响应信息
            end_time = datetime.now()
            processing_time = (end_time - start_time).total_seconds() * 1000  # 毫秒

            # 获取响应状态码
            status_code = response.status_code if hasattr(response, 'status_code') else 200

            logger.info(f"Request completed: request_id={request_id}, status_code={status_code}, "
                        f"processing_time={processing_time:.2f}ms")

            return response

        except Exception as e:
            # 记录异常信息
            end_time = datetime.now()
            processing_time = (end_time - start_time).total_seconds() * 1000  # 毫秒

            logger.error(f"Request failed: request_id={request_id}, error={str(e)}, "
                         f"processing_time={processing_time:.2f}ms", exc_info=True)

            # 重新抛出异常，让Flask处理
            raise

    return decorated_function


@app.route('/')
@log_request_details
def index():
    """主页，显示数据源和股票选择界面"""
    strategies = global_strategy_manager.get_strategy_names()
    return render_template('index.html', data_sources=DATA_SOURCES, strategies=strategies)


@app.route('/get_stocks/<source>')
@log_request_details
def get_stocks(source):
    """获取指定数据源下的所有股票文件"""
    if source not in DATA_SOURCES:
        error_response_data = {'success': False, 'message': f'Invalid data source', 'data':{}}
        error_response = make_response(json.dumps(error_response_data, ensure_ascii=False))
        error_response.headers['Content-Type'] = 'application/json; charset=utf-8'
        return error_response

    source_path = stock_data_root / source
    if not os.path.exists(source_path):
        error_response_data = {'success': False, 'message': f'Source directory not found', 'data':{}}
        error_response = make_response(json.dumps(error_response_data, ensure_ascii=False))
        error_response.headers['Content-Type'] = 'application/json; charset=utf-8'
        return error_response

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
        error_response_data = {'success': False, 'message': f'Error reading stocks: {str(e)}', 'data':{}}
        error_response = make_response(json.dumps(error_response_data, ensure_ascii=False))
        error_response.headers['Content-Type'] = 'application/json; charset=utf-8'
        return error_response
    response_data = {
        'success': True,
        'message': f'Found {len(stocks)} stocks',
        'data':{
            'stocks': stocks
        }
    }
    response = make_response(json.dumps(response_data, ensure_ascii=False))
    response.headers['Content-Type'] = 'application/json; charset=utf-8'
    return response


@app.route('/run_backtest', methods=['POST'])
@log_request_details
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
            error_response_data = {'success': False, 'message': f'Invalid strategy: {strategy_name}', 'data':{}}
            error_response = make_response(json.dumps(error_response_data, ensure_ascii=False))
            error_response.headers['Content-Type'] = 'application/json; charset=utf-8'
            return error_response

        if source not in DATA_SOURCES:
            error_response_data = {'success': False, 'message': f'Invalid data source', 'data':{}}
            error_response = make_response(json.dumps(error_response_data, ensure_ascii=False))
            error_response.headers['Content-Type'] = 'application/json; charset=utf-8'
            return error_response

        if is_batch:
            # 批量回测
            folder_path = stock_data_root / source
            run_backtest_enhanced_volume_strategy_multi(str(folder_path), strategy_class, init_cash)
            response_data = {
                'success': True,
                'message': 'Batch backtest completed',
                'data':{}
            }
            response = make_response(json.dumps(response_data, ensure_ascii=False))
            response.headers['Content-Type'] = 'application/json; charset=utf-8'
            return response
        else:
            # 单个股票回测
            if not stock_file:
                error_response_data = {'success': False, 'message': f'Stock file is required', 'data':{}}
                error_response = make_response(json.dumps(error_response_data, ensure_ascii=False))
                error_response.headers['Content-Type'] = 'application/json; charset=utf-8'
                return error_response

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

                    response_data = {
                        'success': True,
                        'message': 'Backtest completed',
                        'data':{
                            'result_path': result_path
                        }
                    }
                    response = make_response(json.dumps(response_data, ensure_ascii=False))
                    response.headers['Content-Type'] = 'application/json; charset=utf-8'
                    return response

            error_response_data = {'success': False, 'message': f'Backtest completed, but no result file found', 'data':{}}
            error_response = make_response(json.dumps(error_response_data, ensure_ascii=False))
            error_response.headers['Content-Type'] = 'application/json; charset=utf-8'
            return error_response

    except Exception as e:
        logger.error(f"Error running backtest: {str(e)}")
        error_response_data = {'success': False, 'message': f'Error running backtest: {str(e)}', 'data':{}}
        error_response = make_response(json.dumps(error_response_data, ensure_ascii=False))
        error_response.headers['Content-Type'] = 'application/json; charset=utf-8'
        return error_response


@app.route('/get_backtest_results')
@log_request_details
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

        response_data = {
            'success': True,
            'message': f'Found {total} backtest results',
            'data':{
                'results': paginated_results,
                'page': page,
                'total_pages': total_pages,
                'total': total
            }
        }
        response = make_response(json.dumps(response_data, ensure_ascii=False))
        response.headers['Content-Type'] = 'application/json; charset=utf-8'
        return response

    except Exception as e:
        logger.error(f"Error getting backtest results: {str(e)}")
        error_response_data = {'success': False, 'message': f'Error getting backtest results: {str(e)}', 'data':{}}
        error_response = make_response(json.dumps(error_response_data, ensure_ascii=False))
        error_response.headers['Content-Type'] = 'application/json; charset=utf-8'
        return error_response


@app.route('/show_result/<path:result_path>')
@log_request_details
def show_result(result_path):
    """显示回测结果图表"""
    try:
        # 获取实际文件路径
        actual_path = os.path.join(html_root, result_path)
        if not os.path.exists(actual_path):
            error_response_data = {'success': False, 'message': 'Result file not found', 'data':{}}
            error_response = make_response(json.dumps(error_response_data, ensure_ascii=False))
            error_response.headers['Content-Type'] = 'application/json; charset=utf-8'
            return error_response

        # 读取HTML文件内容
        with open(actual_path, 'r', encoding='utf-8') as f:
            html_content = f.read()

        return render_template('result_viewer.html', html_content=html_content, file_path=result_path)

    except Exception as e:
        logger.error(f"Error showing result: {str(e)}")
        error_response_data = {'success': False, 'message': f'Error showing result: {str(e)}', 'data':{}}
        error_response = make_response(json.dumps(error_response_data, ensure_ascii=False))
        error_response.headers['Content-Type'] = 'application/json; charset=utf-8'
        return error_response


@app.route('/static/<path:filename>')
@log_request_details
def serve_static(filename):
    """提供静态文件服务"""
    return send_from_directory('static', filename)


@app.route('/html/<path:filename>')
@log_request_details
def serve_html(filename):
    """提供HTML结果文件服务"""
    return send_from_directory('../html', filename)


@app.route('/acquire_stock_data', methods=['POST'])
@log_request_details
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
            error_response_data = {'success': False, 'message': '缺少必要参数', 'data':{}}
            error_response = make_response(json.dumps(error_response_data, ensure_ascii=False))
            error_response.headers['Content-Type'] = 'application/json; charset=utf-8'
            return error_response

        if data_source not in DATA_SOURCES:
            error_response_data = {'success': False, 'message': f'不支持的数据源: {data_source}', 'data':{}}
            error_response = make_response(json.dumps(error_response_data, ensure_ascii=False))
            error_response.headers['Content-Type'] = 'application/json; charset=utf-8'
            return error_response

        logger.info(f"开始获取数据: 市场={market}, 数据源={data_source}, 股票代码={stock_code}")

        # 根据市场和数据源调用不同的数据获取函数
        success = False
        filename = None
        if data_source == 'akshare':
            if market == 'hk':
                if not stock_code.startswith('HK') :
                    error_response_data = {'success': False, 'message': f'{market}股票代码请保证前缀HK: {stock_code}', 'data':{}}
                    error_response = make_response(json.dumps(error_response_data, ensure_ascii=False))
                    error_response.headers['Content-Type'] = 'application/json; charset=utf-8'
                    return error_response
                stock_code = stock_code.replace('HK.', '')
                success, filename = manager_akshare.get_single_hk_stock_history(
                    stock_code=stock_code,
                    start_date=start_date,
                    end_date=end_date,
                    adjust_type=adjust_type,
                    output_dir=data_source
                )
            elif market == 'us':
                if not stock_code.startswith('US') :
                    error_response_data = {'success': False, 'message': f'{market}股票代码请保证前缀US: {stock_code}', 'data':{}}
                    error_response = make_response(json.dumps(error_response_data, ensure_ascii=False))
                    error_response.headers['Content-Type'] = 'application/json; charset=utf-8'
                    return error_response
                stock_code = stock_code.replace('US.', '')
                success, filename = manager_akshare.get_single_us_history(
                    stock_code=stock_code,
                    start_date=start_date,
                    end_date=end_date,
                    output_dir=data_source
                )
            else:
                error_response_data = {'success': False, 'message': f'暂不支持的市场: {market}', 'data':{}}
                error_response = make_response(json.dumps(error_response_data, ensure_ascii=False))
                error_response.headers['Content-Type'] = 'application/json; charset=utf-8'
                return error_response
        elif data_source == 'baostock':
            if adjust_type == 'qfq':
                adjust_type = '2'
            elif adjust_type == 'hfq':
                adjust_type = '3'
            elif adjust_type == 'bfq':
                adjust_type = '1'
            else:
                error_response_data = {'success': False, 'message': f'不支持的调整类型: {adjust_type}', 'data':{}}
                error_response = make_response(json.dumps(error_response_data, ensure_ascii=False))
                error_response.headers['Content-Type'] = 'application/json; charset=utf-8'
                return error_response
            if market == 'cn':
                if not stock_code.startswith('SH') and not stock_code.startswith('SZ'):
                    error_response_data = {'success': False, 'message': f'{market}股票代码请保证前缀SH或SZ: {stock_code}', 'data':{}}
                    error_response = make_response(json.dumps(error_response_data, ensure_ascii=False))
                    error_response.headers['Content-Type'] = 'application/json; charset=utf-8'
                    return error_response
                stock_code = stock_code.replace('SH.', 'sh.')
                stock_code = stock_code.replace('SZ.', 'sz.')
                success, filename = manager_baostock.get_single_cn_stock_history(
                    stock_code=stock_code,
                    start_date=start_date,
                    end_date=end_date,
                    adjust_type=adjust_type,
                    output_dir=data_source
                )
            else:
                error_response_data = {'success': False, 'message': f'暂不支持的市场: {market}', 'data':{}}
                error_response = make_response(json.dumps(error_response_data, ensure_ascii=False))
                error_response.headers['Content-Type'] = 'application/json; charset=utf-8'
                return error_response
        elif data_source == 'futu':
            if adjust_type == 'qfq':
                pass
            elif adjust_type == 'hfq':
                pass
            elif adjust_type == 'bfq':
                adjust_type = 'None'
            else:
                error_response_data = {'success': False, 'message': f'不支持的调整类型: {adjust_type}', 'data':{}}
                error_response = make_response(json.dumps(error_response_data, ensure_ascii=False))
                error_response.headers['Content-Type'] = 'application/json; charset=utf-8'
                return error_response
            if market == 'cn':
                if not stock_code.startswith('SH') and not stock_code.startswith('SZ'):
                    error_response_data = {'success': False, 'message': f'{market}股票代码请保证前缀SH或SZ: {stock_code}', 'data':{}}
                    error_response = make_response(json.dumps(error_response_data, ensure_ascii=False))
                    error_response.headers['Content-Type'] = 'application/json; charset=utf-8'
                    return error_response
                success, filename = manager_futu.get_single_cn_stock_history(
                    stock_code=stock_code,
                    start_date=start_date,
                    end_date=end_date,
                    adjust_type=adjust_type,
                    output_dir=data_source
                )
            elif market == 'hk':
                if not stock_code.startswith('HK') :
                    error_response_data = {'success': False, 'message': f'{market}股票代码请保证前缀HK: {stock_code}', 'data':{}}
                    error_response = make_response(json.dumps(error_response_data, ensure_ascii=False))
                    error_response.headers['Content-Type'] = 'application/json; charset=utf-8'
                    return error_response
                success, filename = manager_futu.get_single_hk_stock_history(
                    stock_code=stock_code,
                    start_date=start_date,
                    end_date=end_date,
                    adjust_type=adjust_type,
                    output_dir=data_source
                )
            else:
                error_response_data = {'success': False, 'message': f'暂不支持的市场: {market}', 'data':{}}
                error_response = make_response(json.dumps(error_response_data, ensure_ascii=False))
                error_response.headers['Content-Type'] = 'application/json; charset=utf-8'
                return error_response
        else:
            error_response_data = {'success': False, 'message': f'数据源 {data_source} 的数据获取功能尚未实现', 'data':{}}
            error_response = make_response(json.dumps(error_response_data, ensure_ascii=False))
            error_response.headers['Content-Type'] = 'application/json; charset=utf-8'
            return error_response

        if success:
            response_data = {
                'success': True,
                'message': f'股票数据获取成功！股票代码: {stock_code}, 数据文件已保存至: {filename}',
                'data':{
                    'filename': filename
                }
            }
            response = make_response(json.dumps(response_data, ensure_ascii=False))
            response.headers['Content-Type'] = 'application/json; charset=utf-8'
            return response

        else:
            error_response_data = {'success': False, 'message': '股票数据获取失败，请检查股票代码是否正确或稍后重试', 'data':{}}
            error_response = make_response(json.dumps(error_response_data, ensure_ascii=False))
            error_response.headers['Content-Type'] = 'application/json; charset=utf-8'
            return error_response

    except Exception as e:
        logger.error(f"获取股票数据时出错: {str(e)}")
        error_response_data = {'success': False, 'message':f'获取数据时发生错误: {str(e)},请检查股票代码是否正确或稍后重试', 'data':{}}
        error_response = make_response(json.dumps(error_response_data, ensure_ascii=False))
        error_response.headers['Content-Type'] = 'application/json; charset=utf-8'
        return error_response


@app.route('/signal_analysis')
@log_request_details
def signal_analysis():
    """信号分析页面"""
    return render_template('signal_analysis.html')


@app.route('/get_signal_files')
@log_request_details
def get_signal_files():
    """获取所有信号文件信息"""

    try:
        signal_files = signal_get()
        signal_files.sort(key=lambda x: x['file_time'], reverse=True)
        response_data = {
            'success': True,
            'message': f'Found {len(signal_files)} signal files',
            'data': {
                'signal_files': signal_files
            }
        }
        response = make_response(json.dumps(response_data, ensure_ascii=False))
        response.headers['Content-Type'] = 'application/json; charset=utf-8'
        return response
    except Exception as e:
        logger.error(f"获取信号文件失败: {str(e)}")
        error_response_data = {'success': False, 'message': str(e), 'data':{}}
        error_response = make_response(json.dumps(error_response_data, ensure_ascii=False))
        error_response.headers['Content-Type'] = 'application/json; charset=utf-8'
        return error_response


@app.route('/analyze_signals', methods=['POST'])
@log_request_details
def analyze_signals():
    """分析信号文件"""

    try:
        data = request.json
        file_paths = data.get('file_paths', [])
        filters = data.get('filters', {})
        combined_df = signals_analyze(file_paths, filters)
        response_data = {
            'success': True,
            'message': f'Found signals success',
            'data': {
                'signals': combined_df.to_dict('records'),
                'summary': {
                    'total_signals': len(combined_df),
                    'buy_signals': len(combined_df[combined_df['signal_type'].str.contains('buy')]),
                    'sell_signals': len(combined_df[combined_df['signal_type'].str.contains('sell')]),
                    'unique_stocks': combined_df['stock_info'].nunique(),
                    'unique_strategies': combined_df['strategy_name'].nunique()
                }
            }
        }
        response = make_response(json.dumps(response_data, ensure_ascii=False))
        response.headers['Content-Type'] = 'application/json; charset=utf-8'
        return response

    except Exception as e:
        logger.error(f"分析信号失败: {str(e)}")
        error_response_data = {'success': False, 'message': str(e), 'data': {}}
        error_response = make_response(json.dumps(error_response_data, ensure_ascii=False))
        error_response.headers['Content-Type'] = 'application/json; charset=utf-8'
        return error_response

@app.route('/get_signal_metadata')
@log_request_details
def get_signal_metadata():
    """获取信号元数据（用于筛选）"""
    try:
        if not os.path.exists(signals_root):
            response_data = {'success': False, 'message': '信号目录不存在', 'data':{}}
            response = make_response(json.dumps(response_data, ensure_ascii=False))
            response.headers['Content-Type'] = 'application/json; charset=utf-8'
            return response

        strategies = set()
        stock_codes = set()
        signal_types = set()

        # 遍历信号目录
        for root, dirs, files in os.walk(signals_root):
            for file in files:
                if file.endswith('.csv') and file.startswith('stock_signals_'):
                    file_path = os.path.join(root, file)

                    # 从路径中提取策略名称
                    relative_path = os.path.relpath(file_path, signals_root)
                    parts = relative_path.split(os.sep)
                    if len(parts) > 2:
                        strategies.add(parts[2])

                    # 从文件名中提取股票代码
                    if len(parts) > 1:
                        stock_codes.add(parts[1])

                    # 读取文件获取信号类型
                    try:
                        df = read_data(file_path)
                        if 'signal_type' in df.columns:
                            signal_types.update(df['signal_type'].unique())
                    except:
                        pass
        response_data = {
            'success': True,
            'message': 'get signal metadata success',
            'data':{
                'metadata': {
                    'strategies': list(strategies),
                    'stock_codes': list(stock_codes),
                    'signal_types': list(signal_types)
                }
            }

        }
        response = make_response(json.dumps(response_data, ensure_ascii=False))
        response.headers['Content-Type'] = 'application/json; charset=utf-8'
        return response
    except Exception as e:
        logger.error(f"获取信号元数据失败: {str(e)}")
        error_response_data = {'success': False, 'message': str(e), 'data':{}}
        error_response = make_response(json.dumps(error_response_data, ensure_ascii=False))
        error_response.headers['Content-Type'] = 'application/json; charset=utf-8'
        return error_response
# 在现有API端点后添加新的端点
@app.route('/generate_html_report', methods=['POST'])
@log_request_details
def generate_html_report():
    """生成HTML报告"""
    try:
        data = request.get_json()
        signals_data = data.get('signals_data', [])
        filters = data.get('filters', {})
        summary = data.get('summary', {})

        if not signals_data:
            response_data = {'success': False, 'message': '没有可生成报告的信号数据', 'data':{}}
            response = make_response(json.dumps(response_data, ensure_ascii=False))
            response.headers['Content-Type'] = 'application/json; charset=utf-8'
            return response

        # 生成HTML报告
        html_content = signals_to_html(signals_data, filters, summary)

        # 生成文件名
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        file_name = f"信号分析报告_{timestamp}.html"

        logger.info(f"HTML信号分析报告已生成: {file_name}")
        logger.debug(f"HTML信号分析报告内容已生成: {html_content}")

        # 返回HTML内容和文件名，方便前端下载
        response_data = {
            'success': True,
            'message': 'HTML报告生成成功',
            'data':{
                'html_content': html_content,
                'file_name': file_name,
            }
        }
        response = make_response(json.dumps(response_data, ensure_ascii=False))
        response.headers['Content-Type'] = 'application/json; charset=utf-8'
        return response

    except Exception as e:
        logger.error(f"生成HTML报告失败: {str(e)}")
        error_response_data = {'success': False, 'message': str(e), 'data':{}}
        error_response = make_response(json.dumps(error_response_data, ensure_ascii=False))
        error_response.headers['Content-Type'] = 'application/json; charset=utf-8'
        return error_response

@app.route('/strategy_code')
@log_request_details
def strategy_code():
    """策略代码查看页面"""
    strategies = global_strategy_manager.get_strategy_names()
    indicators = global_indicator_manager.get_indicator_names()
    return render_template('strategy_code.html', strategies=strategies, indicators=indicators)


@app.route('/get_strategy_code/<strategy_name>')
@log_request_details
def get_strategy_code(strategy_name):
    """获取策略代码"""
    try:
        code_info = global_strategy_manager.get_strategy_source_code(strategy_name)
        if not code_info:
            error_response_data = {'success': False, 'message': f'Strategy not found: {strategy_name}', 'data': {}}
            error_response = make_response(json.dumps(error_response_data, ensure_ascii=False))
            error_response.headers['Content-Type'] = 'application/json; charset=utf-8'
            return error_response

        response_data = {
            'success': True,
            'message': 'Strategy code retrieved successfully',
            'data': code_info
        }
        response = make_response(json.dumps(response_data, ensure_ascii=False))
        response.headers['Content-Type'] = 'application/json; charset=utf-8'
        return response
    except Exception as e:
        logger.error(f"Error getting strategy code: {str(e)}")
        error_response_data = {'success': False, 'message': f'Error getting strategy code: {str(e)}', 'data': {}}
        error_response = make_response(json.dumps(error_response_data, ensure_ascii=False))
        error_response.headers['Content-Type'] = 'application/json; charset=utf-8'
        return error_response


@app.route('/get_indicator_code/<indicator_name>')
@log_request_details
def get_indicator_code(indicator_name):
    """获取指标类的源代码"""
    try:
        indicator_info = global_indicator_manager.get_indicator_source_code(indicator_name)
        if not indicator_info:
            error_response_data = {'success': False, 'message': f'Indicator not found: {indicator_name}', 'data': {}}
            error_response = make_response(json.dumps(error_response_data, ensure_ascii=False))
            error_response.headers['Content-Type'] = 'application/json; charset=utf-8'
            return error_response

        response_data = {
            'success': True,
            'message': 'Indicator code retrieved successfully',
            'data': indicator_info
        }
        response = make_response(json.dumps(response_data, ensure_ascii=False))
        response.headers['Content-Type'] = 'application/json; charset=utf-8'
        return response
    except Exception as e:
        logger.error(f"Error getting indicator code: {str(e)}")
        error_response_data = {'success': False, 'message': f'Error getting indicator code: {str(e)}', 'data': {}}
        error_response = make_response(json.dumps(error_response_data, ensure_ascii=False))
        error_response.headers['Content-Type'] = 'application/json; charset=utf-8'
        return error_response


@app.route('/schedule')
@log_request_details
def schedule_page():
    """定时任务管理页面"""
    strategies = global_strategy_manager.get_strategy_names()
    return render_template('schedule.html', strategies=strategies)


@app.route('/api/tasks/get_all', methods=['GET'])
@log_request_details
def get_all_tasks():
    """获取所有任务"""
    try:
        tasks = task_manager.read_all()
        response_data = {
            'success': True,
            'message': f'获取到 {len(tasks)} 个任务',
            'data': tasks
        }
        response = make_response(json.dumps(response_data, ensure_ascii=False))
        response.headers['Content-Type'] = 'application/json; charset=utf-8'
        return response
    except Exception as e:
        logger.error(f"获取任务列表失败: {str(e)}")
        error_response_data = {'success': False, 'message': f'获取任务列表失败: {str(e)}', 'data': {}}
        error_response = make_response(json.dumps(error_response_data, ensure_ascii=False))
        error_response.headers['Content-Type'] = 'application/json; charset=utf-8'
        return error_response


@app.route('/api/tasks/get/<task_id>', methods=['GET'])
@log_request_details
def get_task_by_id(task_id):
    """根据ID获取任务"""
    try:
        task = task_manager.read(task_id)
        if not task:
            error_response_data = {'success': False, 'message': f'任务不存在: {task_id}', 'data': {}}
            error_response = make_response(json.dumps(error_response_data, ensure_ascii=False))
            error_response.headers['Content-Type'] = 'application/json; charset=utf-8'
            return error_response

        response_data = {
            'success': True,
            'message': '获取任务成功',
            'data': task
        }
        response = make_response(json.dumps(response_data, ensure_ascii=False))
        response.headers['Content-Type'] = 'application/json; charset=utf-8'
        return response
    except Exception as e:
        logger.error(f"获取任务失败: {str(e)}")
        error_response_data = {'success': False, 'message': f'获取任务失败: {str(e)}', 'data': {}}
        error_response = make_response(json.dumps(error_response_data, ensure_ascii=False))
        error_response.headers['Content-Type'] = 'application/json; charset=utf-8'
        return error_response


@app.route('/api/tasks/create', methods=['POST'])
@log_request_details
def create_task():
    """创建新任务"""
    try:
        task_data = request.json
        if not task_data:
            error_response_data = {'success': False, 'message': '任务数据不能为空', 'data': {}}
            error_response = make_response(json.dumps(error_response_data, ensure_ascii=False))
            error_response.headers['Content-Type'] = 'application/json; charset=utf-8'
            return error_response

        created_task = task_manager.create(task_data)
        if not created_task:
            error_response_data = {'success': False, 'message': '创建任务失败', 'data': {}}
            error_response = make_response(json.dumps(error_response_data, ensure_ascii=False))
            error_response.headers['Content-Type'] = 'application/json; charset=utf-8'
            return error_response

        response_data = {
            'success': True,
            'message': '创建任务成功',
            'data': created_task
        }
        response = make_response(json.dumps(response_data, ensure_ascii=False))
        response.headers['Content-Type'] = 'application/json; charset=utf-8'
        return response
    except Exception as e:
        logger.error(f"创建任务失败: {str(e)}")
        error_response_data = {'success': False, 'message': f'创建任务失败: {str(e)}', 'data': {}}
        error_response = make_response(json.dumps(error_response_data, ensure_ascii=False))
        error_response.headers['Content-Type'] = 'application/json; charset=utf-8'
        return error_response


@app.route('/api/tasks/update/<task_id>', methods=['POST'])
@log_request_details
def update_task_by_id(task_id):
    """更新任务"""
    try:
        request_data = request.json
        if not request_data:
            error_response_data = {'success': False, 'message': '更新数据不能为空', 'data': {}}
            error_response = make_response(json.dumps(error_response_data, ensure_ascii=False))
            error_response.headers['Content-Type'] = 'application/json; charset=utf-8'
            return error_response
        update_data = request_data.get('taskData', request_data)
        updated_task = task_manager.update(task_id, update_data)
        if not updated_task:
            error_response_data = {'success': False, 'message': f'更新任务失败: 任务不存在', 'data': {}}
            error_response = make_response(json.dumps(error_response_data, ensure_ascii=False))
            error_response.headers['Content-Type'] = 'application/json; charset=utf-8'
            return error_response

        response_data = {
            'success': True,
            'message': '更新任务成功',
            'data': updated_task
        }
        response = make_response(json.dumps(response_data, ensure_ascii=False))
        response.headers['Content-Type'] = 'application/json; charset=utf-8'
        return response
    except Exception as e:
        logger.error(f"更新任务失败: {str(e)}")
        error_response_data = {'success': False, 'message': f'更新任务失败: {str(e)}', 'data': {}}
        error_response = make_response(json.dumps(error_response_data, ensure_ascii=False))
        error_response.headers['Content-Type'] = 'application/json; charset=utf-8'
        return error_response


@app.route('/api/tasks/delete/<task_id>', methods=['POST'])
@log_request_details
def delete_task_by_id(task_id):
    """删除任务"""
    try:
        success = task_manager.delete(task_id)
        if not success:
            error_response_data = {'success': False, 'message': f'删除任务失败: 任务不存在', 'data': {}}
            error_response = make_response(json.dumps(error_response_data, ensure_ascii=False))
            error_response.headers['Content-Type'] = 'application/json; charset=utf-8'
            return error_response

        response_data = {
            'success': True,
            'message': '删除任务成功',
            'data': {}
        }
        response = make_response(json.dumps(response_data, ensure_ascii=False))
        response.headers['Content-Type'] = 'application/json; charset=utf-8'
        return response
    except Exception as e:
        logger.error(f"删除任务失败: {str(e)}")
        error_response_data = {'success': False, 'message': f'删除任务失败: {str(e)}', 'data': {}}
        error_response = make_response(json.dumps(error_response_data, ensure_ascii=False))
        error_response.headers['Content-Type'] = 'application/json; charset=utf-8'
        return error_response


@app.route('/api/tasks/query', methods=['POST'])
@log_request_details
def query_tasks():
    """根据条件查询任务"""
    try:
        filters = request.json
        tasks = task_manager.query(filters)

        response_data = {
            'success': True,
            'message': f'查询到 {len(tasks)} 个符合条件的任务',
            'data': tasks
        }
        response = make_response(json.dumps(response_data, ensure_ascii=False))
        response.headers['Content-Type'] = 'application/json; charset=utf-8'
        return response
    except Exception as e:
        logger.error(f"查询任务失败: {str(e)}")
        error_response_data = {'success': False, 'message': f'查询任务失败: {str(e)}', 'data': {}}
        error_response = make_response(json.dumps(error_response_data, ensure_ascii=False))
        error_response.headers['Content-Type'] = 'application/json; charset=utf-8'
        return error_response


@app.route('/api/tasks/enable/<task_id>', methods=['POST'])
@log_request_details
def enable_task(task_id):
    """启用任务"""
    try:
        enabled_task = task_manager.enable(task_id)
        if not enabled_task:
            error_response_data = {'success': False, 'message': f'启用任务失败: 任务不存在', 'data': {}}
            error_response = make_response(json.dumps(error_response_data, ensure_ascii=False))
            error_response.headers['Content-Type'] = 'application/json; charset=utf-8'
            return error_response

        response_data = {
            'success': True,
            'message': '启用任务成功',
            'data': enabled_task
        }
        response = make_response(json.dumps(response_data, ensure_ascii=False))
        response.headers['Content-Type'] = 'application/json; charset=utf-8'
        return response
    except Exception as e:
        logger.error(f"启用任务失败: {str(e)}")
        error_response_data = {'success': False, 'message': f'启用任务失败: {str(e)}', 'data': {}}
        error_response = make_response(json.dumps(error_response_data, ensure_ascii=False))
        error_response.headers['Content-Type'] = 'application/json; charset=utf-8'
        return error_response


@app.route('/api/tasks/disable/<task_id>', methods=['POST'])
@log_request_details
def disable_task(task_id):
    """禁用任务"""
    try:
        disabled_task = task_manager.disable(task_id)
        if not disabled_task:
            error_response_data = {'success': False, 'message': f'禁用任务失败: 任务不存在', 'data': {}}
            error_response = make_response(json.dumps(error_response_data, ensure_ascii=False))
            error_response.headers['Content-Type'] = 'application/json; charset=utf-8'
            return error_response

        response_data = {
            'success': True,
            'message': '禁用任务成功',
            'data': disabled_task
        }
        response = make_response(json.dumps(response_data, ensure_ascii=False))
        response.headers['Content-Type'] = 'application/json; charset=utf-8'
        return response
    except Exception as e:
        logger.error(f"禁用任务失败: {str(e)}")
        error_response_data = {'success': False, 'message': f'禁用任务失败: {str(e)}', 'data': {}}
        error_response = make_response(json.dumps(error_response_data, ensure_ascii=False))
        error_response.headers['Content-Type'] = 'application/json; charset=utf-8'
        return error_response


@app.route('/api/tasks/count', methods=['GET'])
@log_request_details
def get_task_count():
    """获取任务总数"""
    try:
        count = task_manager.count()
        response_data = {
            'success': True,
            'message': '获取任务数量成功',
            'data': {'count': count}
        }
        response = make_response(json.dumps(response_data, ensure_ascii=False))
        response.headers['Content-Type'] = 'application/json; charset=utf-8'
        return response
    except Exception as e:
        logger.error(f"获取任务数量失败: {str(e)}")
        error_response_data = {'success': False, 'message': f'获取任务数量失败: {str(e)}', 'data': {}}
        error_response = make_response(json.dumps(error_response_data, ensure_ascii=False))
        error_response.headers['Content-Type'] = 'application/json; charset=utf-8'
        return error_response


@app.route('/api/tasks/exists/<task_id>', methods=['GET'])
@log_request_details
def check_task_exists(task_id):
    """检查任务是否存在"""
    try:
        exists = task_manager.exists(task_id)
        response_data = {
            'success': True,
            'message': '检查任务存在状态成功',
            'data': {'exists': exists}
        }
        response = make_response(json.dumps(response_data, ensure_ascii=False))
        response.headers['Content-Type'] = 'application/json; charset=utf-8'
        return response
    except Exception as e:
        logger.error(f"检查任务存在状态失败: {str(e)}")
        error_response_data = {'success': False, 'message': f'检查任务存在状态失败: {str(e)}', 'data': {}}
        error_response = make_response(json.dumps(error_response_data, ensure_ascii=False))
        error_response.headers['Content-Type'] = 'application/json; charset=utf-8'
        return error_response


if __name__ == '__main__':
    # 在开发环境中运行，生产环境应使用WSGI服务器
    try:
        # 在Flask debug模式下，避免在子进程中重复启动任务调度器
        import os
        # 检查是否为主进程（Flask会设置WERKZEUG_RUN_MAIN环境变量标识子进程）
        if os.environ.get('WERKZEUG_RUN_MAIN') != 'true':
            # 创建进程启动schedule_tasks
            task_process = multiprocessing.Process(target=schedule_tasks)
            task_process.daemon = True  # 设置为守护进程，主进程结束时自动终止
            task_process.start()
            logger.info("启动任务定时器")
        else:
            logger.info("在Flask子进程中，不启动任务定时器")
    except KeyboardInterrupt:
        logger.info("用户中断，停止任务定时器")
    except Exception as e:
        logger.error(f"任务定时器异常: {str(e)}")
    app.run(debug=True, host='0.0.0.0', port=5000)
