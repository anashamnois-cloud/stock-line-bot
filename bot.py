import requests
import json
import time
import os
from datetime import datetime, timezone, timedelta

# =========================
# LOAD CONFIG
# =========================
with open("config.json", "r", encoding="utf-8") as f:
    config = json.load(f)
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY")
LINE_TOKEN = os.getenv("LINE_CHANNEL_TOKEN")
LINE_USER_ID = os.getenv("LINE_USER_ID")
STOCKS = config["stocks"]
STATE_FILE = "state.json"
TZ = timezone(timedelta(hours=7))

# =========================
# LOAD STATE
# =========================
def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

# =========================
# SAVE STATE
# =========================
def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f)

# =========================
# เช็คว่าตลาดเปิดอยู่ไหม
# =========================
def is_market_open():
    now = datetime.now(TZ)
    weekday = now.weekday()  # 0=จันทร์, 6=อาทิตย์
    hour = now.hour
    minute = now.minute
    total_minutes = hour * 60 + minute

    # ตลาดเปิด 21:30 - 04:00 จันทร์-ศุกร์ (รวมข้ามคืน)
    market_open = 21 * 60 + 30   # 21:30
    midnight = 24 * 60           # 00:00
    market_close = 4 * 60        # 04:00

    # ช่วง 21:30 - 23:59 วันจันทร์-ศุกร์
    if weekday <= 4 and total_minutes >= market_open:
        return True
    # ช่วง 00:00 - 04:00 วันอังคาร-เสาร์ (ข้ามคืน)
    if weekday >= 1 and weekday <= 5 and total_minutes < market_close:
        return True
    return False

# =========================
# GET STOCK PRICE
# =========================
def get_price(symbol):
    url = "https://finnhub.io/api/v1/quote"
    params = {"symbol": symbol, "token": FINNHUB_API_KEY}
    try:
        r = requests.get(url, params=params, timeout=10)
        return r.json().get("c")
    except:
        return None

# =========================
# SEND LINE MESSAGE
# =========================
def send_line(msg):
    url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Authorization": f"Bearer {LINE_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "to": LINE_USER_ID,
        "messages": [{"type": "text", "text": msg}]
    }
    requests.post(url, headers=headers, json=payload)

# =========================
# เช็คราคาหุ้น
# =========================
def check_stocks(state):
    for symbol, alert in STOCKS.items():
        price = get_price(symbol)
        if price is None:
            continue
        last_status = state.get(symbol)

        # 🚀 แตะเป้าขึ้น
        if price >= alert["alert_up"]:
            if last_status != "up":
                send_line(
                    f"🚀 {symbol} แตะเป้าขึ้นแล้ว\n"
                    f"ราคา: {price}\n"
                    f"เป้า: {alert['alert_up']}"
                )
                state[symbol] = "up"

        # 🔻 หลุดเป้าลง
        elif price <= alert["alert_down"]:
            last_price = state.get(f"{symbol}_last_down_price")
            if last_status != "down":
                send_line(
                    f"🔻 {symbol} หลุดเป้าลงแล้ว\n"
                    f"ราคา: {price}\n"
                    f"เป้า: {alert['alert_down']}"
                )
                state[symbol] = "down"
                state[f"{symbol}_last_down_price"] = price
            elif last_price is not None and last_price - price >= 5:
                send_line(
                    f"🔻 {symbol} ลงเพิ่มแล้ว\n"
                    f"ราคา: {price}"
                )
                state[f"{symbol}_last_down_price"] = price

        # 🔁 กลับเข้ากลาง รีเซ็ต
        else:
            state[symbol] = "neutral"
            state.pop(f"{symbol}_last_down_price", None)

        time.sleep(1)
    return state

# =========================
# MAIN LOOP
# =========================
print("🤖 Stock Bot เริ่มทำงานบน Railway")
market_was_open = False

while True:
    now = datetime.now(TZ)
    now_str = now.strftime("%Y-%m-%d %H:%M:%S")

    if is_market_open():
        # แจ้งตอนตลาดเปิดครั้งแรกเท่านั้น
        if not market_was_open:
            send_line(f"🔔 ตลาดเปิดแล้ว\n🕐 เวลา: {now_str}")
            market_was_open = True

        print(f"📊 เช็คราคา: {now_str}")
        state = load_state()
        state = check_stocks(state)
        save_state(state)
        print("✅ เสร็จแล้ว รอ 5 นาที...")
        time.sleep(300)  # รอ 5 นาที

    else:
        # แจ้งตอนตลาดปิดครั้งแรกเท่านั้น
        if market_was_open:
            send_line(f"🔕 ตลาดปิดแล้ว\n🕐 เวลา: {now_str}")
            market_was_open = False

        print(f"⏸ ตลาดปิด รอ... {now_str}")
        time.sleep(60)  # เช็คทุก 1 นาทีว่าตลาดเปิดหรือยัง
