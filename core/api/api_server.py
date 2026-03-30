import asyncio
import json
import time
import uvicorn
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.staticfiles import StaticFiles
from jose import JWTError, jwt
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from core.utils.logger import get_logger
from core.events.event_bus import EventBus
from core.social.social_trading_manager import SocialTradingManager
from core.reporting.performance_reporter import PerformanceReporter
from core.analysis.technical_analyzer import TechnicalAnalyzer
from core.analysis.fundamental_analyzer import FundamentalAnalyzer

logger = get_logger(__name__)

# 配置
SECRET_KEY = "your-secret-key"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

app = FastAPI(
    title="OKX Trading Bot API",
    description="API for OKX Trading Bot mobile app",
    version="1.0.0"
)

# 挂载静态文件
app.mount("/static", StaticFiles(directory="core/api/static"), name="static")

# 添加管理界面路由
@app.get("/admin")
async def admin_page():
    return {"message": "Admin page", "url": "/static/index.html"}

@app.get("/")
async def root():
    return {"message": "OKX Trading Bot API", "admin_url": "/static/index.html"}

# 依赖项
class Dependencies:
    def __init__(self):
        self.event_bus = None
        self.social_trading_manager = None
        self.performance_reporter = None
        self.technical_analyzer = TechnicalAnalyzer()
        self.fundamental_analyzer = FundamentalAnalyzer()
    
    def set_event_bus(self, event_bus: EventBus):
        self.event_bus = event_bus
        if event_bus:
            self.social_trading_manager = SocialTradingManager(event_bus)
            self.performance_reporter = PerformanceReporter(event_bus)

deps = Dependencies()

def get_deps():
    return deps

# 安全
class User:
    def __init__(self, username: str, password: str, role: str = "user"):
        self.username = username
        self.password = password
        self.role = role

# 模拟用户数据库
fake_users_db = {
    "admin": {
        "username": "admin",
        "password": "admin",
        "role": "admin"
    },
    "user": {
        "username": "user",
        "password": "password",
        "role": "user"
    }
}

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token")

def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = fake_users_db.get(username)
    if user is None:
        raise credentials_exception
    return user

# API路由
@app.post("/api/auth/token")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user = fake_users_db.get(form_data.username)
    if not user or user["password"] != form_data.password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user["username"], "role": user["role"]}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer", "user": {"username": user["username"], "role": user["role"]}}

@app.get("/api/strategies")
async def get_strategies(current_user: User = Depends(get_current_user)):
    # 模拟策略数据
    strategies = [
        {
            "id": "1",
            "name": "趋势跟踪策略",
            "description": "基于移动平均线的趋势跟踪策略",
            "status": "active",
            "performance": 15.5
        },
        {
            "id": "2",
            "name": "均值回归策略",
            "description": "基于价格回归的策略",
            "status": "inactive",
            "performance": 8.2
        }
    ]
    return {"strategies": strategies}

@app.get("/api/orders")
async def get_orders(current_user: User = Depends(get_current_user)):
    # 模拟订单数据
    orders = [
        {
            "id": "1",
            "symbol": "BTC/USDT",
            "side": "buy",
            "price": 45000.0,
            "size": 0.01,
            "status": "filled",
            "timestamp": "2023-07-01T12:00:00"
        },
        {
            "id": "2",
            "symbol": "ETH/USDT",
            "side": "sell",
            "price": 3000.0,
            "size": 0.1,
            "status": "pending",
            "timestamp": "2023-07-01T13:00:00"
        }
    ]
    return {"orders": orders}

@app.get("/api/balance")
async def get_balance(current_user: User = Depends(get_current_user)):
    # 模拟余额数据
    balance = {
        "USDT": 10000.0,
        "BTC": 0.1,
        "ETH": 1.0
    }
    return {"balance": balance}

@app.get("/api/social/leaderboard")
async def get_leaderboard(current_user: User = Depends(get_current_user)):
    deps = get_deps()
    if deps.social_trading_manager:
        leaderboard = await deps.social_trading_manager.get_strategy_leaderboard()
        return {"leaderboard": leaderboard}
    else:
        # 模拟排行榜数据
        leaderboard = [
            {
                "strategy_id": "1",
                "strategy_name": "Top Strategy",
                "owner": "user1",
                "performance": 25.5,
                "followers_count": 100
            },
            {
                "strategy_id": "2",
                "strategy_name": "Trend Master",
                "owner": "user2",
                "performance": 18.2,
                "followers_count": 80
            }
        ]
        return {"leaderboard": leaderboard}

@app.post("/api/social/follow")
async def follow_strategy(strategy_id: str, settings: Dict[str, Any], current_user: User = Depends(get_current_user)):
    deps = get_deps()
    if deps.social_trading_manager:
        result = await deps.social_trading_manager.follow_strategy(current_user.username, strategy_id, settings)
        return {"success": result}
    else:
        return {"success": True, "message": "Strategy followed successfully"}

@app.get("/api/reports/daily")
async def get_daily_report(current_user: User = Depends(get_current_user)):
    deps = get_deps()
    if deps.performance_reporter:
        report = await deps.performance_reporter.generate_daily_report()
        return {"report": report}
    else:
        # 模拟日报数据
        report = {
            "date": "2023-07-01",
            "trades_count": 10,
            "performance": {
                "total_return": 100.5,
                "win_rate": 0.7
            }
        }
        return {"report": report}

@app.get("/api/analysis/technical/{symbol}")
async def get_technical_analysis(symbol: str, current_user: User = Depends(get_current_user)):
    deps = get_deps()
    # 模拟价格数据
    prices = [45000, 45200, 45100, 45300, 45500, 45400, 45600, 45800, 45700, 45900]
    rsi = deps.technical_analyzer.calculate_rsi(prices)
    macd = deps.technical_analyzer.calculate_macd(prices)
    bollinger = deps.technical_analyzer.calculate_bollinger_bands(prices)
    
    return {
        "symbol": symbol,
        "rsi": rsi[-1],
        "macd": macd["histogram"][-1],
        "bollinger": {
            "upper": bollinger["upper"][-1],
            "middle": bollinger["middle"][-1],
            "lower": bollinger["lower"][-1]
        }
    }

@app.get("/api/analysis/fundamental/{symbol}")
async def get_fundamental_analysis(symbol: str, current_user: User = Depends(get_current_user)):
    deps = get_deps()
    analysis = await deps.fundamental_analyzer.analyze_coin_fundamentals(symbol)
    return {"analysis": analysis}

# 机器人管理API
@app.get("/api/bots")
async def get_bots(current_user: User = Depends(get_current_user)):
    # 模拟机器人数据
    bots = [
        {
            "id": "1",
            "name": "BTC趋势跟踪",
            "strategy": "移动平均线策略",
            "status": "running",
            "performance": 12.5,
            "uptime": "2d 14h",
            "config": {
                "symbol": "BTC/USDT",
                "timeframe": "1h",
                "params": {
                    "short_ma": 50,
                    "long_ma": 200
                }
            }
        },
        {
            "id": "2",
            "name": "ETH套利",
            "strategy": "套利策略",
            "status": "running",
            "performance": 8.3,
            "uptime": "1d 8h",
            "config": {
                "symbol": "ETH/USDT",
                "timeframe": "15m",
                "params": {
                    "arbitrage_threshold": 0.5
                }
            }
        },
        {
            "id": "3",
            "name": "SOL均值回归",
            "strategy": "均值回归策略",
            "status": "stopped",
            "performance": 5.7,
            "uptime": "3d 6h",
            "config": {
                "symbol": "SOL/USDT",
                "timeframe": "30m",
                "params": {
                    "mean_period": 20,
                    "std_dev": 2
                }
            }
        },
        {
            "id": "4",
            "name": "多币种组合",
            "strategy": "组合策略",
            "status": "stopped",
            "performance": -2.1,
            "uptime": "1d 2h",
            "config": {
                "symbols": ["BTC/USDT", "ETH/USDT", "SOL/USDT"],
                "timeframe": "1h",
                "params": {
                    "allocation": [0.4, 0.3, 0.3]
                }
            }
        }
    ]
    return {"bots": bots}

@app.get("/api/bots/{bot_id}")
async def get_bot(bot_id: str, current_user: User = Depends(get_current_user)):
    # 模拟机器人数据
    bot = {
        "id": bot_id,
        "name": "BTC趋势跟踪",
        "strategy": "移动平均线策略",
        "status": "running",
        "performance": 12.5,
        "uptime": "2d 14h",
        "config": {
            "symbol": "BTC/USDT",
            "timeframe": "1h",
            "params": {
                "short_ma": 50,
                "long_ma": 200
            }
        },
        "stats": {
            "total_trades": 120,
            "win_rate": 0.68,
            "max_drawdown": 8.5,
            "sharpe_ratio": 1.2
        }
    }
    return {"bot": bot}

@app.post("/api/bots")
async def create_bot(bot_data: Dict[str, Any], current_user: User = Depends(get_current_user)):
    # 模拟创建机器人
    new_bot = {
        "id": str(int(time.time())),
        "name": bot_data.get("name", "New Bot"),
        "strategy": bot_data.get("strategy", "移动平均线策略"),
        "status": "stopped",
        "performance": 0.0,
        "uptime": "0h 0m",
        "config": bot_data.get("config", {})
    }
    return {"bot": new_bot, "message": "机器人创建成功"}

@app.put("/api/bots/{bot_id}")
async def update_bot(bot_id: str, bot_data: Dict[str, Any], current_user: User = Depends(get_current_user)):
    # 模拟更新机器人
    updated_bot = {
        "id": bot_id,
        "name": bot_data.get("name", "BTC趋势跟踪"),
        "strategy": bot_data.get("strategy", "移动平均线策略"),
        "status": "stopped",
        "performance": 12.5,
        "uptime": "2d 14h",
        "config": bot_data.get("config", {})
    }
    return {"bot": updated_bot, "message": "机器人更新成功"}

@app.post("/api/bots/{bot_id}/start")
async def start_bot(bot_id: str, current_user: User = Depends(get_current_user)):
    # 模拟启动机器人
    return {"message": "机器人启动成功", "bot_id": bot_id, "status": "running"}

@app.post("/api/bots/{bot_id}/stop")
async def stop_bot(bot_id: str, current_user: User = Depends(get_current_user)):
    # 模拟停止机器人
    return {"message": "机器人停止成功", "bot_id": bot_id, "status": "stopped"}

@app.delete("/api/bots/{bot_id}")
async def delete_bot(bot_id: str, current_user: User = Depends(get_current_user)):
    # 模拟删除机器人
    return {"message": "机器人删除成功", "bot_id": bot_id}

# 实时监控API
@app.get("/api/monitoring/market-data")
async def get_market_data(current_user: User = Depends(get_current_user)):
    # 模拟实时市场数据
    market_data = {
        "BTC/USDT": {
            "price": 45234.56,
            "change_24h": 2.3,
            "volume_24h": 24500000000,
            "high_24h": 45876.23,
            "low_24h": 44890.12
        },
        "ETH/USDT": {
            "price": 3245.78,
            "change_24h": 1.8,
            "volume_24h": 12300000000,
            "high_24h": 3289.45,
            "low_24h": 3198.23
        },
        "SOL/USDT": {
            "price": 123.45,
            "change_24h": -0.5,
            "volume_24h": 3450000000,
            "high_24h": 125.67,
            "low_24h": 121.23
        }
    }
    return {"market_data": market_data}

@app.get("/api/monitoring/bot-status")
async def get_bot_status(current_user: User = Depends(get_current_user)):
    # 模拟机器人状态
    bot_status = [
        {
            "id": "1",
            "name": "BTC趋势跟踪",
            "status": "running",
            "current_price": 45234.56,
            "last_trade": "buy",
            "last_trade_price": 45123.45,
            "pnl": 111.11
        },
        {
            "id": "2",
            "name": "ETH套利",
            "status": "running",
            "current_price": 3245.78,
            "last_trade": "sell",
            "last_trade_price": 3250.12,
            "pnl": -4.34
        },
        {
            "id": "3",
            "name": "SOL均值回归",
            "status": "stopped",
            "current_price": 123.45,
            "last_trade": "buy",
            "last_trade_price": 124.56,
            "pnl": -1.11
        },
        {
            "id": "4",
            "name": "多币种组合",
            "status": "stopped",
            "current_price": None,
            "last_trade": None,
            "last_trade_price": None,
            "pnl": 0.0
        }
    ]
    return {"bot_status": bot_status}

@app.get("/api/monitoring/system-status")
async def get_system_status(current_user: User = Depends(get_current_user)):
    # 模拟系统状态
    system_status = {
        "uptime": "5d 12h 34m",
        "cpu_usage": 15.2,
        "memory_usage": 32.5,
        "disk_usage": 28.3,
        "api_connections": 5,
        "websocket_connections": 3,
        "active_strategies": 2
    }
    return {"system_status": system_status}

# 启动API服务
async def start_api_server(event_bus: EventBus = None):
    if event_bus:
        deps.set_event_bus(event_bus)
    config = uvicorn.Config(
        "core.api.api_server:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
    server = uvicorn.Server(config)
    logger.info("Starting API server on http://localhost:8000")
    await server.serve()
