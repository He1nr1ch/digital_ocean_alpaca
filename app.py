"""
app.py — Catalan Trading Dashboard API

Serves account metrics from Alpaca (paper trading).
API keys are read server-side from .env and never exposed to the client.
"""

import os
from datetime import datetime

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template
from alpaca.trading.client import TradingClient

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
    "EarlyBird": {
        "key": os.getenv("API_KEY_EARLYBIRD"),
        "secret": os.getenv("API_SECRET_EARLYBIRD"),
    },
}


def fetch_account_data(name: str, key: str, secret: str) -> dict:
    if not key or not secret:
        return {"name": name, "error": "credentials not configured"}

    try:
        client = TradingClient(key, secret, paper=True)
        account = client.get_account()
        positions = client.get_all_positions()

        equity = float(account.equity)
        last_equity = float(account.last_equity)
        daily_pnl = equity - last_equity
        daily_pnl_pct = (daily_pnl / last_equity * 100) if last_equity else 0.0

        positions_profit = sum(1 for p in positions if float(p.unrealized_pl) > 0)
        positions_loss = sum(1 for p in positions if float(p.unrealized_pl) < 0)

        return {
            "name": name,
            "account_value": round(equity, 2),
            "buying_power": round(float(account.buying_power), 2),
            "cash": round(float(account.cash), 2),
            "daily_pnl": round(daily_pnl, 2),
            "daily_pnl_pct": round(daily_pnl_pct, 3),
            "positions_total": len(positions),
            "positions_profit": positions_profit,
            "positions_loss": positions_loss,
            "error": None,
        }
    except Exception as e:
        return {"name": name, "error": str(e)}


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/accounts")
def api_accounts():
    results = []
    for name, creds in ACCOUNTS.items():
        data = fetch_account_data(name, creds["key"], creds["secret"])
        results.append(data)

    return jsonify({
        "accounts": results,
        "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    })


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    app.run(host="0.0.0.0", port=port)