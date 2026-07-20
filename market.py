import requests
import pandas as pd
import pandas_ta as ta
from config import TWELVE_API


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

        df = df.sort_index()

        # المؤشرات
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

    rsi = last["RSI"]
    ema20 = last["EMA20"]
    ema50 = last["EMA50"]
    macd = last["MACD_12_26_9"]
    signal = last["MACDs_12_26_9"]

    if (
        ema20 > ema50
        and macd > signal
        and rsi < 70
    ):
        return "📈 شراء 🟢"

    elif (
        ema20 < ema50
        and macd < signal
        and rsi > 30
    ):
        return "📉 بيع 🔴"

    else:
        return "⏳ انتظار تأكيد"
