import asyncio
import json
import time
import datetime
import pandas as pd
from typing import Dict, List, Optional, Any
from core.utils.logger import get_logger
from core.events.event_bus import EventBus

logger = get_logger(__name__)

class PerformanceReporter:
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self.trades: List[Dict[str, Any]] = []
        self.balance_history: List[Dict[str, Any]] = []
        self.event_bus.subscribe('trade_executed', self.handle_trade_executed)
        self.event_bus.subscribe('balance_updated', self.handle_balance_updated)
    
    async def handle_trade_executed(self, event: Dict[str, Any]):
        self.trades.append(event)
        logger.info(f"Trade recorded: {event.get('symbol')} {event.get('side')} {event.get('size')}")
    
    async def handle_balance_updated(self, event: Dict[str, Any]):
        self.balance_history.append(event)
        logger.info(f"Balance updated: {event.get('currency')} {event.get('balance')}")
    
    async def generate_daily_report(self, date: Optional[datetime.date] = None) -> Dict[str, Any]:
        if date is None:
            date = datetime.date.today() - datetime.timedelta(days=1)
        
        start_time = datetime.datetime.combine(date, datetime.time.min)
        end_time = datetime.datetime.combine(date, datetime.time.max)
        
        daily_trades = [t for t in self.trades if start_time.timestamp() <= t.get('timestamp', 0) <= end_time.timestamp()]
        daily_balances = [b for b in self.balance_history if start_time.timestamp() <= b.get('timestamp', 0) <= end_time.timestamp()]
        
        report = {
            'date': date.isoformat(),
            'trades_count': len(daily_trades),
            'performance': await self._calculate_performance(daily_trades, daily_balances),
            'trades_summary': await self._summarize_trades(daily_trades),
            'balance_summary': await self._summarize_balances(daily_balances),
            'metrics': await self._calculate_metrics(daily_trades)
        }
        
        logger.info(f"Generated daily report for {date.isoformat()}")
        return report
    
    async def generate_weekly_report(self, week_start: Optional[datetime.date] = None) -> Dict[str, Any]:
        if week_start is None:
            today = datetime.date.today()
            week_start = today - datetime.timedelta(days=today.weekday() + 7)
        
        week_end = week_start + datetime.timedelta(days=6)
        start_time = datetime.datetime.combine(week_start, datetime.time.min)
        end_time = datetime.datetime.combine(week_end, datetime.time.max)
        
        weekly_trades = [t for t in self.trades if start_time.timestamp() <= t.get('timestamp', 0) <= end_time.timestamp()]
        weekly_balances = [b for b in self.balance_history if start_time.timestamp() <= b.get('timestamp', 0) <= end_time.timestamp()]
        
        report = {
            'week_start': week_start.isoformat(),
            'week_end': week_end.isoformat(),
            'trades_count': len(weekly_trades),
            'performance': await self._calculate_performance(weekly_trades, weekly_balances),
            'trades_summary': await self._summarize_trades(weekly_trades),
            'balance_summary': await self._summarize_balances(weekly_balances),
            'metrics': await self._calculate_metrics(weekly_trades),
            'daily_breakdown': await self._generate_daily_breakdown(week_start, week_end)
        }
        
        logger.info(f"Generated weekly report for {week_start.isoformat()} to {week_end.isoformat()}")
        return report
    
    async def generate_monthly_report(self, year: int, month: int) -> Dict[str, Any]:
        start_date = datetime.date(year, month, 1)
        if month == 12:
            end_date = datetime.date(year + 1, 1, 1) - datetime.timedelta(days=1)
        else:
            end_date = datetime.date(year, month + 1, 1) - datetime.timedelta(days=1)
        
        start_time = datetime.datetime.combine(start_date, datetime.time.min)
        end_time = datetime.datetime.combine(end_date, datetime.time.max)
        
        monthly_trades = [t for t in self.trades if start_time.timestamp() <= t.get('timestamp', 0) <= end_time.timestamp()]
        monthly_balances = [b for b in self.balance_history if start_time.timestamp() <= b.get('timestamp', 0) <= end_time.timestamp()]
        
        report = {
            'year': year,
            'month': month,
            'trades_count': len(monthly_trades),
            'performance': await self._calculate_performance(monthly_trades, monthly_balances),
            'trades_summary': await self._summarize_trades(monthly_trades),
            'balance_summary': await self._summarize_balances(monthly_balances),
            'metrics': await self._calculate_metrics(monthly_trades),
            'weekly_breakdown': await self._generate_weekly_breakdown(start_date, end_date)
        }
        
        logger.info(f"Generated monthly report for {year}-{month:02d}")
        return report
    
    async def _calculate_performance(self, trades: List[Dict[str, Any]], balances: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not trades or not balances:
            return {
                'total_return': 0.0,
                'profit_loss': 0.0,
                'win_rate': 0.0,
                'average_win': 0.0,
                'average_loss': 0.0
            }
        
        profit_loss = 0.0
        win_count = 0
        win_amounts = []
        loss_amounts = []
        
        for trade in trades:
            pl = trade.get('profit_loss', 0.0)
            profit_loss += pl
            if pl > 0:
                win_count += 1
                win_amounts.append(pl)
            elif pl < 0:
                loss_amounts.append(pl)
        
        win_rate = win_count / len(trades) if trades else 0.0
        average_win = sum(win_amounts) / len(win_amounts) if win_amounts else 0.0
        average_loss = sum(loss_amounts) / len(loss_amounts) if loss_amounts else 0.0
        
        return {
            'total_return': profit_loss,
            'profit_loss': profit_loss,
            'win_rate': win_rate,
            'average_win': average_win,
            'average_loss': average_loss
        }
    
    async def _summarize_trades(self, trades: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not trades:
            return {
                'by_symbol': {},
                'by_side': {},
                'total_volume': 0.0
            }
        
        by_symbol = {}
        by_side = {'buy': 0, 'sell': 0}
        total_volume = 0.0
        
        for trade in trades:
            symbol = trade.get('symbol')
            side = trade.get('side')
            size = float(trade.get('size', 0))
            price = float(trade.get('price', 0))
            
            if symbol not in by_symbol:
                by_symbol[symbol] = {'count': 0, 'volume': 0.0, 'profit_loss': 0.0}
            
            by_symbol[symbol]['count'] += 1
            by_symbol[symbol]['volume'] += size * price
            by_symbol[symbol]['profit_loss'] += trade.get('profit_loss', 0.0)
            
            if side in by_side:
                by_side[side] += 1
            
            total_volume += size * price
        
        return {
            'by_symbol': by_symbol,
            'by_side': by_side,
            'total_volume': total_volume
        }
    
    async def _summarize_balances(self, balances: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not balances:
            return {'currencies': {}}
        
        currencies = {}
        
        for balance in balances:
            currency = balance.get('currency')
            if currency not in currencies:
                currencies[currency] = []
            currencies[currency].append(balance)
        
        balance_summary = {}
        for currency, balance_list in currencies.items():
            latest_balance = max(balance_list, key=lambda x: x.get('timestamp', 0))
            balance_summary[currency] = {
                'latest_balance': latest_balance.get('balance', 0),
                'change': latest_balance.get('balance', 0) - balance_list[0].get('balance', 0)
            }
        
        return {'currencies': balance_summary}
    
    async def _calculate_metrics(self, trades: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not trades:
            return {
                'sharpe_ratio': 0.0,
                'max_drawdown': 0.0,
                'profit_factor': 0.0,
                'average_holding_time': 0.0
            }
        
        profits = [t.get('profit_loss', 0) for t in trades]
        win_profits = [p for p in profits if p > 0]
        loss_profits = [abs(p) for p in profits if p < 0]
        
        sharpe_ratio = 0.0
        max_drawdown = 0.0
        profit_factor = sum(win_profits) / sum(loss_profits) if loss_profits else 0.0
        average_holding_time = 0.0
        
        return {
            'sharpe_ratio': sharpe_ratio,
            'max_drawdown': max_drawdown,
            'profit_factor': profit_factor,
            'average_holding_time': average_holding_time
        }
    
    async def _generate_daily_breakdown(self, week_start: datetime.date, week_end: datetime.date) -> List[Dict[str, Any]]:
        breakdown = []
        current_date = week_start
        
        while current_date <= week_end:
            daily_report = await self.generate_daily_report(current_date)
            breakdown.append(daily_report)
            current_date += datetime.timedelta(days=1)
        
        return breakdown
    
    async def _generate_weekly_breakdown(self, start_date: datetime.date, end_date: datetime.date) -> List[Dict[str, Any]]:
        breakdown = []
        current_week_start = start_date
        
        while current_week_start <= end_date:
            current_week_end = current_week_start + datetime.timedelta(days=6)
            if current_week_end > end_date:
                current_week_end = end_date
            
            week_report = await self.generate_weekly_report(current_week_start)
            breakdown.append(week_report)
            current_week_start += datetime.timedelta(days=7)
        
        return breakdown
    
    async def export_report(self, report: Dict[str, Any], format: str = 'json') -> Optional[str]:
        timestamp = time.time()
        filename = f"report_{timestamp}.{format}"
        
        try:
            if format == 'json':
                with open(filename, 'w') as f:
                    json.dump(report, f, indent=2)
            elif format == 'csv':
                if 'trades_summary' in report and 'by_symbol' in report['trades_summary']:
                    df = pd.DataFrame.from_dict(report['trades_summary']['by_symbol'], orient='index')
                    df.to_csv(filename)
            
            logger.info(f"Report exported to {filename}")
            return filename
        except Exception as e:
            logger.error(f"Error exporting report: {e}")
            return None
