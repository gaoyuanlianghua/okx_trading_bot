"""
账户数据自动核对模块
每次订单成交后自动与实际账户对齐数据
"""

import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class AccountSyncManager:
    """
    账户数据同步管理器
    
    负责在每次交易后自动核对并同步本地数据与实际账户数据
    """
    
    def __init__(self, rest_client):
        """
        初始化账户同步管理器
        
        Args:
            rest_client: OKX REST API客户端
        """
        self.rest_client = rest_client
        self.sync_threshold = 0.0001  # 同步阈值（BTC）
        self.usdt_threshold = 0.01    # USDT同步阈值
        
    async def sync_after_trade(self, trade_result: Dict[str, Any]) -> bool:
        """
        交易完成后自动同步账户数据
        
        Args:
            trade_result: 交易结果
            
        Returns:
            bool: 同步是否成功
        """
        try:
            logger.info("=" * 60)
            logger.info("🔄 交易完成，开始自动核对账户数据...")
            logger.info("=" * 60)
            
            # 1. 获取实际账户余额
            actual_balance = await self._get_actual_balance()
            if not actual_balance:
                logger.error("❌ 获取实际账户余额失败")
                return False
            
            # 2. 获取本地数据
            from core.utils.persistence import persistence_manager
            local_data = persistence_manager.load_data("order_agent_state.json") or {}
            
            # 3. 对比并同步数据
            sync_results = await self._compare_and_sync(actual_balance, local_data, trade_result)
            
            # 4. 保存同步后的数据
            if sync_results.get('updated', False):
                persistence_manager.save_data("order_agent_state.json", local_data)
                logger.info("✅ 同步数据已保存到本地")
                
                # 5. 同步到OSS
                try:
                    from core.utils.persistence import persistence_manager
                    if persistence_manager.oss_manager:
                        persistence_manager.oss_manager.save_to_oss("order_agent_state.json", local_data)
                        logger.info("✅ 同步数据已上传到OSS")
                except Exception as e:
                    logger.warning(f"⚠️ OSS同步失败: {e}")
            
            # 6. 检查数据一致性
            await self._check_consistency(actual_balance, local_data)
            
            logger.info("=" * 60)
            logger.info("🔄 账户数据核对完成")
            logger.info("=" * 60)
            
            return True
            
        except Exception as e:
            logger.error(f"❌ 交易后同步失败: {e}")
            return False
    
    async def _get_actual_balance(self) -> Optional[Dict[str, float]]:
        """
        获取实际账户余额
        
        Returns:
            Optional[Dict[str, float]]: 余额数据
        """
        try:
            balance = await self.rest_client.get_account_balance()
            if not balance:
                return None
            
            result = {}
            details = balance.get('details', [])
            
            for item in details:
                ccy = item.get('ccy')
                avail_bal = float(item.get('availBal', 0))
                if avail_bal > 0:
                    result[ccy] = avail_bal
            
            logger.info(f"📊 实际账户余额: {result}")
            return result
            
        except Exception as e:
            logger.error(f"获取实际余额失败: {e}")
            return None
    
    async def _compare_and_sync(self, actual_balance: Dict[str, float], 
                                local_data: Dict[str, Any],
                                trade_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        对比并同步数据
        
        Args:
            actual_balance: 实际余额
            local_data: 本地数据
            trade_result: 交易结果
            
        Returns:
            Dict[str, Any]: 同步结果
        """
        result = {'updated': False, 'differences': []}
        
        # 确保positions存在
        if 'positions' not in local_data:
            local_data['positions'] = {}
        
        positions = local_data['positions']
        
        # 对比BTC
        actual_btc = actual_balance.get('BTC', 0)
        local_btc = positions.get('BTC', {}).get('available', 0)
        
        if abs(actual_btc - local_btc) > self.sync_threshold:
            logger.warning(f"⚠️ BTC余额不一致: 实际={actual_btc:.8f}, 本地={local_btc:.8f}, 差异={actual_btc - local_btc:.8f}")
            positions['BTC'] = {
                'available': actual_btc,
                'total': actual_btc,
                'last_sync': datetime.now().isoformat()
            }
            result['updated'] = True
            result['differences'].append(f"BTC: {local_btc:.8f} -> {actual_btc:.8f}")
            logger.info(f"✅ 已同步BTC余额: {actual_btc:.8f}")
        else:
            logger.info(f"✅ BTC余额一致: {actual_btc:.8f}")
        
        # 对比USDT
        actual_usdt = actual_balance.get('USDT', 0)
        local_usdt = positions.get('USDT', {}).get('available', 0)
        
        if abs(actual_usdt - local_usdt) > self.usdt_threshold:
            logger.warning(f"⚠️ USDT余额不一致: 实际={actual_usdt:.2f}, 本地={local_usdt:.2f}, 差异={actual_usdt - local_usdt:.2f}")
            positions['USDT'] = {
                'available': actual_usdt,
                'total': actual_usdt,
                'last_sync': datetime.now().isoformat()
            }
            result['updated'] = True
            result['differences'].append(f"USDT: {local_usdt:.2f} -> {actual_usdt:.2f}")
            logger.info(f"✅ 已同步USDT余额: {actual_usdt:.2f}")
        else:
            logger.info(f"✅ USDT余额一致: {actual_usdt:.2f}")
        
        # 更新交易记录
        if trade_result.get('success'):
            self._update_trade_history(local_data, trade_result)
            result['updated'] = True
        
        return result
    
    def _update_trade_history(self, local_data: Dict[str, Any], trade_result: Dict[str, Any]):
        """
        更新交易历史
        
        Args:
            local_data: 本地数据
            trade_result: 交易结果
        """
        if 'trade_history' not in local_data:
            local_data['trade_history'] = []
        
        # 添加交易记录
        trade_record = {
            'trade_id': trade_result.get('order_id'),
            'side': trade_result.get('side'),
            'inst_id': trade_result.get('inst_id'),
            'price': trade_result.get('price'),
            'size': trade_result.get('size'),
            'timestamp': datetime.now().isoformat(),
            'state': 'filled',
            'sync_status': 'synced'  # 标记为已同步
        }
        
        local_data['trade_history'].append(trade_record)
        
        # 更新统计
        local_data['order_count'] = local_data.get('order_count', 0) + 1
        
        logger.info(f"📝 已添加交易记录: {trade_record['side']} {trade_record['size']} @ {trade_record['price']}")
    
    async def _check_consistency(self, actual_balance: Dict[str, float], local_data: Dict[str, Any]):
        """
        检查数据一致性
        
        Args:
            actual_balance: 实际余额
            local_data: 本地数据
        """
        positions = local_data.get('positions', {})
        
        # 检查BTC
        actual_btc = actual_balance.get('BTC', 0)
        local_btc = positions.get('BTC', {}).get('available', 0)
        
        # 检查USDT
        actual_usdt = actual_balance.get('USDT', 0)
        local_usdt = positions.get('USDT', {}).get('available', 0)
        
        # 计算总价值（简化计算）
        current_price = 72000  # 假设当前价格，实际应该从市场数据获取
        actual_total = actual_usdt + actual_btc * current_price
        local_total = local_usdt + local_btc * current_price
        
        logger.info("📊 数据一致性检查:")
        logger.info(f"  实际账户总价值: ~{actual_total:.2f} USDT")
        logger.info(f"  本地系统总价值: ~{local_total:.2f} USDT")
        
        if abs(actual_total - local_total) > 1.0:  # 1 USDT阈值
            logger.warning(f"⚠️ 总价值差异较大: {abs(actual_total - local_total):.2f} USDT")
        else:
            logger.info(f"✅ 数据一致性良好")


# 创建全局实例
account_sync_manager = None

def init_account_sync_manager(rest_client):
    """初始化账户同步管理器"""
    global account_sync_manager
    account_sync_manager = AccountSyncManager(rest_client)
    logger.info("✅ 账户同步管理器已初始化")
    return account_sync_manager
