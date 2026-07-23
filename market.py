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
        df = get_candles(pair)
        if df is not None and len(df) > 0:
            return float(df.iloc[-1]["close"])
        return None
    except:
        return None

def get_candles(pair):
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
            print(f"🔄 محاولة جلب البيانات بالرمز: {symbol}")
            url = f"https://api.twelvedata.com/time_series?symbol={symbol}&interval=1min&outputsize=200&apikey={api_key}"
            
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
        print(f"✅ تم جلب {len(df)} شمعة لـ {pair}")
        return df
        
    except Exception as e:
        print(f"❌ خطأ في get_candles: {e}")
        import traceback
        traceback.print_exc()
        return None

# =============================================
# المرحلة 1: فلترة السوق
# =============================================
def market_filter(df, last, atr_avg):
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
    
    # 1.2 التحقق من ATR (التقلب الكافي)
    if last["atr"] < atr_avg * 0.7:
        msg = f"⚠️ التقلب منخفض: ATR {last['atr']:.5f} < {atr_avg * 0.7:.5f}"
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
# المرحلة 2: تحديد الاتجاه
# =============================================
def trend_analysis(df, last, atr):
    """المرحلة 2: تحديد الاتجاه مع وزن 30%"""
    reasons = []
    score = 0
    max_score = 4
    
    # 2.1 EMA9 فوق/تحت EMA21
    if last["ema9"] > last["ema21"]:
        score += 1
        reasons.append(f"✅ EMA9 ({last['ema9']:.5f}) > EMA21 ({last['ema21']:.5f})")
    else:
        reasons.append(f"✅ EMA9 ({last['ema9']:.5f}) < EMA21 ({last['ema21']:.5f})")
    
    # 2.2 اتجاه EMA21 (آخر 5 شموع)
    ema21_slope = last["ema21"] - df.iloc[-5]["ema21"]
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
    
    # تحديد الاتجاه
    if score >= 3:
        direction = "BULLISH" if last["ema9"] > last["ema21"] else "BEARISH"
    else:
        direction = "NEUTRAL"
    
    return direction, score, max_score, reasons

# =============================================
# المرحلة 3: تحليل Price Action (وزن 25%)
# =============================================
def price_action_analysis(df, last):
    """المرحلة 3: تحليل Price Action مع وزن 25%"""
    reasons = []
    pattern = None
    score = 0
    max_score = 5
    
    if len(df) >= 3:
        prev2 = df.iloc[-3]
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
            # Bullish Pin Bar (مطرقة)
            if lower_shadow > body * 2 and upper_shadow < body * 0.5:
                pattern = "BULLISH_PIN_BAR"
                score = 4
                reasons.append(f"✅ Bullish Pin Bar - ظل سفلي {lower_shadow:.5f} > {body * 2:.5f}")
            
            # Bearish Pin Bar (نجم)
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
        
        # 3.5 Breakout
        resistance = df["high"].tail(5).max()
        support = df["low"].tail(5).min()
        
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
# المرحلة 4: الدعم والمقاومة (وزن 20%)
# =============================================
def support_resistance_analysis(df, last):
    """المرحلة 4: تحليل الدعم والمقاومة مع وزن 20%"""
    reasons = []
    score = 0
    max_score = 4
    
    # حساب مستويات الدعم والمقاومة من آخر 20 شمعة
    recent_high = df["high"].tail(20).max()
    recent_low = df["low"].tail(20).min()
    range_mid = (recent_high + recent_low) / 2
    range_width = recent_high - recent_low
    
    # 4.1 عدم الشراء عند مقاومة قوية
    if last["close"] >= recent_high * 0.98:  # قريب من المقاومة
        if last["close"] > last["open"]:  # شمعة صاعدة
            reasons.append("⚠️ شراء عند مقاومة قوية - غير موصى به")
            score -= 2
        else:
            reasons.append("⚠️ السعر عند مقاومة قوية")
            score -= 1
    
    # 4.2 عدم البيع عند دعم قوي
    if last["close"] <= recent_low * 1.02:  # قريب من الدعم
        if last["close"] < last["open"]:  # شمعة هابطة
            reasons.append("⚠️ بيع عند دعم قوي - غير موصى به")
            score -= 2
        else:
            reasons.append("⚠️ السعر عند دعم قوي")
            score -= 1
    
    # 4.3 عدم الدخول في منتصف النطاق
    if abs(last["close"] - range_mid) < range_width * 0.1:
        reasons.append("⚠️ السعر في منتصف النطاق - غير موصى به")
        score -= 1
    
    # 4.4 السعر قريب من الدعم أو المقاومة مع اتجاه
    if last["close"] <= recent_low * 1.03:  # قرب الدعم
        score += 2
        reasons.append(f"✅ السعر قرب الدعم: {recent_low:.5f}")
    elif last["close"] >= recent_high * 0.97:  # قرب المقاومة
        score += 2
        reasons.append(f"✅ السعر قرب المقاومة: {recent_high:.5f}")
    else:
        score += 1
        reasons.append("✅ السعر في منطقة مناسبة")
    
    # التأكد من أن النقاط لا تقل عن 0
    score = max(0, score)
    
    return score, max_score, reasons

# =============================================
# المرحلة 5: تأكيد المؤشرات (وزن 20%)
# =============================================
def indicator_confirmation(df, last, direction):
    """المرحلة 5: تأكيد المؤشرات مع وزن 20%"""
    reasons = []
    score = 0
    max_score = 4
    
    # 5.1 RSI (وزن 10%)
    rsi_score = 0
    if direction == "BULLISH":
        if 55 <= last["rsi"] <= 70:
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
        if 30 <= last["rsi"] <= 45:
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
    
    # 5.2 MACD (وزن 10%)
    macd_score = 0
    if direction == "BULLISH" and last["macd"] > last["macd_signal"]:
        macd_score = 2
        reasons.append(f"✅ MACD صاعد: {last['macd']:.5f} > {last['macd_signal']:.5f}")
    elif direction == "BEARISH" and last["macd"] < last["macd_signal"]:
        macd_score = 2
        reasons.append(f"✅ MACD هابط: {last['macd']:.5f} < {last['macd_signal']:.5f}")
    else:
        reasons.append(f"⚠️ MACD غير متوافق مع الاتجاه")
    
    # 5.3 Bollinger Bands (وزن 5%)
    bb_score = 0
    if direction == "BULLISH" and last["close"] < last["bb_mid"]:
        bb_score = 1
        reasons.append(f"✅ السعر تحت منتصف البولينجر: {last['close']:.5f} < {last['bb_mid']:.5f}")
    elif direction == "BEARISH" and last["close"] > last["bb_mid"]:
        bb_score = 1
        reasons.append(f"✅ السعر فوق منتصف البولينجر: {last['close']:.5f} > {last['bb_mid']:.5f}")
    else:
        reasons.append(f"⚠️ البولينجر غير داعم")
    
    # 5.4 حجم الشمعة (وزن 5%)
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
    max_score = 4
    
    return score, max_score, reasons

# =============================================
# المرحلة 6: حساب القوة بالأوزان
# =============================================
def calculate_strength(direction, trend_score, pa_score, sr_score, ind_score):
    """المرحلة 6: حساب قوة الإشارة بالأوزان المحددة"""
    
    # الأوزان
    weights = {
        'trend': 0.30,      # 30%
        'price_action': 0.25,  # 25%
        'support_resistance': 0.20,  # 20%
        'indicators': 0.20   # 20%
    }
    
    # حساب الدرجة الموزونة
    weighted_score = (
        (trend_score / 4) * weights['trend'] +
        (pa_score / 5) * weights['price_action'] +
        (sr_score / 4) * weights['support_resistance'] +
        (ind_score / 4) * weights['indicators']
    ) * 100
    
    return int(weighted_score)

# =============================================
# الدالة الرئيسية المحسنة
# =============================================
def analyze_market(pair):
    """تحليل السوق باستخدام نظام المراحل الست"""
    try:
        print(f"\n{'=' * 50}")
        print(f"🔍 جاري تحليل الزوج: {pair}")
        print(f"{'=' * 50}")
        
        # جلب البيانات
        df = get_candles(pair)
        if df is None:
            print(f"❌ فشل جلب البيانات لـ {pair}")
            return None
        
        if len(df) < 50:
            print(f"❌ بيانات غير كافية لتحليل {pair}")
            return None
        
        print(f"✅ تم جلب {len(df)} شمعة")
        
        # حساب المؤشرات الفنية
        print("🔄 حساب المؤشرات الفنية...")
        try:
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
        atr_avg = df["atr"].tail(20).mean()
        
        print(f"\n📊 آخر سعر: {last['close']:.5f}")
        print(f"📊 ADX: {last['adx']:.2f}")
        print(f"📊 RSI: {last['rsi']:.2f}")
        
        all_reasons = []
        failed_reasons = []
        
        # =============================================
        # المرحلة 1: فلترة السوق
        # =============================================
        print("\n🔍 المرحلة 1: فلترة السوق")
        filter_passed, filter_reasons, failed = market_filter(df, last, atr_avg)
        
        for reason in filter_reasons:
            print(f"  {reason}")
        
        if not filter_passed:
            print("❌ لم تجتز فلترة السوق")
            # عرض أسباب الفشل بشكل مفصل
            fail_text = "فشل فلترة السوق:\n" + "\n".join(failed)
            
            # تجهيز النتيجة مع أسباب الفشل
            result = {
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
            return result
        
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
                "atr": round(last["atr"], 5) if not pd.isna(last["atr"]) else 0,
                "reason": "الاتجاه غير واضح (نقاط الاتجاه منخفضة)",
                "timestamp": datetime.now().isoformat(),
                "pair": pair
            }
        
        print(f"✅ الاتجاه: {direction}")
        
        # =============================================
        # المرحلة 3: Price Action (وزن 25%)
        # =============================================
        print("\n🔍 المرحلة 3: تحليل Price Action (وزن 25%)")
        pattern, pa_score, pa_max, pa_reasons = price_action_analysis(df, last)
        
        for reason in pa_reasons:
            print(f"  {reason}")
        
        print(f"📊 نقاط Price Action: {pa_score}/{pa_max}")
        all_reasons.extend(pa_reasons)
        
        if pattern is None:
            print("⚠️ لم يتم العثور على نمط Price Action")
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
                "reason": "لا يوجد نمط Price Action واضح",
                "timestamp": datetime.now().isoformat(),
                "pair": pair
            }
        
        print(f"✅ النمط: {pattern}")
        
        # =============================================
        # المرحلة 4: الدعم والمقاومة (وزن 20%)
        # =============================================
        print("\n🔍 المرحلة 4: تحليل الدعم والمقاومة (وزن 20%)")
        sr_score, sr_max, sr_reasons = support_resistance_analysis(df, last)
        
        for reason in sr_reasons:
            print(f"  {reason}")
        
        print(f"📊 نقاط الدعم والمقاومة: {sr_score}/{sr_max}")
        all_reasons.extend(sr_reasons)
        
        # =============================================
        # المرحلة 5: تأكيد المؤشرات (وزن 20%)
        # =============================================
        print("\n🔍 المرحلة 5: تأكيد المؤشرات (وزن 20%)")
        ind_score, ind_max, ind_reasons = indicator_confirmation(df, last, direction)
        
        for reason in ind_reasons:
            print(f"  {reason}")
        
        print(f"📊 نقاط المؤشرات: {ind_score:.1f}/{ind_max}")
        all_reasons.extend(ind_reasons)
        
        # =============================================
        # المرحلة 6: حساب القوة النهائية
        # =============================================
        print("\n🔍 المرحلة 6: حساب قوة الإشارة")
        
        strength = calculate_strength(
            direction,
            trend_score,
            pa_score,
            sr_score,
            ind_score
        )
        
        print(f"📊 قوة الإشارة: {strength}%")
        
        # تحديد الإشارة بناءً على القوة
        if strength >= 90:
            signal = "CALL" if direction == "BULLISH" else "PUT"
            duration = 30
            signal_quality = "قوية جداً"
        elif strength >= 80:
            signal = "CALL" if direction == "BULLISH" else "PUT"
            duration = 45
            signal_quality = "جيدة"
        else:
            print(f"❌ قوة الإشارة منخفضة: {strength}% < 80%")
            return {
                "signal": "WAIT",
                "strength": strength,
                "duration": 0,
                "price": float(last["close"]),
                "ema9": round(last["ema9"], 5),
                "ema21": round(last["ema21"], 5),
                "rsi": round(last["rsi"], 2),
                "macd": round(last["macd"], 5),
                "macd_signal": round(last["macd_signal"], 5),
                "adx": round(last["adx"], 2),
                "atr": round(last["atr"], 5) if not pd.isna(last["atr"]) else 0,
                "reason": f"قوة الإشارة منخفضة ({strength}% < 80%)",
                "timestamp": datetime.now().isoformat(),
                "pair": pair
            }
        
        # تجهيز النتيجة النهائية
        result = {
            "signal": signal,
            "strength": strength,
            "quality": signal_quality,
            "duration": duration,
            "price": float(last["close"]),
            "ema9": round(last["ema9"], 5),
            "ema21": round(last["ema21"], 5),
            "rsi": round(last["rsi"], 2),
            "macd": round(last["macd"], 5),
            "macd_signal": round(last["macd_signal"], 5),
            "adx": round(last["adx"], 2),
            "atr": round(last["atr"], 5) if not pd.isna(last["atr"]) else 0,
            "pattern": pattern,
            "direction": direction,
            "reason": f"{signal} - {signal_quality} ({strength}%)",
            "details": all_reasons[:8],
            "timestamp": datetime.now().isoformat(),
            "pair": pair,
            "stage_scores": {
                "trend": f"{trend_score}/{trend_max}",
                "price_action": f"{pa_score}/{pa_max}",
                "support_resistance": f"{sr_score}/{sr_max}",
                "indicators": f"{ind_score:.1f}/{ind_max}"
            }
        }
        
        print(f"\n✅ تم التحليل بنجاح")
        print(f"📊 الإشارة: {signal}, القوة: {strength}% ({signal_quality})")
        print(f"📐 النمط: {pattern}")
        
        return result
        
    except Exception as e:
        print(f"❌ خطأ في تحليل {pair}: {e}")
        import traceback
        traceback.print_exc()
        return None

def display_signal_formatted(result):
    """عرض الإشارة بشكل منسق"""
    if not result:
        return
    
    print("\n" + "=" * 50)
    print(f"💱 الزوج: {result['pair']}")
    print(f"💰 السعر الحالي: {result['price']:.5f}")
    print(f"⏰ الوقت: {datetime.now().strftime('%H:%M:%S')}")
    print("-" * 50)
    
    if result['signal'] == "WAIT":
        print(f"⏸ الحالة: انتظار")
        print(f"📝 السبب: {result.get('reason', 'لا يوجد سبب')}")
        
        # عرض المؤشرات الحالية
        print("-" * 50)
        print(f"📊 RSI: {result['rsi']:.2f}")
        print(f"📊 ADX: {result['adx']:.1f}")
        print(f"📊 EMA9: {result['ema9']:.5f}")
        print(f"📊 EMA21: {result['ema21']:.5f}")
        
        # عرض الأسباب المفصلة إن وجدت
        if 'failed_checks' in result and result['failed_checks']:
            print("-" * 50)
            print("📝 أسباب الفشل:")
            for reason in result['failed_checks']:
                print(f"  {reason}")
    else:
        signal_emoji = "🟢" if result['signal'] == "CALL" else "🔴"
        signal_text = "شراء (CALL)" if result['signal'] == "CALL" else "بيع (PUT)"
        print(f"📊 الإشارة: {signal_emoji} {signal_text}")
        print(f"🔥 القوة: {result['strength']}% - {result.get('quality', '')}")
        print(f"📐 النمط: {result.get('pattern', 'غير محدد')}")
        print(f"🧭 الاتجاه: {result.get('direction', 'غير محدد')}")
        print(f"⏱ المدة: {result['duration']} ثانية")
        
        print("-" * 50)
        print(f"📈 EMA9  : {result['ema9']:.5f}")
        print(f"📉 EMA21 : {result['ema21']:.5f}")
        print(f"📊 RSI   : {result['rsi']:.2f}")
        print(f"📊 MACD  : {result['macd']:.4f}")
        print(f"📊 ADX   : {result['adx']:.1f}")
        if 'atr' in result and result['atr'] > 0:
            print(f"📊 ATR   : {result['atr']:.5f}")
        
        if 'stage_scores' in result:
            print("-" * 50)
            print("📊 تفاصيل التقييم:")
            stage_names = {
                'trend': 'الاتجاه (30%)',
                'price_action': 'Price Action (25%)',
                'support_resistance': 'الدعم والمقاومة (20%)',
                'indicators': 'المؤشرات (20%)'
            }
            for stage, score in result['stage_scores'].items():
                print(f"  {stage_names.get(stage, stage)}
