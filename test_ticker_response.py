import sys
import json
from okx_api_client import OKXAPIClient

# Load configuration
with open('config/okx_config.json', 'r') as f:
    config = json.load(f)

# Create API client
client = OKXAPIClient(
    api_key=config['api']['api_key'],
    api_secret=config['api']['api_secret'],
    passphrase=config['api']['passphrase'],
    is_test=config['api']['is_test'],
    api_url=config['api']['api_url']
)

# Test get_ticker method
print("Testing get_ticker method...")
ticker = client.get_ticker('BTC-USDT-SWAP')
if ticker:
    print(f"\nAPI Response Structure:")
    print(f"Type: {type(ticker)}")
    print(f"Length: {len(ticker)}")
    
    if isinstance(ticker, list) and len(ticker) > 0:
        print(f"\nFirst item keys: {list(ticker[0].keys())}")
        print(f"\nFull response:")
        print(json.dumps(ticker, indent=2))
    else:
        print(f"\nResponse content:")
        print(json.dumps(ticker, indent=2))
else:
    print("Failed to get ticker")

# Test order book method
print("\n\nTesting get_order_book method...")
order_book = client.get_order_book('BTC-USDT-SWAP', 5)
if order_book:
    print(f"Order book type: {type(order_book)}")
    if isinstance(order_book, list) and len(order_book) > 0:
        print(f"Order book keys: {list(order_book[0].keys())}")
        print(f"Bids count: {len(order_book[0].get('bids', []))}")
        print(f"Asks count: {len(order_book[0].get('asks', []))}")
        print(f"Sample bid: {order_book[0].get('bids', [])[0]}")
        print(f"Sample ask: {order_book[0].get('asks', [])[0]}")
    else:
        print(f"Order book content: {order_book}")
else:
    print("Failed to get order book")
