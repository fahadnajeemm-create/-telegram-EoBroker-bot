import requests
import pandas as pd
import ta
import os
import time
from datetime import datetime
from config import TWELVE_API
try:
    from config import TWELVE_API
except ImportError:
    TWELVE_API = os.environ.get('TWELVE_API', '')
def get_price(pair):
    try:
     pair = pair.replace(" (ذهب)", "").replace(" (Gold)", "").strip()
    api_key = TWELVE_API or os.environ.get('TWELVE_API')
 if not api_key:
print("خطأ: مفتاح API غير موجود")
return None
 url = (
            f"https://api.twelvedata.com/price"
            f"?symbol={pair}"
            f"&apikey={TWELVE_API}"
        )
        url = f"https://api.twelvedata.com/price?symbol={pair}&apikey={api_key}"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        if "price" in data:
            return float(data["price"])
        elif "status" in data and data["status"] == "error":
            print(f"خطأ في API: {data.get('message', 'خطأ غير معروف')}")
            return None
        return None
    except requests.exceptions.RequestException as e:
        print(f"خطأ في الاتصال: {e}")
        return None
    except ValueError as e:
        print(f"خطأ في تحويل البيانات: {e}")
        return None
    except Exception as e:
        print(f"خطأ غير متوقع في get_price: {e}")
        return None
def get_candles(pair):
    try:
        pair = pair.replace(" (ذهب)", "").replace(" (Gold)", "").strip()
        api_key = TWELVE_API or os.environ.get('TWELVE_API')
        if not api_key:
            print("خطأ: مفتاح API غير موجود")
            return None
        url = f"https://api.twelvedata.com/time_series?symbol={pair}&interval=1min&outputsize=200&apikey={api_key}"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        if "status" in data and data["status"] == "error":
            print(f"خطأ في API: {data.get('message', 'خطأ غير معروف')}")
            return None
        if "values" not in data or not data["values"]:
            print(f"لا توجد بيانات للزوج {pair}")
            return None
        df = pd.DataFrame(data["values"])
        for col in ["open", "high", "low", "close"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        df = df.dropna()
        if len(df) < 50:
            print(f"عدد الشموع غير كافٍ: {len(df)}")
            return None
        df = df.iloc[::-1].reset_index(drop=True)
        return df
    except requests.exceptions.RequestException as e:
        print(f"خطأ في الاتصال: {e}")
        return None
    except Exception as e:
        print(f"خطأ غير متوقع في get_candles: {e}")
        return None
def analyze_market(pair):
    try:
        df = get_candles(pair)
        if df is None or len(df) < 50:
            print(f"بيانات غير كافية لتحليل {pair}")
            return None
        score_buy = 0
        score_sell = 0
        reasons = []
        df["ema9"] = ta.trend.EMAIndicator(close=df["close"], window=9).ema_indicator()
        df["ema21"] = ta.trend.EMAIndicator(close=df["close"], window=21).ema_indicator()
        df["rsi"] = ta.momentum.RSIIndicator(close=df["close"], window=14).rsi()
        macd = ta.trend.MACD(df["close"])
        df["macd"] = macd.macd()
        df["macd_signal"] = macd.macd_signal()
        adx = ta.trend.ADXIndicator(high=df["high"], low=df["low"], close=df["close"], window=14)
        df["adx"] = adx.adx()
        bb = ta.volatility.BollingerBands(close=df["close"], window=20, window_dev=2)
        df["bb_high"] = bb.bollinger_hband()
        df["bb_low"] = bb.bollinger_lband()
        df = df.dropna()
        if len(df) == 0:
            print("جميع القيم NaN بعد الحسابات")
            return None
        last = df.iloc[-1]
        if last["ema9"] > last["ema21"]:
        score_buy += 20
        reasons.append(f"EMA صاعد ✅ (9: {last['ema9']:.5f} > 21: {last['ema21']:.5f})")
        else:
            score_sell += 20
            reasons.append(f"EMA هابط ✅ (9: {last['ema9']:.5f} < 21: {last['ema21']:.5f})")
        if last["rsi"] > 60:
            score_buy += 15
            reasons.append(f"RSI قوي = {last['rsi']:.1f}")
        elif last["rsi"] > 55:
            score_buy += 10
            reasons.append(f"RSI = {last['rsi']:.1f}")
        elif last["rsi"] < 40:
            score_sell += 15
            reasons.append(f"RSI ضعيف = {last['rsi']:.1f}")
        elif last["rsi"] < 45:
            score_sell += 10
            reasons.append(f"RSI = {last['rsi']:.1f}")
        if last["macd"] > last["macd_signal"]:
            score_buy += 20
            reasons.append(f"MACD صاعد ✅ ({last['macd']:.5f} > {last['macd_signal']:.5f})")
        else:
            score_sell += 20
            reasons.append(f"MACD هابط ✅ ({last['macd']:.5f} < {last['macd_signal']:.5f})")
        if last["adx"] >= 25:
            if score_buy > score_sell:
                score_buy += 10
            elif score_sell > score_buy:
                score_sell += 10
            reasons.append(f"ADX قوي = {last['adx']:.1f}")
        else:
            reasons.append(f"ADX ضعيف = {last['adx']:.1f}")
        if last["close"] <= last["bb_low"]:
            score_buy += 20
            reasons.append(f"ارتداد من الحد السفلي (السعر: {last['close']:.5f} ≤ {last['bb_low']:.5f})")
        elif last["close"] >= last["bb_high"]:
            score_sell += 20
            reasons.append(f"ارتداد من الحد العلوي (السعر: {last['close']:.5f} ≥ {last['bb_high']:.5f})")
        if score_buy > score_sell:
            signal = "CALL"
            strength = score_buy
        elif score_sell > score_buy:
            signal = "PUT"
            strength = score_sell
        else:
            signal = "WAIT"
            strength = 50
        if strength < 60:
            signal = "WAIT"
            strength = 50
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
            "reasons": reasons,
            "timestamp": datetime.now().isoformat(),
            "pair": pair
        }
    except Exception as e:
        print(f"خطأ في تحليل {pair}: {e}")
        print(e)
        return None
def test_analysis():
    pairs = ["XAU/USD", "BTC/USD", "EUR/USD"]
    for pair in pairs:
        print(f"\n{'='*50}")
        print(f"تحليل الزوج: {pair}")
        print(f"{'='*50}")
        result = analyze_market(pair)
        if result:
            print(f"الإشارة: {result['signal']}")
            print(f"القوة: {result['strength']}%")
            print(f"المدة: {result['duration']} دقيقة")
            print(f"السعر: {result['price']}")
            print(f"RSI: {result['rsi']}")
            print(f"ADX: {result['adx']}")
            print("الأسباب:")
            for reason in result['reasons']:
                print(f"  - {reason}")
        else:
            print("فشل في الحصول على التحليل")
        time.sleep(1)
if __name__ == "__main__":
    if not TWELVE_API and not os.environ.get('TWELVE_API'):
        print("تحذير: لم يتم العثور على مفتاح API لـ Twelve Data")
        print("يرجى تعيين TWELVE_API في ملف config.py أو في متغيرات البيئة")
    else:
        test_analysis()
