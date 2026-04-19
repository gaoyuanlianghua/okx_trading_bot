import json

with open('trade_records.json', 'r') as f:
    data = json.load(f)
    print('订单记录数:', len(data))
    print('最近5条订单记录:')
    for trade in data[-5:]:
        print(trade)