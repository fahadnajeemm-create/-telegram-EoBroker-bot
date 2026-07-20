import requests
import pandas as pd
import pandas_ta as ta
from config import TWELVE_API


def get_price(pair):
    try:
        pair = pair.replace(" (ذهب)", "")

        url = (
            f"https://api.twelvedata.com/price"
            f"?symbol={pair}"
            f"&apikey={TWELVE_API}"
        )

        response = requests.get(url, timeout=10)
        data = response.json()

        if "price" in data:
            return round(float(data["price"]), 5)

        return None

    except Exception as e:
        print(e)
        return None


def get_market_data(pair):
    try:
        pair = pair.replace(" (ذهب)", "")

        url = (
            f"https://api.twelvedata.com/time_series"
            f"?symbol={pair}"
            f"&interval=1min"
            f"&outputsize=100"
            f"&apikey={TWELVE_API}"
        )

        response = requests.get(url, timeout=10)
        data = response.json()

        if "values" not in data:
            print(data)
            return None

        df = pd.DataFrame(data["values"])

        df = df.astype({
            "open": float,
            "high": float,
            "low": float,
            "close": float
        })

        df = df.iloc[::-1].reset_index(drop=True)

        df["EMA20"] = ta.ema(df["close"], length=20)
        df["EMA50"] = ta.ema(df["close"], length=50)
        df["RSI"] = ta.rsi(df["close"], length=14)

        macd = ta.macd(df["close"])
        df = pd.concat([df, macd], axis=1)

        return df

    except Exception as e:
        print(e)
        return None
def get_signal(pair):
    df = get_market_data(pair)

    if df is None:
        return "⏳ جمع البيانات..."

    last = df.iloc[-1]

    buy_score = 0
    sell_score = 0

    # EMA
    if last["EMA20"] > last["EMA50"]:
        buy_score += 1
    else:
        sell_score += 1

    # MACD
    if last["MACD_12_26_9"] > last["MACDs_12_26_9"]:
        buy_score += 1
    else:
        sell_score += 1

    # RSI
    if last["RSI"] < 30:
        buy_score += 1
    elif last["RSI"] > 70:
        sell_score += 1

    # الشمعة الحالية
    if last["close"] > last["open"]:
        buy_score += 1
    elif last["close"] < last["open"]:
        sell_score += 1

    if buy_score >= sell_score:
        return "📈 شراء 🟢"
    else:
        return "📉 بيع 🔴"
def get_signal_strength(pair):
    df = get_market_data(pair)

    if df is None:
        return "0%"

    last = df.iloc[-1]

    score = 0

    if last["EMA20"] > last["EMA50"] or last["EMA20"] < last["EMA50"]:
        score += 25

    if last["MACD_12_26_9"] > last["MACDs_12_26_9"] or last["MACD_12_26_9"] < last["MACDs_12_26_9"]:
        score += 25

    if last["close"] > last["open"] or last["close"] < last["open"]:
        score += 25

    if last["RSI"] < 30 or last["RSI"] > 70:
        score += 25

    return f"{score}%"

