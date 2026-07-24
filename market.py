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

# ✅ إعدادات التنبيه (ضع التوكن هنا)
TELEGRAM_BOT_TOKEN = ""  # ضع توكن البوت هنا من @BotFather
TELEGRAM_CHAT_ID = ""    # ضع معرف الدردشة هنا من @userinfobot

# ✅ تثبيت yfinance
try:
    import yfinance as yf
except ImportError:
    print("⚠️ جاري تثبيت yfinance...")
    os.system('pip install yfinance')
    import yfinance as yf

# =============================================
# ✅ متغيرات التحكم في عدد الصفقات
# =============================================
DAILY_TARGET = 5  # هدف 5 صفقات يومياً
trades_today = 0
last_trade_date = datetime.now().date()
trades_history = []

def can_trade():
    """التحقق من إمكانية الدخول في صفقة جديدة"""
    global trades_today, last_trade_date, trades_history
    
    today = datetime.now().date()
    
    # ✅ إعادة تعيين العداد كل يوم جديد
    if today != last_trade_date:
        trades_today = 0
        last_trade_date = today
        print(f"\n📅 يوم جديد! تم إعادة تعيين العداد")
    
    # ✅ التحقق من عدم تجاوز الهدف اليومي
    if trades_today >= DAILY_TARGET:
        print(f"⏸ تم تحقيق الهدف اليومي ({DAILY_TARGET} صفقات)")
        return False
    
    return True

def record_trade(result):
    """تسجيل صفقة جديدة"""
    global trades_today, trades_history
    
    trades_today += 1
    trades_history.append({
        'time': datetime.now().isoformat(),
        'pair': result['pair'],
        'signal': result['signal'],
        'price': result['price'],
        'strength': result['strength']
    })
    
    print(f"\n✅ تم تسجيل الصفقة رقم {trades_today}/{DAILY_TARGET}")
    print(f"📊 متبقي {DAILY_TARGET - trades_today} صفقات لليوم")

# =============================================
# ✅ دوال التنبيه
# =============================================
def send_telegram_alert(result):
    """إرسال تنبيه عبر تلغرام"""
    try:
        if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
            print("⚠️ لم يتم تعيين توكن تلغرام")
            print("📌 اذهب إلى @BotFather في تلغرام لإنشاء بوت")
            print("📌 ثم اذهب إلى @userinfobot للحصول على Chat ID")
            return False
        
        emoji = "🟢" if result['signal'] == "BUY" else "🔴" if result['signal'] == "SELL" else "⏸"
        
        message = f"""
{emoji} *إشارة تداول جديدة!*

💱 *الزوج:* {result['pair']}
💰 *السعر:* {result['price']:.5f}
📈 *الإشارة:* {result['signal']}
💪 *القوة:* {result['strength']}%
⏱ *المدة:* {result['duration']} دقيقة

📊 *المؤشرات:*
• RSI: {result.get('rsi', 'N/A')}
• ADX: {result.get('adx', 'N/A')}
• نمط: {result.get('pattern', 'لا يوجد')}

📝 *السبب:* 
{result['reason'][:200]}

📅 *الصفقة رقم:* {trades_today}/{DAILY_TARGET}
⏰ *الوقت:* {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

⚠️ هذا ليس نصيحة استثمارية
        """
        
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            'chat_id': TELEGRAM_CHAT_ID,
            'text': message,
            'parse_mode': 'Markdown'
        }
        
        response = requests.post(url, json=payload, timeout=10)
        
        if response.status_code == 200:
            print("✅ تم إرسال التنبيه إلى تلغرام")
            return True
        else:
            print(f"❌ فشل إرسال التنبيه: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ خطأ في إرسال التنبيه: {e}")
        return False

def save_signal_to_file(result):
    """حفظ الإشارة في ملف"""
    try:
        filename = "trading_signals.json"
        signals = []
        if os.path.exists(filename):
            with open(filename, 'r') as f:
                try:
                    signals = json.load(f)
                except:
                    signals = []
        
        signals.append(result)
        
        with open(filename, 'w') as f:
            json.dump(signals, f, indent=2)
        
        return True
        
    except Exception as e:
        print(f"❌ خطأ في حفظ الإشارة: {e}")
        return False

# =============================================
# ✅ دوال جلب البيانات
# =============================================
def get_price(pair):
    try:
        df = get_candles(pair, interval="1min")
        if df is not None and len(df) > 0:
            return float(df.iloc[-1]["close"])
        return None
    except:
        return None

def get_candles(pair, interval="1min", outputsize=150):
    """جلب بيانات - حجم أقل للسرعة"""
    try:
        metals = ["XAU", "GOLD", "XAG", "SILVER"]
        is_metal = any(metal in pair.upper() for metal in metals)
        
        if is_metal:
            symbols = ["XAU/USD", "XAUUSD", "GOLD"] if "XAU" in pair.upper() else ["XAG/USD", "XAGUSD", "SILVER"]
            for symbol in symbols:
                df = get_candles_twelvedata_symbol(symbol, interval, outputsize)
                if df is not None and len(df) >= 30:
                    return df
            return None
        
        df = get_candles_twelvedata(pair, interval, outputsize)
        if df is not None and len(df) >= 30:
            return df
        
        if yf is not None:
            df = get_candles_yahoo(pair, interval)
            if df is not None and len(df) >= 30:
                return df
        
        return None
        
    except Exception as e:
        print(f"❌ خطأ في get_candles: {e}")
        return None

def get_candles_twelvedata_symbol(symbol, interval="1min", outputsize=150):
    try:
        api_key = TWELVE_API
        if not api_key:
            return None
        
        encoded_symbol = symbol.replace("/", "%2F").replace(":", "%3A")
        url = f"https://api.twelvedata.com/time_series?symbol={encoded_symbol}&interval={interval}&outputsize={outputsize}&apikey={api_key}"
        
        response = requests.get(url, timeout=10)
        data = response.json()
        
        if "values" in data and data["values"] and len(data["values"]) > 0:
            df = pd.DataFrame(data["values"])
            
            for col in ["open", "high", "low", "close", "volume"]:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            
            df = df.dropna(subset=["open", "high", "low", "close"])
            
            if len(df) >= 30:
                df = df.iloc[::-1].reset_index(drop=True)
                return df
        
        return None
        
    except Exception as e:
        return None

def get_candles_twelvedata(pair, interval="1min", outputsize=150):
    try:
        api_key = TWELVE_API
        if not api_key:
            return None
        
        symbols_to_try = [
            pair,
            pair.replace("/", ""),
            pair.replace("/", "").upper(),
            pair.split("/")[0] + pair.split("/")[1],
        ]
        
        symbols_to_try = list(dict.fromkeys(symbols_to_try))
        
        for symbol in symbols_to_try[:5]:
            df = get_candles_twelvedata_symbol(symbol, interval, outputsize)
            if df is not None:
                return df
        
        return None
        
    except Exception as e:
        return None

def get_candles_yahoo(pair, interval="1min"):
    try:
        if yf is None:
            return None
        
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
        
        interval_map = {"1min": "1m", "5min": "5m", "15min": "15m", "1h": "60m", "1d": "1d"}
        yf_interval = interval_map.get(interval, "1m")
        
        for attempt in range(2):
            try:
                ticker = yf.Ticker(symbol)
                df = ticker.history(period="5d", interval=yf_interval)
                
                if df is not None and len(df) > 0:
                    df = df.rename(columns={
                        'Open': 'open',
                        'High': 'high',
                        'Low': 'low',
                        'Close': 'close',
                        'Volume': 'volume'
                    })
                    df = df.dropna(subset=['open', 'high', 'low', 'close'])
                    
                    if len(df) >= 30:
                        df = df.iloc[::-1].reset_index(drop=True)
                        return df
                
                time.sleep(0.5)
                
            except:
                time.sleep(1)
        
        return None
        
    except Exception as e:
        return None

# =============================================
# ✅ دوال التحليل (معدلة - شروط أخف للصفقات)
# =============================================
def check_data_availability(pair):
    try:
        df = get_candles(pair, interval="5min", outputsize=30)
        if df is not None and len(df) > 0:
            return True
        return False
    except:
        return False

def wait_for_candle_close(df):
    """التحقق من أن الشمعة قاربت على الإغلاق"""
    try:
        current_time = datetime.now()
        seconds_remaining = 60 - current_time.second
        if seconds_remaining > 30:
            return False, f"⏳ انتظر {seconds_remaining} ثانية"
        
        return True, "✅ الشمعة جاهزة"
        
    except:
        return True, "⚠️ لا يمكن التحقق"

def market_filter(df, last, atr_percent):
    """فلترة السوق - شروط مخففة"""
    reasons = []
    passed = True
    failed_reasons = []
    
    # ✅ خفض ADX من 25 إلى 20
    if last["adx"] < 20:
        msg = f"⚠️ ADX ضعيف: {last['adx']:.1f} (يحتاج ≥ 20)"
        reasons.append(msg)
        failed_reasons.append(msg)
        passed = False
    
    # ✅ خفض ATR من 0.08% إلى 0.05%
    if atr_percent < 0.0005:
        msg = f"⚠️ التقلب منخفض: ATR {atr_percent:.4%} (يحتاج ≥ 0.05%)"
        reasons.append(msg)
        failed_reasons.append(msg)
        passed = False
    
    avg_body = (df["close"] - df["open"]).abs().tail(10).mean()
    body = abs(last["close"] - last["open"])
    if body > avg_body * 2.5:
        msg = f"⚠️ شمعة انفجارية"
        reasons.append(msg)
        failed_reasons.append(msg)
        passed = False
    
    candle_range = last["high"] - last["low"]
    avg_range = (df["high"] - df["low"]).tail(20).mean()
    if candle_range > avg_range * 2:
        msg = f"⚠️ تذبذب قوي"
        reasons.append(msg)
        failed_reasons.append(msg)
        passed = False
    
    if passed:
        reasons.append("✅ اجتازت فلترة السوق")
    
    return passed, reasons, failed_reasons

def check_news_impact(pair):
    """تجاهل الأخبار لتسريع العملية"""
    return True

def volume_filter(df, last):
    """تخفيف شرط الحجم"""
    try:
        if "volume" not in df.columns:
            return True, "⚠️ لا توجد بيانات حجم"
        
        avg_volume = df["volume"].tail(20).mean()
        current_volume = last["volume"]
        
        if current_volume < avg_volume * 0.5:
            return False, f"⚠️ حجم التداول منخفض"
        
        return True, f"✅ حجم التداول جيد"
        
    except Exception as e:
        return True, f"⚠️ خطأ"

def enhanced_price_action_analysis(df, last):
    """تحليل Price Action - معدل"""
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
        
        # أنماط الانعكاس
        if (prev["close"] < prev["open"] and
            current["close"] > current["open"] and
            current["open"] < prev["close"] and
            current["close"] > prev["open"]):
            pattern = "BULLISH_ENGULFING"
            score = 7
            reasons.append("✅ Bullish Engulfing")
        
        elif (prev["close"] > prev["open"] and
              current["close"] < current["open"] and
              current["open"] > prev["close"] and
              current["close"] < prev["open"]):
            pattern = "BEARISH_ENGULFING"
            score = 7
            reasons.append("✅ Bearish Engulfing")
        
        # Pin Bars
        elif total_range > 0:
            if lower_shadow > body * 2 and upper_shadow < body * 0.5:
                pattern = "BULLISH_PIN_BAR"
                score = 6
                reasons.append("✅ Bullish Pin Bar")
            
            elif upper_shadow > body * 2 and lower_shadow < body * 0.5:
                pattern = "BEARISH_PIN_BAR"
                score = 6
                reasons.append("✅ Bearish Pin Bar")
        
        # Inside Bar
        if (prev["high"] > current["high"] and prev["low"] < current["low"]):
            if not pattern:
                pattern = "INSIDE_BAR"
                score = max(score, 4)
                reasons.append("✅ Inside Bar")
        
        # اختراقات
        resistance = df.iloc[:-1]["high"].tail(5).max()
        support = df.iloc[:-1]["low"].tail(5).min()
        
        if current["close"] > resistance and current["close"] > current["open"]:
            if not pattern or score < 5:
                pattern = "BREAKOUT_BULLISH"
                score = max(score, 5)
                reasons.append(f"✅ اختراق مقاومة")
        
        elif current["close"] < support and current["close"] < current["open"]:
            if not pattern or score < 5:
                pattern = "BREAKOUT_BEARISH"
                score = max(score, 5)
                reasons.append(f"✅ اختراق دعم")
    
    return pattern, score, max_score, reasons

def enhanced_trend_analysis(df, last, atr):
    """تحليل الاتجاه - معدل"""
    reasons = []
    score = 0
    max_score = 6
    
    if last["ema9"] > last["ema21"]:
        score += 1
        reasons.append(f"✅ EMA9 > EMA21")
    else:
        reasons.append(f"✅ EMA9 < EMA21")
    
    ema21_slope = df["ema21"].diff().tail(5).mean()
    if ema21_slope > 0:
        score += 1
        reasons.append(f"✅ EMA21 صاعد")
    else:
        reasons.append(f"✅ EMA21 هابط")
    
    if last["close"] > last["ema21"]:
        score += 1
        reasons.append(f"✅ السعر > EMA21")
    else:
        reasons.append(f"✅ السعر < EMA21")
    
    ema_diff = abs(last["ema9"] - last["ema21"])
    atr_ratio = ema_diff / atr if atr > 0 else 0
    if atr_ratio >= 0.2:
        score += 1
        reasons.append(f"✅ فرق EMA = {atr_ratio:.1%} من ATR")
    else:
        reasons.append(f"⚠️ فرق EMA صغير")
    
    if "ema100" in df.columns:
        if last["ema21"] > last["ema100"]:
            score += 1
            reasons.append(f"✅ EMA21 > EMA100")
        else:
            reasons.append(f"✅ EMA21 < EMA100")
    
    if "ema200" in df.columns:
        if last["ema21"] > last["ema200"]:
            score += 1
            reasons.append(f"✅ EMA21 > EMA200")
        else:
            reasons.append(f"✅ EMA21 < EMA200")
    
    # ✅ خفض من 4 إلى 3
    if score >= 3:
        direction = "BULLISH" if last["ema9"] > last["ema21"] else "BEARISH"
    else:
        direction = "NEUTRAL"
    
    return direction, score, max_score, reasons

def bollinger_width_filter(df, last):
    """تخفيف شرط البولينجر"""
    try:
        if "bb_high" not in df.columns or "bb_low" not in df.columns:
            return True, "⚠️ لا توجد بيانات"
        
        bb_width = (last["bb_high"] - last["bb_low"]) / last["bb_mid"]
        avg_width = ((df["bb_high"] - df["bb_low"]) / df["bb_mid"]).tail(20).mean()
        
        if bb_width > avg_width * 2:
            return False, f"⚠️ عرض البولينجر كبير"
        
        return True, f"✅ عرض البولينجر طبيعي"
        
    except Exception as e:
        return True, f"⚠️ خطأ"

def stochastic_rsi_confirmation(df, last, direction):
    """تخفيف شرط Stochastic"""
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
            return 0, max_score, ["⚠️ لا توجد بيانات"]
        
        current_k = stoch_k.iloc[-1]
        current_d = stoch_d.iloc[-1]
        
        if pd.isna(current_k) or pd.isna(current_d):
            return 0, max_score, ["⚠️ قيم غير صالحة"]
        
        # شروط مخففة
        if direction == "BULLISH":
            if current_k > 20 and current_k > current_d:
                score += 1.5
                reasons.append(f"✅ Stochastic صاعد")
            elif current_k < 30:
                score += 1
                reasons.append(f"⚠️ منطقة ذروة البيع")
            else:
                reasons.append(f"⚠️ Stochastic غير داعم")
        else:
            if current_k < 80 and current_k < current_d:
                score += 1.5
                reasons.append(f"✅ Stochastic هابط")
            elif current_k > 70:
                score += 1
                reasons.append(f"⚠️ منطقة ذروة الشراء")
            else:
                reasons.append(f"⚠️ Stochastic غير داعم")
        
        # نطاق RSI أوسع
        if direction == "BULLISH" and 50 <= last["rsi"] <= 75:
            score += 0.5
            reasons.append(f"✅ RSI متوافق")
        elif direction == "BEARISH" and 25 <= last["rsi"] <= 50:
            score += 0.5
            reasons.append(f"✅ RSI متوافق")
        
        return score, max_score, reasons
        
    except Exception as e:
        return 0, max_score, [f"⚠️ خطأ: {e}"]

def supertrend_filter(df, last, direction):
    """تخفيف شرط SuperTrend"""
    try:
        atr_indicator = ta.volatility.AverageTrueRange(
            high=df["high"],
            low=df["low"],
            close=df["close"],
            window=10
        )
        atr_values = atr_indicator.average_true_range()
        
        if len(atr_values) < 2:
            return True, "⚠️ بيانات ATR غير كافية"
        
        multiplier = 2.5
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
            return True, f"⚠️ SuperTrend مختلف"
        
    except Exception as e:
        return True, f"⚠️ خطأ"

def multi_timeframe_analysis(pair):
    """تحليل متعدد الفريمات - مخفف"""
    try:
        # جلب 5 دقائق
        df_5m = get_candles(pair, interval="5min", outputsize=100)
        if df_5m is None or len(df_5m) < 30:
            return None, None, None
        
        df_5m["ema21"] = ta.trend.EMAIndicator(close=df_5m["close"], window=21).ema_indicator()
        df_5m["ema50"] = ta.trend.EMAIndicator(close=df_5m["close"], window=50).ema_indicator()
        
        adx = ta.trend.ADXIndicator(high=df_5m["high"], low=df_5m["low"], close=df_5m["close"], window=14)
        df_5m["adx"] = adx.adx()
        
        df_5m = df_5m.dropna()
        
        if len(df_5m) == 0:
            return None, None, None
        
        last_5m = df_5m.iloc[-1]
        
        # شروط مخففة
        is_bullish = (
            last_5m["ema21"] > last_5m["ema50"] and
            last_5m["adx"] >= 18
        )
        
        is_bearish = (
            last_5m["ema21"] < last_5m["ema50"] and
            last_5m["adx"] >= 18
        )
        
        if is_bullish:
            direction_5m = "BULLISH"
        elif is_bearish:
            direction_5m = "BEARISH"
        else:
            direction_5m = "NEUTRAL"
        
        print(f"📊 اتجاه 5 دقائق: {direction_5m}")
        
        # جلب 1 دقيقة
        df_1m = get_candles(pair, interval="1min", outputsize=100)
        if df_1m is None or len(df_1m) < 30:
            return None, None, None
        
        return df_1m, df_5m, direction_5m
        
    except Exception as e:
        return None, None, None

# =============================================
# ✅ الدالة الرئيسية
# =============================================
def analyze_market(pair, send_alerts=True):
    """تحليل السوق - نسخة مخففة للصفقات"""
    global trades_today
    
    try:
        # ✅ التحقق من إمكانية التداول
        if not can_trade():
            return {
                "signal": "WAIT",
                "strength": 0,
                "duration": 0,
                "price": 0,
                "reason": f"تم تحقيق الهدف اليومي ({DAILY_TARGET} صفقات)",
                "timestamp": datetime.now().isoformat(),
                "pair": pair
            }
        
        print(f"\n{'=' * 50}")
        print(f"🔍 جاري تحليل الزوج: {pair}")
        print(f"📊 الصفقات اليوم: {trades_today}/{DAILY_TARGET}")
        print(f"{'=' * 50}")
        
        # التحقق من البيانات
        if not check_data_availability(pair):
            return None
        
        # التحليل
        df, df_5m, direction_5m = multi_timeframe_analysis(pair)
        
        if df is None or len(df) < 30:
            return None
        
        # ✅ إذا كان 5 دقائق محايد، نستخدم 1 دقيقة
        if direction_5m == "NEUTRAL":
            print("⚠️ اتجاه 5 دقائق محايد - نستخدم 1 دقيقة")
            direction_5m = "NEUTRAL_ALLOWED"
        
        # حساب المؤشرات
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
            
        except Exception as e:
            return None
        
        df = df.dropna()
        if len(df) == 0:
            return None
        
        last = df.iloc[-1]
        atr_percent = last["atr"] / last["close"] if last["close"] > 0 else 0
        
        # فلترة السوق
        filter_passed, filter_reasons, failed = market_filter(df, last, atr_percent)
        
        if not filter_passed:
            return {
                "signal": "WAIT",
                "strength": 0,
                "duration": 0,
                "price": float(last["close"]),
                "reason": "فشل فلترة السوق",
                "timestamp": datetime.now().isoformat(),
                "pair": pair
            }
        
        # تحديد الاتجاه
        direction, trend_score, trend_max, trend_reasons = enhanced_trend_analysis(df, last, last["atr"])
        
        if direction == "NEUTRAL":
            return {
                "signal": "WAIT",
                "strength": 0,
                "duration": 0,
                "price": float(last["close"]),
                "reason": "الاتجاه غير واضح",
                "timestamp": datetime.now().isoformat(),
                "pair": pair
            }
        
        # Price Action
        pattern, pa_score, pa_max, pa_reasons = enhanced_price_action_analysis(df, last)
        
        # Stochastic
        stoch_score, stoch_max, stoch_reasons = stochastic_rsi_confirmation(df, last, direction)
        
        # SuperTrend
        st_ok, st_msg = supertrend_filter(df, last, direction)
        
        # حساب القوة
        total_weight = 30 + 25 + 15 + 15 + 15
        weighted_score = (
            (trend_score / trend_max) * 30 +
            (pa_score / pa_max) * 25 +
            (stoch_score / stoch_max) * 15 +
            15 +
            15
        )
        
        strength_percent = (weighted_score / total_weight) * 100
        
        # ✅ خفض العتبات للحصول على صفقات أكثر
        if strength_percent >= 55:
            signal = "BUY" if direction == "BULLISH" else "SELL"
            duration = 10
            strength_text = "قوية"
        elif strength_percent >= 40:
            signal = "BUY" if direction == "BULLISH" else "SELL"
            duration = 5
            strength_text = "متوسطة"
        else:
            signal = "WAIT"
            duration = 0
            strength_text = "ضعيفة"
        
        if signal != "WAIT":
            # ✅ تسجيل الصفقة
            all_reasons = filter_reasons + trend_reasons + pa_reasons + stoch_reasons
            
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
                "reason": "\n".join(all_reasons[:10]),
                "timestamp": datetime.now().isoformat(),
                "pair": pair,
                "trade_number": trades_today + 1
            }
            
            # ✅ تسجيل الصفقة
            record_trade(result)
            
            # ✅ إرسال تنبيه
            if send_alerts:
                send_telegram_alert(result)
                save_signal_to_file(result)
            
            print(f"\n🚨🚨🚨 إشارة {signal} لـ {pair}!")
            print(f"   💪 القوة: {strength_percent:.1f}% ({strength_text})")
            print(f"   💰 السعر: {last['close']:.5f}")
            print(f"   📊 الصفقة رقم {trades_today}/{DAILY_TARGET}")
            print(f"   📝 النمط: {pattern if pattern else 'لا يوجد'}")
            
            return result
        
        return {
            "signal": "WAIT",
            "strength": round(strength_percent),
            "duration": 0,
            "price": float(last["close"]),
            "reason": f"قوة الإشارة {strength_percent:.1f}% - تحتاج ≥ 40%",
            "timestamp": datetime.now().isoformat(),
            "pair": pair
        }

    except Exception as e:
        print(f"❌ خطأ: {e}")
        import traceback
        traceback.print_exc()
        return None

# =============================================
# ✅ التشغيل المستمر مع تنبيهات تلغرام
# =============================================
def run_continuous_with_alerts(pairs, interval=30, send_alerts=True):
    """تشغيل مستمر مع تنبيهات"""
    print("🚀 بدء التشغيل المستمر مع تنبيهات تلغرام...")
    print(f"🎯 هدف اليوم: {DAILY_TARGET} صفقات")
    print(f"📊 الأزواج: {', '.join(pairs)}")
    print(f"⏱ الفاصل: {interval} ثانية")
    print(f"🔔 التنبيهات: {'مفعلة' if send_alerts else 'معطلة'}")
    
    if send_alerts and (not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID):
        print("\n⚠️ تحذير: لم يتم تعيين توكن تلغرام!")
        print("📌 اذهب إلى @BotFather في تلغرام لإنشاء بوت")
        print("📌 ثم اذهب إلى @userinfobot للحصول على Chat ID")
        print("📌 ضعهم في المتغيرات: TELEGRAM_BOT_TOKEN و TELEGRAM_CHAT_ID")
        print("\n⏳ سيستمر التشغيل بدون تنبيهات...")
    
    print("=" * 60)
    
    while True:
        try:
            current_time = datetime.now().strftime("%H:%M:%S")
            remaining = DAILY_TARGET - trades_today
            print(f"\n🕐 {current_time} - الصفقات اليوم: {trades_today}/{DAILY_TARGET} (متبقي {remaining})")
            
            for pair in pairs:
                # ✅ التحقق من الهدف قبل كل تحليل
                if trades_today >= DAILY_TARGET:
                    print(f"⏸ تم تحقيق الهدف اليومي! انتظار حتى الغد...")
                    time.sleep(60)
                    continue
                
                result = analyze_market(pair, send_alerts=send_alerts)
                
                if result and result['signal'] != 'WAIT':
                    print(f"\n✅ تم العثور على إشارة {result['signal']} لـ {pair}")
                    print(f"📊 القوة: {result['strength']}%")
                    print(f"💰 السعر: {result['price']}")
                    
                    # ✅ التنبيه أرسل داخل analyze_market
                    
                    # ✅ إذا وصلنا للهدف، نوقف التحليل مؤقتاً
                    if trades_today >= DAILY_TARGET:
                        print(f"\n🎯 تم تحقيق الهدف اليومي ({DAILY_TARGET} صفقات)!")
                        print("⏳ انتظار حتى منتصف الليل...")
                        break
                    
                elif result:
                    # عرض الحالة
                    status = "⏸"
                    reason = result.get('reason', '')
                    if reason:
                        print(f"{status} {pair}: {reason[:50]}...")
            
            # ✅ إذا وصلنا للهدف، ننام حتى منتصف الليل
            if trades_today >= DAILY_TARGET:
                now = datetime.now()
                tomorrow = now.replace(hour=0, minute=0, second=0) + timedelta(days=1)
                wait_seconds = (tomorrow - now).total_seconds()
                print(f"⏳ انتظار {wait_seconds/3600:.1f} ساعة حتى منتصف الليل...")
                time.sleep(min(wait_seconds, 3600))  # ننام ساعة على الأقل
                continue
            
            print(f"\n⏳ انتظار {interval} ثانية...")
            time.sleep(interval)
            
        except KeyboardInterrupt:
            print("\n🛑 تم إيقاف التشغيل بواسطة المستخدم")
            
            # عرض تقرير اليوم
            print(f"\n📊 تقرير اليوم:")
            print(f"   - عدد الصفقات: {trades_today}/{DAILY_TARGET}")
            print(f"   - الأزواج: {', '.join(set([t['pair'] for t in trades_history]))}")
            
            break
        except Exception as e:
            print(f"❌ خطأ: {e}")
            time.sleep(interval)

# =============================================
# ✅ التشغيل
# =============================================
if __name__ == "__main__":
    # ✅ قائمة الأزواج للتحليل (زيادة عدد الأزواج للحصول على 5 صفقات)
    pairs_to_analyze = [
        "XAU/USD",    # الذهب - تقلب عالي
        "EUR/USD",    # يورو دولار
        "GBP/JPY",    # باوند ين - تقلب عالي جداً
        "AUD/JPY",    # استرالي ين - تقلب عالي
        "GBP/USD",    # باوند دولار
        "USD/JPY",    # دولار ين
        "NZD/JPY",    # نيوزيلندي ين
    ]
    
    # ✅ تشغيل مع تنبيهات
    run_continuous_with_alerts(
        pairs=pairs_to_analyze,
        interval=20,        # كل 20 ثانية للسرعة
        send_alerts=True    # إرسال تنبيهات تلغرام
    )
