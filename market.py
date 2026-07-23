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
    """الحصول على السعر الحالي"""
    try:
        df = get_candles(pair, interval="1min")
        if df is not None and len(df) > 0:
            return float(df.iloc[-1]["close"])
        return None
    except:
        return None

def get_candles(pair, interval="1min", outputsize=200):
    """جلب بيانات الشموع من API مع محاولات متعددة"""
    try:
        api_key = TWELVE_API or os.environ.get('TWELVE_API')
        if not api_key:
            print("❌ خطأ: مفتاح API غير موجود")
            return None
        
        symbols_to_try = [
            pair,
            pair.replace("/", ""),
            pair.replace("/", "").upper(),
            pair.split("/")[0] + pair.split("/")[1],
        ]
        
        symbols_to_try = list(dict.fromkeys(symbols_to_try))
        df = None
        
        for symbol in symbols_to_try:
            print(f"🔄 محاولة جلب البيانات بالرمز: {symbol} ({interval})")
            url = f"https://api.twelvedata.com/time_series?symbol={symbol}&interval={interval}&outputsize={outputsize}&apikey={api_key}"
            
            try:
                response = requests.get(url, timeout=10)
                response.raise_for_status()
                data = response.json()
                
                if "values" in data and data["values"]:
                    print(f"✅ نجح جلب البيانات بالرمز: {symbol}")
                    df = pd.DataFrame(data["values"])
                    break
                elif "status" in data and data["status"] == "error":
                    print(f"⚠️ خطأ في API للرمز {symbol}: {data.get('message', 'خطأ غير معروف')}")
                else:
                    print(f"⚠️ لا توجد بيانات للرمز {symbol}")
                    
            except requests.exceptions.Timeout:
                print(f"⚠️ انتهت المهلة للرمز {symbol}")
            except requests.exceptions.RequestException as e:
                print(f"⚠️ خطأ في الطلب للرمز {symbol}: {e}")
            except Exception as e:
                print(f"⚠️ فشل المحاولة للرمز {symbol}: {e}")
                continue
        
        if df is None:
            print(f"❌ فشل جلب البيانات لـ {pair} بجميع الصيغ")
            return None
        
        for col in ["open", "high", "low", "close"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        df = df.dropna()
        
        if len(df) < 50:
            print(f"⚠️ عدد الشموع غير كافٍ: {len(df)} (يحتاج 50 على الأقل)")
            return None
        
        df = df.iloc[::-1].reset_index(drop=True)
        print(f"✅ تم جلب {len(df)} شمعة لـ {pair} ({interval})")
        return df
        
    except Exception as e:
        print(f"❌ خطأ في get_candles: {e}")
        import traceback
        traceback.print_exc()
        return None

# =============================================
# دالة مساعدة: حساب Pivot Points
# =============================================
def find_pivot_points(df, window=5):
    """العثور على نقاط Pivot High و Pivot Low"""
    pivots_high = []
    pivots_low = []
    
    for i in range(window, len(df) - window):
        # Pivot High
        if df.iloc[i]["high"] == df.iloc[i-window:i+window+1]["high"].max():
            pivots_high.append({
                'index': i,
                'price': df.iloc[i]["high"],
                'time': df.iloc[i].get('datetime', i)
            })
        
        # Pivot Low
        if df.iloc[i]["low"] == df.iloc[i-window:i+window+1]["low"].min():
            pivots_low.append({
                'index': i,
                'price': df.iloc[i]["low"],
                'time': df.iloc[i].get('datetime', i)
            })
    
    return pivots_high, pivots_low

# =============================================
# تحليل الفريمات المتعددة (5 دقائق + 1 دقيقة)
# =============================================
def multi_timeframe_analysis(pair):
    """تحليل متعدد الفريمات - الاتجاه من 5 دقائق والدخول من 1 دقيقة"""
    try:
        # جلب بيانات 5 دقائق للاتجاه
        df_5m = get_candles(pair, interval="5min", outputsize=100)
        if df_5m is None or len(df_5m) < 50:
            print("❌ فشل جلب بيانات 5 دقائق")
            return None, None, None
        
        # حساب المؤشرات على فريم 5 دقائق
        df_5m["ema21"] = ta.trend.EMAIndicator(close=df_5m["close"], window=21).ema_indicator()
        df_5m["ema50"] = ta.trend.EMAIndicator(close=df_5m["close"], window=50).ema_indicator()
        df_5m["ema200"] = ta.trend.EMAIndicator(close=df_5m["close"], window=200).ema_indicator()
        
        adx = ta.trend.ADXIndicator(high=df_5m["high"], low=df_5m["low"], close=df_5m["close"], window=14)
        df_5m["adx"] = adx.adx()
        
        df_5m = df_5m.dropna()
        
        if len(df_5m) == 0:
            print("❌ بيانات 5 دقائق غير صالحة")
            return None, None, None
        
        last_5m = df_5m.iloc[-1]
        
        # تحديد الاتجاه على فريم 5 دقائق
        is_bullish = (
            last_5m["ema21"] > last_5m["ema50"] and
            last_5m["ema50"] > last_5m["ema200"] and
            last_5m["adx"] >= 25
        )
        
        is_bearish = (
            last_5m["ema21"] < last_5m["ema50"] and
            last_5m["ema50"] < last_5m["ema200"] and
            last_5m["adx"] >= 25
        )
        
        if is_bullish:
            direction_5m = "BULLISH"
        elif is_bearish:
            direction_5m = "BEARISH"
        else:
            direction_5m = "NEUTRAL"
        
        print(f"📊 اتجاه 5 دقائق: {direction_5m} (ADX: {last_5m['adx']:.1f})")
        
        # جلب بيانات 1 دقيقة للدخول
        df_1m = get_candles(pair, interval="1min", outputsize=200)
        if df_1m is None or len(df_1m) < 50:
            print("❌ فشل جلب بيانات 1 دقيقة")
            return None, None, None
        
        return df_1m, df_5m, direction_5m
        
    except Exception as e:
        print(f"❌ خطأ في التحليل متعدد الفريمات: {e}")
        return None, None, None

# =============================================
# المرحلة 1: فلترة السوق (محسنة)
# =============================================
def market_filter(df, last, atr_percent):
    """المرحلة 1: فلترة السوق - التحقق من ظروف السوق المناسبة"""
    reasons = []
    passed = True
    failed_reasons = []
    
    # 1.1 التحقق من ADX (قوة الاتجاه)
    if last["adx"] < 25:
        msg = f"⚠️ ADX ضعيف: {last['adx']:.1f} (يحتاج ≥ 25)"
        reasons.append(msg)
        failed_reasons.append(msg)
        passed = False
    
    # 1.2 التحقق من ATR كنسبة من السعر (بدلاً من القيمة المطلقة)
    if atr_percent < 0.0008:  # 0.08% من السعر
        msg = f"⚠️ التقلب منخفض: ATR {atr_percent:.4%} من السعر (يحتاج ≥ 0.08%)"
        reasons.append(msg)
        failed_reasons.append(msg)
        passed = False
    
    # 1.3 التحقق من عدم وجود شمعة انفجارية
    avg_body = (df["close"] - df["open"]).abs().tail(10).mean()
    body = abs(last["close"] - last["open"])
    if body > avg_body * 2:
        msg = f"⚠️ شمعة انفجارية: الجسم {body:.5f} > {avg_body * 2:.5f}"
        reasons.append(msg)
        failed_reasons.append(msg)
        passed = False
    
    # 1.4 التحقق من عدم وجود تذبذب قوي
    candle_range = last["high"] - last["low"]
    avg_range = (df["high"] - df["low"]).tail(20).mean()
    if candle_range > avg_range * 1.8:
        msg = f"⚠️ تذبذب قوي: المدى {candle_range:.5f} > {avg_range * 1.8:.5f}"
        reasons.append(msg)
        failed_reasons.append(msg)
        passed = False
    
    if passed:
        reasons.append("✅ اجتازت فلترة السوق")
    
    return passed, reasons, failed_reasons

# =============================================
# المرحلة 2: تحديد الاتجاه (محسّن مع EMA200)
# =============================================
def trend_analysis(df, last, atr):
    """المرحلة 2: تحديد الاتجاه مع وزن 30%"""
    reasons = []
    score = 0
    max_score = 5  # زيادة لاستيعاب EMA200
    
    # 2.1 EMA9 فوق/تحت EMA21
    if last["ema9"] > last["ema21"]:
        score += 1
        reasons.append(f"✅ EMA9 ({last['ema9']:.5f}) > EMA21 ({last['ema21']:.5f})")
    else:
        reasons.append(f"✅ EMA9 ({last['ema9']:.5f}) < EMA21 ({last['ema21']:.5f})")
    
    # 2.2 اتجاه EMA21 (الميل الحقيقي - محسن)
    ema21_slope = df["ema21"].diff().tail(5).mean()
    if ema21_slope > 0:
        score += 1
        reasons.append(f"✅ EMA21 صاعد: {ema21_slope:.5f}")
    else:
        reasons.append(f"✅ EMA21 هابط: {ema21_slope:.5f}")
    
    # 2.3 السعر بالنسبة لـ EMA21
    if last["close"] > last["ema21"]:
        score += 1
        reasons.append(f"✅ السعر ({last['close']:.5f}) > EMA21 ({last['ema21']:.5f})")
    else:
        reasons.append(f"✅ السعر ({last['close']:.5f}) < EMA21 ({last['ema21']:.5f})")
    
    # 2.4 فرق EMA بالنسبة لـ ATR
    ema_diff = abs(last["ema9"] - last["ema21"])
    atr_ratio = ema_diff / atr if atr > 0 else 0
    if atr_ratio >= 0.3:
        score += 1
        reasons.append(f"✅ فرق EMA ({ema_diff:.5f}) = {atr_ratio:.1%} من ATR")
    else:
        reasons.append(f"⚠️ فرق EMA صغير: {atr_ratio:.1%} من ATR")
    
    # 2.5 EMA21 مقابل EMA200 (فلتر قوي)
    if "ema200" in df.columns:
        if last["ema21"] > last["ema200"]:
            score += 1
            reasons.append(f"✅ EMA21 ({last['ema21']:.5f}) > EMA200 ({last['ema200']:.5f})")
        else:
            reasons.append(f"✅ EMA21 ({last['ema21']:.5f}) < EMA200 ({last['ema200']:.5f})")
    
    # تحديد الاتجاه
    if score >= 4:
        direction = "BULLISH" if last["ema9"] > last["ema21"] else "BEARISH"
    else:
        direction = "NEUTRAL"
    
    return direction, score, max_score, reasons

# =============================================
# المرحلة 3: تحليل Price Action (محسّن)
# =============================================
def price_action_analysis(df, last):
    """المرحلة 3: تحليل Price Action مع وزن 25% - يعطي نقاط بدلاً من الرفض"""
    reasons = []
    pattern = None
    score = 0
    max_score = 5
    
    if len(df) >= 3:
        prev = df.iloc[-2]
        current = last
        
        body = abs(current["close"] - current["open"])
        upper_shadow = current["high"] - max(current["open"], current["close"])
        lower_shadow = min(current["open"], current["close"]) - current["low"]
        total_range = current["high"] - current["low"]
        
        # 3.1 Bullish Engulfing
        if (prev["close"] < prev["open"] and
            current["close"] > current["open"] and
            current["open"] < prev["close"] and
            current["close"] > prev["open"]):
            pattern = "BULLISH_ENGULFING"
            score = 5
            reasons.append("✅ Bullish Engulfing - نمط انعكاس صاعد قوي")
        
        # 3.2 Bearish Engulfing
        elif (prev["close"] > prev["open"] and
              current["close"] < current["open"] and
              current["open"] > prev["close"] and
              current["close"] < prev["open"]):
            pattern = "BEARISH_ENGULFING"
            score = 5
            reasons.append("✅ Bearish Engulfing - نمط انعكاس هابط قوي")
        
        # 3.3 Pin Bar
        elif total_range > 0:
            if lower_shadow > body * 2 and upper_shadow < body * 0.5:
                pattern = "BULLISH_PIN_BAR"
                score = 4
                reasons.append(f"✅ Bullish Pin Bar - ظل سفلي {lower_shadow:.5f} > {body * 2:.5f}")
            
            elif upper_shadow > body * 2 and lower_shadow < body * 0.5:
                pattern = "BEARISH_PIN_BAR"
                score = 4
                reasons.append(f"✅ Bearish Pin Bar - ظل علوي {upper_shadow:.5f} > {body * 2:.5f}")
        
        # 3.4 Inside Bar
        if (prev["high"] > current["high"] and prev["low"] < current["low"]):
            if not pattern:
                pattern = "INSIDE_BAR"
                score = 2
                reasons.append("✅ Inside Bar - شمعة داخل نطاق سابق")
    
    # 3.5 Breakout (محسّن - استبعاد الشمعة الحالية)
    resistance = df.iloc[:-1]["high"].tail(5).max()
    support = df.iloc[:-1]["low"].tail(5).min()
    
    if current["close"] > resistance and current["close"] > current["open"]:
        if not pattern or score < 3:
            pattern = "BREAKOUT_BULLISH"
            score = max(score, 3)
            reasons.append(f"✅ اختراق مقاومة: {current['close']:.5f} > {resistance:.5f}")
    
    elif current["close"] < support and current["close"] < current["open"]:
        if not pattern or score < 3:
            pattern = "BREAKOUT_BEARISH"
            score = max(score, 3)
            reasons.append(f"✅ اختراق دعم: {current['close']:.5f} < {support:.5f}")
    
    return pattern, score, max_score, reasons

# =============================================
# المرحلة 4: الدعم والمقاومة (محسّن مع Pivot Points)
# =============================================
def support_resistance_analysis(df, last):
    """المرحلة 4: تحليل الدعم والمقاومة مع وزن 20%"""
    reasons = []
    score = 0
    max_score = 4
    
    # استخدام Pivot Points بدلاً من القيم البسيطة
    pivots_high, pivots_low = find_pivot_points(df, window=5)
    
    # أحدث نقاط الدعم والمقاومة
    recent_pivot_high = pivots_high[-1]["price"] if pivots_high else df["high"].tail(20).max()
    recent_pivot_low = pivots_low[-1]["price"] if pivots_low else df["low"].tail(20).min()
    
    range_mid = (recent_pivot_high + recent_pivot_low) / 2
    range_width = recent_pivot_high - recent_pivot_low
    
    # 4.1 عدم الشراء عند مقاومة قوية
    if last["close"] >= recent_pivot_high * 0.98:
        if last["close"] > last["open"]:
            reasons.append("⚠️ شراء عند مقاومة قوية - غير موصى به")
            score -= 2
        else:
            reasons.append("⚠️ السعر عند مقاومة قوية")
            score -= 1
    
    # 4.2 عدم البيع عند دعم قوي
    if last["close"] <= recent_pivot_low * 1.02:
        if last["close"] < last["open"]:
            reasons.append("⚠️ بيع عند دعم قوي - غير موصى به")
            score -= 2
        else:
            reasons.append("⚠️ السعر عند دعم قوي")
            score -= 1
    
    # 4.3 عدم الدخول في منتصف النطاق
    if abs(last["close"] - range_mid) < range_width * 0.1:
        reasons.append("⚠️ السعر في منتصف النطاق - غير موصى به")
        score -= 1
    
    # 4.4 السعر قريب من الدعم أو المقاومة
    if last["close"] <= recent_pivot_low * 1.03:
        score += 2
        reasons.append(f"✅ السعر قرب الدعم: {recent_pivot_low:.5f}")
    elif last["close"] >= recent_pivot_high * 0.97:
        score += 2
        reasons.append(f"✅ السعر قرب المقاومة: {recent_pivot_high:.5f}")
    else:
        score += 1
        reasons.append("✅ السعر في منطقة مناسبة")
    
    score = max(0, score)
    
    return score, max_score, reasons

# =============================================
# المرحلة 5: تأكيد المؤشرات (محسّن)
# =============================================
def indicator_confirmation(df, last, direction):
    """المرحلة 5: تأكيد المؤشرات مع وزن 25%"""
    reasons = []
    score = 0
    max_score = 5
    
    # 5.1 RSI (محسّن - مع التحقق من الاتجاه)
    rsi_score = 0
    rsi_rising = last["rsi"] > df.iloc[-2]["rsi"]
    
    if direction == "BULLISH":
        if 55 <= last["rsi"] <= 70 and rsi_rising:
            rsi_score = 2.5
            reasons.append(f"✅ RSI صاعد وداعم للشراء: {last['rsi']:.1f}")
        elif 55 <= last["rsi"] <= 70:
            rsi_score = 2
            reasons.append(f"✅ RSI داعم للشراء: {last['rsi']:.1f}")
        elif 45 < last["rsi"] < 55:
            rsi_score = 1
            reasons.append(f"✅ RSI محايد: {last['rsi']:.1f}")
        elif last["rsi"] < 35:
            rsi_score = 1.5
            reasons.append(f"⚠️ RSI منخفض جداً: {last['rsi']:.1f} (احتمال ارتداد)")
        else:
            reasons.append(f"⚠️ RSI غير داعم: {last['rsi']:.1f}")
    else:  # BEARISH
        if 30 <= last["rsi"] <= 45 and not rsi_rising:
            rsi_score = 2.5
            reasons.append(f"✅ RSI هابط وداعم للبيع: {last['rsi']:.1f}")
        elif 30 <= last["rsi"] <= 45:
            rsi_score = 2
            reasons.append(f"✅ RSI داعم للبيع: {last['rsi']:.1f}")
        elif 45 < last["rsi"] < 55:
            rsi_score = 1
            reasons.append(f"✅ RSI محايد: {last['rsi']:.1f}")
        elif last["rsi"] > 70:
            rsi_score = 1.5
            reasons.append(f"⚠️ RSI مرتفع جداً: {last['rsi']:.1f} (احتمال ارتداد)")
        else:
            reasons.append(f"⚠️ RSI غير داعم: {last['rsi']:.1f}")
    
    # 5.2 MACD (محسّن - مع التحقق من التسارع)
    macd_score = 0
    macd_rising = last["macd"] > df.iloc[-2]["macd"]
    
    if direction == "BULLISH" and last["macd"] > last["macd_signal"] and macd_rising:
        macd_score = 2.5
        reasons.append(f"✅ MACD صاعد ومتسارع: {last['macd']:.5f} > {last['macd_signal']:.5f}")
    elif direction == "BULLISH" and last["macd"] > last["macd_signal"]:
        macd_score = 2
        reasons.append(f"✅ MACD صاعد: {last['macd']:.5f} > {last['macd_signal']:.5f}")
    elif direction == "BEARISH" and last["macd"] < last["macd_signal"] and not macd_rising:
        macd_score = 2.5
        reasons.append(f"✅ MACD هابط ومتسارع: {last['macd']:.5f} < {last['macd_signal']:.5f}")
    elif direction == "BEARISH" and last["macd"] < last["macd_signal"]:
        macd_score = 2
        reasons.append(f"✅ MACD هابط: {last['macd']:.5f} < {last['macd_signal']:.5f}")
    else:
        reasons.append(f"⚠️ MACD غير متوافق مع الاتجاه")
    
    # 5.3 Bollinger Bands
    bb_score = 0
    if direction == "BULLISH" and last["close"] < last["bb_mid"]:
        bb_score = 1
        reasons.append(f"✅ السعر تحت منتصف البولينجر: {last['close']:.5f} < {last['bb_mid']:.5f}")
    elif direction == "BEARISH" and last["close"] > last["bb_mid"]:
        bb_score = 1
        reasons.append(f"✅ السعر فوق منتصف البولينجر: {last['close']:.5f} > {last['bb_mid']:.5f}")
    else:
        reasons.append(f"⚠️ البولينجر غير داعم")
    
    # 5.4 حجم الشمعة
    candle_score = 0
    avg_body = (df["close"] - df["open"]).abs().tail(10).mean()
    body = abs(last["close"] - last["open"])
    body_ratio = body / avg_body if avg_body > 0 else 0
    
    if body_ratio >= 1.5:
        candle_score = 1
        reasons.append(f"✅ شمعة قوية: {body_ratio:.1f}x المتوسط")
    elif body_ratio >= 1.0:
        candle_score = 0.5
        reasons.append(f"✅ شمعة متوسطة: {body_ratio:.1f}x المتوسط")
    else:
        reasons.append(f"⚠️ شمعة ضعيفة: {body_ratio:.1f}x المتوسط")
    
    score = rsi_score + macd_score + bb_score + candle_score
    
    return score, max_score, reasons

# =============================================
# المرحلة 6: حساب القوة (محسّن - 100%)
# =============================================
def calculate_strength(direction, trend_score, pa_score, sr_score, ind_score):
    """المرحلة 6: حساب قوة الإشارة بالأوزان المحددة (مجموع 100%)"""
    
    # الأوزان المعدلة (مجموع 100%)
    weights = {
        'trend': 0.30,           # 30%
        'price_action': 0.25,    # 25%
        'support_resistance': 0.20,  # 20%
        'indicators': 0.25       # 25% (زيادة من 20%)
    }
    
    # حساب الدرجة الموزونة
    weighted_score = (
        (trend_score / 5) * weights['trend'] +      # تغيير المقام إلى 5
        (pa_score / 5) * weights['price_action'] +
        (sr_score / 4) * weights['support_resistance'] +
        (ind_score / 5) * weights['indicators']    # تغيير المقام إلى 5
    ) * 100
    
    return int(weighted_score)

# =============================================
# الدالة الرئيسية المحسنة
# =============================================
def analyze_market(pair):
    """تحليل السوق باستخدام نظام المراحل الست مع فريمات متعددة"""
    try:
        print(f"\n{'=' * 50}")
        print(f"🔍 جاري تحليل الزوج: {pair}")
        print(f"{'=' * 50}")
        
        # =============================================
        # التحليل متعدد الفريمات
        # =============================================
        print("\n📊 التحليل متعدد الفريمات...")
        df, df_5m, direction_5m = multi_timeframe_analysis(pair)
        
        if df is None:
            print(f"❌ فشل جلب البيانات لـ {pair}")
            return None
        
        if len(df) < 50:
            print(f"❌ بيانات غير كافية لتحليل {pair}")
            return None
        
        # إذا كان اتجاه 5 دقائق محايد، لا نكمل
        if direction_5m == "NEUTRAL":
            print("⚠️ اتجاه 5 دقائق محايد - انتظار")
            last = df.iloc[-1]
            return {
                "signal": "WAIT",
                "strength": 0,
                "duration": 0,
                "price": float(last["close"]),
                "ema9": round(last["ema9"], 5) if "ema9" in df.columns else 0,
                "ema21": round(last["ema21"], 5) if "ema21" in df.columns else 0,
                "rsi": round(last["rsi"], 2) if "rsi" in df.columns else 0,
                "macd": round(last["macd"], 5) if "macd" in df.columns else 0,
                "macd_signal": round(last["macd_signal"], 5) if "macd_signal" in df.columns else 0,
                "adx": round(last["adx"], 2) if "adx" in df.columns else 0,
                "atr": round(last["atr"], 5) if not pd.isna(last["atr"]) else 0,
                "reason": "اتجاه 5 دقائق محايد",
                "timestamp": datetime.now().isoformat(),
                "pair": pair
            }
        
        print(f"✅ اتجاه 5 دقائق: {direction_5m}")
        
        # استخدام بيانات 1 دقيقة للدخول
        last = df.iloc[-1]
        
        # حساب المؤشرات على 1 دقيقة
        print("🔄 حساب المؤشرات الفنية على 1 دقيقة...")
        try:
            df["ema9"] = ta.trend.EMAIndicator(close=df["close"], window=9).ema_indicator()
            df["ema21"] = ta.trend.EMAIndicator(close=df["close"], window=21).ema_indicator()
            df["ema200"] = ta.trend.EMAIndicator(close=df["close"], window=200).ema_indicator()
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
            
            atr = ta.volatility.AverageTrueRange(
                high=df["high"],
                low=df["low"],
                close=df["close"],
                window=14
            )
            df["atr"] = atr.average_true_range()
            
            print("✅ تم حساب جميع المؤشرات")
        except Exception as e:
            print(f"❌ خطأ في حساب المؤشرات: {e}")
            return None
        
        df = df.dropna()
        if len(df) == 0:
            print("❌ جميع القيم NaN")
            return None
        
        last = df.iloc[-1]
        
        # حساب ATR كنسبة من السعر
        atr_percent = last["atr"] / last["close"] if last["close"] > 0 else 0
        
        print(f"\n📊 آخر سعر: {last['close']:.5f}")
        print(f"📊 ADX: {last['adx']:.2f}")
        print(f"📊 RSI: {last['rsi']:.2f}")
        print(f"📊 ATR%: {atr_percent:.4%}")
        
        all_reasons = []
        failed_reasons = []
        
        # =============================================
        # المرحلة 1: فلترة السوق
        # =============================================
        print("\n🔍 المرحلة 1: فلترة السوق")
        filter_passed, filter_reasons, failed = market_filter(df, last, atr_percent)
        
        for reason in filter_reasons:
            print(f"  {reason}")
        
        if not filter_passed:
            print("❌ لم تجتز فلترة السوق")
            fail_text = "فشل فلترة السوق:\n" + "\n".join(failed)
            
            return {
                "signal": "WAIT",
                "strength": 0,
                "duration": 0,
                "price": float(last["close"]),
                "ema9": round(last["ema9"], 5),
                "ema21": round(last["ema21"], 5),
                "rsi": round(last["rsi"], 2),
                "macd": round(last["macd"], 5),
                "macd_signal": round(last["macd_signal"], 5),
                "adx": round(last["adx"], 2),
                "atr": round(last["atr"], 5) if not pd.isna(last["atr"]) else 0,
                "reason": fail_text,
                "failed_checks": failed,
                "timestamp": datetime.now().isoformat(),
                "pair": pair
            }
        
        print("✅ اجتازت فلترة السوق")
        all_reasons.extend(filter_reasons)
        
        # =============================================
        # المرحلة 2: تحديد الاتجاه (وزن 30%)
        # =============================================
        print("\n🔍 المرحلة 2: تحديد الاتجاه (وزن 30%)")
        direction, trend_score, trend_max, trend_reasons = trend_analysis(df, last, last["atr"])
        
        for reason in trend_reasons:
            print(f"  {reason}")
        
        print(f"📊 نقاط الاتجاه: {trend_score}/{trend_max}")
        all_reasons.extend(trend_reasons)
        
        # التحقق من توافق الاتجاه مع فريم 5 دقائق
        if direction != direction_5m and direction != "NEUTRAL":
            print(f"⚠️ اختلاف الاتجاه: 1m={direction}, 5m={direction_5m}")
            return {
                "signal": "WAIT",
                "strength": 0,
                "duration": 0,
                "price": float(last["close"]),
                "ema9": round(last["ema9"], 5),
                "ema21": round(last["ema21"], 5),
                "rsi": round(last["rsi"], 2),
                "macd": round(last["macd"], 5),
                "macd_signal": round(last["macd_signal"], 5),
                "adx": round(last["adx"], 2),
                "atr": round(last["atr"], 5) if not pd.isna(last["atr"]) else 0,
                "reason": f"اختلاف الاتجاه: 1m={direction}, 5m={direction_5m}",
                "timestamp": datetime.now().isoformat(),
                "pair": pair
            }
        
        if direction == "NEUTRAL":
            print("⚠️ اتجاه غير واضح")
            return {
                "signal": "WAIT",
                "strength": 0,
                "duration": 0,
                "price": float(last["close"]),
                "ema9": round(last["ema9"], 5),
                "ema21": round(last["ema21"], 5),
                "rsi": round(last["rsi"], 2),
                "macd": round(last["macd"], 5),
                "macd_signal": round(last["macd_signal"], 5),
                "adx": round(last["adx"], 2),
                "atr": round(last["atr"], 5) if not pd
