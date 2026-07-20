import requests
import pandas as pd
import pandas_ta as ta
from config import TWELVE_API


# =========================
# جلب السعر الحالي
# =========================
def get_price(pair):
    try:
        pair = pair.replace(" (ذهب)", "")

        url = (
            f"https://api.twelvedata.com/price"
            f"?symbol={pair}"
            f"&apikey={TWELVE_API}"
        )

        data = requests.get(url, timeout=10).json()

        if "price" in data:
            return round(float(data["price"]), 5)

        return None

    except Exception as e:
        print(e)
        return None


# =========================
# جلب البيانات
# =========================
def get_market_data(pair):
    try:
        pair = pair.replace(" (ذهب)", "")

        url = (
            f"https://api.twelvedata.com/time_series"
            f"?symbol={pair}"
            f"&interval=1min"
            f"&outputsize=250"
            f"&apikey={TWELVE_API}"
        )

        data = requests.get(url, timeout=10).json()

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

        # EMA
        df["EMA20"] = ta.ema(df["close"], length=20)
        df["EMA50"] = ta.ema(df["close"], length=50)
        df["EMA200"] = ta.ema(df["close"], length=200)

        # RSI
        df["RSI"] = ta.rsi(df["close"], length=14)

        # MACD
        macd = ta.macd(df["close"])
        df = pd.concat([df, macd], axis=1)

        # ADX
        adx = ta.adx(df["high"], df["low"], df["close"])
        df = pd.concat([df, adx], axis=1)

        # ATR
        df["ATR"] = ta.atr(
            df["high"],
            df["low"],
            df["close"],
            length=14
        )

        # Bollinger
        bb = ta.bbands(df["close"], length=20)
        df = pd.concat([df, bb], axis=1)

        return df

    except Exception as e:
        print(e)
        return None


# =========================
# تحليل الشموع
# =========================
def bullish_engulfing(df):

    if len(df) < 2:
        return False

    prev = df.iloc[-2]
    last = df.iloc[-1]

    return (
        prev["close"] < prev["open"]
        and last["close"] > last["open"]
        and last["close"] > prev["open"]
        and last["open"] < prev["close"]
    )


def bearish_engulfing(df):

    if len(df) < 2:
        return False

    prev = df.iloc[-2]
    last = df.iloc[-1]

    return (
        prev["close"] > prev["open"]
        and last["close"] < last["open"]
        and last["open"] > prev["close"]
        and last["close"] < prev["open"]
    )


# =========================
# التحليل
# =========================
def analyze_market(pair):

    df = get_market_data(pair)

    if df is None:
        return None

    last = df.iloc[-1]

    buy = 0
    sell = 0
    indicators = []

    # EMA
    if last["EMA20"] > last["EMA50"] > last["EMA200"]:
        buy += 20
        indicators.append("✅ EMA")

    elif last["EMA20"] < last["EMA50"] < last["EMA200"]:
        sell += 20
        indicators.append("✅ EMA")

    # MACD
    if last["MACD_12_26_9"] > last["MACDs_12_26_9"]:
        buy += 20
        indicators.append("✅ MACD")
    else:
        sell += 20
        indicators.append("✅ MACD")

    # RSI
    if 45 <= last["RSI"] <= 65:
        buy += 10
        indicators.append("✅ RSI")

    elif last["RSI"] > 70:
        sell += 10
        indicators.append("✅ RSI")

    elif last["RSI"] < 30:
        buy += 10
        indicators.append("✅ RSI")

    # ADX
    if last["ADX_14"] > 25:
        buy += 15
        sell += 15
        indicators.append("✅ ADX")

    # Bollinger
    if last["close"] > last["BBM_20_2.0"]:
        buy += 10
        indicators.append("✅ Bollinger")

    else:
        sell += 10
        indicators.append("✅ Bollinger")

    # ATR
    if last["ATR"] > 0:
        buy += 5
        sell += 5
        indicators.append("✅ ATR")

    # Candlestick
    if bullish_engulfing(df):
        buy += 20
        indicators.append("✅ Bullish Engulfing")

    if bearish_engulfing(df):
        sell += 20
        indicators.append("✅ Bearish Engulfing")

    if buy >= sell:
        signal = "📈 شراء 🟢"
        confidence = buy
        trend = "صاعد قوي ⬆️"
    else:
        signal = "📉 بيع 🔴"
        confidence = sell
        trend = "هابط قوي ⬇️"

    duration = "30 ثانية" if confidence >= 90 else "45 ثانية"

    return {
        "signal": signal,
        "confidence": min(confidence, 100),
        "trend": trend,
        "duration": duration,
        "indicators": indicators
    }


# =========================
# دوال البوت
# =========================
def get_signal(pair):
    result = analyze_market(pair)
    return result["signal"] if result else "❌"


def get_signal_strength(pair):
    result = analyze_market(pair)
    return f'{result["confidence"]}%' if result else "0%"


def get_trade_time(pair):
    result = analyze_market(pair)
    return result["duration"] if result else "30 ثانية"


def get_trend(pair):
    result = analyze_market(pair)
    return result["trend"] if result else "-"


def get_indicators(pair):
    result = analyze_market(pair)
    return "\n".join(result["indicators"]) if result else "-"
