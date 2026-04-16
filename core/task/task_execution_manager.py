import json
import os
from datetime import datetime
from common.logger import create_log

logger = create_log('task_execution')


class TaskExecutionManager:
    """
    任务执行记录管理器，用于存储和管理定时任务的执行历史
    """

    def __init__(self, file_path=None):
        if file_path is None:
            self.file_path = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                '../../config',
                'task_executions.json'
            )
        else:
            self.file_path = file_path
        self._ensure_file_exists()

    def _ensure_file_exists(self):
        config_dir = os.path.dirname(self.file_path)
        if not os.path.exists(config_dir):
            os.makedirs(config_dir)
            logger.info(f"创建配置目录: {config_dir}")
        if not os.path.exists(self.file_path):
            with open(self.file_path, 'w', encoding='utf-8') as f:
                json.dump([], f, ensure_ascii=False, indent=2)
            logger.info(f"创建空执行记录文件: {self.file_path}")

    def _read_executions(self):
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"读取执行记录文件失败: {e}")
            return []

    def _write_executions(self, executions):
        try:
            with open(self.file_path, 'w', encoding='utf-8') as f:
                json.dump(executions, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            logger.error(f"写入执行记录文件失败: {e}")
            return False

    def create(self, task_id, task_name, status='running', details=None, stocks=None):
        execution = {
            'id': f"exec_{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
            'task_id': task_id,
            'task_name': task_name,
            'status': status,
            'start_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'end_time': None,
            'duration': None,
            'details': details or {},
            'stocks': stocks or [],
            'stocks_processed': 0,
            'stocks_success': 0,
            'stocks_failed': 0
        }
        executions = self._read_executions()
        executions.append(execution)
        if self._write_executions(executions):
            logger.info(f"创建执行记录: {execution['id']} (任务: {task_name})")
            return execution
        return None

    def update(self, execution_id, status=None, details=None, stocks_processed=None, stocks_success=None, stocks_failed=None):
        executions = self._read_executions()
        for i, exec_record in enumerate(executions):
            if exec_record.get('id') == execution_id:
                if status:
                    exec_record['status'] = status
                if details:
                    exec_record['details'].update(details)
                if stocks_processed is not None:
                    exec_record['stocks_processed'] = stocks_processed
                if stocks_success is not None:
                    exec_record['stocks_success'] = stocks_success
                if stocks_failed is not None:
                    exec_record['stocks_failed'] = stocks_failed
                if status in ['success', 'failed', 'partial']:
                    exec_record['end_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    start = datetime.strptime(exec_record['start_time'], '%Y-%m-%d %H:%M:%S')
                    end = datetime.strptime(exec_record['end_time'], '%Y-%m-%d %H:%M:%S')
                    exec_record['duration'] = round((end - start).total_seconds(), 2)
                self._write_executions(executions)
                logger.info(f"更新执行记录: {execution_id}, status: {status}")
                return exec_record
        return None

    def read(self, execution_id):
        executions = self._read_executions()
        for exec_record in executions:
            if exec_record.get('id') == execution_id:
                return exec_record
        return None

    def read_by_task(self, task_id, limit=50):
        executions = self._read_executions()
        task_executions = [e for e in executions if e.get('task_id') == task_id]
        task_executions.sort(key=lambda x: x.get('start_time', ''), reverse=True)
        return task_executions[:limit]

    def read_all(self, limit=100):
        executions = self._read_executions()
        executions.sort(key=lambda x: x.get('start_time', ''), reverse=True)
        return executions[:limit]

    def delete(self, execution_id):
        executions = self._read_executions()
        executions = [e for e in executions if e.get('id') != execution_id]
        return self._write_executions(executions)

    def delete_old(self, days=30):
        executions = self._read_executions()
        cutoff = datetime.now() - datetime.timedelta(days=days)
        old_count = 0
        new_list = []
        for e in executions:
            try:
                exec_time = datetime.strptime(e.get('start_time', ''), '%Y-%m-%d %H:%M:%S')
                if exec_time >= cutoff:
                    new_list.append(e)
                else:
                    old_count += 1
            except:
                new_list.append(e)
        if old_count > 0:
            self._write_executions(new_list)
            logger.info(f"删除了 {old_count} 条过期执行记录")
        return old_count


task_execution_manager = TaskExecutionManager()
