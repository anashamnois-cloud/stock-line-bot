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
    weekday = now.weekday() # 0=Mon, 4=Fri
    minutes = now.hour * 60 + now.minute

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
    # 🚀 โซนขาขึ้น (UP & TRAILING DOWN FROM PEAK)
    # ==========================================
    if target_up and price >= target_up:
        last_up = state.get(key_up)
        
        # แจ้งครั้งแรกที่ทะลุเป้า / ขึ้นต่ออีก 5 / ย่อตัวลงจากยอดสูงสุด 5
        if last_up is None:
            send_line(f"🚀 {symbol} ทะลุเป้าขาขึ้น!\nราคา: {price}\nเป้า: {target_up}")
            state[key_up] = price
        elif (price - last_up) >= 5:
            send_line(f"📈 {symbol} พุ่งต่อไม่หยุด!\nราคา: {price}\n(ขึ้นมาจากจุดเดิม +{round(price - last_up, 2)})")
            state[key_up] = price
        elif (last_up - price) >= 5:
            send_line(f"📉 {symbol} ย่อตัวลงจากยอดสูงสุด!\nราคา: {price}\n(ลดลงจากจุดสูงสุด -{round(last_up - price, 2)})")
            state[key_up] = price # อัปเดตฐานใหม่เป็นจุดที่ย่อลงมา
            
    elif target_up and price < target_up - 5:
        # ถ้าราคามันร่วงกลับลงมาต่ำกว่าเป้าเกิน 5 หน่วย ค่อยรีเซ็ตสมอง
        if key_up in state: del state[key_up]

    # ==========================================
    # 🔻 โซนขาลง (DOWN & TRAILING UP FROM BOTTOM)
    # ==========================================
    if target_down and price <= target_down:
        last_down = state.get(key_down)
        
        # แจ้งครั้งแรกที่หลุดเป้าล่าง / ดิ่งลงต่ออีก 5 / ดีดเด้งจากก้นเหวกลับขึ้นมา 5
        if last_down is None:
            send_line(f"🔻 {symbol} หลุดเป้าขาลง!\nราคา: {price}\nเป้า: {target_down}")
            state[key_down] = price
        elif (last_down - price) >= 5:
            send_line(f"📉 {symbol} ดิ่งลงเหวต่อเนื่อง!\nราคา: {price}\n(ลดลงจากจุดเดิม -{round(last_down - price, 2)})")
            state[key_down] = price
        elif (price - last_down) >= 5:
            send_line(f"🧗 {symbol} เริ่มเด้งกลับจากก้นเหว!\nราคา: {price}\n(ดีดขึ้นมาจากจุดต่ำสุด +{round(price - last_down, 2)})")
            state[key_down] = price # อัปเดตฐานใหม่เป็นจุดที่เด้งขึ้นมา
            
    elif target_down and price > target_down + 5:
        # ถ้าราคาดีดกลับขึ้นไปสูงกว่าเป้าขาลงเกิน 5 หน่วย ค่อยรีเซ็ตสมอง
        if key_down in state: del state[key_down]

# -----------------------
# MAIN LOOP (รันต่อเนื่องยาวๆ บน GitHub Actions)
# -----------------------
def main():
    print(f"[{datetime.now(TZ)}] Bot started and waiting for market...")
    state = load_state()
    has_run_in_market = False 

    while True:
        now = datetime.now(TZ)
        
        if market_open():
            print(f"[{now.strftime('%H:%M:%S')}] Checking stock prices...")
            for symbol, rule in STOCKS.items():
                check_stock(symbol, rule, state)
                time.sleep(1) 
            
            has_run_in_market = True
            time.sleep(60) # พัก 1 นาทีแล้วเช็กซ้ำแบบเรียลไทม์
            
        else:
            # ถ้าตลาดปิดแล้ว และก่อนหน้านี้บอทเคยรันช่วงตลาดเปิดมาแล้ว -> ให้จบโปรแกรมเพื่อบันทึกไฟล์
            if has_run_in_market:
                print(f"[{now}] Market has closed. Exiting loop to save state...")
                break 
                
            # ถ้าตื่นมาแล้วตลาดยังไม่เปิด (เช่น มารอก่อนเวลา) ให้รอ 1 นาทีแล้วเช็กเวลาตลาดใหม่
            print(f"[{now.strftime('%H:%M:%S')}] Market is closed. Waiting...")
            time.sleep(60)

    save_state(state)
    print("System finished.")

if __name__ == "__main__":
    main()
