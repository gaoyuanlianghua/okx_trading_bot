import os
import time
import uuid
from okx_api_client import OKXAPIClient

# 初始化日志配置
from commons.logger_config import global_logger_config

# 获取区域化日志记录器
def get_logger(region=None):
    return global_logger_config.get_logger(region=region)

# 创建默认日志记录器
logger = get_logger("Trade")

class OrderManager:
    """订单管理服务，封装OKX API的订单相关功能"""
    
    def __init__(self, api_client=None):
        """
        初始化订单管理服务
        
        Args:
            api_client (OKXAPIClient, optional): OKX API客户端实例
        """
        if api_client:
            self.api_client = api_client
        else:
            # 创建默认的API客户端
            self.api_client = OKXAPIClient()
        self.order_history = []
        self.pending_orders = {}
        
        logger.info("订单管理服务初始化完成")
    
    def place_order(self, inst_id, side, ord_type, sz, px=None, tp_px=None, sl_px=None):
        """
        下单
        
        Args:
            inst_id (str): 交易对
            side (str): 买卖方向，'buy' 或 'sell'
            ord_type (str): 订单类型，'market' 或 'limit'
            sz (str): 订单数量
            px (str, optional): 订单价格，限价单必填
            tp_px (str, optional): 止盈价格
            sl_px (str, optional): 止损价格
        
        Returns:
            dict: 订单信息
        """
        try:
            logger.info(f"下单请求: {inst_id}, {side}, {ord_type}, 数量: {sz}, 价格: {px}")
            
            # 调用API下单
            result = self.api_client.place_order(
                inst_id=inst_id,
                side=side,
                ord_type=ord_type,
                sz=sz,
                px=px,
                tp_px=tp_px,
                sl_px=sl_px
            )
            
            if result:
                order_info = result[0]
                
                # 保存订单信息到历史记录
                self.order_history.append(order_info)
                
                # 如果是未成交订单，添加到待处理订单列表
                if order_info.get('state') in ['live', 'partially_filled']:
                    self.pending_orders[order_info['ordId']] = order_info
                
                logger.info(f"下单成功: {order_info['ordId']}, 状态: {order_info['state']}")
                return order_info
            
            logger.error(f"下单失败: API返回为空")
            return None
            
        except Exception as e:
            logger.error(f"下单失败 [{inst_id}]: {e}")
            return None
    
    def place_market_order(self, inst_id, side, sz):
        """
        下市价单
        
        Args:
            inst_id (str): 交易对
            side (str): 买卖方向
            sz (str): 订单数量
        
        Returns:
            dict: 订单信息
        """
        return self.place_order(inst_id, side, 'market', sz)
    
    def place_limit_order(self, inst_id, side, sz, px, tp_px=None, sl_px=None):
        """
        下限价单
        
        Args:
            inst_id (str): 交易对
            side (str): 买卖方向
            sz (str): 订单数量
            px (str): 订单价格
            tp_px (str, optional): 止盈价格
            sl_px (str, optional): 止损价格
        
        Returns:
            dict: 订单信息
        """
        return self.place_order(inst_id, side, 'limit', sz, px, tp_px, sl_px)
    
    def cancel_order(self, inst_id, ord_id):
        """
        取消订单
        
        Args:
            inst_id (str): 交易对
            ord_id (str): 订单ID
        
        Returns:
            dict: 取消结果
        """
        try:
            logger.info(f"取消订单请求: {ord_id}, {inst_id}")
            
            result = self.api_client.cancel_order(inst_id, ord_id)
            if result:
                cancel_result = result[0]
                
                # 从待处理订单列表中移除
                if ord_id in self.pending_orders:
                    del self.pending_orders[ord_id]
                
                logger.info(f"取消订单成功: {ord_id}")
                return cancel_result
            
            logger.error(f"取消订单失败: API返回为空")
            return None
            
        except Exception as e:
            logger.error(f"取消订单失败 [{ord_id}]: {e}")
            return None
    
    def cancel_all_orders(self, inst_id=None):
        """
        取消所有订单
        
        Args:
            inst_id (str, optional): 交易对，不指定则取消所有订单
        
        Returns:
            list: 取消结果列表
        """
        try:
            logger.info(f"取消所有订单请求: {inst_id or '所有交易对'}")
            
            # 获取所有未成交订单
            pending_orders = self.get_pending_orders(inst_id)
            if not pending_orders:
                logger.info("没有未成交订单需要取消")
                return []
            
            # 逐个取消订单
            results = []
            for order in pending_orders:
                result = self.cancel_order(order['instId'], order['ordId'])
                if result:
                    results.append(result)
                # 避免请求过快
                time.sleep(0.1)
            
            logger.info(f"取消订单完成，共取消 {len(results)} 个订单")
            return results
            
        except Exception as e:
            logger.error(f"取消所有订单失败: {e}")
            return []
    
    def get_order(self, inst_id, ord_id):
        """
        获取订单信息
        
        Args:
            inst_id (str): 交易对
            ord_id (str): 订单ID
        
        Returns:
            dict: 订单信息
        """
        try:
            logger.debug(f"获取订单信息请求: {ord_id}, {inst_id}")
            
            result = self.api_client.get_order(inst_id, ord_id)
            if result:
                order_info = result[0]
                
                # 更新订单历史记录
                for i, order in enumerate(self.order_history):
                    if order['ordId'] == ord_id:
                        self.order_history[i] = order_info
                        break
                
                # 更新待处理订单列表
                if order_info.get('state') in ['live', 'partially_filled']:
                    self.pending_orders[ord_id] = order_info
                elif ord_id in self.pending_orders:
                    del self.pending_orders[ord_id]
                
                return order_info
            
            logger.error(f"获取订单信息失败: API返回为空")
            return None
            
        except Exception as e:
            logger.error(f"获取订单信息失败 [{ord_id}]: {e}")
            return None
    
    def get_pending_orders(self, inst_id=None):
        """
        获取未成交订单
        
        Args:
            inst_id (str, optional): 交易对，不指定则获取所有未成交订单
        
        Returns:
            list: 未成交订单列表
        """
        try:
            logger.debug(f"获取未成交订单请求: {inst_id or '所有交易对'}")
            
            result = self.api_client.get_pending_orders(inst_id)
            if result:
                # 更新待处理订单列表
                self.pending_orders = {order['ordId']: order for order in result if order.get('state') in ['live', 'partially_filled']}
                
                logger.debug(f"获取未成交订单成功，共 {len(result)} 个订单")
                return result
            
            logger.error(f"获取未成交订单失败: API返回为空")
            return []
            
        except Exception as e:
            logger.error(f"获取未成交订单失败: {e}")
            return []
    
    def get_order_history(self, limit=100):
        """
        获取订单历史记录
        
        Args:
            limit (int, optional): 返回数量，默认100
        
        Returns:
            list: 订单历史记录
        """
        try:
            # 从API获取最新的订单历史
            # 注意：OKX API的订单历史需要分页获取，这里简化处理
            logger.debug(f"获取订单历史记录请求，限制: {limit}")
            
            # 这里返回本地保存的订单历史
            return self.order_history[-limit:]
            
        except Exception as e:
            logger.error(f"获取订单历史记录失败: {e}")
            return []
    
    def get_orders(self, inst_id=None):
        """
        获取订单信息
        
        Args:
            inst_id (str, optional): 交易对
        
        Returns:
            list: 订单列表
        """
        # 调用get_pending_orders获取未成交订单
        return self.get_pending_orders(inst_id)
    
    def get_fills(self, ord_id=None, inst_id=None, limit=100):
        """
        获取成交明细
        
        Args:
            ord_id (str, optional): 订单ID
            inst_id (str, optional): 交易对
            limit (int, optional): 返回数量，默认100
        
        Returns:
            list: 成交明细列表
        """
        try:
            logger.debug(f"获取成交明细请求: 订单ID: {ord_id}, 交易对: {inst_id}, 限制: {limit}")
            
            # OKX API的成交明细获取需要使用不同的endpoint，这里简化处理
            # 实际实现需要调用相应的API
            return []
            
        except Exception as e:
            logger.error(f"获取成交明细失败: {e}")
            return []
    
    def update_order_status(self, ord_id):
        """
        更新订单状态
        
        Args:
            ord_id (str): 订单ID
        
        Returns:
            dict: 更新后的订单信息
        """
        try:
            # 获取最新订单状态
            order = self.get_order(None, ord_id)  # 不指定inst_id，让API自动处理
            if order:
                logger.debug(f"订单状态更新: {ord_id}, 新状态: {order['state']}")
                return order
            return None
            
        except Exception as e:
            logger.error(f"更新订单状态失败 [{ord_id}]: {e}")
            return None
    
    def get_order_summary(self):
        """
        获取订单摘要信息
        
        Returns:
            dict: 订单摘要
        """
        try:
            # 获取未成交订单
            pending_orders = self.get_pending_orders()
            
            # 统计订单数量
            summary = {
                'total_pending': len(pending_orders),
                'buy_orders': len([o for o in pending_orders if o['side'] == 'buy']),
                'sell_orders': len([o for o in pending_orders if o['side'] == 'sell']),
                'total_history': len(self.order_history),
                'pending_orders': pending_orders
            }
            
            logger.debug(f"获取订单摘要成功: {summary}")
            return summary
            
        except Exception as e:
            logger.error(f"获取订单摘要失败: {e}")
            return None

# 创建默认服务实例
default_order_manager = None

def get_order_manager():
    """获取默认订单管理服务实例"""
    global default_order_manager
    if not default_order_manager:
        default_order_manager = OrderManager()
    return default_order_manager

if __name__ == "__main__":
    # 测试订单管理服务
    try:
        # 创建服务实例
        order_manager = OrderManager()
        
        # 测试获取未成交订单
        pending_orders = order_manager.get_pending_orders('BTC-USDT-SWAP')
        logger.info(f"未成交订单数量: {len(pending_orders)}")
        
        # 测试获取订单摘要
        summary = order_manager.get_order_summary()
        if summary:
            logger.info(f"订单摘要: 未成交: {summary['total_pending']}, 历史总订单: {summary['total_history']}")
        
    except Exception as e:
        logger.error(f"测试失败: {e}")
