import requests
import json
import time
import os
from datetime import datetime, timezone, timedelta

# -----------------------
# CONFIG
# -----------------------
with open("config.json", "r", encoding="utf-8") as f:
    config = json.load(f)

STOCKS = config["stocks"]

FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY")
LINE_TOKEN = os.getenv("LINE_CHANNEL_TOKEN")
LINE_USER_ID = os.getenv("LINE_USER_ID")

STATE_FILE = "state.json"

TZ = timezone(timedelta(hours=7))


# -----------------------
# STATE
# -----------------------
def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)


# -----------------------
# MARKET TIME
# -----------------------
def market_open():

    now = datetime.now(TZ)
    weekday = now.weekday()

    minutes = now.hour * 60 + now.minute

    open_time = 21 * 60 + 30
    close_time = 4 * 60

    if weekday <= 4 and minutes >= open_time:
        return True

    if 1 <= weekday <= 5 and minutes < close_time:
        return True

    return False


# -----------------------
# GET PRICE
# -----------------------
def get_price(symbol):

    url = "https://finnhub.io/api/v1/quote"

    params = {
        "symbol": symbol,
        "token": FINNHUB_API_KEY
    }

    try:
        r = requests.get(url, params=params, timeout=10)
        data = r.json()
        return data.get("c")
    except:
        return None


# -----------------------
# LINE
# -----------------------
def send_line(text):

    url = "https://api.line.me/v2/bot/message/push"

    headers = {
        "Authorization": f"Bearer {LINE_TOKEN}",
        "Content-Type": "application/json"
    }

    payload = {
        "to": LINE_USER_ID,
        "messages": [{
            "type": "text",
            "text": text
        }]
    }

    requests.post(url, headers=headers, json=payload)


# -----------------------
# CHECK STOCK
# -----------------------
def check_stock(symbol, rule, state):

    price = get_price(symbol)

    if price is None:
        return

    key = f"{symbol}_last_alert"

    target = rule["alert_down"]

    # ต่ำกว่าเป้า
    if price <= target:

        last = state.get(key)

        # แจ้งครั้งแรก
        if last is None:

            send_line(
                f"🔻 {symbol} หลุดเป้า\n"
                f"ราคา: {price}\n"
                f"เป้า: {target}"
            )

            state[key] = price

        # ลงเพิ่ม 5$
        elif last - price >= 5:

            send_line(
                f"🔻 {symbol} ลงเพิ่ม\n"
                f"ราคา: {price}"
            )

            state[key] = price

    else:
        # กลับเหนือเป้า รีเซ็ต
        if key in state:
            del state[key]


# -----------------------
# MAIN LOOP
# -----------------------
print("bot running...")

state = load_state()

while True:

    if market_open():

        for symbol, rule in STOCKS.items():

            check_stock(symbol, rule, state)

            time.sleep(1)

        save_state(state)

    time.sleep(60)
