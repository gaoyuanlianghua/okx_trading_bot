import json

with open('order_agent_state.json', 'r') as f:
    data = json.load(f)
    print('订单记录数:', len(data.get('trades', [])))
    print('最近5条订单记录:')
    for trade in data.get('trades', [])[-5:]:
        print(trade)