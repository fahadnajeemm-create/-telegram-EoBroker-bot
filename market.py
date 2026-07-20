import requests
import pandas as pd
import pandas_ta as ta
from config import TWELVE_API


def get_price(pair):
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
            return None, "خطأ في جلب البيانات"

        df = pd.DataFrame(data["values"])

        # تحويل الأعمدة إلى أرقام
        for col in ["open", "high", "low", "close"]:
            df[col] = pd.to_numeric(df[col])

        # ترتيب البيانات من الأقدم إلى الأحدث
        df = df.iloc[::-1].reset_index(drop=True)

        # المؤشرات الفنية
        df["EMA9"] = ta.ema(df["close"], length=9)
        df["EMA21"] = ta.ema(df["close"], length=21)
        df["RSI"] = ta.rsi(df["close"], length=14)

        macd = ta.macd(df["close"])
        df["MACD"] = macd["MACD_12_26_9"]
        df["MACDs"] = macd["MACDs_12_26_9"]

        last = df.iloc[-1]

        signal = "⏳ جمع البيانات..."

        # شراء
        if (
            last["EMA9"] > last["EMA21"]
            and last["RSI"] > 55
            and last["MACD"] > last["MACDs"]
        ):
            signal = "🟢 شراء"
            duration = "30 ثانية"

        # بيع
        elif (
            last["EMA9"] < last["EMA21"]
            and last["RSI"] < 45
            and last["MACD"] < last["MACDs"]
        ):
            signal = "🔴 بيع"
            duration = "45 ثانية"

        else:
            duration = "30 ثانية"

        return float(last["close"]), signal, duration

    except Exception as e:
        print("Market Error:", e)
        return None, "خطأ", "30 ثانية"
