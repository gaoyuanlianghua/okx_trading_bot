#!/usr/bin/env python3
"""
测试OSS连接脚本
"""

import os
from core.utils.oss_persistence import OSSPersistenceManager

def main():
    print("=== 测试OSS连接 ===")
    
    # 获取环境变量
    access_key_id = os.environ.get('OSS_ACCESS_KEY_ID')
    access_key_secret = os.environ.get('OSS_ACCESS_KEY_SECRET')
    endpoint = os.environ.get('OSS_ENDPOINT')
    bucket_name = os.environ.get('OSS_BUCKET_NAME')
    
    print("OSS配置：")
    print(f"  AccessKey ID: {access_key_id}")
    print(f"  Endpoint: {endpoint}")
    print(f"  Bucket: {bucket_name}")
    
    # 测试连接
    try:
        oss_manager = OSSPersistenceManager(
            access_key_id=access_key_id,
            access_key_secret=access_key_secret,
            endpoint=endpoint,
            bucket_name=bucket_name
        )
        
        files = oss_manager.list_oss_files()
        print(f"✅ OSS连接成功，找到 {len(files)} 个文件")
        
        if files:
            print("前5个文件：")
            for f in files[:5]:
                print(f"  - {f}")
        
    except Exception as e:
        print(f"❌ OSS连接失败: {e}")

if __name__ == "__main__":
    main()
