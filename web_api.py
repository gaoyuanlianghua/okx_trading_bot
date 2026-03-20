from flask import Flask, jsonify, request
import sys
import os

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from main import TradingBot

app = Flask(__name__)
trading_bot = None

@app.route('/')
def index():
    """首页"""
    return '''
    <h1>OKX 交易机器人</h1>
    <p>API 接口: /api/health</p>
    <p>状态: /api/status</p>
    '''

@app.route('/api/health')
def health():
    """健康检查"""
    return jsonify({
        "status": "ok",
        "service": "okx_trading_bot",
        "version": "1.0.0"
    })

@app.route('/api/status')
def status():
    """获取机器人状态"""
    global trading_bot
    if trading_bot is None:
        try:
            trading_bot = TradingBot()
        except Exception as e:
            return jsonify({
                "status": "error",
                "message": f"初始化交易机器人失败: {str(e)}"
            }), 500
    
    return jsonify({
        "status": "running",
        "agents": list(trading_bot.agents.keys()) if hasattr(trading_bot, 'agents') else []
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8083, debug=False)
