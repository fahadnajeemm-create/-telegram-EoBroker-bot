import requests
import pandas as pd
import ta
import os
import time
from datetime import datetime

try:
    from config import TWELVE_API
except ImportError:
    TWELVE_API = os.environ.get('TWELVE_API', '')

def get_price(pair):
    """جلب السعر الحالي للزوج"""
    try:
        symbol = pair.replace("/", "")
        
        api_key = TWELVE_API or os.environ.get('TWELVE_API')
        if not api_key:
            print("خطأ: مفتاح API غير موجود")
            return None
        
        url = f"https://api.twelvedata.com/price?symbol={symbol}&apikey={api_key}"
        print(f"جاري جلب السعر: {url}")
        
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if "price" in data:
            return float(data["price"])
        elif "status" in data and data["status"] == "error":
            print(f"خطأ في API: {data.get('message', 'خطأ غير معروف')}")
            return None
        return None
    except Exception as e:
        print(f"خطأ في get_price: {e}")
        return None

def get_candles(pair):
    """جلب بيانات الشموع من API"""
    try:
        symbol = pair
        
        api_key = TWELVE_API or os.environ.get('TWELVE_API')
        if not api_key:
            print("خطأ: مفتاح API غير موجود")
            return None
        
        url = f"https://api.twelvedata.com/time_series?symbol={symbol}&interval=1min&outputsize=200&apikey={api_key}"
        print(f"جاري جلب الشموع: {url}")
        
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
        print(f"تم جلب {len(df)} شمعة لـ {pair}")
        return df
    except Exception as e:
        print(f"خطأ في get_candles: {e}")
        import traceback
        traceback.print_exc()
        return None

def analyze_market(pair):
    """تحليل السوق وإصدار إشارة تداول"""
    try:
        print(f"=" * 50)
        print(f"جاري تحليل الزوج: {pair}")
        print(f"=" * 50)
        
        df = get_candles(pair)
        if df is None or len(df) < 50:
            print(f"بيانات غير كافية لتحليل {pair}")
            return None
        
        print(f"تم جلب {len(df)} شمعة، جاري التحليل...")
        
        score_buy = 0
        score_sell = 0
        reasons = []
        
        # حساب المؤشرات الفنية
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
        df["bb_mid"] = bb.bollinger_mavg() 
        
        df = df.dropna()
        if len(df) == 0:
            print("جميع القيم NaN بعد الحسابات")
            return None
        
        last = df.iloc[-1]
        body = abs(last["close"] - last["open"])
        candle_range = last["high"] - last["low"]
        print(f"آخر سعر: {last['close']}")
        
        # 1. تحليل EMA
        if last["ema9"] > last["ema21"]:
            score_buy += 30
            reasons.append(f"✅ EMA صاعد (9: {last['ema9']:.5f} > 21: {last['ema21']:.5f})")
        else:
            score_sell += 30
            reasons.append(f"✅ EMA هابط (9: {last['ema9']:.5f} < 21: {last['ema21']:.5f})")
        
        # 2. تحليل RSI
        if last["rsi"] > 60:
            score_buy += 15
            reasons.append(f"✅ RSI قوي = {last['rsi']:.1f}")
        elif last["rsi"] > 55:
            score_buy += 10
            reasons.append(f"✅ RSI = {last['rsi']:.1f}")
        elif last["rsi"] < 40:
            score_sell += 15
            reasons.append(f"✅ RSI ضعيف = {last['rsi']:.1f}")
        elif last["rsi"] < 45:
            score_sell += 10
            reasons.append(f"✅ RSI = {last['rsi']:.1f}")
        
        # 3. تحليل MACD
        if last["macd"] > last["macd_signal"]:
            score_buy += 20
            reasons.append(f"✅ MACD صاعد ({last['macd']:.5f} > {last['macd_signal']:.5f})")
        else:
            score_sell += 20
            reasons.append(f"✅ MACD هابط ({last['macd']:.5f} < {last['macd_signal']:.5f})")
        
        # 4. تحليل ADX
        if last["adx"] >= 25:
            if score_buy > score_sell:
                score_buy += 15
            elif score_sell > score_buy:
                score_sell += 15
            reasons.append(f"✅ ADX قوي = {last['adx']:.1f}")
        else:
            reasons.append(f"⚠️ ADX ضعيف = {last['adx']:.1f}")
        
        # 5. تحليل Bollinger Bands
        if last["close"] <= last["bb_low"]:
            score_buy += 10
            reasons.append(f"✅ ارتداد من الحد السفلي (السعر: {last['close']:.5f} ≤ {last['bb_low']:.5f})")
        elif last["close"] >= last["bb_high"]:
            score_sell += 10
            reasons.append(f"✅ ارتداد من الحد العلوي (السعر: {last['close']:.5f} ≥ {last['bb_high']:.

                                                                                    # 6. تحديد الإشارة وقوة التوافق

if score_buy > score_sell:
    signal = "CALL"
else:
    signal = "PUT"

score = 0

# EMA
if (signal == "CALL" and last["ema9"] > last["ema21"]) or \
   (signal == "PUT" and last["ema9"] < last["ema21"]):
    score += 1

# RSI
if signal == "CALL" and 55 <= last["rsi"] <= 70:
    score += 1
elif signal == "PUT" and 30 <= last["rsi"] <= 45:
    score += 1

# MACD
if (signal == "CALL" and last["macd"] > last["macd_signal"]) or \
   (signal == "PUT" and last["macd"] < last["macd_signal"]):
    score += 1

# ADX
if last["adx"] >= 25:
    score += 1

# Bollinger (الخط الأوسط)
if signal == "CALL" and last["close"] > last["bb_mid"]:
    score += 1
elif signal == "PUT" and last["close"] < last["bb_mid"]:
    score += 1

# قوة الشمعة
if candle_range > 0 and (body / candle_range) >= 0.6:
    score += 1

# آخر 3 شموع
last3 = df.tail(3)

if signal == "CALL":
    if (last3["close"] > last3["open"]).sum() >= 2:
        score += 1
elif signal == "PUT":
    if (last3["close"] < last3["open"]).sum() >= 2:
        score += 1

# السعر بالنسبة لـ EMA21
if signal == "CALL" and last["close"] > last["ema21"]:
    score += 1
elif signal == "PUT" and last["close"] < last["ema21"]:
    score += 1

strength = int((score / 8) * 100)

# لا ترسل الإشارات الضعيفة
if strength < 90:
    print("❌ تم تجاهل الإشارة لأن قوتها أقل من 90%")
    return None

# مدة الصفقة
if strength >= 95:
    duration = 30
else:
    duration = 45
        # 9. تجهيز النتيجة
        result = {
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
        
        print(f"✅ تم تحليل {pair} بنجاح")
        print(f"الإشارة: {signal}, القوة: {strength}%")
        return result
    except Exception as e:
        print(f"❌ خطأ في تحليل {pair}: {e}")
        import traceback
        traceback.print_exc()
        return None

def test_analysis():
    """اختبار تحليل جميع الأزواج"""
    pairs = ["XAU/USD", "XAG/USD", "EUR/USD", "BTC/USD"]
    for pair in pairs:
        print(f"\n{'=' * 50}")
        print(f"تحليل الزوج: {pair}")
        print(f"{'=' * 50}")
        result = analyze_market(pair)
        if result:
            print(f"\n📊 نتائج التحليل:")
            print(f"الإشارة: {'🟢 شراء (CALL)' if result['signal'] == 'CALL' else '🔴 بيع (PUT)'}")
            print(f"القوة: {result['strength']}%")
            print(f"السعر: {result['price']:.5f}")
            print(f"المدة: {result['duration']} ثانية")
            print(f"\n📈 المؤشرات:")
            print(f"  EMA9: {result['ema9']}")
            print(f"  EMA21: {result['ema21']}")
            print(f"  RSI: {result['rsi']}")
            print(f"  MACD: {result['macd']}")
            print(f"  ADX: {result['adx']}")
            print(f"\n📋 أسباب الإشارة:")
            for reason in result['reasons']:
                print(f"  {reason}")
        else:
            print(f"❌ فشل تحليل {pair}")
        time.sleep(2)

def display_signal_formatted(result):
    """عرض الإشارة بشكل منسق مثل المثال"""
    if not result:
        return
    
    print("\n" + "=" * 50)
    print(f"💱 الزوج: {result['pair']}")
    print(f"💰 السعر الحالي: {result['price']:.5f}")
    signal_emoji = "🟢" if result['signal'] == "CALL" else "🔴"
    signal_text = "شراء (CALL)" if result['signal'] == "CALL" else "بيع (PUT)"
    print(f"📊 الإشارة: {signal_emoji} {signal_text}")
    print(f"🔥 قوة الإشارة: {result['strength']}%")
    print("-" * 50)
    print(f"📈 EMA9 : {result['ema9']:.5f}")
    print(f"📉 EMA21 : {result['ema21']:.5f}")
    print(f"📊 RSI : {result['rsi']:.2f}")
    print(f"📊 MACD : {result['macd']:.4f}")
    print(f"📊 ADX : {result['adx']:.1f}")
    print("-" * 50)
    print(f"⏱ مدة الصفقة: {result['duration']} ثانية")
    print(f"⏰ الوقت: {datetime.now().strftime('%H:%M')}")
    print("=" * 50)

def main():
    """الوظيفة الرئيسية"""
    if not TWELVE_API and not os.environ.get('TWELVE_API'):
        print("⚠️ تحذير: لم يتم العثور على مفتاح API لـ Twelve Data")
        print("يرجى تعيين المتغير TWELVE_API في ملف config.py أو كمتغير بيئي")
        print("\nمثال config.py:")
        print('TWELVE_API = "مفتاح_api_الخاص_بك"')
        return
    
    # تحليل زوج واحد بشكل منسق
    pair = "XAU/USD"
    result = analyze_market(pair)
    display_signal_formatted(result)
    
    # اختيارياً: اختبار جميع الأزواج
    # test_analysis()

if __name__ == "__main__":
    main()
