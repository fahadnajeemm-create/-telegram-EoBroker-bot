import requests
import pandas as pd
import pandas_ta as ta
from config import TWELVE_API

def get_price(pair):
    try:
        pair = pair.replace(" (ذهب)", "")
        url = f"https://api.twelvedata.com/price?symbol={pair}&apikey={TWELVE_API}"
        data = requests.get(url, timeout=10).json()
        return round(float(data["price"]), 5) if "price" in data else None
    except:
        return None

def get_market_data(pair):
    try:
        pair = pair.replace(" (ذهب)", "")
        url = f"https://api.twelvedata.com/time_series?symbol={pair}&interval=1min&outputsize=100&apikey={TWELVE_API}"
        data = requests.get(url, timeout=10).json()
        if "values" not in data:
            return None
        df = pd.DataFrame(data["values"]).astype({"open": float, "high": float, "low": float, "close": float})
        df = df.iloc[::-1].reset_index(drop=True)
        df["EMA20"] = ta.ema(df["close"], length=20)
        df["EMA50"] = ta.ema(df["close"], length=50)
        df["RSI"] = ta.rsi(df["close"], length=14)
        return df
    except:
        return None

def analyze_market(pair):
    df = get_market_data(pair)
    if df is None:
        return None
    last = df.iloc[-1]
    buy = 0
    sell = 0
    if last["EMA20"] > last["EMA50"]:
        buy += 50
    else:
        sell += 50
    if 45 <= last["RSI"] <= 65:
        buy += 30
    elif last["RSI"] > 70:
        sell += 30
    elif last["RSI"] < 30:
        buy += 30
    if buy >= sell:
        return {"signal": "📈 شراء", "confidence": min(buy, 100), "trend": "صاعد"}
    else:
        return {"signal": "📉 بيع", "confidence": min(sell, 100), "trend": "هابط"}

def test():
    print("="*40)
    print("اختبار تحليل السوق")
    print("="*40)
    pairs = ["BTC/USD", "EUR/USD", "XAU/USD (ذهب)"]
    for pair in pairs:
        print(f"\n🔍 تحليل: {pair}")
        result = analyze_market(pair)
        if result:
            print(f"الإشارة: {result['signal']}")
            print(f"الثقة: {result['confidence']}%")
            print(f"الاتجاه: {result['trend']}")
        else:
            print("❌ فشل في جلب البيانات")
        print("-"*40)

if __name__ == "__main__":
    test()
