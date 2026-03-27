# -*- mode: python ; coding: utf-8 -*-

block_cipher = None


a = Analysis(['main.py'],
             pathex=['.'],
             binaries=[],
             datas=[],
             hiddenimports=[
                 'PyQt5.QtWidgets',
                 'PyQt5.QtCore',
                 'PyQt5.QtGui',
                 'agents.market_data_agent',
                 'agents.order_agent',
                 'agents.risk_management_agent',
                 'agents.strategy_execution_agent',
                 'agents.decision_coordination_agent',
                 'commons.logger_config',
                 'commons.health_checker',
                 'commons.agent_registry',
                 'commons.event_bus',
                 'commons.config_manager',
                 'commons.error_handler',
                 'services.market_data.market_data_service',
                 'services.order_management.order_manager',
                 'services.risk_management.risk_manager',
                 'strategies.base_strategy',
                 'strategies.dynamics_strategy',
                 'strategies.passivbot_integrator',
                 'okx_api_client',
                 'okx_websocket_client'
             ],
             hookspath=['.'],
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher,
             noarchive=False)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(pyz,
          a.scripts,
          a.binaries,
          a.zipfiles,
          a.datas,
          [],
          name='okx_trading_bot',
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=True,
          console=False,
          disable_windowed_traceback=False,
          target_arch=None,
          codesign_identity=None,
          entitlements_file=None)
