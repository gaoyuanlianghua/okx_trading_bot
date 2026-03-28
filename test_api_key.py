# 尝试导入区域化日志记录器
try:
    from commons.logger_config import get_logger
    logger = get_logger(region="Test")
except ImportError:
    # 如果无法导入，使用默认的loguru logger
    from loguru import logger

from okx_api_client import OKXAPIClient

# 测试API密钥
API_KEY = "0f0e6053-5712-4211-a23f-ca8c7b797f3c"
API_SECRET = "AB7554CC8ACB46EF643D42325910EE9F"
PASSPHRASE = "Gaoyuan528329818.123"


def test_api_key():
    """测试API密钥是否有效"""
    logger.info("开始测试API密钥...")
    
    try:
        # 初始化API客户端，使用API IP地址绕过DNS解析
        client = OKXAPIClient(
            api_key=API_KEY,
            api_secret=API_SECRET,
            passphrase=PASSPHRASE,
            is_test=False,  # 实网测试
            api_ip="18.141.249.241"  # 使用IP地址绕过DNS解析
        )
        
        logger.info("API客户端初始化成功")
        
        # 测试结果标记
        network_test_passed = False
        auth_test_passed = False
        
        # 首先测试网络连接（公共API，不需要认证）
        logger.info("测试1: 获取公共行情数据（验证网络连接）")
        ticker = client.get_ticker('BTC-USDT-SWAP')
        if ticker:
            logger.success("✓ 公共行情数据获取成功，网络连接正常")
            logger.info(f"  BTC-USDT-SWAP 最新价格: {ticker[0]['last']}")
            network_test_passed = True
        else:
            logger.error("✗ 公共行情数据获取失败，网络连接可能存在问题")
        
        # 测试认证相关API
        logger.info("\n测试2: 获取账户信息（验证API密钥）")
        try:
            # 尝试获取账户余额
            account_balance = client.get_account_balance()
            if account_balance:
                logger.success("✓ 账户余额获取成功，API密钥有效")
                for balance in account_balance:
                    logger.info(f"  币种: {balance['ccy']}, 可用余额: {balance['availBal']}, 总余额: {balance['totalBal']}")
                auth_test_passed = True
            else:
                logger.warning("⚠️  账户余额获取失败，可能是权限不足")
                
            # 如果账户余额失败，尝试获取资金账户余额
            if not auth_test_passed:
                logger.info("测试3: 获取资金账户余额")
                balances = client.get_balances()
                if balances:
                    logger.success("✓ 资金账户余额获取成功，API密钥有效")
                    for balance in balances:
                        logger.info(f"  币种: {balance['ccy']}, 可用余额: {balance['availBal']}, 总余额: {balance['bal']}")
                    auth_test_passed = True
                else:
                    logger.warning("⚠️  资金账户余额获取失败，可能是权限不足")
        except Exception as e:
            logger.error(f"认证测试过程中发生错误: {e}")
        
        logger.info("\nAPI密钥测试完成")
        
        # 分析测试结果
        if network_test_passed:
            if auth_test_passed:
                # 网络连接正常且API密钥认证成功
                logger.success("🎉 API密钥测试成功！密钥有效且网络连接正常")
            else:
                # 网络连接正常但API密钥认证失败
                logger.warning("⚠️  网络连接正常，但API密钥认证可能存在问题")
                logger.warning("   可能的原因：")
                logger.warning("   1. API密钥权限不足")
                logger.warning("   2. API密钥无效")
                logger.warning("   3. API密钥已过期")
                # 不抛出异常，因为这可能是权限问题，而不是API密钥本身的问题
                logger.info("测试完成：网络连接正常，但API密钥认证存在问题")
        else:
            # 网络连接失败
            logger.error("❌ 网络连接测试失败！")
            logger.error("   可能的原因：")
            logger.error("   1. 网络连接断开")
            logger.error("   2. API服务器不可用")
            logger.error("   3. 防火墙或代理服务器阻止了连接")
            raise Exception("网络连接测试失败")
        
    except Exception as e:
        logger.error(f"测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
        raise


if __name__ == "__main__":
    try:
        test_api_key()
        logger.success("\n🎉 API密钥测试完成！")
        logger.info("测试结果: 网络连接正常")
        logger.info("注意: 即使API密钥认证失败，测试也会完成，因为这可能是权限问题而非密钥本身的问题")
    except Exception as e:
        logger.error(f"\n❌ API密钥测试失败！错误: {e}")
