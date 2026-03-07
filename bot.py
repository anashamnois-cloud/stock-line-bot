import requests
import json
import time
import os

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

# =========================
# LOAD STATE
# =========================
if os.path.exists(STATE_FILE):
    with open(STATE_FILE, "r", encoding="utf-8") as f:
        state = json.load(f)
else:
    state = {}

# =========================
# SAVE STATE
# =========================
def save_state():
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f)

# =========================
# GET STOCK PRICE
# =========================
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
        "messages": [{
            "type": "text",
            "text": msg
        }]
    }
    requests.post(url, headers=headers, json=payload)

# =========================
# MAIN
# =========================
print("📊 Stock Line Bot started")

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
        
    last_price = state.get(symbol)
    
    # แจ้งครั้งแรก
    if last_price is None:
        send_line(
            f"🔻 {symbol} หลุดเป้าลงแล้ว\n"
            f"ราคา: {price}\n"
            f"เป้า: {alert['alert_down']}"
        )
        state[symbol] = price

    # ลงเพิ่มอีก 5$ ค่อยแจ้ง
    elif last_price - price >= 5:
        send_line(
            f"🔻 {symbol} ลงเพิ่มแล้ว\n"
            f"ราคา: {price}"
        )
        state[symbol] = price

    # 🔁 กลับเข้ากลาง รีเซ็ต
    else:
        state[symbol] = "neutral"

    time.sleep(1)

save_state()
print("✅ เช็กราคาเสร็จแล้ว")

