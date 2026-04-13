"""
app.py — Catalan Trading Dashboard API

Serves account metrics from Alpaca (paper trading).
API keys are read server-side from .env and never exposed to the client.
"""

import json
import os
from datetime import datetime
from pathlib import Path

import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template
from alpaca.trading.client import TradingClient
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockSnapshotRequest

load_dotenv()

app = Flask(__name__)

ACCOUNTS = {
    "Heinrich": {
        "key": os.getenv("API_KEY"),
        "secret": os.getenv("API_SECRET"),
    },
    "Valya": {
        "key": os.getenv("API_KEY_VALYA"),
        "secret": os.getenv("API_SECRET_VALYA"),
    },
    "Outliers": {
        "key": os.getenv("API_KEY_OUTLIERS"),
        "secret": os.getenv("API_SECRET_OUTLIERS"),
    },
    "RUSS2K": {
        "key": os.getenv("API_KEY_RUSS2K"),
        "secret": os.getenv("API_SECRET_RUSS2K"),
    },
}


def _snapshot_to_dict(snap) -> dict:
    price = float(snap.latest_trade.price)
    prev_close = float(snap.previous_daily_bar.close)
    change = price - prev_close
    change_pct = (change / prev_close * 100) if prev_close else 0.0
    return {
        "price": round(price, 2),
        "change": round(change, 2),
        "change_pct": round(change_pct, 3),
        "error": None,
    }


SECTORS = [
    ("XLK",  "Technology"),
    ("XLF",  "Financials"),
    ("XLV",  "Health Care"),
    ("XLY",  "Cons. Discretionary"),
    ("XLP",  "Cons. Staples"),
    ("XLI",  "Industrials"),
    ("XLE",  "Energy"),
    ("XLC",  "Communication"),
    ("XLB",  "Materials"),
    ("XLRE", "Real Estate"),
    ("XLU",  "Utilities"),
]

SECTOR_SYMBOLS = [s[0] for s in SECTORS]


def fetch_ticker_data() -> dict:
    try:
        client = StockHistoricalDataClient(os.getenv("API_KEY"), os.getenv("API_SECRET"))
        all_symbols = ["SPY", "IWM"] + SECTOR_SYMBOLS
        snapshots = client.get_stock_snapshot(StockSnapshotRequest(symbol_or_symbols=all_symbols))

        sectors = []
        for symbol, name in SECTORS:
            if symbol in snapshots:
                entry = _snapshot_to_dict(snapshots[symbol])
            else:
                entry = {"error": "no data"}
            entry["symbol"] = symbol
            entry["name"] = name
            sectors.append(entry)

        return {
            "spy": _snapshot_to_dict(snapshots["SPY"]),
            "iwm": _snapshot_to_dict(snapshots["IWM"]),
            "sectors": sectors,
        }
    except Exception as e:
        err = {"error": str(e)}
        return {"spy": err, "iwm": err, "sectors": []}


def fetch_account_data(name: str, key: str, secret: str) -> dict:
    if not key or not secret:
        return {"name": name, "error": "credentials not configured"}

    try:
        client = TradingClient(key, secret, paper=True)
        account = client.get_account()
        positions = client.get_all_positions()

        equity = float(account.equity or 0)
        last_equity = float(account.last_equity or 0)
        daily_pnl = equity - last_equity
        daily_pnl_pct = (daily_pnl / last_equity * 100) if last_equity else 0.0

        positions_profit = sum(1 for p in positions if float(p.unrealized_pl or 0) > 0)
        positions_loss = sum(1 for p in positions if float(p.unrealized_pl or 0) < 0)
        positions_long = sum(1 for p in positions if p.side.value == "long")
        positions_short = sum(1 for p in positions if p.side.value == "short")

        return {
            "name": name,
            "account_value": round(equity, 2),
            "buying_power": round(float(account.buying_power or 0), 2),
            "cash": round(float(account.cash or 0), 2),
            "daily_pnl": round(daily_pnl, 2),
            "daily_pnl_pct": round(daily_pnl_pct, 3),
            "positions_total": len(positions),
            "positions_long": positions_long,
            "positions_short": positions_short,
            "positions_profit": positions_profit,
            "positions_loss": positions_loss,
            "error": None,
        }
    except Exception as e:
        return {"name": name, "error": str(e)}


HISTORY_FILE = Path("data/history.json")


def load_history() -> dict:
    if HISTORY_FILE.exists():
        with open(HISTORY_FILE) as f:
            return json.load(f)
    return {name: [] for name in ACCOUNTS}


def save_history(history: dict) -> None:
    HISTORY_FILE.parent.mkdir(exist_ok=True)
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2)


def record_snapshot() -> None:
    ny = pytz.timezone("America/New_York")
    today = datetime.now(ny).strftime("%Y-%m-%d")
    history = load_history()
    changed = False
    for name, creds in ACCOUNTS.items():
        entries = history.setdefault(name, [])
        if any(e["date"] == today for e in entries):
            continue
        data = fetch_account_data(name, creds["key"], creds["secret"])
        if data.get("error"):
            continue
        entries.append({
            "date": today,
            "account_value": data["account_value"],
            "daily_pnl": data["daily_pnl"],
        })
        changed = True
    if changed:
        save_history(history)


_scheduler = BackgroundScheduler(timezone=pytz.timezone("America/New_York"))
_scheduler.add_job(
    record_snapshot,
    CronTrigger(day_of_week="mon-fri", hour=16, minute=1,
                timezone=pytz.timezone("America/New_York")),
)
_scheduler.start()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/history")
def api_history():
    return jsonify(load_history())


@app.route("/api/accounts")
def api_accounts():
    results = []
    for name, creds in ACCOUNTS.items():
        data = fetch_account_data(name, creds["key"], creds["secret"])
        results.append(data)

    tickers = fetch_ticker_data()
    return jsonify({
        "accounts": results,
        "spy": tickers["spy"],
        "iwm": tickers["iwm"],
        "sectors": tickers["sectors"],
        "last_updated": datetime.now(pytz.timezone("America/New_York")).strftime("%Y-%m-%d %H:%M:%S ET"),
    })


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    app.run(host="0.0.0.0", port=port)