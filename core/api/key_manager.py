"""
API密钥管理模块 - 处理API密钥的安全存储和管理
"""

import os
import json
import base64
import hashlib
import getpass
from datetime import datetime, timedelta
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import padding
from typing import Dict, Optional


class KeyManager:
    """
    API密钥管理器

    负责API密钥的加密存储、读取和管理
    """

    def __init__(self, key_file: str = "api_keys.json"):
        """
        初始化密钥管理器

        Args:
            key_file: 密钥存储文件路径
        """
        self.key_file = key_file
        self._encryption_key = None
        self._load_encryption_key()

    def _load_encryption_key(self):
        """
        加载或生成加密密钥
        """
        # 从环境变量获取加密密钥，或生成新的
        encryption_key = os.environ.get("OKX_BOT_ENCRYPTION_KEY")
        if not encryption_key:
            # 生成新的加密密钥
            encryption_key = base64.b64encode(os.urandom(32)).decode("utf-8")
            print(f"生成新的加密密钥: {encryption_key}")
            print("请将此密钥设置为环境变量 OKX_BOT_ENCRYPTION_KEY")
            # 临时设置环境变量，以便策略能够继续执行
            os.environ["OKX_BOT_ENCRYPTION_KEY"] = encryption_key
        self._encryption_key = base64.b64decode(encryption_key)[
            :32
        ]  # 确保密钥长度为32字节

    def _encrypt(self, data: str) -> str:
        """
        加密数据

        Args:
            data: 要加密的数据

        Returns:
            str: 加密后的数据（base64编码）
        """
        iv = os.urandom(16)  # 生成16字节的初始化向量
        padder = padding.PKCS7(128).padder()
        padded_data = padder.update(data.encode("utf-8")) + padder.finalize()

        cipher = Cipher(
            algorithms.AES(self._encryption_key),
            modes.CBC(iv),
            backend=default_backend(),
        )
        encryptor = cipher.encryptor()
        encrypted_data = encryptor.update(padded_data) + encryptor.finalize()

        # 返回IV和加密数据的base64编码
        return base64.b64encode(iv + encrypted_data).decode("utf-8")

    def _decrypt(self, encrypted_data: str) -> str:
        """
        解密数据

        Args:
            encrypted_data: 加密的数据（base64编码）

        Returns:
            str: 解密后的数据
        """
        decoded_data = base64.b64decode(encrypted_data)
        iv = decoded_data[:16]
        ciphertext = decoded_data[16:]

        cipher = Cipher(
            algorithms.AES(self._encryption_key),
            modes.CBC(iv),
            backend=default_backend(),
        )
        decryptor = cipher.decryptor()
        decrypted_padded = decryptor.update(ciphertext) + decryptor.finalize()

        unpadder = padding.PKCS7(128).unpadder()
        decrypted = unpadder.update(decrypted_padded) + unpadder.finalize()

        return decrypted.decode("utf-8")

    def save_api_keys(
        self, api_key: str, api_secret: str, passphrase: str, is_test: bool = False
    ):
        """
        保存API密钥

        Args:
            api_key: API密钥
            api_secret: API密钥密码
            passphrase: 密码短语
            is_test: 是否为模拟盘
        """
        # 加密敏感信息
        encrypted_data = {
            "api_key": self._encrypt(api_key),
            "api_secret": self._encrypt(api_secret),
            "passphrase": self._encrypt(passphrase),
            "is_test": is_test,
            "created_at": datetime.now().isoformat(),
            "last_rotated": datetime.now().isoformat(),
        }

        # 保存到文件
        with open(self.key_file, "w", encoding="utf-8") as f:
            json.dump(encrypted_data, f, indent=2, ensure_ascii=False)

        # 设置文件权限，确保只有当前用户可读
        if os.name == "nt":
            # Windows系统
            import win32security
            import win32api
            import win32con

            # 获取文件句柄
            hfile = win32api.CreateFile(
                self.key_file,
                win32con.GENERIC_READ,
                0,  # 不共享
                None,
                win32con.OPEN_EXISTING,
                win32con.FILE_ATTRIBUTE_NORMAL,
                None,
            )

            # 获取安全描述符
            sd = win32security.GetFileSecurity(
                self.key_file, win32security.DACL_SECURITY_INFORMATION
            )

            # 获取当前用户
            user = win32api.GetUserName()
            domain = win32api.GetUserNameEx(win32api.NameSamCompatible).split("\\")[0]
            user_sid = win32security.LookupAccountName(domain, user)[0]

            # 创建访问控制项
            ace = win32security.ACL()
            ace.AddAccessAllowedAce(
                win32security.ACL_REVISION, win32con.FILE_ALL_ACCESS, user_sid
            )

            # 设置DACL
            sd.SetSecurityDescriptorDacl(1, ace, 0)
            win32security.SetFileSecurity(
                self.key_file, win32security.DACL_SECURITY_INFORMATION, sd
            )
        else:
            # Unix/Linux系统
            os.chmod(self.key_file, 0o600)

    def load_api_keys(self) -> Optional[Dict[str, str]]:
        """
        加载API密钥

        Returns:
            Dict[str, str]: API密钥信息，包含api_key, api_secret, passphrase, is_test
        """
        if not os.path.exists(self.key_file):
            return None

        try:
            with open(self.key_file, "r", encoding="utf-8") as f:
                encrypted_data = json.load(f)

            # 解密敏感信息
            decrypted_data = {
                "api_key": self._decrypt(encrypted_data["api_key"]),
                "api_secret": self._decrypt(encrypted_data["api_secret"]),
                "passphrase": self._decrypt(encrypted_data["passphrase"]),
                "is_test": encrypted_data.get("is_test", False),
                "created_at": encrypted_data.get("created_at"),
                "last_rotated": encrypted_data.get("last_rotated"),
            }

            return decrypted_data
        except Exception as e:
            print(f"加载API密钥失败: {e}")
            return None

    def check_key_expiry(self) -> bool:
        """
        检查API密钥是否需要轮换

        Returns:
            bool: 是否需要轮换
        """
        keys = self.load_api_keys()
        if not keys or "last_rotated" not in keys:
            return True

        try:
            last_rotated = datetime.fromisoformat(keys["last_rotated"])
            # 30天轮换一次
            return (datetime.now() - last_rotated).days >= 30
        except Exception:
            return True

    def rotate_keys(self, new_api_key: str, new_api_secret: str, new_passphrase: str):
        """
        轮换API密钥

        Args:
            new_api_key: 新的API密钥
            new_api_secret: 新的API密钥密码
            new_passphrase: 新的密码短语
        """
        keys = self.load_api_keys()
        if keys:
            self.save_api_keys(
                new_api_key, new_api_secret, new_passphrase, keys.get("is_test", False)
            )
            print("API密钥轮换成功")
        else:
            print("无法加载当前API密钥，无法进行轮换")

    def delete_keys(self):
        """
        删除API密钥
        """
        if os.path.exists(self.key_file):
            os.remove(self.key_file)
            print("API密钥已删除")
        else:
            print("API密钥文件不存在")

    def get_key_info(self) -> Optional[Dict[str, str]]:
        """
        获取密钥信息（不包含敏感数据）

        Returns:
            Dict[str, str]: 密钥信息
        """
        keys = self.load_api_keys()
        if keys:
            return {
                "is_test": keys.get("is_test", False),
                "created_at": keys.get("created_at"),
                "last_rotated": keys.get("last_rotated"),
                "api_key_masked": keys["api_key"][:4] + "****" + keys["api_key"][-4:],
            }
        return None


# 创建全局密钥管理器实例
key_manager = KeyManager()
