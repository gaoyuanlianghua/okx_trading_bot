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
        test1_passed = False
        test2_passed = False
        test3_passed = False
        
        # 测试1: 获取资金账户余额（需要认证，但不会产生交易）
        logger.info("测试1: 获取资金账户余额")
        balances = client.get_balances()
        if balances:
            logger.success("✓ 资金账户余额获取成功")
            for balance in balances:
                logger.info(f"  币种: {balance['ccy']}, 可用余额: {balance['availBal']}, 总余额: {balance['bal']}")
            test1_passed = True
        else:
            logger.error("✗ 资金账户余额获取失败")
        
        # 测试2: 获取账户余额（需要认证）
        logger.info("\n测试2: 获取账户余额")
        account_balance = client.get_account_balance()
        if account_balance:
            logger.success("✓ 账户余额获取成功")
            for balance in account_balance:
                logger.info(f"  币种: {balance['ccy']}, 可用余额: {balance['availBal']}, 总余额: {balance['totalBal']}")
            test2_passed = True
        else:
            logger.error("✗ 账户余额获取失败")
        
        # 测试3: 获取公共行情数据（不需要认证，用于验证网络连接）
        logger.info("\n测试3: 获取公共行情数据")
        ticker = client.get_ticker('BTC-USDT-SWAP')
        if ticker:
            logger.success("✓ 公共行情数据获取成功")
            logger.info(f"  BTC-USDT-SWAP 最新价格: {ticker[0]['last']}")
            test3_passed = True
        else:
            logger.error("✗ 公共行情数据获取失败")
        
        logger.info("\nAPI密钥测试完成")
        
        # 分析测试结果
        if test1_passed or test2_passed:
            # 如果认证相关测试通过，说明API密钥有效
            logger.success("🎉 API密钥测试成功！密钥有效")
            return True
        elif test3_passed:
            # 如果只有公共API测试通过，说明网络连接正常，但API密钥可能存在问题
            logger.warning("⚠️  网络连接正常，但API密钥认证可能存在问题")
            return False
        else:
            # 所有测试都失败，可能是网络问题或API密钥问题
            logger.error("❌ API密钥测试失败！")
            logger.error("   可能的原因：")
            logger.error("   1. 网络连接问题")
            logger.error("   2. API密钥无效")
            logger.error("   3. API密钥权限不足")
            return False
        
    except Exception as e:
        logger.error(f"测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_api_key()
    if success:
        logger.success("\n🎉 API密钥测试成功！密钥有效。")
    else:
        logger.error("\n❌ API密钥测试失败！密钥可能无效或权限不足。")
