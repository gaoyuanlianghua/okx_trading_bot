#!/usr/bin/env python3
# 调整策略参数，使其更敏感

import yaml

# 读取当前策略配置
with open('config/config.yaml', 'r') as f:
    config = yaml.safe_load(f)

# 调整策略参数
config['strategy']['strategies']['NuclearDynamicsStrategy'].update({
    'G_eff': 0.005,  # 增加市场耦合系数，使策略更敏感
    'max_position': 0.5,
    'position_size': 0.1,
    'stop_loss': 0.02,
    'take_profit': 0.05,
    'ε': 0.85
})

# 保存修改后的配置
with open('config/config.yaml', 'w') as f:
    yaml.safe_dump(config, f)

print("策略参数已调整，使其更敏感")
