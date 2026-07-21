import requests
import pandas as pd
import ta

from config import TWELVE_API


# ==========================
# جلب السعر الحالي
# ==========================
def get_price(pair):
    try:
        pair = pair.replace(" (ذهب)", "")
        pair = pair.replace(" (Gold)", "")

        url = (
            f"https://api.twelvedata.com/price"
            f"?symbol={pair}"
            f"&apikey={TWELVE_API}"
        )

        response = requests.get(url, timeout=10)
        data = response.json()

        if "price" in data:
            return float(data["price"])

        return None

    except Exception as e:
        print("PRICE ERROR:", e)
        return None


# ==========================
# جلب الشموع
# ==========================
def get_candles(pair):

    try:

        pair = pair.replace(" (ذهب)", "")
        pair = pair.replace(" (Gold)", "")

        url = (
            f"https://api.twelvedata.com/time_series"
            f"?symbol={pair}"
            f"&interval=1min"
            f"&outputsize=200"
            f"&apikey={TWELVE_API}"
        )

        response = requests.get(url, timeout=10)
        data = response.json()

        if "values" not in data:
            return None

        df = pd.DataFrame(data["values"])

        df = df.iloc[::-1].reset_index(drop=True)

        for col in ["open", "high", "low", "close"]:
            df[col] = df[col].astype(float)

        return df

    except Exception as e:
        print("CANDLES ERROR:", e)
        return None


# ==========================
# تحليل السوق
# ==========================
def analyze_market(pair):

    df = get_candles(pair)

    if df is None or len(df) < 50:
        return None
    score_buy = 0
    score_sell = 0
    reasons = []

    # ==========================
    # EMA 9 / EMA 21
    # ==========================
    df["ema9"] = ta.trend.EMAIndicator(
        close=df["close"],
        window=9
    ).ema_indicator()

    df["ema21"] = ta.trend.EMAIndicator(
        close=df["close"],
        window=21
    ).ema_indicator()

    # ==========================
    # RSI
    # ==========================
    df["rsi"] = ta.momentum.RSIIndicator(
        close=df["close"],
        window=14
    ).rsi()

    # ==========================
    # MACD
    # ==========================
    macd = ta.trend.MACD(df["close"])

    df["macd"] = macd.macd()
    df["macd_signal"] = macd.macd_signal()

    # ==========================
    # ADX
    # ==========================
    adx = ta.trend.ADXIndicator(
        high=df["high"],
        low=df["low"],
        close=df["close"],
        window=14
    )

    df["adx"] = adx.adx()

    # ==========================
    # Bollinger Bands
    # ==========================
    bb = ta.volatility.BollingerBands(
        close=df["close"],
        window=20,
        window_dev=2
    )

    df["bb_high"] = bb.bollinger_hband()
    df["bb_low"] = bb.bollinger_lband()

    last = df.iloc[-1]

    # ==========================
    # EMA
    # ==========================
    if last["ema9"] > last["ema21"]:
        score_buy += 20
        reasons.append("EMA صاعد ✅")
    else:
        score_sell += 20
        reasons.append("EMA هابط ✅")

    # ==========================
    # RSI
    # ==========================
    if last["rsi"] > 55:
        score_buy += 20
        reasons.append(f"RSI = {last['rsi']:.1f}")

    elif last["rsi"] < 45:
        score_sell += 20
        reasons.append(f"RSI = {last['rsi']:.1f}")

    # ==========================
    # MACD
    # ==========================
    if last["macd"] > last["macd_signal"]:
        score_buy += 20
        reasons.append("MACD صاعد ✅")
    else:
        score_sell += 20
        reasons.append("MACD هابط ✅")

    # ==========================
    # ADX
    # ==========================
    if last["adx"] >= 25:
        score_buy += 20
        score_sell += 20
        reasons.append(f"ADX = {last['adx']:.1f}")

    # ==========================
    # Bollinger
    # ==========================
    if last["close"] <= last["bb_low"]:
        score_buy += 20
        reasons.append("ارتداد من الحد السفلي")

    elif last["close"] >= last["bb_high"]:
        score_sell += 20
        reasons.append("ارتداد من الحد العلوي")
 
    # ==========================
    # تحديد الإشارة
    # ==========================
    if score_buy > score_sell:
        signal = "CALL"
        strength = score_buy
    elif score_sell > score_buy:
        signal = "PUT"
        strength = score_sell
    else:
        signal = "WAIT"
        strength = 50

    # لا نعطي إشارة ضعيفة
    if strength < 60:
        signal = "WAIT"

    # مدة الصفقة
    if strength >= 90:
        duration = 30
    elif strength >= 75:
        duration = 45
    else:
        duration = 60

    return {
        "signal": signal,
        "strength": strength,
        "duration": duration,
        "price": float(last["close"]),
        "ema9": round(last["ema9"], 5),
        "ema21": round(last["ema21"], 5),
        "rsi": round(last["rsi"], 2),
        "macd": round(last["macd"], 5),
        "macd_signal": round(last["macd_signal"], 5),
        "adx": round(last["adx"], 2),
        "reasons": reasons
    }
