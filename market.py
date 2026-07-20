import requests
import pandas as pd
import pandas_ta as ta
import logging
from datetime import datetime
from config import TWELVE_API

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_price(pair):
    try:
        pair = pair.replace(" (ذهب)", "")
        url = f"https://api.twelvedata.com/price?symbol={pair}&apikey={TWELVE_API}"
        response = requests.get(url, timeout=10)
        data = response.json()
        if "price" in data:
            return round(float(data["price"]), 5)
        else:
            logging.error(f"Price not found for {pair}: {data}")
            return None
    except Exception as e:
        logging.error(f"Error in get_price: {e}")
        return None

def get_market_data(pair):
    try:
        pair = pair.replace(" (ذهب)", "")
        url = f"https://api.twelvedata.com/time_series?symbol={pair}&interval=1min&outputsize=250&apikey={TWELVE_API}"
        response = requests.get(url, timeout=10)
        data = response.json()
        if "values" not in data:
            logging.error(f"Invalid response: {data}")
            return None
        df = pd.DataFrame(data["values"])
        df = df.astype({"open": float, "high": float, "low": float, "close": float})
        df = df.iloc[::-1].reset_index(drop=True)
        df["EMA20"] = ta.ema(df["close"], length=20)
        df["EMA50"] = ta.ema(df["close"], length=50)
        df["EMA200"] = ta.ema(df["close"], length=200)
        df["RSI"] = ta.rsi(df["close"], length=14)
        macd = ta.macd(df["close"])
        df = pd.concat([df, macd], axis=1)
        adx = ta.adx(df["high"], df["low"], df["close"])
        df = pd.concat([df, adx], axis=1)
        df["ATR"] = ta.atr(df["high"], df["low"], df["close"], length=14)
        bb = ta.bbands(df["close"], length=20)
        df = pd.concat([df, bb], axis=1)
        return df
    except Exception as e:
        logging.error(f"Error in get_market_data: {e}")
        return None

def analyze_market(pair):
    df = get_market_data(pair)
    if df is None:
        return None
    last = df.iloc[-1]
    buy = 0
    sell = 0
    indicators = []
    if last["EMA20"] > last["EMA50"] > last["EMA200"]:
        buy += 20
        indicators.append("✅ EMA")
    elif last["EMA20"] < last["EMA50"] < last["EMA200"]:
        sell += 20
        indicators.append("✅ EMA")
    if last["MACD_12_26_9"] > last["MACDs_12_26_9"]:
        buy += 20
        indicators.append("✅ MACD")
    else:
        sell += 20
        indicators.append("✅ MACD")
    if 45 <= last["RSI"] <= 65:
        buy += 10
        indicators.append("✅ RSI")
    elif last["RSI"] > 70:
        sell += 10
        indicators.append("✅ RSI")
    elif last["RSI"] < 30:
        buy += 10
        indicators.append("✅ RSI")
    if last["ADX_14"] > 25:
        buy += 15
        sell += 15
        indicators.append("✅ ADX")
    if last["close"] > last["BBM_20_2.0"]:
        buy += 10
        indicators.append("✅ Bollinger")
    else:
        sell += 10
        indicators.append("✅ Bollinger")
    if last["ATR"] > 0:
        buy += 5
        sell += 5
        indicators.append("✅ ATR")
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
