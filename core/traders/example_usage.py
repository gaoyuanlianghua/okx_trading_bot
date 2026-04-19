"""
交易器使用示例 - 展示智能体如何使用交易器
"""

from decimal import Decimal
import asyncio
import logging

from core.traders import TraderManager, TradeResult, OrderType, PositionSide

logger = logging.getLogger(__name__)


class TradingAgent:
    """
    示例智能体 - 展示如何使用交易器
    
    这个智能体可以通过交易器管理器调用不同的交易器进行交易
    """

    def __init__(self, trader_manager: TraderManager):
        """
        初始化智能体
        
        Args:
            trader_manager: 交易器管理器
        """
        self.trader_manager = trader_manager
        self.name = "TradingAgent"

    async def execute_spot_trade(self, inst_id: str, side: str, amount: float):
        """
        执行现货交易
        
        Args:
            inst_id: 产品ID，如 "BTC-USDT"
            side: "buy" 或 "sell"
            amount: 交易金额（USDT）
        """
        # 获取或创建现货交易器
        spot_trader = self.trader_manager.get_or_create_trader('spot', 'my_spot_trader')
        
        # 交易前检查风险
        from core.traders.base_trader import TradeSide
        trade_side = TradeSide.BUY if side == 'buy' else TradeSide.SELL
        
        passed, reason = await self.trader_manager.check_risk_before_trade(
            inst_id, trade_side, Decimal(str(amount)), 'my_spot_trader'
        )
        
        if not passed:
            logger.warning(f"风险检查未通过: {reason}")
            return None
        
        # 执行交易
        if side == 'buy':
            result = await self.trader_manager.buy(
                inst_id=inst_id,
                size=Decimal(str(amount)),
                order_type=OrderType.MARKET,
                trader_name='my_spot_trader',
                tgtCcy='quote_ccy'  # 按USDT金额下单
            )
        else:
            # 卖出需要获取持仓
            position = await self.trader_manager.get_position(inst_id, None, 'my_spot_trader')
            if not position:
                logger.warning(f"无持仓可卖: {inst_id}")
                return None
            
            result = await self.trader_manager.sell(
                inst_id=inst_id,
                size=position.size,  # 卖出全部持仓
                order_type=OrderType.MARKET,
                trader_name='my_spot_trader',
                tgtCcy='base_ccy'
            )
        
        if result.success:
            logger.info(f"现货交易成功: {side} {inst_id}, 订单ID: {result.order_id}")
        else:
            logger.error(f"现货交易失败: {result.error_message}")
        
        return result

    async def execute_contract_trade(self, inst_id: str, side: str, size: float,
                                     leverage: int = 10, pos_side: str = 'long'):
        """
        执行合约交易
        
        Args:
            inst_id: 产品ID，如 "BTC-USDT-SWAP"
            side: "buy" 或 "sell"
            size: 合约数量（张）
            leverage: 杠杆倍数
            pos_side: "long" 或 "short"
        """
        # 获取或创建合约交易器
        contract_trader = self.trader_manager.get_or_create_trader(
            'contract', 'my_contract_trader'
        )
        
        # 设置杠杆
        await self.trader_manager.set_leverage(
            inst_id, leverage, PositionSide(pos_side), 'my_contract_trader'
        )
        
        # 执行交易
        if side == 'buy':
            result = await self.trader_manager.buy(
                inst_id=inst_id,
                size=Decimal(str(size)),
                order_type=OrderType.MARKET,
                trader_name='my_contract_trader',
                pos_side=PositionSide(pos_side)
            )
        else:
            result = await self.trader_manager.sell(
                inst_id=inst_id,
                size=Decimal(str(size)),
                order_type=OrderType.MARKET,
                trader_name='my_contract_trader',
                pos_side=PositionSide(pos_side)
            )
        
        if result.success:
            logger.info(f"合约交易成功: {side} {inst_id} {pos_side}, 订单ID: {result.order_id}")
        else:
            logger.error(f"合约交易失败: {result.error_message}")
        
        return result

    async def close_contract_position(self, inst_id: str, pos_side: str):
        """
        平仓合约持仓
        
        Args:
            inst_id: 产品ID
            pos_side: 持仓方向
        """
        result = await self.trader_manager.close_position(
            inst_id=inst_id,
            pos_side=PositionSide(pos_side),
            trader_name='my_contract_trader'
        )
        
        if result.success:
            logger.info(f"合约平仓成功: {inst_id} {pos_side}")
        else:
            logger.error(f"合约平仓失败: {result.error_message}")
        
        return result

    async def get_account_summary(self):
        """获取所有账户摘要"""
        # 获取所有交易器的账户信息
        accounts = await self.trader_manager.get_all_accounts_summary()
        
        for name, account in accounts.items():
            logger.info(f"\n{name} 账户信息:")
            logger.info(f"  总权益: {account.total_equity}")
            logger.info(f"  可用余额: {account.available_balance}")
            logger.info(f"  未实现盈亏: {account.unrealized_pnl}")
            
            # 各币种详情
            for ccy, info in account.currencies.items():
                logger.info(f"  {ccy}: 可用={info['available']}, 权益={info['equity']}")
        
        return accounts

    async def get_risk_summary(self):
        """获取风险摘要"""
        risks = await self.trader_manager.get_all_risks_summary()
        
        for name, risk in risks.items():
            logger.info(f"\n{name} 风险信息:")
            logger.info(f"  保证金率: {risk.margin_ratio}")
            logger.info(f"  风险等级: {risk.risk_level}")
        
        return risks

    async def monitor_and_trade(self):
        """
        监控并交易示例
        
        这是一个完整的交易流程示例
        """
        # 1. 获取账户和风险信息
        await self.get_account_summary()
        await self.get_risk_summary()
        
        # 2. 检查现货持仓
        btc_position = await self.trader_manager.get_position(
            'BTC-USDT', None, 'my_spot_trader'
        )
        
        if btc_position and btc_position.size > 0:
            logger.info(f"当前BTC持仓: {btc_position.size}")
            
            # 如果满足卖出条件，执行卖出
            # 这里可以添加策略逻辑
            # await self.execute_spot_trade('BTC-USDT', 'sell', 0)
        else:
            logger.info("无BTC持仓")
            
            # 如果满足买入条件，执行买入
            # 这里可以添加策略逻辑
            # await self.execute_spot_trade('BTC-USDT', 'buy', 100)
        
        # 3. 检查合约持仓
        contract_position = await self.trader_manager.get_position(
            'BTC-USDT-SWAP', PositionSide.LONG, 'my_contract_trader'
        )
        
        if contract_position and contract_position.size > 0:
            logger.info(f"当前合约持仓: {contract_position.size}")
            
            # 检查是否需要平仓
            risk_info = await self.trader_manager.get_risk_info('my_contract_trader')
            if risk_info.risk_level == 'danger':
                logger.warning("风险过高，执行平仓")
                await self.close_contract_position('BTC-USDT-SWAP', 'long')


# 使用示例
async def main():
    """主函数示例"""
    from core.api.okx_rest_client import OKXRESTClient
    from core.config import OKXConfig
    
    # 1. 初始化配置和客户端
    config = OKXConfig()
    rest_client = OKXRESTClient(config)
    
    # 2. 创建交易器管理器
    trader_manager = TraderManager(rest_client)
    
    # 3. 创建智能体
    agent = TradingAgent(trader_manager)
    
    # 4. 执行交易操作
    
    # 现货交易示例
    # result = await agent.execute_spot_trade('BTC-USDT', 'buy', 100)
    
    # 合约交易示例
    # result = await agent.execute_contract_trade(
    #     'BTC-USDT-SWAP', 'buy', 1, leverage=10, pos_side='long'
    # )
    
    # 5. 监控和交易
    await agent.monitor_and_trade()


if __name__ == "__main__":
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # 运行示例
    asyncio.run(main())
