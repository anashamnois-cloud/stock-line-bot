import requests
import json
import time
import os
from datetime import datetime, timezone, timedelta

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
        print("State successfully saved to file.")
    except Exception as e:
        print(f"Error saving state: {e}")

# -----------------------
# MARKET TIME (US Market Example: 21:30 - 04:00 TH)
# -----------------------
def market_open():
    now = datetime.now(TZ)
    weekday = now.weekday()  # 0=Mon, 4=Fri
    minutes = now.hour * 60 + now.minute

    open_time = 20 * 60 + 30  # 20:30
    close_time = 4 * 60       # 04:00

    if weekday <= 4 and minutes >= open_time:  # คืนวันจันทร์-ศุกร์
        return True
    if 1 <= weekday <= 5 and minutes < close_time:  # เช้าวันอังคาร-เสาร์
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
# CORE LOGIC (เวอร์ชันตาดีสองข้าง แกว่งขึ้น-ลงจับหมด)
# -----------------------
def check_stock(symbol, rule, state):
    price = get_price(symbol)
    if price is None or price == 0:
        return

    key_down = f"{symbol}_last_down_price"
    key_up = f"{symbol}_last_up_price"
    
    target_down = rule.get("alert_down")
    target_up = rule.get("alert_up")

    # ==========================================
    # 🚀 โซนขาขึ้น (เน้นแจ้ง New High เท่านั้น)
    # ==========================================
    if target_up and price >= target_up:
        last_up = state.get(key_up)
        
        if last_up is None:
            send_line(f"🚀 {symbol} ทะลุเป้าขาขึ้น!\nราคา: {price}\nเป้า: {target_up}")
            state[key_up] = price
        # ล็อกเงื่อนไข: จะเตือนพุ่งต่อเมื่อต้องเป็นราคาที่ "สูงกว่ายอดเดิม" เกิน 5 หน่วยขึ้นไปเท่านั้น
        elif (price - last_up) >= 5:
            send_line(f"📈 {symbol} ทำยอดสูงสุดใหม่!\nราคา: {price}\n(พุ่งทะลุยอดเดิม +{round(price - last_up, 2)})")
            state[key_up] = price  # เซฟยอดสูงสุดใหม่ (New High)
        # จะเตือนย่อตัวครั้งแรกเมื่อ "ราคายังเท่ากับยอดสูงสุดเดิม" แต่ร่วงลงมาเกิน 5 หน่วย
        elif (last_up - price) >= 5:
            # ตรวจสอบเพิ่มไม่ให้แจ้งเตือนย่อตัวซ้ำซากที่ราคาเดิม
            key_warned_drop = f"{symbol}_warned_drop"
            if state.get(key_warned_drop) != last_up: 
                send_line(f"📉 {symbol} ย่อตัวลงจากยอดสูงสุด!\nราคา: {price}\n(ลดลงจากจุดสูงสุด -{round(last_up - price, 2)})")
                state[key_warned_drop] = last_up  # ล็อกไว้ว่ายอดนี้เตือนย่อตัวไปแล้ว ห้ามเตือนซ้ำอีกจนกว่าจะมี New High
            
    elif target_up and price < target_up - 5:
        if key_up in state: del state[key_up]
        if f"{symbol}_warned_drop" in state: del state[f"{symbol}_warned_drop"]


    # ==========================================
    # 🔻 โซนขาลง (เน้นแจ้ง New Low เท่านั้น)
    # ==========================================
    if target_down and price <= target_down:
        last_down = state.get(key_down)
        
        if last_down is None:
            send_line(f"🔻 {symbol} หลุดเป้าขาลง!\nราคา: {price}\nเป้า: {target_down}")
            state[key_down] = price
        # ล็อกเงื่อนไข: จะเตือนดิ่งต่อเมื่อต้องเป็นราคาที่ "ต่ำกว่าก้นเหวเดิม" ลงไปอีก 5 หน่วยเท่านั้น
        elif (last_down - price) >= 5:
            send_line(f"📉 {symbol} ทุบสถิติดิ่งลงเหวใหม่!\nราคา: {price}\n(ทะลุก้นเหวเดิม -{round(last_down - price, 2)})")
            state[key_down] = price  # เซฟจุดต่ำสุดใหม่ (New Low)
        # จะเตือนเด้งกลับครั้งแรกเมื่อ "ราคายังเท่ากับก้นเหวเดิม" แต่ดีดกลับขึ้นมาเกิน 5 หน่วย
        elif (price - last_down) >= 5:
            key_warned_bounce = f"{symbol}_warned_bounce"
            if state.get(key_warned_bounce) != last_down:
                send_line(f"🧗 {symbol} เริ่มเด้งกลับจากก้นเหว!\nราคา: {price}\n(ดีดขึ้นมาจากจุดต่ำสุด +{round(price - last_down, 2)})")
                state[key_warned_bounce] = last_down  # ล็อกไว้ว่าก้นเหวนี้เตือนเด้งไปแล้ว ห้ามเตือนซ้ำอีกจนกว่าจะมี New Low
            
    elif target_down and price > target_down + 5:
        if key_down in state: del state[key_down]
        if f"{symbol}_warned_bounce" in state: del state[f"{symbol}_warned_bounce"]

# -----------------------
# MAIN LOOP (รันต่อเนื่องยาวๆ บน GitHub Actions)
# -----------------------
def main():
    if not market_open():
        print(f"[{datetime.now(TZ)}] Market is closed. Skipping...")
        return

    print(f"[{datetime.now(TZ)}] Checking stocks...")
    state = load_state()
    
    for symbol, rule in STOCKS.items():
        check_stock(symbol, rule, state)
        time.sleep(1)

    save_state(state)
    print("Done.")

if __name__ == "__main__":
    main()
