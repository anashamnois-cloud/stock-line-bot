import requests
import json
import time

# =========================
# LOAD CONFIG
# =========================
with open("config.json", "r", encoding="utf-8") as f:
    config = json.load(f)

FINNHUB_API_KEY = config["finnhub_api_key"]
LINE_TOKEN = config["line_channel_token"]
LINE_USER_ID = config["line_user_id"]
STOCKS = config["stocks"]

# =========================
# GET STOCK PRICE
# =========================
def get_price(symbol):
    url = "https://finnhub.io/api/v1/quote"
    params = {
        "symbol": symbol,
        "token": FINNHUB_API_KEY
    }

    r = requests.get(url, params=params, timeout=10)
    data = r.json()

    price = data.get("c")
    if not price:
        return None

    return price

# =========================
# SEND LINE MESSAGE (BOT)
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
# MAIN (RUN ONCE)
# =========================
print("📊 Stock Line Bot started")

message = "📈 สรุปราคาหุ้นที่ถืออยู่\n\n"

for symbol, alert in STOCKS.items():
    price = get_price(symbol)

    if price is None:
        message += f"{symbol}: ดึงราคาไม่ได้\n"
        continue

    message += f"{symbol}: {price}\n"

    if price >= alert["alert_up"]:
        message += "🚀 ถึงเป้าขึ้นแล้ว\n"

    elif price <= alert["alert_down"]:
        message += "🔻 หลุดเป้าลงแล้ว\n"

    message += "\n"
    time.sleep(1)  # กัน rate limit

send_line(message)
print("✅ ส่งเข้า LINE แล้ว")
