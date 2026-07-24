import requests
import pandas as pd
import ta
import os
import time
from datetime import datetime, timedelta
import json

# ✅ تعيين المفتاح
TWELVE_API = "cd927853f89c420380e0dcb9cecf2846"
NEWS_API = os.environ.get('NEWS_API', '')

# ✅ محاولة استيراد yfinance
try:
    import yfinance as yf
except ImportError:
    yf = None
    print("⚠️ yfinance غير مثبت - سيتم استخدام Twelve Data فقط")

def get_price(pair):
    """الحصول على السعر الحالي"""
    try:
        df = get_candles(pair, interval="1min")
        if df is not None and len(df) > 0:
            return float(df.iloc[-1]["close"])
        return None
    except:
        return None

def get_candles(pair, interval="1min", outputsize=300):
    """جلب بيانات الشموع - تركيز على Twelve Data للذهب"""
    try:
        # ✅ للذهب: استخدام Twelve Data API فقط مع رموز محددة
        if "XAU" in pair.upper() or "GOLD" in pair.upper():
            print(f"🔄 {pair} - جلب من Twelve Data API...")
            
            # ✅ رموز الذهب في Twelve Data
            gold_symbols = [
                "XAU/USD",
                "XAUUSD",
                "GOLD",
                "XAU",
                "FX_IDC:XAUUSD"
            ]
            
            for symbol in gold_symbols:
                print(f"  محاولة الرمز: {symbol}")
                df = get_candles_twelvedata_symbol(symbol, interval, outputsize)
                if df is not None and len(df) >= 50:
                    print(f"✅ تم جلب {pair} بنجاح باستخدام {symbol}")
                    return df
            
            print(f"❌ فشل جلب {pair} من Twelve Data")
            return None
        
        # ✅ للفضة
        if "XAG" in pair.upper() or "SILVER" in pair.upper():
            print(f"🔄 {pair} - جلب من Twelve Data API...")
            
            silver_symbols = [
                "XAG/USD",
                "XAGUSD",
                "SILVER",
                "XAG",
                "FX_IDC:XAGUSD"
            ]
            
            for symbol in silver_symbols:
                print(f"  محاولة الرمز: {symbol}")
                df = get_candles_twelvedata_symbol(symbol, interval, outputsize)
                if df is not None and len(df) >= 50:
                    print(f"✅ تم جلب {pair} بنجاح باستخدام {symbol}")
                    return df
            
            print(f"❌ فشل جلب {pair} من Twelve Data")
            return None
        
        # ✅ باقي الأزواج: Twelve Data أولاً
        print(f"🔄 محاولة جلب {pair} من Twelve Data API...")
        df = get_candles_twelvedata(pair, interval, outputsize)
        
        if df is not None and len(df) >= 50:
            print(f"✅ تم جلب البيانات من Twelve Data API")
            return df
        
        # ✅ Backup: Yahoo Finance (إذا كان مثبتاً)
        if yf is not None:
            print(f"🔄 محاولة جلب {pair} من Yahoo Finance...")
            df = get_candles_yahoo(pair, interval)
            if df is not None and len(df) >= 50:
                print(f"✅ تم جلب البيانات من Yahoo Finance")
                return df
        
        print(f"❌ فشل جلب البيانات لـ {pair} من جميع المصادر")
        return None
        
    except Exception as e:
        print(f"❌ خطأ في get_candles: {e}")
        import traceback
        traceback.print_exc()
        return None

def get_candles_twelvedata_symbol(symbol, interval="1min", outputsize=300):
    """جلب بيانات من Twelve Data API لرمز محدد"""
    try:
        api_key = TWELVE_API
        if not api_key:
            print("⚠️ مفتاح Twelve Data غير موجود")
            return None
        
        # ✅ ترميز الرمز
        encoded_symbol = symbol.replace("/", "%2F").replace(":", "%3A")
        url = f"https://api.twelvedata.com/time_series?symbol={encoded_symbol}&interval={interval}&outputsize={outputsize}&apikey={api_key}"
        
        print(f"  📡 جلب من: {url[:80]}...")
        
        response = requests.get(url, timeout=15)
        data = response.json()
        
        # ✅ التحقق من وجود بيانات
        if "values" in data and data["values"] and len(data["values"]) > 0:
            print(f"  ✅ تم جلب {len(data['values'])} شمعة")
            
            df = pd.DataFrame(data["values"])
            
            # تحويل الأعمدة
            for col in ["open", "high", "low", "close", "volume"]:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            
            df = df.dropna(subset=["open", "high", "low", "close"])
            
            if len(df) >= 50:
                # عكس الترتيب (الأحدث أولاً)
                df = df.iloc[::-1].reset_index(drop=True)
                
                # عرض آخر سعر للتحقق
                latest_price = df.iloc[-1]['close']
                print(f"  ✅ آخر سعر: {latest_price:.2f}")
                return df
            else:
                print(f"  ⚠️ بيانات غير كافية: {len(df)} شمعة فقط")
        elif "status" in data and data["status"] == "error":
            print(f"  ⚠️ خطأ: {data.get('message', '')}")
        else:
            print(f"  ⚠️ لا توجد بيانات")
        
        return None
        
    except Exception as e:
        print(f"  ❌ خطأ: {e}")
        return None

def get_candles_twelvedata(pair, interval="1min", outputsize=300):
    """جلب بيانات من Twelve Data API - للأزواج العادية"""
    try:
        api_key = TWELVE_API
        if not api_key:
            print("⚠️ مفتاح Twelve Data غير موجود")
            return None
        
        # ✅ قائمة الرموز للمحاولة
        symbols_to_try = [
            pair,
            pair.replace("/", ""),
            pair.replace("/", "").upper(),
            pair.split("/")[0] + pair.split("/")[1],
        ]
        
        # رموز خاصة
        pair_upper = pair.upper()
        if "BTC" in pair_upper:
            symbols_to_try.extend(["BTCUSD", "BTC/USD"])
        if "ETH" in pair_upper:
            symbols_to_try.extend(["ETHUSD", "ETH/USD"])
        
        symbols_to_try = list(dict.fromkeys(symbols_to_try))
        
        for symbol in symbols_to_try[:10]:
            df = get_candles_twelvedata_symbol(symbol, interval, outputsize)
            if df is not None:
                return df
        
        return None
        
    except Exception as e:
        print(f"❌ خطأ في Twelve Data: {e}")
        return None

def get_candles_yahoo(pair, interval="1min"):
    """جلب بيانات من Yahoo Finance (احتياطي)"""
    try:
        if yf is None:
            return None
        
        # خريطة الرموز
        symbol_map = {
            "EUR/USD": "EURUSD=X",
            "GBP/USD": "GBPUSD=X",
            "USD/JPY": "USDJPY=X",
            "AUD/USD": "AUDUSD=X",
            "NZD/USD": "NZDUSD=X",
            "EUR/JPY": "EURJPY=X",
            "GBP/JPY": "GBPJPY=X",
            "AUD/JPY": "AUDJPY=X",
            "NZD/JPY": "NZDJPY=X",
        }
        
        symbol = symbol_map.get(pair)
        if not symbol:
            if "/" in pair:
                base, quote = pair.split("/")
                symbol = f"{base}{quote}=X"
            else:
                symbol = pair
        
        print(f"📌 رمز Yahoo: {symbol}")
        
        # تحويل الفاصل الزمني
        interval_map = {
            "1min": "1m",
            "5min": "5m",
            "15min": "15m",
            "1h": "60m",
            "1d": "1d"
        }
        yf_interval = interval_map.get(interval, "1m")
        
        # محاولات متعددة
        for attempt in range(3):
            try:
                ticker = yf.Ticker(symbol)
                df = ticker.history(period="7d", interval=yf_interval)
                
                if df is not None and len(df) > 0:
                    df = df.rename(columns={
                        'Open': 'open',
                        'High': 'high',
                        'Low': 'low',
                        'Close': 'close',
                        'Volume': 'volume'
                    })
                    df = df.dropna(subset=['open', 'high', 'low', 'close'])
                    
                    if len(df) >= 50:
                        df = df.iloc[::-1].reset_index(drop=True)
                        print(f"✅ Yahoo: {len(df)} شمعة")
                        return df
                
                time.sleep(1)
                
            except Exception as e:
                print(f"⚠️ محاولة {attempt+1} فشلت: {e}")
                time.sleep(2)
        
        return None
        
    except Exception as e:
        print(f"❌ خطأ في Yahoo: {e}")
        return None

def check_data_availability(pair):
    """التحقق من توفر البيانات"""
    try:
        print(f"🔍 جاري التحقق من توفر البيانات لـ {pair}...")
        df = get_candles(pair, interval="5min", outputsize=50)
        
        if df is not None and len(df) > 0:
            latest_price = df.iloc[-1]['close']
            print(f"✅ البيانات متوفرة - آخر سعر: {latest_price:.2f}")
            return True
        else:
            print(f"❌ البيانات غير متوفرة")
            return False
            
    except Exception as e:
        print(f"❌ خطأ: {e}")
        return False

# =============================================
# باقي الدوال (نفس الكود السابق)
# =============================================

def market_filter(df, last, atr_percent):
    """المرحلة 1: فلترة السوق"""
    reasons = []
    passed = True
    failed_reasons = []
    
    if last["adx"] < 25:
        msg = f"⚠️ ADX ضعيف: {last['adx']:.1f} (يحتاج ≥ 25)"
        reasons.append(msg)
        failed_reasons.append(msg)
        passed = False
    
    if atr_percent < 0.0008:
        msg = f"⚠️ التقلب منخفض: ATR {atr_percent:.4%} من السعر (يحتاج ≥ 0.08%)"
        reasons.append(msg)
        failed_reasons.append(msg)
        passed = False
    
    avg_body = (df["close"] - df["open"]).abs().tail(10).mean()
    body = abs(last["close"] - last["open"])
    if body > avg_body * 2:
        msg = f"⚠️ شمعة انفجارية: الجسم {body:.5f} > {avg_body * 2:.5f}"
        reasons.append(msg)
        failed_reasons.append(msg)
        passed = False
    
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

def check_news_impact(pair):
    """التحقق من وجود أخبار اقتصادية مؤثرة"""
    try:
        if "/" in pair:
            base_currency, quote_currency = pair.split("/")
        else:
            base_currency = pair[:3]
            quote_currency = pair[3:6]
        
        major_currencies = ["USD", "EUR", "GBP", "JPY", "AUD", "CAD", "CHF", "NZD"]
        
        news_keywords = []
        if base_currency in major_currencies:
            news_keywords.append(base_currency)
        if quote_currency in major_currencies:
            news_keywords.append(quote_currency)
        
        if "XAU" in pair or "GOLD" in pair:
            news_keywords.append("GOLD")
        
        if not news_keywords:
            return True
        
        if NEWS_API:
            for keyword in news_keywords:
                url = f"https://newsapi.org/v2/everything?q={keyword}&apiKey={NEWS_API}&language=en&pageSize=5"
                try:
                    response = requests.get(url, timeout=5)
                    if response.status_code == 200:
                        data = response.json()
                        if data.get("totalResults", 0) > 0:
                            for article in data.get("articles", [])[:3]:
                                title = article.get("title", "").lower()
                                if any(word in title for word in ["emergency", "urgent", "breaking", "shock", "surprise"]):
                                    print(f"⚠️ خبر عاجل لـ {keyword}: {article.get('title')}")
                                    return False
                except:
                    pass
        
        return True
        
    except Exception as e:
        print(f"⚠️ خطأ في فحص الأخبار: {e}")
        return True

def volume_filter(df, last):
    """التحقق من حجم التداول"""
    try:
        if "volume" not in df.columns:
            return True, "⚠️ لا توجد بيانات حجم"
        
        avg_volume = df["volume"].tail(20).mean()
        current_volume = last["volume"]
        
        if current_volume < avg_volume * 0.7:
            return False, f"⚠️ حجم التداول منخفض: {current_volume:.0f} < {avg_volume * 0.7:.0f}"
        
        return True, f"✅ حجم التداول جيد: {current_volume:.0f} > {avg_volume * 0.7:.0f}"
        
    except Exception as e:
        return True, f"⚠️ خطأ في فحص الحجم: {e}"

def wait_for_candle_close(df):
    """التحقق من أن الشمعة قاربت على الإغلاق"""
    try:
        current_time = datetime.now()
        seconds_remaining = 60 - current_time.second
        if seconds_remaining > 30:
            return False, f"⏳ انتظر {seconds_remaining} ثانية لإغلاق الشمعة"
        
        return True, "✅ الشمعة جاهزة للإغلاق"
        
    except:
        return True, "⚠️ لا يمكن التحقق من وقت الشمعة"

def enhanced_price_action_analysis(df, last):
    """تحليل Price Action محسن"""
    reasons = []
    pattern = None
    score = 0
    max_score = 7
    
    if len(df) >= 5:
        prev = df.iloc[-2]
        current = last
        
        body = abs(current["close"] - current["open"])
        upper_shadow = current["high"] - max(current["open"], current["close"])
        lower_shadow = min(current["open"], current["close"]) - current["low"]
        total_range = current["high"] - current["low"]
        
        if (prev["close"] < prev["open"] and
            current["close"] > current["open"] and
            current["open"] < prev["close"] and
            current["close"] > prev["open"]):
            pattern = "BULLISH_ENGULFING"
            score = 7
            reasons.append("✅ Bullish Engulfing - نمط انعكاس صاعد قوي")
        
        elif (prev["close"] > prev["open"] and
              current["close"] < current["open"] and
              current["open"] > prev["close"] and
              current["close"] < prev["open"]):
            pattern = "BEARISH_ENGULFING"
            score = 7
            reasons.append("✅ Bearish Engulfing - نمط انعكاس هابط قوي")
        
        elif total_range > 0:
            if lower_shadow > body * 2 and upper_shadow < body * 0.5:
                pattern = "BULLISH_PIN_BAR"
                score = 6
                reasons.append(f"✅ Bullish Pin Bar - ظل سفلي {lower_shadow:.5f} > {body * 2:.5f}")
            
            elif upper_shadow > body * 2 and lower_shadow < body * 0.5:
                pattern = "BEARISH_PIN_BAR"
                score = 6
                reasons.append(f"✅ Bearish Pin Bar - ظل علوي {upper_shadow:.5f} > {body * 2:.5f}")
        
        if (prev["high"] > current["high"] and prev["low"] < current["low"]):
            if not pattern:
                pattern = "INSIDE_BAR"
                score = max(score, 4)
                reasons.append("✅ Inside Bar - شمعة داخل نطاق سابق")
        
        resistance = df.iloc[:-1]["high"].tail(5).max()
        support = df.iloc[:-1]["low"].tail(5).min()
        
        if current["close"] > resistance and current["close"] > current["open"]:
            if not pattern or score < 5:
                pattern = "BREAKOUT_BULLISH"
                score = max(score, 5)
                reasons.append(f"✅ اختراق مقاومة: {current['close']:.5f} > {resistance:.5f}")
        
        elif current["close"] < support and current["close"] < current["open"]:
            if not pattern or score < 5:
                pattern = "BREAKOUT_BEARISH"
                score = max(score, 5)
                reasons.append(f"✅ اختراق دعم: {current['close']:.5f} < {support:.5f}")
    
    return pattern, score, max_score, reasons

def enhanced_trend_analysis(df, last, atr):
    """تحليل الاتجاه المحسن"""
    reasons = []
    score = 0
    max_score = 6
    
    if last["ema9"] > last["ema21"]:
        score += 1
        reasons.append(f"✅ EMA9 ({last['ema9']:.5f}) > EMA21 ({last['ema21']:.5f})")
    else:
        reasons.append(f"✅ EMA9 ({last['ema9']:.5f}) < EMA21 ({last['ema21']:.5f})")
    
    ema21_slope = df["ema21"].diff().tail(5).mean()
    if ema21_slope > 0:
        score += 1
        reasons.append(f"✅ EMA21 صاعد: {ema21_slope:.5f}")
    else:
        reasons.append(f"✅ EMA21 هابط: {ema21_slope:.5f}")
    
    if last["close"] > last["ema21"]:
        score += 1
        reasons.append(f"✅ السعر ({last['close']:.5f}) > EMA21 ({last['ema21']:.5f})")
    else:
        reasons.append(f"✅ السعر ({last['close']:.5f}) < EMA21 ({last['ema21']:.5f})")
    
    ema_diff = abs(last["ema9"] - last["ema21"])
    atr_ratio = ema_diff / atr if atr > 0 else 0
    if atr_ratio >= 0.3:
        score += 1
        reasons.append(f"✅ فرق EMA ({ema_diff:.5f}) = {atr_ratio:.1%} من ATR")
    else:
        reasons.append(f"⚠️ فرق EMA صغير: {atr_ratio:.1%} من ATR")
    
    if "ema100" in df.columns:
        if last["ema21"] > last["ema100"]:
            score += 1
            reasons.append(f"✅ EMA21 ({last['ema21']:.5f}) > EMA100 ({last['ema100']:.5f})")
        else:
            reasons.append(f"✅ EMA21 ({last['ema21']:.5f}) < EMA100 ({last['ema100']:.5f})")
    
    if "ema200" in df.columns:
        if last["ema21"] > last["ema200"]:
            score += 1
            reasons.append(f"✅ EMA21 ({last['ema21']:.5f}) > EMA200 ({last['ema200']:.5f})")
        else:
            reasons.append(f"✅ EMA21 ({last['ema21']:.5f}) < EMA200 ({last['ema200']:.5f})")
    
    if score >= 4:
        direction = "BULLISH" if last["ema9"] > last["ema21"] else "BEARISH"
    else:
        direction = "NEUTRAL"
    
    return direction, score, max_score, reasons

def bollinger_width_filter(df, last):
    """فلتر عرض البولينجر"""
    try:
        if "bb_high" not in df.columns or "bb_low" not in df.columns:
            return True, "⚠️ لا توجد بيانات بولينجر"
        
        bb_width = (last["bb_high"] - last["bb_low"]) / last["bb_mid"]
        avg_width = ((df["bb_high"] - df["bb_low"]) / df["bb_mid"]).tail(20).mean()
        
        if bb_width > avg_width * 1.5:
            return False, f"⚠️ عرض البولينجر كبير: {bb_width:.2%} > {avg_width * 1.5:.2%}"
        
        return True, f"✅ عرض البولينجر طبيعي: {bb_width:.2%}"
        
    except Exception as e:
        return True, f"⚠️ خطأ في فحص البولينجر: {e}"

def stochastic_rsi_confirmation(df, last, direction):
    """تأكيد الزخم باستخدام Stochastic و RSI"""
    reasons = []
    score = 0
    max_score = 3
    
    try:
        stoch = ta.momentum.StochasticOscillator(
            high=df["high"],
            low=df["low"],
            close=df["close"],
            window=14,
            smooth_window=3
        )
        stoch_k = stoch.stoch()
        stoch_d = stoch.stoch_signal()
        
        if len(stoch_k) == 0 or len(stoch_d) == 0:
            return 0, max_score, ["⚠️ لا توجد بيانات Stochastic كافية"]
        
        current_k = stoch_k.iloc[-1]
        current_d = stoch_d.iloc[-1]
        
        if pd.isna(current_k) or pd.isna(current_d):
            return 0, max_score, ["⚠️ قيم Stochastic غير صالحة"]
        
        if direction == "BULLISH":
            if current_k > 20 and current_k < 80 and current_k > current_d:
                score += 1.5
                reasons.append(f"✅ Stochastic صاعد: K={current_k:.1f} > D={current_d:.1f}")
            elif current_k < 20:
                score += 1
                reasons.append(f"⚠️ Stochastic في منطقة ذروة البيع: K={current_k:.1f}")
            else:
                reasons.append(f"⚠️ Stochastic غير داعم: K={current_k:.1f}")
        else:
            if current_k < 80 and current_k > 20 and current_k < current_d:
                score += 1.5
                reasons.append(f"✅ Stochastic هابط: K={current_k:.1f} < D={current_d:.1f}")
            elif current_k > 80:
                score += 1
                reasons.append(f"⚠️ Stochastic في منطقة ذروة الشراء: K={current_k:.1f}")
            else:
                reasons.append(f"⚠️ Stochastic غير داعم: K={current_k:.1f}")
        
        if direction == "BULLISH" and 55 <= last["rsi"] <= 70:
            score += 0.5
            reasons.append(f"✅ RSI متوافق: {last['rsi']:.1f}")
        elif direction == "BEARISH" and 30 <= last["rsi"] <= 45:
            score += 0.5
            reasons.append(f"✅ RSI متوافق: {last['rsi']:.1f}")
        
        return score, max_score, reasons
        
    except Exception as e:
        return 0, max_score, [f"⚠️ خطأ في Stochastic: {e}"]

def supertrend_filter(df, last, direction):
    """فلتر SuperTrend للتأكيد على الاتجاه"""
    try:
        atr_indicator = ta.volatility.AverageTrueRange(
            high=df["high"],
            low=df["low"],
            close=df["close"],
            window=10
        )
        atr_values = atr_indicator.average_true_range()
        
        if len(atr_values) < 2:
            return True, "⚠️ بيانات ATR غير كافية لـ SuperTrend"
        
        multiplier = 3
        upper_band = (df["high"] + df["low"]) / 2 + multiplier * atr_values
        lower_band = (df["high"] + df["low"]) / 2 - multiplier * atr_values
        
        supertrend = pd.Series(1, index=df.index)
        for i in range(1, len(df)):
            try:
                if df.iloc[i]["close"] > upper_band.iloc[i-1]:
                    supertrend.iloc[i] = 1
                elif df.iloc[i]["close"] < lower_band.iloc[i-1]:
                    supertrend.iloc[i] = -1
                else:
                    supertrend.iloc[i] = supertrend.iloc[i-1]
            except:
                supertrend.iloc[i] = supertrend.iloc[i-1]
        
        last_supertrend = supertrend.iloc[-1]
        
        if direction == "BULLISH" and last_supertrend == 1:
            return True, "✅ SuperTrend صاعد"
        elif direction == "BEARISH" and last_supertrend == -1:
            return True, "✅ SuperTrend هابط"
        else:
            return False, f"⚠️ SuperTrend غير متوافق: {last_supertrend}"
        
    except Exception as e:
        return True, f"⚠️ خطأ في SuperTrend: {e}"

def multi_timeframe_analysis(pair):
    """تحليل متعدد الفريمات"""
    try:
        # ✅ جلب بيانات 5 دقائق
        df_5m = get_candles(pair, interval="5min", outputsize=200)
        if df_5m is None or len(df_5m) < 50:
            print("❌ فشل جلب بيانات 5 دقائق")
            return None, None, None
        
        print(f"📊 تم جلب {len(df_5m)} شمعة لـ 5 دقائق")
        
        # حساب المؤشرات لـ 5 دقائق
        df_5m["ema21"] = ta.trend.EMAIndicator(close=df_5m["close"], window=21).ema_indicator()
        df_5m["ema50"] = ta.trend.EMAIndicator(close=df_5m["close"], window=50).ema_indicator()
        df_5m["ema100"] = ta.trend.EMAIndicator(close=df_5m["close"], window=100).ema_indicator()
        df_5m["ema200"] = ta.trend.EMAIndicator(close=df_5m["close"], window=200).ema_indicator()
        
        adx = ta.trend.ADXIndicator(high=df_5m["high"], low=df_5m["low"], close=df_5m["close"], window=14)
        df_5m["adx"] = adx.adx()
        
        df_5m = df_5m.dropna()
        
        if len(df_5m) == 0:
            print("❌ بيانات 5 دقائق غير صالحة بعد الحسابات")
            return None, None, None
        
        last_5m = df_5m.iloc[-1]
        
        # ✅ تخفيف شروط الاتجاه
        is_bullish = (
            last_5m["ema21"] > last_5m["ema50"] and
            last_5m["ema50"] > last_5m["ema100"] and
            last_5m["adx"] >= 20
        )
        
        is_bearish = (
            last_5m["ema21"] < last_5m["ema50"] and
            last_5m["ema50"] < last_5m["ema100"] and
            last_5m["adx"] >= 20
        )
        
        if is_bullish:
            direction_5m = "BULLISH"
        elif is_bearish:
            direction_5m = "BEARISH"
        else:
            direction_5m = "NEUTRAL"
        
        print(f"📊 اتجاه 5 دقائق: {direction_5m} (ADX: {last_5m['adx']:.1f})")
        
        # ✅ جلب بيانات 1 دقيقة
        df_1m = get_candles(pair, interval="1min", outputsize=200)
        if df_1m is None or len(df_1m) < 50:
            print("❌ فشل جلب بيانات 1 دقيقة")
            return None, None, None
        
        print(f"📊 تم جلب {len(df_1m)} شمعة لـ 1 دقيقة")
        
        return df_1m, df_5m, direction_5m
        
    except Exception as e:
        print(f"❌ خطأ في التحليل متعدد الفريمات: {e}")
        import traceback
        traceback.print_exc()
        return None, None, None

# =============================================
# الدالة الرئيسية
# =============================================
def analyze_market(pair):
    """تحليل السوق باستخدام جميع الفلاتر المحسنة"""
    try:
        print(f"\n{'=' * 50}")
        print(f"🔍 جاري تحليل الزوج: {pair}")
        print(f"{'=' * 50}")
        
        # ✅ التحقق من توفر البيانات
        if not check_data_availability(pair):
            print(f"❌ البيانات غير متوفرة لـ {pair}")
            return None
        
        print("\n📰 فحص الأخبار الاقتصادية...")
        if not check_news_impact(pair):
            print("❌ توجد أخبار مؤثرة - انتظار")
            return {
                "signal": "WAIT",
                "strength": 0,
                "duration": 0,
                "price": 0,
                "reason": "توجد أخبار اقتصادية مؤثرة - انتظار",
                "timestamp": datetime.now().isoformat(),
                "pair": pair
            }
        print("✅ لا توجد أخبار مؤثرة")
        
        print("\n📊 التحليل متعدد الفريمات...")
        df, df_5m, direction_5m = multi_timeframe_analysis(pair)
        
        if df is None:
            print(f"❌ فشل جلب البيانات لـ {pair}")
            return None
        
        if len(df) < 50:
            print(f"❌ بيانات غير كافية: {len(df)} شمعة فقط")
            return None
        
        if direction_5m == "NEUTRAL":
            print("⚠️ اتجاه 5 دقائق محايد - انتظار")
            return {
                "signal": "WAIT",
                "strength": 0,
                "duration": 0,
                "price": float(df.iloc[-1]["close"]),
                "reason": "اتجاه 5 دقائق محايد",
                "timestamp": datetime.now().isoformat(),
                "pair": pair
            }
        
        print(f"✅ اتجاه 5 دقائق: {direction_5m}")
        
        print("\n⏳ التحقق من إغلاق الشمعة...")
        candle_ready, candle_msg = wait_for_candle_close(df)
        if not candle_ready:
            print(f"❌ {candle_msg}")
            return {
                "signal": "WAIT",
                "strength": 0,
                "duration": 0,
                "price": float(df.iloc[-1]["close"]),
                "reason": candle_msg,
                "timestamp": datetime.now().isoformat(),
                "pair": pair
            }
        print(f"✅ {candle_msg}")
        
        print("🔄 حساب المؤشرات الفنية...")
        try:
            df["ema9"] = ta.trend.EMAIndicator(close=df["close"], window=9).ema_indicator()
            df["ema21"] = ta.trend.EMAIndicator(close=df["close"], window=21).ema_indicator()
            df["ema100"] = ta.trend.EMAIndicator(close=df["close"], window=100).ema_indicator()
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
        atr_percent = last["atr"] / last["close"] if last["close"] > 0 else 0
        
        print(f"\n📊 آخر سعر: {last['close']:.5f}")
        print(f"📊 ADX: {last['adx']:.2f}")
        print(f"📊 RSI: {last['rsi']:.2f}")
        print(f"📊 ATR%: {atr_percent:.4%}")
        
        all_reasons = []
        failed_reasons = []
        
        print("\n🔍 المرحلة 1: فلترة السوق")
        
        filter_passed, filter_reasons, failed = market_filter(df, last, atr_percent)
        
        volume_ok, volume_msg = volume_filter(df, last)
        filter_reasons.append(volume_msg)
        if not volume_ok:
            failed.append(volume_msg)
            filter_passed = False
        
        bb_ok, bb_msg = bollinger_width_filter(df, last)
        filter_reasons.append(bb_msg)
        if not bb_ok:
            failed.append(bb_msg)
            filter_passed = False
        
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
        
        print("\n🔍 المرحلة 2: تحديد الاتجاه (وزن 30%)")
        direction, trend_score, trend_max, trend_reasons = enhanced_trend_analysis(df, last, last["atr"])
        
        for reason in trend_reasons:
            print(f"  {reason}")
        
        print(f"📊 نقاط الاتجاه: {trend_score}/{trend_max}")
        all_reasons.extend(trend_reasons)
        
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
                "atr": round(last["atr"], 5) if not pd.isna(last["atr"]) else 0,
                "reason": "الاتجاه غير واضح (نقاط الاتجاه منخفضة)",
                "timestamp": datetime.now().isoformat(),
                "pair": pair
            }
        
        print(f"✅ الاتجاه: {direction}")
        
        print("\n🔍 المرحلة 3: تحليل Price Action (وزن 25%)")
        pattern, pa_score, pa_max, pa_reasons = enhanced_price_action_analysis(df, last)
        
        for reason in pa_reasons:
            print(f"  {reason}")
        
        print(f"📊 نقاط Price Action: {pa_score}/{pa_max}")
        all_reasons.extend(pa_reasons)
        
        print("\n🔍 المرحلة 4: تأكيد Stochastic و RSI")
        stoch_score, stoch_max, stoch_reasons = stochastic_rsi_confirmation(df, last, direction)
        
        for reason in stoch_reasons:
            print(f"  {reason}")
        
        print(f"📊 نقاط Stochastic: {stoch_score:.1f}/{stoch_max}")
        all_reasons.extend(stoch_reasons)
        
        print("\n🔍 المرحلة 5: فلتر SuperTrend")
        st_ok, st_msg = supertrend_filter(df, last, direction)
        print(f"  {st_msg}")
        all_reasons.append(st_msg)
        
        if not st_ok:
            print("❌ SuperTrend غير متوافق")
            return {
                "signal": "WAIT",
                "strength": 0,
                "duration": 0,
                "price": float(last["close"]),
                "reason": "SuperTrend غير متوافق مع الاتجاه",
                "timestamp": datetime.now().isoformat(),
                "pair": pair
            }
        
        print("\n📊 حساب قوة الإشارة النهائية...")
        
        total_weight = 30 + 25 + 15 + 15 + 15
        weighted_score = (
            (trend_score / trend_max) * 30 +
            (pa_score / pa_max) * 25 +
            (stoch_score / stoch_max) * 15 +
            15 +
            15
        )
        
        strength_percent = (weighted_score / total_weight) * 100
        
        print(f"📊 قوة الإشارة: {strength_percent:.1f}%")
        
        if strength_percent >= 70:
            signal = "BUY" if direction == "BULLISH" else "SELL"
            duration = 15
            strength_text = "قوية جداً"
        elif strength_percent >= 55:
            signal = "BUY" if direction == "BULLISH" else "SELL"
            duration = 10
            strength_text = "متوسطة"
        else:
            signal = "WAIT"
            duration = 0
            strength_text = "ضعيفة"
        
        print(f"✅ الإشارة النهائية: {signal} (القوة: {strength_text})")
        
        result = {
            "signal": signal,
            "strength": round(strength_percent),
            "duration": duration,
            "price": float(last["close"]),
            "ema9": round(last["ema9"], 5),
            "ema21": round(last["ema21"], 5),
            "ema100": round(last["ema100"], 5) if "ema100" in df.columns else None,
            "ema200": round(last["ema200"], 5) if "ema200" in df.columns else None,
            "rsi": round(last["rsi"], 2),
            "macd": round(last["macd"], 5),
            "macd_signal": round(last["macd_signal"], 5),
            "adx": round(last["adx"], 2),
            "atr": round(last["atr"], 5),
            "direction": direction,
            "direction_5m": direction_5m,
            "pattern": pattern,
            "trend_score": f"{trend_score}/{trend_max}",
            "pa_score": f"{pa_score}/{pa_max}",
            "stoch_score": f"{stoch_score:.1f}/{stoch_max}",
            "reason": "\n".join(all_reasons),
            "timestamp": datetime.now().isoformat(),
            "pair": pair
        }
        
        print(f"\n📊 النتيجة النهائية:")
        print(f"  - الزوج: {pair}")
        print(f"  - الإشارة: {signal}")
        print(f"  - القوة: {strength_percent:.1f}%")
        print(f"  - المدة: {duration} دقيقة")
        print(f"  - السعر: {last['close']:.5f}")
        print(f"{'=' * 50}\n")
        
        return result

    except Exception as e:
        print(f"❌ خطأ في analyze_market: {e}")
        import traceback
        traceback.print_exc()
        return None

# =============================================
# دالة الاختبار
# =============================================
if __name__ == "__main__":
    # ✅ اختبار الأزواج المختلفة
    test_pairs = [
        "XAU/USD",    # الذهب
        "EUR/USD",    # يورو دولار
        "GBP/JPY",    # باوند ين
        "NZD/JPY",    # نيوزيلندي ين
    ]
    
    for pair in test_pairs:
        print(f"\n{'=' * 60}")
        print(f"🧪 اختبار تحليل الزوج: {pair}")
        print(f"{'=' * 60}")
        
        result = analyze_market(pair)
        
        if result:
            print(f"\n✅ نجح تحليل {pair}")
            print(f"   الإشارة: {result['signal']}")
            print(f"   القوة: {result['strength']}%")
            print(f"   السعر: {result['price']}")
            if result['signal'] != 'WAIT':
                print(f"   ✅ صفقة محتملة! المدة: {result['duration']} دقيقة")
            else:
                print(f"   ⏳ انتظار - لا توجد إشارة حالياً")
        else:
            print(f"\n❌ فشل تحليل {pair}")
