"""
盈利增长管理器
确保每次交易都实现正增长，实现BTC和USDT的相互增长
"""

import json
import logging
import yaml
import requests
import hmac
import hashlib
import base64
from typing import Dict, Any, Optional, Tuple
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class ProfitGrowthManager:
    """
    盈利增长管理器
    
    核心原则：
    1. 买入时必须确保未来能盈利卖出（低买）
    2. 卖出时必须确保盈利（高卖）
    3. 每次交易后，USDT和BTC的总价值都应该增长
    """
    
    def __init__(self, storage_file: str = "./data/profit_growth_state.json"):
        """
        初始化盈利增长管理器

        Args:
            storage_file: 状态存储文件路径
        """
        self.storage_file = storage_file
        self.min_profit_rate = 0.005  # 最小盈利率 0.5%
        self.fee_rate = 0.001  # 单边手续费率 0.1%（OKX现货Taker费率）
        self.total_profit_usdt = 0.0  # 累计盈利（USDT）
        self.total_profit_btc = 0.0   # 累计盈利（BTC）
        self.trade_count = 0          # 交易次数
        self._last_sell_price = None  # 上次卖出价格
        self._avg_buy_price = 0.0     # 平均买入价格
        self._avg_sell_price = 0.0    # 平均卖出价格（用于做空持仓）
        self._total_btc_held = 0.0    # 持有的BTC总量

        # 加载API配置
        self.api_config = self._load_api_config()
        
        # 加载历史状态
        self._load_state()

        logger.info("盈利增长管理器初始化完成")
        logger.info(f"最小盈利率: {self.min_profit_rate * 100:.2f}%")
        logger.info(f"手续费率: {self.fee_rate * 100:.2f}%（按币种计价）")
        if self._last_sell_price:
            logger.info(f"上次卖出价格: {self._last_sell_price:.2f} USDT")
        if self._avg_buy_price > 0:
            logger.info(f"平均买入价格: {self._avg_buy_price:.2f} USDT")
            logger.info(f"持有BTC数量: {self._total_btc_held:.8f} BTC")
    
    def _load_api_config(self):
        """加载API配置"""
        try:
            with open('config/config.yaml', 'r') as f:
                config = yaml.safe_load(f)
            return config.get('api', {})
        except Exception as e:
            logger.warning(f"加载API配置失败: {e}")
            return {}
    
    def _get_timestamp(self):
        """获取时间戳"""
        return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'
    
    def _get_signature(self, timestamp, method, path, body=''):
        """生成签名"""
        api_secret = self.api_config.get('api_secret', '')
        message = timestamp + method + path + body
        mac = hmac.new(api_secret.encode('utf-8'), message.encode('utf-8'), hashlib.sha256)
        return base64.b64encode(mac.digest()).decode('utf-8')
    
    def _get_headers(self, timestamp, method, path, body=''):
        """获取API头信息"""
        return {
            'OK-ACCESS-KEY': self.api_config.get('api_key', ''),
            'OK-ACCESS-SIGN': self._get_signature(timestamp, method, path, body),
            'OK-ACCESS-TIMESTAMP': timestamp,
            'OK-ACCESS-PASSPHRASE': self.api_config.get('passphrase', ''),
            'Content-Type': 'application/json'
        }
    
    def _load_state(self):
        """加载状态"""
        try:
            import os
            if os.path.exists(self.storage_file):
                with open(self.storage_file, 'r') as f:
                    state = json.load(f)
                self.total_profit_usdt = state.get('total_profit_usdt', 0.0)
                self.total_profit_btc = state.get('total_profit_btc', 0.0)
                self.trade_count = state.get('trade_count', 0)
                self._last_sell_price = state.get('last_sell_price', None)
                self._avg_buy_price = state.get('avg_buy_price', 0.0)
                self._avg_sell_price = state.get('avg_sell_price', 0.0)
                self._total_btc_held = state.get('total_btc_held', 0.0)
                logger.info(f"加载盈利状态: 累计盈利 {self.total_profit_usdt:.4f} USDT, {self.total_profit_btc:.8f} BTC, 交易次数 {self.trade_count}")
        except Exception as e:
            logger.warning(f"加载盈利状态失败: {e}")
    
    def _save_state(self):
        """保存状态"""
        try:
            import os
            os.makedirs(os.path.dirname(self.storage_file), exist_ok=True)
            state = {
                'total_profit_usdt': self.total_profit_usdt,
                'total_profit_btc': self.total_profit_btc,
                'trade_count': self.trade_count,
                'last_sell_price': self._last_sell_price,
                'avg_buy_price': self._avg_buy_price,
                'avg_sell_price': self._avg_sell_price,
                'total_btc_held': self._total_btc_held,
                'last_update': datetime.now().isoformat()
            }
            with open(self.storage_file, 'w') as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            logger.error(f"保存盈利状态失败: {e}")
    
    def should_buy(self, current_price: float, last_sell_price: Optional[float] = None) -> Tuple[bool, str]:
        """
        判断是否应该买入

        买入条件：
        1. 当前价格低于上次卖出价格（低买）
        2. 或者没有持仓（首次买入）

        Args:
            current_price: 当前价格
            last_sell_price: 上次卖出价格（如果有），如果为None则使用持久化的值

        Returns:
            Tuple[bool, str]: (是否应该买入, 原因)
        """
        # 使用传入的值或持久化的值
        effective_last_sell_price = last_sell_price if last_sell_price is not None else self._last_sell_price

        if effective_last_sell_price is None:
            # 没有上次卖出记录，可以买入（首次买入）
            return True, "首次买入，无历史卖出记录"

        # 计算价格下跌幅度
        price_drop_rate = (effective_last_sell_price - current_price) / effective_last_sell_price

        # 买入条件：当前价格低于上次卖出价格，且跌幅超过0.20%
        # 梯度交易法：要求0.20%以上跌幅才买入，避免订单过于集中
        min_drop_rate = 0.002  # 0.20% 最小跌幅要求

        if price_drop_rate >= min_drop_rate:
            return True, f"价格从上次卖出价 {effective_last_sell_price:.2f} 下跌 {price_drop_rate * 100:.2f}%，满足买入条件（最小跌幅 {min_drop_rate * 100:.2f}%）"
        else:
            return False, f"价格跌幅不足: {price_drop_rate * 100:.2f}% < {min_drop_rate * 100:.2f}%，不满足买入条件"
    
    def should_sell(self, current_price: float, avg_price: float = None, is_short: bool = False) -> Tuple[bool, str, float]:
        """
        判断是否应该卖出

        卖出条件：
        1. 对于做多持仓：当前价格高于平均买入价格 + 手续费 + 最小盈利
        2. 对于做空持仓：当前价格低于平均卖出价格 - 手续费 - 最小盈利

        Args:
            current_price: 当前价格
            avg_price: 平均价格，如果为None则使用持久化的值
            is_short: 是否是做空持仓

        Returns:
            Tuple[bool, str, float]: (是否应该卖出, 原因, 预期收益率)
        """
        # 使用传入的值或持久化的值
        if is_short:
            effective_avg_price = avg_price if avg_price is not None else self._avg_sell_price
        else:
            effective_avg_price = avg_price if avg_price is not None else self._avg_buy_price

        if effective_avg_price <= 0:
            return False, "无持仓记录，无法计算收益率", 0.0

        # 计算手续费率（双向，买入和卖出）
        total_fee_rate = self.fee_rate * 2  # 0.2%

        # 计算飘逸值影响因子（这里使用一个简单的模型，实际应该根据市场趋势计算）
        # 飘逸值影响因子：基于当前价格的小幅波动预期
        drift_factor = 0.001  # 0.1%的飘逸值影响
        
        # 计算未来收益价格：现价 + 飘逸值的影响因子
        if is_short:
            # 做空时，价格下跌预期
            future_price = current_price * (1 - drift_factor)
        else:
            # 做多时，价格上涨预期
            future_price = current_price * (1 + drift_factor)

        # 计算预期收益率（考虑手续费）
        if is_short:
            # 做空收益 = (开仓价格 - 未来收益价格) / 开仓价格 - 手续费率
            expected_return = (effective_avg_price - future_price) / effective_avg_price - total_fee_rate
        else:
            # 做多收益 = (未来收益价格 - 开仓价格) / 开仓价格 - 手续费率
            expected_return = (future_price - effective_avg_price) / effective_avg_price - total_fee_rate

        # 卖出条件：收益率 >= 0.50%
        min_return = 0.005  # 0.5%

        if expected_return >= min_return:
            return True, f"预期收益率 {expected_return * 100:.2f}% >= 最小要求 {min_return * 100:.2f}%，满足卖出条件", expected_return
        else:
            return False, f"预期收益率不足: {expected_return * 100:.2f}% < {min_return * 100:.2f}%，不满足卖出条件", expected_return
    
    def record_trade(self, side: str, price: float, amount: float, profit: float = 0.0, fee_currency: str = 'USDT', leverage: float = 1.0):
        """
        记录交易

        Args:
            side: 'buy' 或 'sell'
            price: 交易价格
            amount: 交易数量
            profit: 盈利金额
            fee_currency: 手续费计价币种（'USDT'或'BTC'）
            leverage: 杠杆倍数
        """
        self.trade_count += 1

        # 计算手续费（按币种的0.1%，考虑杠杆倍数）
        if fee_currency == 'USDT':
            # 买入时：按USDT金额计算手续费
            # 卖出时：按USDT金额计算手续费
            fee = price * amount * self.fee_rate * leverage
        else:  # BTC
            # 按BTC数量计算手续费
            fee = amount * self.fee_rate * leverage

        if side == 'buy':
            logger.info(f"记录买入: 价格 {price:.2f} USDT, 数量 {amount:.8f} BTC, 手续费 {fee:.8f} {fee_currency}")
            # 更新平均买入价格（加权平均，包含手续费）
            total_cost = self._avg_buy_price * self._total_btc_held + price * amount
            # 买入时的手续费已经包含在总成本中
            self._total_btc_held += amount
            if self._total_btc_held > 0:
                self._avg_buy_price = total_cost / self._total_btc_held
            logger.info(f"更新平均买入价格: {self._avg_buy_price:.2f} USDT, 持有BTC: {self._total_btc_held:.8f}")
        else:
            # 计算实际盈利（扣除卖出手续费）
            actual_profit = profit - (fee if fee_currency == 'USDT' else fee * price)
            self.total_profit_usdt += actual_profit
            # 更新上次卖出价格
            self._last_sell_price = price
            # 减少持有的BTC
            self._total_btc_held = max(0, self._total_btc_held - amount)
            # 如果BTC全部卖出，重置平均买入价格
            if self._total_btc_held <= 0:
                self._avg_buy_price = 0.0
            logger.info(f"记录卖出: 价格 {price:.2f} USDT, 数量 {amount:.8f} BTC, 盈利 {actual_profit:.4f} USDT, 手续费 {fee:.8f} {fee_currency}")
            logger.info(f"累计盈利: {self.total_profit_usdt:.4f} USDT, {self.total_profit_btc:.8f} BTC")
            logger.info(f"更新上次卖出价格: {self._last_sell_price:.2f} USDT, 剩余BTC: {self._total_btc_held:.8f}")

        # 保存状态
        self._save_state()
    
    def calculate_total_fees(self, buy_amount: float, buy_price: float, sell_amount: float, sell_price: float, buy_fee_currency: str = 'USDT', sell_fee_currency: str = 'USDT', leverage: float = 1.0):
        """
        计算买入卖出两次币种转换的总手续费

        Args:
            buy_amount: 买入数量
            buy_price: 买入价格
            sell_amount: 卖出数量
            sell_price: 卖出价格
            buy_fee_currency: 买入手续费计价币种
            sell_fee_currency: 卖出手续费计价币种
            leverage: 杠杆倍数

        Returns:
            Dict: 包含各种手续费信息
        """
        # 计算买入手续费（考虑杠杆倍数）
        if buy_fee_currency == 'USDT':
            buy_fee = buy_price * buy_amount * self.fee_rate * leverage
        else:
            buy_fee = buy_amount * self.fee_rate * leverage
        
        # 计算卖出手续费（考虑杠杆倍数）
        if sell_fee_currency == 'USDT':
            sell_fee = sell_price * sell_amount * self.fee_rate * leverage
        else:
            sell_fee = sell_amount * self.fee_rate * leverage
        
        # 转换为USDT计算总手续费
        total_fee_usdt = 0
        if buy_fee_currency == 'USDT':
            total_fee_usdt += buy_fee
        else:
            total_fee_usdt += buy_fee * buy_price
        
        if sell_fee_currency == 'USDT':
            total_fee_usdt += sell_fee
        else:
            total_fee_usdt += sell_fee * sell_price
        
        return {
            'buy_fee': buy_fee,
            'buy_fee_currency': buy_fee_currency,
            'sell_fee': sell_fee,
            'sell_fee_currency': sell_fee_currency,
            'total_fee_usdt': total_fee_usdt,
            'buy_fee_usdt': buy_fee if buy_fee_currency == 'USDT' else buy_fee * buy_price,
            'sell_fee_usdt': sell_fee if sell_fee_currency == 'USDT' else sell_fee * sell_price
        }
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            'total_profit_usdt': self.total_profit_usdt,
            'total_profit_btc': self.total_profit_btc,
            'trade_count': self.trade_count,
            'min_profit_rate': self.min_profit_rate,
            'fee_rate': self.fee_rate,
            'last_sell_price': self._last_sell_price,
            'avg_buy_price': self._avg_buy_price,
            'avg_sell_price': self._avg_sell_price,
            'total_btc_held': self._total_btc_held,
            'position_type': 'short' if self._total_btc_held < 0 else 'long' if self._total_btc_held > 0 else 'none'
        }

    def get_last_sell_price(self) -> Optional[float]:
        """获取上次卖出价格"""
        return self._last_sell_price

    def get_avg_buy_price(self) -> float:
        """获取平均买入价格"""
        return self._avg_buy_price

    def get_total_btc_held(self) -> float:
        """获取持有的BTC总量"""
        return self._total_btc_held
    
    def get_positions(self):
        """从API获取持仓信息"""
        try:
            timestamp = self._get_timestamp()
            headers = self._get_headers(timestamp, 'GET', '/api/v5/account/positions?instType=MARGIN')
            response = requests.get('https://www.okx.com/api/v5/account/positions?instType=MARGIN', headers=headers)
            return response.json()
        except Exception as e:
            logger.error(f"获取持仓信息失败: {e}")
            return {}
    
    def get_account_balance(self):
        """从API获取账户余额"""
        try:
            timestamp = self._get_timestamp()
            headers = self._get_headers(timestamp, 'GET', '/api/v5/account/balance')
            response = requests.get('https://www.okx.com/api/v5/account/balance', headers=headers)
            return response.json()
        except Exception as e:
            logger.error(f"获取账户余额失败: {e}")
            return {}
    
    def get_current_price(self, inst_id='BTC-USDT'):
        """从API获取当前价格"""
        try:
            timestamp = self._get_timestamp()
            headers = self._get_headers(timestamp, 'GET', f'/api/v5/market/ticker?instId={inst_id}')
            response = requests.get(f'https://www.okx.com/api/v5/market/ticker?instId={inst_id}', headers=headers)
            data = response.json()
            if data.get('data'):
                return float(data['data'][0].get('last', '0') or '0')
            return 0
        except Exception as e:
            logger.error(f"获取当前价格失败: {e}")
            return 0
    
    def get_position_pnl(self):
        """从API获取持仓收益"""
        try:
            timestamp = self._get_timestamp()
            headers = self._get_headers(timestamp, 'GET', '/api/v5/account/positions?instType=MARGIN&pnl=true')
            response = requests.get('https://www.okx.com/api/v5/account/positions?instType=MARGIN&pnl=true', headers=headers)
            return response.json()
        except Exception as e:
            logger.error(f"获取持仓收益失败: {e}")
            return {}
    
    def sync_with_api(self):
        """与API同步数据"""
        try:
            logger.info("开始与API同步数据...")
            
            # 获取持仓信息
            positions_data = self.get_positions()
            if positions_data.get('data'):
                for position in positions_data['data']:
                    if position.get('instId') == 'BTC-USDT':
                        pos_usdt = float(position.get('pos', '0') or '0')
                        avg_px = float(position.get('avgPx', '0') or '0')
                        pos_side = position.get('posSide')
                        lever = float(position.get('lever', '1') or '1')
                        
                        # 检查是否是做空持仓，使用posSide字段
                        # 对于net模式，根据liab和liabCcy来判断
                        if pos_side == 'short':
                            is_short = True
                        elif pos_side == 'long':
                            is_short = False
                        else:  # net模式
                            # 对于net模式，根据liab和liabCcy来判断
                            liab = float(position.get('liab', '0') or '0')
                            liab_ccy = position.get('liabCcy')
                            is_short = liab < 0 and liab_ccy == 'BTC'
                        
                        if pos_usdt > 0 and avg_px > 0:
                            # 计算实际BTC数量
                            actual_btc = pos_usdt / avg_px
                            
                            # 对于做空持仓，数量应该为负数
                            if is_short:
                                actual_btc = -abs(actual_btc)
                                logger.info(f"同步{lever}倍杠杆做空持仓数据: {pos_usdt:.8f} USDT @ {avg_px:.2f} USDT/BTC = {actual_btc:.8f} BTC")
                                # 对于做空持仓，保存开仓价格作为做空价格
                                self._avg_sell_price = avg_px
                                # 重置做多价格，避免混淆
                                self._avg_buy_price = 0.0
                            else:
                                logger.info(f"同步{lever}倍杠杆做多持仓数据: {pos_usdt:.8f} USDT @ {avg_px:.2f} USDT/BTC = {actual_btc:.8f} BTC")
                                # 对于做多持仓，保存开仓价格作为买入价格
                                self._avg_buy_price = avg_px
                                # 重置做空价格，避免混淆
                                self._avg_sell_price = 0.0
                            
                            self._total_btc_held = actual_btc
            
            # 获取当前价格
            current_price = self.get_current_price()
            
            # 保存状态
            self._save_state()
            
            logger.info("API数据同步完成")
            return True
        except Exception as e:
            logger.error(f"API同步失败: {e}")
            return False
    
    def get_api_position_stats(self):
        """获取API持仓统计信息"""
        try:
            # 获取持仓信息
            positions_data = self.get_positions()
            position_pnl_data = self.get_position_pnl()
            current_price = self.get_current_price()
            
            stats = {
                'current_price': current_price,
                'positions': [],
                'total_pnl': 0.0,
                'total_value': 0.0
            }
            
            if positions_data.get('data'):
                for position in positions_data['data']:
                    inst_id = position.get('instId')
                    pos_usdt = float(position.get('pos', '0') or '0')  # pos是以USDT为单位的持仓价值
                    avg_px = float(position.get('avgPx', '0') or '0')
                    pos_side = position.get('posSide')
                    lever = float(position.get('lever', '1') or '1')
                    
                    # 检查是否是做空持仓，使用posSide字段
                    # 对于net模式，根据liab和liabCcy来判断
                    if pos_side == 'short':
                        is_short = True
                    elif pos_side == 'long':
                        is_short = False
                    else:  # net模式
                        # 对于net模式，根据liab和liabCcy来判断
                        liab = float(position.get('liab', '0') or '0')
                        liab_ccy = position.get('liabCcy')
                        is_short = liab < 0 and liab_ccy == 'BTC'
                    
                    if pos_usdt > 0 and avg_px > 0:
                        # 计算实际BTC数量
                        actual_btc = pos_usdt / avg_px
                        
                        # 对于做空持仓，数量应该为负数
                        if is_short:
                            actual_btc = -abs(actual_btc)
                        
                        # 计算当前价值
                        current_value = abs(actual_btc) * current_price
                        
                        # 计算手续费率（双向，买入和卖出）
                        total_fee_rate = self.fee_rate * 2  # 0.2%
                        
                        # 计算飘逸值影响因子
                        drift_factor = 0.001  # 0.1%的飘逸值影响
                        
                        # 计算未来收益价格：现价 + 飘逸值的影响因子
                        if is_short:
                            # 做空时，价格下跌预期
                            future_price = current_price * (1 - drift_factor)
                        else:
                            # 做多时，价格上涨预期
                            future_price = current_price * (1 + drift_factor)
                        
                        # 计算收益（做空的收益计算方式不同，考虑手续费）
                        if is_short:
                            # 做空收益 = (开仓价格 - 未来收益价格) * 实际BTC数量 - 手续费
                            pnl = (avg_px - future_price) * abs(actual_btc)
                            # 扣除手续费
                            fee = pnl * total_fee_rate
                            pnl = pnl - fee
                            pnl_rate = ((avg_px - future_price) / avg_px - total_fee_rate) * 100 if avg_px > 0 else 0
                        else:
                            # 做多收益 = (未来收益价格 - 开仓价格) * 实际BTC数量 - 手续费
                            pnl = (future_price - avg_px) * actual_btc
                            # 扣除手续费
                            fee = pnl * total_fee_rate
                            pnl = pnl - fee
                            pnl_rate = ((future_price - avg_px) / avg_px - total_fee_rate) * 100 if avg_px > 0 else 0
                        
                        # 考虑杠杆对收益的放大效应
                        leveraged_pnl = pnl * lever
                        leveraged_pnl_rate = pnl_rate * lever
                        
                        stats['positions'].append({
                            'inst_id': inst_id,
                            'amount_usdt': pos_usdt,
                            'amount_btc': actual_btc,
                            'avg_price': avg_px,
                            'current_price': current_price,
                            'value': current_value,
                            'pnl': pnl,
                            'leveraged_pnl': leveraged_pnl,
                            'pnl_rate': pnl_rate,
                            'leveraged_pnl_rate': leveraged_pnl_rate,
                            'position_type': 'short' if is_short else 'long',
                            'leverage': lever
                        })
                        
                        stats['total_value'] += current_value
                        stats['total_pnl'] += leveraged_pnl
            
            return stats
        except Exception as e:
            logger.error(f"获取API持仓统计信息失败: {e}")
            return {}


# 创建全局实例
profit_growth_manager = ProfitGrowthManager()
