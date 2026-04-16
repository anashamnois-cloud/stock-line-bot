import requests
import json
import time
import os
from datetime import datetime, timezone, timedelta

# -----------------------
# CONFIG
# -----------------------
# ใช้ทางเลือกเผื่อไฟล์หายให้บอทไม่พัง
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

STATE_FILE = "state.json"
TZ = timezone(timedelta(hours=7))

# -----------------------
# STATE MANAGEMENT
# -----------------------
def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                content = f.read().strip()
                return json.loads(content) if content else {}
        except Exception as e:
            print(f"Error loading state: {e}")
            return {}
    return {}

def save_state(state):
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(state, f, indent=4)
    except Exception as e:
        print(f"Error saving state: {e}")

# -----------------------
# MARKET TIME (US Market Example: 21:30 - 04:00 TH)
# -----------------------
def market_open():
    now = datetime.now(TZ)
    weekday = now.weekday() # 0=Mon, 4=Fri
    minutes = now.hour * 60 + now.minute

    # เวลาเปิด 21:30 (1290 นาที) ถึง 04:00 (240 นาที ของวันถัดไป)
    open_time = 21 * 60 + 30
    close_time = 4 * 60

    if weekday <= 4 and minutes >= open_time: # คืนวันจันทร์-ศุกร์
        return True
    if 1 <= weekday <= 5 and minutes < close_time: # เช้าวันอังคาร-เสาร์
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
        return data.get("c") # Current price
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

    # สร้าง Key แยกกันระหว่างขาขึ้นกับขาลง
    key_down = f"{symbol}_last_down_price"
    key_up = f"{symbol}_last_up_price"
    
    target_down = rule.get("alert_down")
    target_up = rule.get("alert_up")

    # --- เช็กขาลง (Down) ---
    if target_down and price <= target_down:
        last_down = state.get(key_down)
        if last_down is None or (last_down - price) >= 5:
            send_line(f"🔻 {symbol} หลุดเป้าขาลง!\nราคา: {price}\nเป้า: {target_down}")
            state[key_down] = price
    elif target_down and price > target_down + 2:
        if key_down in state: del state[key_down]

    # --- เช็กขาขึ้น (Up) --- เพิ่มส่วนนี้เข้าไปครับ!
    if target_up and price >= target_up:
        last_up = state.get(key_up)
        # แจ้งครั้งแรกที่ทะลุเป้า หรือ แจ้งเพิ่มทุกครั้งที่ขึ้นไปอีก 5$
        if last_up is None or (price - last_up) >= 5:
            send_line(f"🚀 {symbol} ทะลุเป้าขาขึ้น!\nราคา: {price}\nเป้า: {target_up}")
            state[key_up] = price
            print(f"Alert Up for {symbol}")
            
    elif target_up and price < target_up - 2:
        # ถ้าราคาตกลงมาต่ำกว่าเป้าขาขึ้น (Reset) เพื่อรอแจ้งใหม่เมื่อมันพุ่งรอบหน้า
        if key_up in state:
            del state[key_up]

# -----------------------
# MAIN (No while True for GitHub Actions)
# -----------------------
def main():
    if not market_open():
        print(f"[{datetime.now(TZ)}] Market is closed. Skipping...")
        return

    print(f"[{datetime.now(TZ)}] Checking stocks...")
    state = load_state()
    
    for symbol, rule in STOCKS.items():
        check_stock(symbol, rule, state)
        time.sleep(1) # เลี่ยง Rate limit

    save_state(state)
    print("Done.")

if __name__ == "__main__":
    main()
