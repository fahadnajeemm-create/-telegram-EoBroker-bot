import requests
import pandas as pd
import pandas_ta as ta
from config import TWELVE_API
def get_price(pair):
try:
url = (
f"https://api.twelvedata.com/time_series"
f"?symbol={pair}"
f"&interval=1min"
f"&outputsize=100"
f"&apikey={TWELVE_API}"  )
response = requests.get(url, timeout=10)
data = response.json()
if "values" not in data:
print(data)
 return None
df = pd.DataFrame(data["values"])
df["close"] = df["close"].astype(float)
        df = df.iloc[::-1].reset_index(drop=True)
# المؤشرات
    df["EMA9"] = ta.ema(df["close"], length=9)
    df["EMA21"] = ta.ema(df["close"], length=21)
df["RSI"] = ta.rsi(df["close"], length=14)
macd = ta.macd(df["close"])
 df["MACD"] = macd["MACD_12_26_9"]
        df["SIGNAL"] = macd["MACDs_12_26_9"]
  last = df.iloc[-1]
signal = "⏳ انتظار"
duration = 30
buy = 0
 sell = 0
if last["EMA9"] > last["EMA21"]:
            buy += 1
        else:
            sell += 1
if last["RSI"] > 55:
            buy += 1
        elif last["RSI"] < 45:
            sell += 1
if last["MACD"] > last["SIGNAL"]:
            buy += 1
        else:
            sell += 1
if buy >= 2:
            signal = "🟢 شراء"
            duration = 45 if buy == 3 else 30
elif sell >= 2:
            signal = "🔴 بيع"
            duration = 45 if sell == 3 else 30
 return {
            "price": round(last["close"], 5),
            "signal": signal,
            "duration": duration,}
except Exception as e:
        print("Market Error:", e)
        return None
