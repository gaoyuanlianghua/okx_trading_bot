#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
API响应解析器
负责解析API返回的信息，提取关键数据
"""

import json
from datetime import datetime
from typing import Dict, Any, List, Optional


class APIResponseParser:
    """API响应解析器"""
    
    def __init__(self):
        self.parsed_data = {}
    
    def parse_balance_response(self, response: Dict) -> Dict[str, Any]:
        """解析账户余额响应"""
        try:
            if not response or not isinstance(response, dict):
                return {}
            
            data = response.get('data', [])
            if not data:
                return {}
            
            result = {
                'timestamp': None,
                'total_eq': 0,
                'total_liab': 0,
                'total_mgn': 0,
                'currencies': [],
                'api_status': 'success'
            }
            
            # 提取API时间戳
            if 'ts' in response:
                result['timestamp'] = int(response['ts']) / 1000
            else:
                # 提取数据时间戳
                u_time = data[0].get('uTime', None)
                if u_time:
                    result['timestamp'] = int(u_time) / 1000
            
            # 提取总权益
            result['total_eq'] = float(data[0].get('totalEq', 0))
            result['total_liab'] = float(data[0].get('totalLiab', 0))
            result['total_mgn'] = float(data[0].get('totalMgn', 0))
            
            # 提取各币种信息
            details = data[0].get('details', [])
            for detail in details:
                currency_info = {
                    'currency': detail.get('ccy', ''),
                    'equity': float(detail.get('eq', 0)),
                    'available': float(detail.get('availBal', 0)),
                    'frozen': float(detail.get('frozenBal', 0)),
                    'unrealized_pnl': float(detail.get('upl', 0)),
                    'max_loan': float(detail.get('maxLoan', 0)) if 'maxLoan' in detail else 0,
                    'margin_ratio': float(detail.get('marginRatio', 0)) if 'marginRatio' in detail else 0,
                    'interest': float(detail.get('interest', 0)) if 'interest' in detail else 0,
                    'liab': float(detail.get('liab', 0)) if 'liab' in detail else 0
                }
                result['currencies'].append(currency_info)
            
            self.parsed_data['balance'] = result
            return result
            
        except Exception as e:
            print(f"解析账户余额响应失败: {e}")
            return {'api_status': 'error', 'error_message': str(e)}
    
    def parse_positions_response(self, response: Dict) -> Dict[str, Any]:
        """解析持仓信息响应"""
        try:
            if not response or not isinstance(response, dict):
                return {}
            
            data = response.get('data', [])
            if not data:
                return {}
            
            result = {
                'timestamp': None,
                'positions': [],
                'api_status': 'success'
            }
            
            # 提取API时间戳
            if 'ts' in response:
                result['timestamp'] = int(response['ts']) / 1000
            
            # 提取持仓信息
            for position in data:
                position_info = {
                    'instrument_id': position.get('instId', ''),
                    'position_side': position.get('posSide', ''),
                    'position': float(position.get('pos', 0)),
                    'average_price': float(position.get('avgPx', 0)),
                    'unrealized_pnl': float(position.get('upl', 0)),
                    'unrealized_pnl_ratio': float(position.get('uplRatio', 0)),
                    'leverage': float(position.get('lever', 0)),
                    'margin_mode': position.get('mgnMode', ''),
                    'liquidation_price': float(position.get('liqPx', 0)),
                    'initial_margin': float(position.get('initMargin', 0)) if 'initMargin' in position else 0,
                    'maintenance_margin': float(position.get('maintMargin', 0)) if 'maintMargin' in position else 0,
                    'margin_ratio': float(position.get('marginRatio', 0)) if 'marginRatio' in position else 0,
                    'margin_used': float(position.get('margin', 0)) if 'margin' in position else 0,
                    'timestamp': int(position.get('uTime', 0)) / 1000 if position.get('uTime') else None
                }
                result['positions'].append(position_info)
                
                # 更新时间戳
                if position_info['timestamp']:
                    if result['timestamp'] is None or position_info['timestamp'] > result['timestamp']:
                        result['timestamp'] = position_info['timestamp']
            
            self.parsed_data['positions'] = result
            return result
            
        except Exception as e:
            print(f"解析持仓信息响应失败: {e}")
            return {'api_status': 'error', 'error_message': str(e)}
    
    def parse_ticker_response(self, response: Dict) -> Dict[str, Any]:
        """解析行情数据响应"""
        try:
            print(f"开始解析行情数据响应: {response}")
            if not response or not isinstance(response, dict):
                print("响应为空或不是字典")
                return {}
            
            data = response.get('data', [])
            if not data:
                print("数据为空")
                return {}
            
            result = {
                'timestamp': None,
                'instrument_id': '',
                'last_price': 0,
                'open_24h': 0,
                'high_24h': 0,
                'low_24h': 0,
                'volume_24h': 0,
                'volume_currency_24h': 0,
                'bid_price': 0,
                'bid_size': 0,
                'ask_price': 0,
                'ask_size': 0,
                'change_24h': 0,
                'change_percent_24h': 0,
                'api_status': 'success'
            }
            
            # 提取API时间戳
            if 'ts' in response:
                result['timestamp'] = int(response['ts']) / 1000
                print(f"从响应中提取时间戳: {result['timestamp']}")
            
            ticker = data[0]
            print(f"行情数据: {ticker}")
            
            # 提取时间戳
            ts = ticker.get('ts', None)
            if ts:
                result['timestamp'] = int(ts) / 1000
                print(f"从行情数据中提取时间戳: {result['timestamp']}")
            
            # 提取行情数据
            result['instrument_id'] = ticker.get('instId', '')
            result['last_price'] = float(ticker.get('last', 0))
            result['open_24h'] = float(ticker.get('open24h', 0))
            result['high_24h'] = float(ticker.get('high24h', 0))
            result['low_24h'] = float(ticker.get('low24h', 0))
            result['volume_24h'] = float(ticker.get('vol24h', 0))
            result['volume_currency_24h'] = float(ticker.get('volCcy24h', 0)) if 'volCcy24h' in ticker else 0
            result['bid_price'] = float(ticker.get('bidPx', 0))
            result['bid_size'] = float(ticker.get('bidSz', 0)) if 'bidSz' in ticker else 0
            result['ask_price'] = float(ticker.get('askPx', 0))
            result['ask_size'] = float(ticker.get('askSz', 0)) if 'askSz' in ticker else 0
            result['change_24h'] = float(ticker.get('sodUtc0', 0)) if 'sodUtc0' in ticker else 0
            result['change_percent_24h'] = float(ticker.get('change24h', 0)) if 'change24h' in ticker else 0
            
            print(f"解析后的行情数据: {result}")
            
            self.parsed_data['ticker'] = result
            return result
            
        except Exception as e:
            print(f"解析行情数据响应失败: {e}")
            import traceback
            traceback.print_exc()
            return {'api_status': 'error', 'error_message': str(e)}
    
    def parse_order_response(self, response: Dict) -> Dict[str, Any]:
        """解析订单响应"""
        try:
            if not response or not isinstance(response, dict):
                return {}
            
            data = response.get('data', [])
            if not data:
                return {}
            
            result = {
                'timestamp': None,
                'orders': [],
                'api_status': 'success'
            }
            
            # 提取API时间戳
            if 'ts' in response:
                result['timestamp'] = int(response['ts']) / 1000
            
            # 提取订单信息
            for order in data:
                order_info = {
                    'order_id': order.get('ordId', ''),
                    'instrument_id': order.get('instId', ''),
                    'order_type': order.get('ordType', ''),
                    'side': order.get('side', ''),
                    'price': float(order.get('px', 0)),
                    'size': float(order.get('sz', 0)),
                    'filled_size': float(order.get('fillSz', 0)),
                    'average_price': float(order.get('avgPx', 0)),
                    'state': order.get('state', ''),
                    'margin_mode': order.get('mgnMode', ''),
                    'position_side': order.get('posSide', ''),
                    'leverage': float(order.get('lever', 0)) if 'lever' in order else 0,
                    'client_order_id': order.get('clOrdId', '') if 'clOrdId' in order else '',
                    'fee': float(order.get('fee', 0)) if 'fee' in order else 0,
                    'fee_currency': order.get('feeCcy', '') if 'feeCcy' in order else '',
                    'timestamp': int(order.get('uTime', 0)) / 1000 if order.get('uTime') else None
                }
                result['orders'].append(order_info)
                
                # 更新时间戳
                if order_info['timestamp']:
                    if result['timestamp'] is None or order_info['timestamp'] > result['timestamp']:
                        result['timestamp'] = order_info['timestamp']
            
            self.parsed_data['orders'] = result
            return result
            
        except Exception as e:
            print(f"解析订单响应失败: {e}")
            return {'api_status': 'error', 'error_message': str(e)}
    
    def parse_orders_response(self, response: Dict) -> Dict[str, Any]:
        """解析订单响应（别名方法）"""
        return self.parse_order_response(response)
    
    def get_timestamp(self, data_type: str = None) -> Optional[float]:
        """获取最新的时间戳
        
        Args:
            data_type: 数据类型，可选值：balance, positions, ticker, orders
        """
        if data_type:
            # 获取指定数据类型的时间戳
            if data_type in self.parsed_data and self.parsed_data[data_type].get('timestamp'):
                return self.parsed_data[data_type]['timestamp']
            return None
        else:
            # 获取所有数据类型的最新时间戳
            timestamps = []
            for key in ['balance', 'positions', 'ticker', 'orders']:
                if key in self.parsed_data and self.parsed_data[key].get('timestamp'):
                    timestamps.append(self.parsed_data[key]['timestamp'])
            
            if timestamps:
                return max(timestamps)
            return None
    
    def get_parsed_data(self) -> Dict[str, Any]:
        """获取所有解析后的数据"""
        return self.parsed_data
    
    def clear_parsed_data(self):
        """清空解析后的数据"""
        self.parsed_data = {}
