import json
import os
from datetime import datetime
from pathlib import Path
import settings
from common.logger import create_log
import secrets

logger = create_log('backtest_record_manager')


class BacktestRecordManager:
    @property
    def record_dir(self):
        return settings.backtest_records_root

    def _ensure_dir(self):
        os.makedirs(self.record_dir, exist_ok=True)

    def create_record_id(self):
        return f"BT_{datetime.now().strftime('%Y%m%d%H%M%S')}_{secrets.token_hex(4)}"

    def save(self, record_data):
        try:
            self._ensure_dir()
            record_id = record_data.get('record_id')
            if not record_id:
                record_id = self.create_record_id()
                record_data['record_id'] = record_id

            record_path = self.record_dir / f"{record_id}.json"
            with open(record_path, 'w', encoding='utf-8') as f:
                json.dump(record_data, f, ensure_ascii=False, indent=2)

            logger.info(f"回测记录已保存: {record_path}")
            return record_id
        except Exception as e:
            logger.error(f"保存回测记录失败: {str(e)}")
            return None

    def read(self, record_id):
        try:
            self._ensure_dir()
            record_path = self.record_dir / f"{record_id}.json"
            if not record_path.exists():
                return None
            with open(record_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"读取回测记录失败: {str(e)}")
            return None

    def read_all(self, limit=None):
        try:
            self._ensure_dir()
            records = []
            for record_file in sorted(self.record_dir.glob('*.json'), reverse=True):
                with open(record_file, 'r', encoding='utf-8') as f:
                    records.append(json.load(f))
                if limit and len(records) >= limit:
                    break
            return records
        except Exception as e:
            logger.error(f"读取回测记录列表失败: {str(e)}")
            return []


backtest_record_manager = BacktestRecordManager()
