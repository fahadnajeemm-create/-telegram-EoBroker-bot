import requests
import pandas as pd
import pandas_ta as ta
import logging
from datetime import datetime
from config import TWELVE_API
logging.basicConfig(level=logging.INFO,format='%(asctime)s - %(levelname)s - %(message)s')
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
    except requests.exceptions.Timeout:
        logging.error(f"Timeout fetching price for {pair}")
        return None
    except requests.exceptions.RequestException as e:
        logging.error(f"Request error: {e}")
        return None
    except Exception as e:
        logging.error(f"Unexpected error in get_price: {e}")
        return None
def get_market_data(pair):
    try:
        pair = pair.replace(" (ذهب)", "")
        url = f"https://api.twelvedata.com/time_series?symbol={pair}&interval=1min&outputsize=250&apikey={TWELVE_API}"
        response = requests.get(url, timeout=10)
        data = response.json()
        if "values" not in data:
            logging.error(f"Invalid response for {pair}: {data}")
            return None
        df = pd.DataFrame(data["values"])
        df = df.astype({"open": float,"high": float,"low": float,"close": float})
        df = df.iloc[::-1].reset_index(drop=True)
        df["EMA20"] = ta.ema(df["close"], length=20)
        df["EMA50"] = ta.ema(df["close"], length=50)
        df["EMA200"] = ta.ema(df["close"], length=200)
        df["RSI"] = ta.rsi(df["close"], length=14)
        macd = ta.macd(df["close"], fast=12, slow=26, signal=9)
        df = pd.concat([df, macd], axis=1)
        adx = ta.adx(df["high"], df["low"], df["close"], length=14)
        df = pd.concat([df, adx], axis=1)
        df["ATR"] = ta.atr(df["high"], df["low"], df["close"], length=14)
        bb = ta.bbands(df["close"], length=20, std=2)
        df = pd.concat([df, bb], axis=1)
        if not validate_data(df):
            return None
        return df
    except requests.exceptions.Timeout:
        logging.error(f"Timeout fetching data for {pair}")
        return None
    except requests.exceptions.RequestException as e:
        logging.error(f"Request error for {pair}: {e}")
        return None
    except Exception as e:
        logging.error(f"Unexpected error in get_market_data: {e}")
        return None
def validate_data(df):
    required_columns = ["open", "high", "low", "close"]
    if not all(col in df.columns for col in required_columns):
        logging.error("Missing required columns")
        return False
    if df[required_columns].isna().any().any():
        logging.error("Data contains NaN values")
        return False
    if len(df) < 200:
        logging.error(f"Insufficient data: {len(df)} rows")
        return False
    return True
def bullish_engulfing(df):
    if len(df) < 2:
        return False
    prev = df.iloc[-2]
    last = df.iloc[-1]
    return (prev["close"] < prev["open"] and last["close"] > last["open"] and last["close"] > prev["open"] and last["open"] < prev["close"])
def bearish_engulfing(df):
    if len(df) < 2:
        return False
    prev = df.iloc[-2]
    last = df.iloc[-1]
    return (prev["close"] > prev["open"] and last["close"] < last["open"] and last["open"] > prev["close"] and last["close"] < prev["open"])
def detect_doji(df):
    if len(df) < 1:
        return False
    last = df.iloc[-1]
    body = abs(last["close"] - last["open"])
    range_ = last["high"] - last["low"]
    return body <= (range_ * 0.1)
def detect_hammer(df):
    if len(df) < 1:
        return False
    last = df.iloc[-1]
    body = abs(last["close"] - last["open"])
    lower_shadow = min(last["close"], last["open"]) - last["low"]
    upper_shadow = last["high"] - max(last["close"], last["open"])
    return (lower_shadow > (body * 2) and upper_shadow < (body * 0.3) and last["close"] > last["open"])
def analyze_market(pair):
    df = get_market_data(pair)
    if df is None:
        return None
    last = df.iloc[-1]
    buy_score = 0
    sell_score = 0
    indicators = []
    analysis_details = []
    if last["EMA20"] > last["EMA50"] > last["EMA200"]:
        buy_score += 20
        indicators.append("✅ EMA")
        analysis_details.append("EMA: ترتيب صاعد (20 > 50 > 200)")
    elif last["EMA20"] < last["EMA50"] < last["EMA200"]:
        sell_score += 20
        indicators.append("✅ EMA")
        analysis_details.append("EMA: ترتيب هابط (20 < 50 < 200)")
    else:
        analysis_details.append("EMA: تقاطع أو تذبذب")
    if last["MACD_12_26_9"] > last["MACDs_12_26_9"]:
        buy_score += 20
        indicators.append("✅ MACD")
        analysis_details.append("MACD: إيجابي (خط MACD فوق خط الإشارة)")
    else:
        sell_score += 20
        indicators.append("✅ MACD")
        analysis_details.append("MACD: سلبي (خط MACD تحت خط الإشارة)")
    if 45 <= last["RSI"] <= 65:
        buy_score += 10
        indicators.append("✅ RSI")
        analysis_details.append(f"RSI: محايد ({last['RSI']:.2f})")
    elif last["RSI"] > 70:
        sell_score += 15
        indicators.append("✅ RSI")
        analysis_details.append(f"RSI: تشبع شرائي ({last['RSI']:.2f})")
    elif last["RSI"] < 30:
        buy_score += 15
        indicators.append("✅ RSI")
        analysis_details.append(f"RSI: تشبع بيعي ({last['RSI']:.2f})")
    else:
        analysis_details.append(f"RSI: متوسط ({last['RSI']:.2f})")
    if last["ADX_14"] > 25:
        buy_score += 10
        sell_score += 10
        indicators.append("✅ ADX")
        analysis_details.append(f"ADX: اتجاه قوي ({last['ADX_14']:.2f})")
    else:
        analysis_details.append(f"ADX: اتجاه ضعيف ({last['ADX_14']:.2f})")
    if last["close"] > last["BBU_20_2.0"]:
        sell_score += 10
        indicators.append("✅ Bollinger")
        analysis_details.append("Bollinger: فوق النطاق العلوي (تشبع شرائي)")
    elif last["close"] < last["BBL_20_2.0"]:
        buy_score += 10
        indicators.append("✅ Bollinger")
        analysis_details.append("Bollinger: تحت النطاق السفلي (تشبع بيعي)")
    elif last["close"] > last["BBM_20_2.0"]:
        buy_score += 5
        indicators.append("✅ Bollinger")
        analysis_details.append("Bollinger: في النصف العلوي")
    else:
        sell_score += 5
        indicators.append("✅ Bollinger")
        analysis_details.append("Bollinger: في النصف السفلي")
    if last["ATR"] > 0:
        buy_score += 5
        sell_score += 5
        indicators.append("✅ ATR")
        analysis_details.append(f"ATR: تقلب {last['ATR']:.5f}")
    if bullish_engulfing(df):
        buy_score += 20
        indicators.append("✅ Bullish Engulfing")
        analysis_details.append("نمط: ابتلاع صاعد")
    elif bearish_engulfing(df):
        sell_score += 20
        indicators.append("✅ Bearish Engulfing")
        analysis_details.append("نمط: ابتلاع هابط")
    elif detect_hammer(df):
        buy_score += 15
        indicators.append("✅ Hammer")
        analysis_details.append("نمط: مطرقة")
    elif detect_doji(df):
        analysis_details.append("نمط: دوجي (ترقب)")
    confidence = max(buy_score, sell_score)
    confidence = min(confidence, 100)
    if buy_score > sell_score:
        signal = "📈 شراء 🟢"
        trend = "صاعد ⬆️"
        signal_type = "BUY"
    elif sell_score > buy_score:
        signal = "📉 بيع 🔴"
        trend = "هابط ⬇️"
        signal_type = "SELL"
    else:
        signal = "⏸️ انتظار 🟡"
        trend = "محايد ➡️"
        signal_type = "HOLD"
    if confidence >= 90:
        duration = "30 ثانية"
        risk = "منخفض"
    elif confidence >= 70:
        duration = "45 ثانية"
        risk = "متوسط"
    elif confidence >= 50:
        duration = "60 ثانية"
        risk = "مرتفع"
    else:
        duration = "90 ثانية"
        risk = "عالي جداً"
    return {
        "signal": signal,
        "signal_type": signal_type,
        "confidence": confidence,
        "buy_score": buy_score,
        "sell_score": sell_score,
        "trend": trend,
        "duration": duration,
        "risk": risk,
        "indicators": indicators,
        "analysis_details": analysis_details,
        "current_price": last["close"],
        "rsi": last["RSI"],
        "adx": last["ADX_14"],
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
def get_signal(pair):
    result = analyze_market(pair)
    return result["signal"] if result else "❌ خطأ في التحليل"
def get_signal_type(pair):
    result = analyze_market(pair)
    return result["signal_type"] if result else "HOLD"
def get_signal_strength(pair):
    result = analyze_market(pair)
    return f'{result["confidence"]}%' if result else "0%"
def get_trade_time(pair):
    result = analyze_market(pair)
    return result["duration"] if result else "60 ثانية"
def get_trend(pair):
    result = analyze_market(pair)
    return result["trend"] if result else "-"
def get_indicators(pair):
    result = analyze_market(pair)
    return "\n".join(result["indicators"]) if result else "-"
def get_full_analysis(pair):
    result = analyze_market(pair)
    if not result:
        return "❌ فشل في جلب البيانات"
    output = f"""
===============================
📊 تحليل السوق: {pair}
===============================
🕐 الوقت: {result['timestamp']}
💰 السعر الحالي: {result['current_price']:.5f}
📈 الإشارة: {result['signal']}
📊 الثقة: {result['confidence']}%
🎯 الاتجاه: {result['trend']}
⏱️ المدة المقترحة: {result['duration']}
⚠️ المخاطرة: {result['risk']}
📋 المؤشرات المستخدمة:
{chr(10).join(result['indicators'])}
📝 تفاصيل التحليل:
{chr(10).join(result['analysis_details'])}
📊 درجات التحليل:
شراء: {result['buy_score']}%
بيع: {result['sell_score']}%
===============================
"""
    return output
if __name__ == "__main__":
    pair = "BTC/USD"
    print(f"\n🔍 جاري تحليل {pair}...\n")
    analysis = get_full_analysis(pair)
    print(analysis)
    signal = get_signal(pair)
    print(f"الإشارة المبسطة: {signal}")
    strength = get_signal_strength(pair)
    print(f"قوة الإشارة: {strength}")
    duration = get_trade_time(pair)
    print(f"المدة المقترحة: {duration}")
