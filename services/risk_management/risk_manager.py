import os
import time
from okx_api_client import OKXAPIClient

# 初始化日志配置
from commons.logger_config import global_logger_config

# 获取区域化日志记录器
def get_logger(region=None):
    return global_logger_config.get_logger(region=region)

# 创建默认日志记录器
logger = get_logger("Risk")

class RiskManager:
    """风险管理服务，封装OKX API的风险管理功能"""
    
    def __init__(self, api_client=None):
        """
        初始化风险管理服务
        
        Args:
            api_client (OKXAPIClient, optional): OKX API客户端实例
        """
        if api_client:
            self.api_client = api_client
        else:
            # 创建默认的API客户端
            self.api_client = OKXAPIClient()
        
        # 默认风险参数
        self.risk_params = {
            'max_leverage': 10,            # 最大杠杆倍数
            'max_position_percent': 0.5,    # 单个品种最大仓位占比
            'max_total_position': 0.8,      # 总仓位最大占比
            'stop_loss_percent': 0.05,      # 默认止损比例
            'take_profit_percent': 0.1,     # 默认止盈比例
            'max_order_amount': 10000,      # 最大订单金额（美元）
            'max_daily_loss': 0.1,          # 每日最大亏损比例
            'max_consecutive_losses': 5,    # 最大连续亏损次数
            'min_account_balance': 100      # 最小账户余额
        }
        
        # 风险状态
        self.risk_state = {
            'daily_pnl': 0.0,
            'consecutive_losses': 0,
            'current_leverage': 1,
            'total_position_value': 0.0,
            'account_balance': 0.0
        }
        
        logger.info("风险管理服务初始化完成")
    
    def update_risk_params(self, **kwargs):
        """
        更新风险参数
        
        Args:
            **kwargs: 风险参数键值对
        """
        for key, value in kwargs.items():
            if key in self.risk_params:
                old_value = self.risk_params[key]
                self.risk_params[key] = value
                logger.info(f"更新风险参数: {key}, 从 {old_value} 到 {value}")
            else:
                logger.warning(f"未知的风险参数: {key}")
    
    def get_account_balance(self):
        """
        获取账户余额
        
        Returns:
            dict: 账户余额信息
        """
        try:
            logger.debug("获取账户余额请求")
            
            result = self.api_client.get_account_balance()
            if result:
                balance_info = result[0]
                
                # 更新风险状态
                total_eq = float(balance_info.get('totalEq', 0))
                self.risk_state['account_balance'] = total_eq
                
                logger.info(f"获取账户余额成功: 总权益: {total_eq} USDT")
                return balance_info
            
            logger.error("获取账户余额失败: API返回为空")
            return None
            
        except Exception as e:
            logger.error(f"获取账户余额失败: {e}")
            return None
    
    def get_positions(self, inst_id=None):
        """
        获取持仓信息
        
        Args:
            inst_id (str, optional): 交易对
        
        Returns:
            list: 持仓信息列表
        """
        try:
            logger.debug(f"获取持仓信息请求: {inst_id}")
            
            result = self.api_client.get_positions(inst_id)
            if result is not None:
                logger.info(f"获取持仓信息成功，共 {len(result)} 个持仓")
                
                # 更新风险状态
                total_position_value = 0.0
                for position in result:
                    pos_sz = float(position.get('pos', 0))
                    avg_px = float(position.get('avgPx', 0))
                    total_position_value += abs(pos_sz * avg_px)
                
                self.risk_state['total_position_value'] = total_position_value
                
                return result
            
            logger.error("获取持仓信息失败: API返回为空")
            return []
            
        except Exception as e:
            logger.error(f"获取持仓信息失败: {e}")
            return []
    
    def get_pending_orders(self, inst_id=None):
        """
        获取待成交订单
        
        Args:
            inst_id (str, optional): 交易对
        
        Returns:
            list: 待成交订单列表
        """
        try:
            logger.debug(f"获取待成交订单请求: {inst_id}")
            
            # 调用API客户端获取订单
            result = self.api_client.get_pending_orders(inst_id, state='live')
            if result:
                logger.info(f"获取待成交订单成功，共 {len(result)} 个订单")
                return result
            
            logger.debug("获取待成交订单: 无待成交订单")
            return []
            
        except Exception as e:
            logger.error(f"获取待成交订单失败: {e}")
            return []
    
    def set_leverage(self, inst_id, lever, mgn_mode='isolated'):
        """
        设置杠杆
        
        Args:
            inst_id (str): 交易对
            lever (int): 杠杆倍数
            mgn_mode (str, optional): 保证金模式，'isolated' 或 'cross'
        
        Returns:
            dict: 设置结果
        """
        try:
            # 检查杠杆是否在允许范围内
            if lever > self.risk_params['max_leverage']:
                logger.warning(f"请求的杠杆 {lever} 超过最大允许杠杆 {self.risk_params['max_leverage']}，自动调整为最大杠杆")
                lever = self.risk_params['max_leverage']
            
            logger.info(f"设置杠杆请求: {inst_id}, 杠杆: {lever}, 保证金模式: {mgn_mode}")
            
            result = self.api_client.set_leverage(inst_id, lever, mgn_mode)
            if result:
                logger.info(f"设置杠杆成功: {inst_id}, 杠杆: {lever}")
                
                # 更新风险状态
                self.risk_state['current_leverage'] = lever
                
                return result
            
            logger.error("设置杠杆失败: API返回为空")
            return None
            
        except Exception as e:
            logger.error(f"设置杠杆失败 [{inst_id}]: {e}")
            return None
    
    def calculate_position_risk(self, position):
        """
        计算持仓风险
        
        Args:
            position (dict): 持仓信息
        
        Returns:
            dict: 风险评估结果
        """
        try:
            pos_sz = float(position.get('pos', 0))
            avg_px = float(position.get('avgPx', 0))
            mark_px = float(position.get('markPx', avg_px))
            liq_px = float(position.get('liqPx', 0))
            
            # 计算风险指标
            position_value = abs(pos_sz * mark_px)
            unrealized_pnl = float(position.get('upl', 0))
            pnl_ratio = (unrealized_pnl / position_value) if position_value > 0 else 0
            
            # 计算爆仓风险
            distance_to_liq = 0.0
            if liq_px > 0:
                if pos_sz > 0:  # 多仓
                    distance_to_liq = (mark_px - liq_px) / mark_px
                else:  # 空仓
                    distance_to_liq = (liq_px - mark_px) / mark_px
            
            risk_assessment = {
                'position_value': position_value,
                'unrealized_pnl': unrealized_pnl,
                'pnl_ratio': pnl_ratio,
                'distance_to_liquidation': distance_to_liq,
                'liquidation_price': liq_px,
                'is_in_danger': distance_to_liq < 0.05
            }
            
            return risk_assessment
            
        except Exception as e:
            logger.error(f"计算持仓风险失败: {e}")
            return None
    
    def assess_overall_risk(self):
        """
        评估整体风险
        
        Returns:
            dict: 整体风险评估结果
        """
        try:
            logger.debug("评估整体风险请求")
            
            # 获取最新账户和持仓信息
            account_balance = self.get_account_balance()
            positions = self.get_positions()
            
            if not account_balance:
                logger.error("评估整体风险失败: 无法获取账户余额")
                return None
            
            total_eq = float(account_balance.get('totalEq', 0))
            used_margin = float(account_balance.get('usedMargin', 0))
            margin_ratio = (used_margin / total_eq) if total_eq > 0 else 0
            
            # 计算持仓风险
            position_risks = []
            high_risk_positions = 0
            total_position_value = 0.0
            
            for position in positions:
                pos_risk = self.calculate_position_risk(position)
                if pos_risk:
                    position_risks.append(pos_risk)
                    total_position_value += pos_risk['position_value']
                    if pos_risk['is_in_danger']:
                        high_risk_positions += 1
            
            # 计算整体风险指标
            overall_risk = {
                'account_balance': total_eq,
                'used_margin_ratio': margin_ratio,
                'total_position_value': total_position_value,
                'position_value_ratio': (total_position_value / total_eq) if total_eq > 0 else 0,
                'high_risk_positions': high_risk_positions,
                'total_positions': len(positions),
                'leverage': self.risk_state['current_leverage'],
                'daily_pnl': self.risk_state['daily_pnl'],
                'consecutive_losses': self.risk_state['consecutive_losses'],
                'is_account_healthy': self._check_account_health()
            }
            
            logger.info(f"整体风险评估完成: 保证金使用率: {margin_ratio:.2%}, 持仓价值比例: {overall_risk['position_value_ratio']:.2%}")
            return overall_risk
            
        except Exception as e:
            logger.error(f"评估整体风险失败: {e}")
            return None
    
    def _check_account_health(self):
        """
        检查账户健康状况
        
        Returns:
            bool: 账户是否健康
        """
        # 检查账户余额
        if self.risk_state['account_balance'] < self.risk_params['min_account_balance']:
            logger.warning(f"账户余额过低: {self.risk_state['account_balance']} < {self.risk_params['min_account_balance']}")
            return False
        
        # 检查每日亏损
        if self.risk_state['daily_pnl'] < -self.risk_params['max_daily_loss'] * self.risk_state['account_balance']:
            logger.warning(f"每日亏损超过限制: {self.risk_state['daily_pnl']}")
            return False
        
        # 检查连续亏损次数
        if self.risk_state['consecutive_losses'] >= self.risk_params['max_consecutive_losses']:
            logger.warning(f"连续亏损次数超过限制: {self.risk_state['consecutive_losses']}")
            return False
        
        return True
    
    def check_order_risk(self, order_info):
        """
        检查订单风险
        
        Args:
            order_info (dict): 订单信息，包含 inst_id, side, sz, px 等
        
        Returns:
            tuple: (bool, str) 是否允许下单，原因
        """
        try:
            logger.debug(f"检查订单风险请求: {order_info}")
            
            # 检查账户健康状况
            if not self._check_account_health():
                return False, "账户健康状况不佳"
            
            # 检查订单金额
            sz = float(order_info.get('sz', 0))
            px = float(order_info.get('px', 0)) or 1.0  # 如果是市价单，使用默认价格
            order_amount = sz * px
            
            if order_amount > self.risk_params['max_order_amount']:
                return False, f"订单金额超过限制: {order_amount} > {self.risk_params['max_order_amount']}"
            
            # 检查杠杆
            if self.risk_state['current_leverage'] > self.risk_params['max_leverage']:
                return False, f"当前杠杆超过限制: {self.risk_state['current_leverage']} > {self.risk_params['max_leverage']}"
            
            # 检查持仓比例
            if self.risk_state['total_position_value'] + order_amount > self.risk_state['account_balance'] * self.risk_params['max_total_position']:
                return False, "总持仓将超过限制"
            
            logger.info(f"订单风险检查通过: 金额: {order_amount} USDT")
            return True, "OK"
            
        except Exception as e:
            logger.error(f"检查订单风险失败: {e}")
            return False, f"风险检查失败: {e}"
    
    def update_daily_pnl(self, pnl):
        """
        更新每日盈亏
        
        Args:
            pnl (float): 盈亏金额
        """
        self.risk_state['daily_pnl'] += pnl
        
        # 更新连续亏损次数
        if pnl < 0:
            self.risk_state['consecutive_losses'] += 1
            logger.warning(f"连续亏损次数: {self.risk_state['consecutive_losses']}")
        else:
            self.risk_state['consecutive_losses'] = 0
        
        logger.debug(f"更新每日盈亏: {pnl}, 当前每日盈亏: {self.risk_state['daily_pnl']}")
    
    def reset_daily_pnl(self):
        """
        重置每日盈亏
        """
        logger.info(f"重置每日盈亏，当前值: {self.risk_state['daily_pnl']}")
        self.risk_state['daily_pnl'] = 0.0
        self.risk_state['consecutive_losses'] = 0
    
    def get_risk_report(self):
        """
        获取风险报告
        
        Returns:
            dict: 风险报告
        """
        try:
            logger.debug("获取风险报告请求")
            
            # 评估整体风险
            overall_risk = self.assess_overall_risk()
            if not overall_risk:
                return None
            
            # 获取所有持仓的风险评估
            positions = self.get_positions()
            position_risks = []
            
            for position in positions:
                pos_risk = self.calculate_position_risk(position)
                if pos_risk:
                    position_risks.append({
                        'inst_id': position['instId'],
                        'side': 'long' if float(position['pos']) > 0 else 'short',
                        'size': float(position['pos']),
                        'avg_price': float(position['avgPx']),
                        'mark_price': float(position['markPx']),
                        'risk': pos_risk
                    })
            
            # 生成风险报告
            risk_report = {
                'timestamp': int(time.time() * 1000),
                'overall_risk': overall_risk,
                'position_risks': position_risks,
                'risk_params': self.risk_params,
                'risk_state': self.risk_state
            }
            
            logger.info("生成风险报告成功")
            return risk_report
            
        except Exception as e:
            logger.error(f"获取风险报告失败: {e}")
            return None

# 创建默认服务实例
default_risk_manager = None

def get_risk_manager():
    """获取默认风险管理服务实例"""
    global default_risk_manager
    if not default_risk_manager:
        default_risk_manager = RiskManager()
    return default_risk_manager

if __name__ == "__main__":
    # 测试风险管理服务
    try:
        # 创建服务实例
        risk_manager = RiskManager()
        
        # 测试更新风险参数
        risk_manager.update_risk_params(max_leverage=20, stop_loss_percent=0.03)
        
        # 测试获取账户余额
        account_balance = risk_manager.get_account_balance()
        if account_balance:
            logger.info(f"账户余额测试成功: {account_balance}")
        
        # 测试获取持仓
        positions = risk_manager.get_positions()
        logger.info(f"持仓数量: {len(positions)}")
        
        # 测试评估整体风险
        overall_risk = risk_manager.assess_overall_risk()
        if overall_risk:
            logger.info(f"整体风险评估: 账户健康: {overall_risk['is_account_healthy']}")
        
        # 测试订单风险检查
        order_info = {'inst_id': 'BTC-USDT-SWAP', 'side': 'buy', 'sz': '0.01', 'px': '50000'}
        is_allowed, reason = risk_manager.check_order_risk(order_info)
        logger.info(f"订单风险检查: {is_allowed}, 原因: {reason}")
        
    except Exception as e:
        logger.error(f"测试失败: {e}")
