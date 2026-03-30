import json
import os
from typing import Dict, Optional, Any
from core.utils.logger import get_logger

logger = get_logger(__name__)

class LanguageManager:
    def __init__(self):
        self.languages: Dict[str, Dict[str, str]] = {}
        self.current_language: str = 'zh'
        self._load_languages()
    
    def _load_languages(self):
        language_dir = os.path.join(os.path.dirname(__file__), 'translations')
        if not os.path.exists(language_dir):
            os.makedirs(language_dir)
            self._create_default_translations(language_dir)
        
        for filename in os.listdir(language_dir):
            if filename.endswith('.json'):
                lang_code = filename.split('.')[0]
                try:
                    with open(os.path.join(language_dir, filename), 'r', encoding='utf-8') as f:
                        self.languages[lang_code] = json.load(f)
                    logger.info(f"Loaded language: {lang_code}")
                except Exception as e:
                    logger.error(f"Error loading language {lang_code}: {e}")
    
    def _create_default_translations(self, language_dir: str):
        default_translations = {
            'zh': {
                'app.title': 'OKX交易机器人',
                'app.description': '自动化加密货币交易系统',
                'menu.home': '首页',
                'menu.strategies': '策略管理',
                'menu.market': '市场数据',
                'menu.orders': '订单管理',
                'menu.account': '账户设置',
                'menu.social': '社交交易',
                'menu.analysis': '市场分析',
                'menu.reports': '交易报告',
                'menu.settings': '系统设置',
                'strategy.list': '策略列表',
                'strategy.create': '创建策略',
                'strategy.edit': '编辑策略',
                'strategy.delete': '删除策略',
                'strategy.activate': '激活策略',
                'strategy.deactivate': '停用策略',
                'order.open': '未成交订单',
                'order.history': '历史订单',
                'order.create': '创建订单',
                'order.cancel': '取消订单',
                'account.balance': '账户余额',
                'account.api': 'API设置',
                'account.security': '安全设置',
                'social.leaderboard': '策略排行榜',
                'social.follow': '跟随策略',
                'social.my_follows': '我的跟随',
                'analysis.technical': '技术分析',
                'analysis.fundamental': '基本面分析',
                'reports.daily': '每日报告',
                'reports.weekly': '每周报告',
                'reports.monthly': '每月报告',
                'settings.general': '通用设置',
                'settings.language': '语言设置',
                'settings.notifications': '通知设置',
                'settings.api': 'API设置',
                'common.save': '保存',
                'common.cancel': '取消',
                'common.confirm': '确认',
                'common.delete': '删除',
                'common.edit': '编辑',
                'common.create': '创建',
                'common.back': '返回',
                'common.next': '下一步',
                'common.previous': '上一步',
                'common.success': '操作成功',
                'common.error': '操作失败',
                'common.warning': '警告',
                'common.info': '信息',
                'common.loading': '加载中...',
                'common.search': '搜索',
                'common.filter': '筛选',
                'common.sort': '排序',
                'common.export': '导出',
                'common.import': '导入',
                'common.refresh': '刷新',
                'common.clear': '清除',
                'common.reset': '重置',
                'common.apply': '应用',
                'common.cancel': '取消',
                'common.confirm': '确认',
                'common.delete': '删除',
                'common.edit': '编辑',
                'common.create': '创建',
                'common.back': '返回',
                'common.next': '下一步',
                'common.previous': '上一步',
                'common.success': '操作成功',
                'common.error': '操作失败',
                'common.warning': '警告',
                'common.info': '信息',
                'common.loading': '加载中...',
                'common.search': '搜索',
                'common.filter': '筛选',
                'common.sort': '排序',
                'common.export': '导出',
                'common.import': '导入',
                'common.refresh': '刷新',
                'common.clear': '清除',
                'common.reset': '重置',
                'common.apply': '应用',
            },
            'en': {
                'app.title': 'OKX Trading Bot',
                'app.description': 'Automated cryptocurrency trading system',
                'menu.home': 'Home',
                'menu.strategies': 'Strategies',
                'menu.market': 'Market Data',
                'menu.orders': 'Orders',
                'menu.account': 'Account',
                'menu.social': 'Social Trading',
                'menu.analysis': 'Market Analysis',
                'menu.reports': 'Reports',
                'menu.settings': 'Settings',
                'strategy.list': 'Strategy List',
                'strategy.create': 'Create Strategy',
                'strategy.edit': 'Edit Strategy',
                'strategy.delete': 'Delete Strategy',
                'strategy.activate': 'Activate Strategy',
                'strategy.deactivate': 'Deactivate Strategy',
                'order.open': 'Open Orders',
                'order.history': 'Order History',
                'order.create': 'Create Order',
                'order.cancel': 'Cancel Order',
                'account.balance': 'Account Balance',
                'account.api': 'API Settings',
                'account.security': 'Security Settings',
                'social.leaderboard': 'Strategy Leaderboard',
                'social.follow': 'Follow Strategy',
                'social.my_follows': 'My Follows',
                'analysis.technical': 'Technical Analysis',
                'analysis.fundamental': 'Fundamental Analysis',
                'reports.daily': 'Daily Report',
                'reports.weekly': 'Weekly Report',
                'reports.monthly': 'Monthly Report',
                'settings.general': 'General Settings',
                'settings.language': 'Language Settings',
                'settings.notifications': 'Notification Settings',
                'settings.api': 'API Settings',
                'common.save': 'Save',
                'common.cancel': 'Cancel',
                'common.confirm': 'Confirm',
                'common.delete': 'Delete',
                'common.edit': 'Edit',
                'common.create': 'Create',
                'common.back': 'Back',
                'common.next': 'Next',
                'common.previous': 'Previous',
                'common.success': 'Success',
                'common.error': 'Error',
                'common.warning': 'Warning',
                'common.info': 'Info',
                'common.loading': 'Loading...',
                'common.search': 'Search',
                'common.filter': 'Filter',
                'common.sort': 'Sort',
                'common.export': 'Export',
                'common.import': 'Import',
                'common.refresh': 'Refresh',
                'common.clear': 'Clear',
                'common.reset': 'Reset',
                'common.apply': 'Apply',
            }
        }
        
        for lang_code, translations in default_translations.items():
            with open(os.path.join(language_dir, f'{lang_code}.json'), 'w', encoding='utf-8') as f:
                json.dump(translations, f, indent=2, ensure_ascii=False)
            logger.info(f"Created default translation for {lang_code}")
    
    def set_language(self, language: str):
        if language in self.languages:
            self.current_language = language
            logger.info(f"Language set to: {language}")
            return True
        else:
            logger.error(f"Language {language} not found")
            return False
    
    def get_text(self, key: str, **kwargs) -> str:
        if self.current_language in self.languages:
            if key in self.languages[self.current_language]:
                text = self.languages[self.current_language][key]
                if kwargs:
                    return text.format(**kwargs)
                return text
            else:
                logger.warning(f"Translation key not found: {key}")
                return key
        else:
            logger.error(f"Current language not found: {self.current_language}")
            return key
    
    def get_available_languages(self) -> Dict[str, str]:
        language_names = {
            'zh': '中文',
            'en': 'English',
        }
        return {
            lang_code: language_names.get(lang_code, lang_code)
            for lang_code in self.languages
        }
    
    def add_translation(self, language: str, key: str, value: str):
        if language not in self.languages:
            self.languages[language] = {}
        
        self.languages[language][key] = value
        logger.info(f"Added translation for {key} in {language}")
        
        # Save to file
        language_dir = os.path.join(os.path.dirname(__file__), 'translations')
        try:
            with open(os.path.join(language_dir, f'{language}.json'), 'w', encoding='utf-8') as f:
                json.dump(self.languages[language], f, indent=2, ensure_ascii=False)
            logger.info(f"Saved translations for {language}")
        except Exception as e:
            logger.error(f"Error saving translations: {e}")
    
    def import_translation(self, language: str, translations: Dict[str, str]):
        self.languages[language] = translations
        logger.info(f"Imported translations for {language}")
        
        # Save to file
        language_dir = os.path.join(os.path.dirname(__file__), 'translations')
        try:
            with open(os.path.join(language_dir, f'{language}.json'), 'w', encoding='utf-8') as f:
                json.dump(translations, f, indent=2, ensure_ascii=False)
            logger.info(f"Saved imported translations for {language}")
        except Exception as e:
            logger.error(f"Error saving imported translations: {e}")
