"""
数据持久化模块

负责保存和加载操作记录、交易历史和市场数据
"""

import json
import os
import pickle
from datetime import datetime
from typing import List, Dict, Any

class DataPersistence:
    """数据持久化类"""

    def __init__(self, storage_dir: str = "data"):
        """
        初始化数据持久化

        Args:
            storage_dir: 存储目录
        """
        self.storage_dir = storage_dir
        self._ensure_directory()

    def _ensure_directory(self):
        """确保存储目录存在"""
        if not os.path.exists(self.storage_dir):
            os.makedirs(self.storage_dir)

    def save_trade_logs(self, strategy_name: str, logs: List[Dict]) -> bool:
        """
        保存交易日志

        Args:
            strategy_name: 策略名称
            logs: 交易日志列表

        Returns:
            bool: 是否保存成功
        """
        try:
            file_path = os.path.join(self.storage_dir, f"{strategy_name}_trades.json")
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(logs, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"保存交易日志失败: {e}")
            return False

    def load_trade_logs(self, strategy_name: str) -> List[Dict]:
        """
        加载交易日志

        Args:
            strategy_name: 策略名称

        Returns:
            List[Dict]: 交易日志列表
        """
        try:
            file_path = os.path.join(self.storage_dir, f"{strategy_name}_trades.json")
            if not os.path.exists(file_path):
                return []
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"加载交易日志失败: {e}")
            return []

    def save_execution_logs(self, strategy_name: str, logs: List[Dict]) -> bool:
        """
        保存执行日志

        Args:
            strategy_name: 策略名称
            logs: 执行日志列表

        Returns:
            bool: 是否保存成功
        """
        try:
            file_path = os.path.join(self.storage_dir, f"{strategy_name}_executions.json")
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(logs, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"保存执行日志失败: {e}")
            return False

    def load_execution_logs(self, strategy_name: str) -> List[Dict]:
        """
        加载执行日志

        Args:
            strategy_name: 策略名称

        Returns:
            List[Dict]: 执行日志列表
        """
        try:
            file_path = os.path.join(self.storage_dir, f"{strategy_name}_executions.json")
            if not os.path.exists(file_path):
                return []
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"加载执行日志失败: {e}")
            return []

    def save_market_data(self, symbol: str, data: List[Dict]) -> bool:
        """
        保存市场数据

        Args:
            symbol: 交易对
            data: 市场数据列表

        Returns:
            bool: 是否保存成功
        """
        try:
            file_path = os.path.join(self.storage_dir, f"market_data_{symbol}.json")
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"保存市场数据失败: {e}")
            return False

    def load_market_data(self, symbol: str) -> List[Dict]:
        """
        加载市场数据

        Args:
            symbol: 交易对

        Returns:
            List[Dict]: 市场数据列表
        """
        try:
            file_path = os.path.join(self.storage_dir, f"market_data_{symbol}.json")
            if not os.path.exists(file_path):
                return []
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"加载市场数据失败: {e}")
            return []

    def save_strategy_state(self, strategy_name: str, state: Dict) -> bool:
        """
        保存策略状态

        Args:
            strategy_name: 策略名称
            state: 策略状态

        Returns:
            bool: 是否保存成功
        """
        try:
            file_path = os.path.join(self.storage_dir, f"{strategy_name}_state.json")
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"保存策略状态失败: {e}")
            return False

    def load_strategy_state(self, strategy_name: str) -> Dict:
        """
        加载策略状态

        Args:
            strategy_name: 策略名称

        Returns:
            Dict: 策略状态
        """
        try:
            file_path = os.path.join(self.storage_dir, f"{strategy_name}_state.json")
            if not os.path.exists(file_path):
                return {}
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"加载策略状态失败: {e}")
            return {}

    def save_order_history(self, orders: List[Dict]) -> bool:
        """
        保存订单历史

        Args:
            orders: 订单列表

        Returns:
            bool: 是否保存成功
        """
        try:
            file_path = os.path.join(self.storage_dir, "order_history.json")
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(orders, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"保存订单历史失败: {e}")
            return False

    def load_order_history(self) -> List[Dict]:
        """
        加载订单历史

        Returns:
            List[Dict]: 订单列表
        """
        try:
            file_path = os.path.join(self.storage_dir, "order_history.json")
            if not os.path.exists(file_path):
                return []
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"加载订单历史失败: {e}")
            return []

    def save_account_history(self, history: List[Dict]) -> bool:
        """
        保存账户历史

        Args:
            history: 账户历史列表

        Returns:
            bool: 是否保存成功
        """
        try:
            file_path = os.path.join(self.storage_dir, "account_history.json")
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(history, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"保存账户历史失败: {e}")
            return False

    def load_account_history(self) -> List[Dict]:
        """
        加载账户历史

        Returns:
            List[Dict]: 账户历史列表
        """
        try:
            file_path = os.path.join(self.storage_dir, "account_history.json")
            if not os.path.exists(file_path):
                return []
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"加载账户历史失败: {e}")
            return []

    def clear_data(self, strategy_name: str = None):
        """
        清理数据

        Args:
            strategy_name: 策略名称，None表示清理所有数据
        """
        if strategy_name:
            # 清理指定策略的数据
            files = [
                f"{strategy_name}_trades.json",
                f"{strategy_name}_executions.json",
                f"{strategy_name}_state.json"
            ]
        else:
            # 清理所有数据
            files = os.listdir(self.storage_dir)

        for file in files:
            file_path = os.path.join(self.storage_dir, file)
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except Exception as e:
                    print(f"删除文件失败 {file}: {e}")

# 全局实例
data_persistence = DataPersistence()
