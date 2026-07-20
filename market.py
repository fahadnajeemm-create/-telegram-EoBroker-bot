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
            return None, "تعذر جلب البيانات", 30

        df = pd.DataFrame(data["values"])

        df["close"] = df["close"].astype(float)
        df = df.iloc[::-1].reset_index(drop=True)

        # المؤشرات
        df["EMA9"] = ta.ema(df["close"], length=9)
        df["EMA21"] = ta.ema(df["close"], length=21)
        df["RSI"] = ta.rsi(df["close"], length=14)

        last = df.iloc[-1]

        # السعر الحالي
        price = round(last["close"], 5)

        # تحديد الإشارة
        if (
            last["EMA9"] > last["EMA21"]
            and last["RSI"] > 55
        ):
            signal = "🟢 شراء (CALL)"
            duration = 30

        elif (
            last["EMA9"] < last["EMA21"]
            and last["RSI"] < 45
        ):
            signal = "🔴 بيع (PUT)"
            duration = 30

        else:
            # إجبار البوت على إعطاء إشارة
            if last["EMA9"] >= last["EMA21"]:
                signal = "🟢 شراء (CALL)"
            else:
                signal = "🔴 بيع (PUT)"

            duration = 45

        return price, signal, duration

    except Exception as e:
        return None, f"خطأ: {e}", 30
