import json

with open('trade_records.json', 'r') as f:
    data = json.load(f)
    print('交易记录数:', len(data))
    print('最近5条交易记录:')
    for trade in data[-5:]:
        print(trade)