import requests
import json
import time
import os
from datetime import datetime, timezone, timedelta
from upstash_redis import Redis

# -----------------------
# CONFIG
# -----------------------
def load_config():
    try:
        with open("config.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print("Error: config.json not found!")
        return {"stocks": {}}

config = load_config()
STOCKS = config.get("stocks", {})

FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY")
LINE_TOKEN = os.getenv("LINE_CHANNEL_TOKEN")
LINE_USER_ID = os.getenv("LINE_USER_ID")

TZ = timezone(timedelta(hours=7))

# -----------------------
# REDIS STATE
# -----------------------
redis = Redis(
    url=os.getenv("UPSTASH_REDIS_REST_URL"),
    token=os.getenv("UPSTASH_REDIS_REST_TOKEN")
)

def load_state():
    try:
        data = redis.get("stock_state")
        return json.loads(data) if data else {}
    except Exception as e:
        print(f"Error loading state: {e}")
        return {}

def save_state(state):
    try:
        redis.set("stock_state", json.dumps(state))
        print("State saved to Redis.")
    except Exception as e:
        print(f"Error saving state: {e}")

# -----------------------
# MARKET TIME
# -----------------------
def market_open():
    now = datetime.now(TZ)
    weekday = now.weekday()
    minutes = now.hour * 60 + now.minute

    open_time = 20 * 60 + 30
    close_time = 4 * 60

    if 0 <= weekday <= 4 and minutes >= open_time:
        return True
    if 2 <= weekday <= 6 and minutes < close_time:
        return True
    return False

# -----------------------
# GET PRICE & LINE
# -----------------------
def get_price(symbol):
    url = f"https://finnhub.io/api/v1/quote?symbol={symbol}&token={FINNHUB_API_KEY}"
    try:
        r = requests.get(url, timeout=10)
        data = r.json()
        return data.get("c")
    except:
        return None

def send_line(text):
    url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Authorization": f"Bearer {LINE_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "to": LINE_USER_ID,
        "messages": [{"type": "text", "text": text}]
    }
    requests.post(url, headers=headers, json=payload)

# -----------------------
# CORE LOGIC
# -----------------------
def check_stock(symbol, rule, state):
    price = get_price(symbol)
    if price is None or price == 0:
        return

    key_down = f"{symbol}_last_down_price"
    key_up = f"{symbol}_last_up_price"

    target_down = rule.get("alert_down")
    target_up = rule.get("alert_up")

    if target_up and price >= target_up:
        last_up = state.get(key_up)

        if last_up is None:
            send_line(f"🚀 {symbol} ทะลุเป้าขาขึ้น!\nราคา: {price}\nเป้า: {target_up}")
            state[key_up] = price
        elif (price - last_up) >= 5:
            send_line(f"📈 {symbol} ทำยอดสูงสุดใหม่!\nราคา: {price}\n(พุ่งทะลุยอดเดิม +{round(price - last_up, 2)})")
            state[key_up] = price
        elif (last_up - price) >= 5:
            key_warned_drop = f"{symbol}_warned_drop"
            if state.get(key_warned_drop) != last_up:
                send_line(f"📉 {symbol} ย่อตัวลงจากยอดสูงสุด!\nราคา: {price}\n(ลดลงจากจุดสูงสุด -{round(last_up - price, 2)})")
                state[key_warned_drop] = last_up

    elif target_up and price < target_up - 5:
        if key_up in state: del state[key_up]
        if f"{symbol}_warned_drop" in state: del state[f"{symbol}_warned_drop"]

    if target_down and price <= target_down:
        last_down = state.get(key_down)

        if last_down is None:
            send_line(f"🔻 {symbol} หลุดเป้าขาลง!\nราคา: {price}\nเป้า: {target_down}")
            state[key_down] = price
        elif (last_down - price) >= 5:
            send_line(f"📉 {symbol} ทุบสถิติดิ่งลงเหวใหม่!\nราคา: {price}\n(ทะลุก้นเหวเดิม -{round(last_down - price, 2)})")
            state[key_down] = price
        elif (price - last_down) >= 5:
            key_warned_bounce = f"{symbol}_warned_bounce"
            if state.get(key_warned_bounce) != last_down:
                send_line(f"🧗 {symbol} เริ่มเด้งกลับจากก้นเหว!\nราคา: {price}\n(ดีดขึ้นมาจากจุดต่ำสุด +{round(price - last_down, 2)})")
                state[key_warned_bounce] = last_down

    elif target_down and price > target_down + 5:
        if key_down in state: del state[key_down]
        if f"{symbol}_warned_bounce" in state: del state[f"{symbol}_warned_bounce"]

# -----------------------
# MAIN LOOP
# -----------------------
def main():
    print(f"[{datetime.now(TZ)}] Bot started...")
    state = load_state()
    has_run_in_market = False

    try:
        while True:
            now = datetime.now(TZ)

            if market_open():
                print(f"[{now.strftime('%H:%M:%S')}] Checking stocks...")
                for symbol, rule in STOCKS.items():
                    try:
                        check_stock(symbol, rule, state)
                    except Exception as e:
                        print(f"[ERROR] {symbol}: {e}")
                    time.sleep(1)

                save_state(state)
                has_run_in_market = True
                time.sleep(60)

            else:
                if has_run_in_market:
                    print(f"[{now}] Market closed. Waiting for next session...")
                    has_run_in_market = False

                print(f"[{now.strftime('%H:%M:%S')}] Market closed. Sleeping 60s...")
                time.sleep(60)

    except KeyboardInterrupt:
        print("Stopped.")
        save_state(state)

if __name__ == "__main__":
    main()
