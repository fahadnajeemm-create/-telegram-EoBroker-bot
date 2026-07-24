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

# ✅ إعدادات التنبيه - تم تعيينها بالكامل ✅
TELEGRAM_BOT_TOKEN = "8920872994:AAFt-9_WPBGGVB_jvWwqZEqphGvpvlk0LWE"
TELEGRAM_CHAT_ID = "1228195080"  # ✅ تم التعيين

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
DAILY_TARGET = 5
trades_today = 0
last_trade_date = datetime.now().date()
trades_history = []

def can_trade():
    global trades_today, last_trade_date
    today = datetime.now().date()
    if today != last_trade_date:
        trades_today = 0
        last_trade_date = today
        print(f"\n📅 يوم جديد! تم إعادة تعيين العداد")
    if trades_today >= DAILY_TARGET:
        print(f"⏸ تم تحقيق الهدف اليومي ({DAILY_TARGET} صفقات)")
        return False
    return True

def record_trade(result):
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

# =============================================
# ✅ دوال التنبيه - معدلة وجاهزة
# =============================================
def send_telegram_alert(result):
    """إرسال تنبيه عبر تلغرام"""
    try:
        if not TELEGRAM_BOT_TOKEN:
            print("⚠️ توكن البوت غير موجود")
            return False
        
        if not TELEGRAM_CHAT_ID:
            print("⚠️ Chat ID غير موجود!")
            return False
        
        emoji = "🟢" if result['signal'] == "BUY" else "🔴"
        
        # ✅ تنسيق الرسالة
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

def send_test_message():
    """إرسال رسالة اختبار للتأكد من إعدادات البوت"""
    try:
        message = """
🚀 *تم تشغيل البوت بنجاح!*

✅ البوت جاهز للعمل
🎯 هدف اليوم: 5 صفقات
📊 الأزواج: XAU/USD, EUR/USD, GBP/JPY, AUD/JPY

⏳ جاري تحليل السوق...
📍 سيتم إرسال الإشارات فور ظهورها

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
            print("✅ تم إرسال رسالة الاختبار إلى تلغرام")
            return True
        else:
            print(f"❌ فشل إرسال رسالة الاختبار: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ خطأ: {e}")
        return False

def save_signal_to_file(result):
    try:
        filename = "trading_signals.json"
        signals = []
        if os.path.exists(filename):
            with open(filename, 'r') as f:
                try:
                    signals = json.load(f)
                except:
                    pass
        signals.append(result)
        with open(filename, 'w') as f:
            json.dump(signals, f, indent=2)
        return True
    except:
        return False

# =============================================
# ✅ دوال جلب البيانات
# =============================================

def get_candles(pair, interval="1min", outputsize=150):
    """جلب بيانات من عدة مصادر"""
    try:
        # ✅ للذهب: استخدام Yahoo Finance أولاً
        if "XAU" in pair.upper() or "GOLD" in pair.upper():
            print(f"🔄 جلب الذهب من Yahoo Finance...")
            df = get_candles_yahoo_gold(interval, outputsize)
            if df is not None and len(df) >= 30:
                print(f"✅ تم جلب {len(df)} شمعة للذهب")
                return df
        
        # ✅ للفضة
        if "XAG" in pair.upper() or "SILVER" in pair.upper():
            print(f"🔄 جلب الفضة من Yahoo Finance...")
            df = get_candles_yahoo_silver(interval, outputsize)
            if df is not None and len(df) >= 30:
                print(f"✅ تم جلب {len(df)} شمعة للفضة")
                return df
        
        # ✅ باقي الأزواج: Twelve Data API
        print(f"🔄 جلب {pair} من Twelve Data API...")
        df = get_candles_twelvedata(pair, interval, outputsize)
        if df is not None and len(df) >= 30:
            return df
        
        # ✅ Backup: Yahoo Finance للعملات
        print(f"🔄 جلب {pair} من Yahoo Finance...")
        df = get_candles_yahoo_forex(pair, interval)
        if df is not None and len(df) >= 30:
            return df
        
        print(f"❌ فشل جلب {pair}")
        return None
        
    except Exception as e:
        print(f"❌ خطأ: {e}")
        return None

def get_candles_yahoo_gold(interval="1min", outputsize=150):
    """جلب بيانات الذهب من Yahoo Finance"""
    try:
        symbols = ["GC=F", "XAUUSD=X", "GOLD"]
        
        for symbol in symbols:
            try:
                print(f"  محاولة: {symbol}")
                ticker = yf.Ticker(symbol)
                
                interval_map = {"1min": "1m", "5min": "5m", "15min": "15m", "1h": "60m"}
                yf_interval = interval_map.get(interval, "1m")
                
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
                        print(f"  ✅ نجح مع {symbol}: {len(df)} شمعة")
                        return df
                
                time.sleep(0.5)
                
            except Exception as e:
                print(f"  ❌ فشل {symbol}: {e}")
                continue
        
        return None
        
    except Exception as e:
        print(f"❌ خطأ في جلب الذهب: {e}")
        return None

def get_candles_yahoo_silver(interval="1min", outputsize=150):
    """جلب بيانات الفضة من Yahoo Finance"""
    try:
        symbols = ["SI=F", "XAGUSD=X", "SILVER"]
        
        for symbol in symbols:
            try:
                print(f"  محاولة: {symbol}")
                ticker = yf.Ticker(symbol)
                
                interval_map = {"1min": "1m", "5min": "5m", "15min": "15m", "1h": "60m"}
                yf_interval = interval_map.get(interval, "1m")
                
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
                        print(f"  ✅ نجح مع {symbol}: {len(df)} شمعة")
                        return df
                
                time.sleep(0.5)
                
            except Exception as e:
                print(f"  ❌ فشل {symbol}: {e}")
                continue
        
        return None
        
    except Exception as e:
        print(f"❌ خطأ في جلب الفضة: {e}")
        return None

def get_candles_yahoo_forex(pair, interval="1min"):
    """جلب بيانات العملات من Yahoo Finance"""
    try:
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
            "USD/CAD": "USDCAD=X",
            "USD/CHF": "USDCHF=X",
        }
        
        symbol = symbol_map.get(pair)
        if not symbol:
            if "/" in pair:
                base, quote = pair.split("/")
                symbol = f"{base}{quote}=X"
            else:
                symbol = pair
        
        print(f"  رمز Yahoo: {symbol}")
        
        interval_map = {"1min": "1m", "5min": "5m", "15min": "15m", "1h": "60m"}
        yf_interval = interval_map.get(interval, "1m")
        
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
                print(f"  ✅ نجح: {len(df)} شمعة")
                return df
        
        return None
        
    except Exception as e:
        print(f"  ❌ فشل: {e}")
        return None

def get_candles_twelvedata(pair, interval="1min", outputsize=150):
    """جلب بيانات من Twelve Data API"""
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
        
        # رموز إضافية
        if "XAU" in pair.upper():
            symbols_to_try.extend(["XAUUSD", "XAU/USD"])
        if "XAG" in pair.upper():
            symbols_to_try.extend(["XAGUSD", "XAG/USD"])
        
        symbols_to_try = list(dict.fromkeys(symbols_to_try))
        
        for symbol in symbols_to_try[:5]:
            try:
                encoded_symbol = symbol.replace("/", "%2F")
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
                        print(f"  ✅ Twelve Data: {len(df)} شمعة")
                        return df
                
                time.sleep(0.5)
                
            except Exception as e:
                continue
        
        return None
        
    except Exception as e:
        return None

# =============================================
# ✅ دوال التحليل
# =============================================

def check_data_availability(pair):
    try:
        df = get_candles(pair, interval="5min", outputsize=30)
        if df is not None and len(df) > 0:
            latest = df.iloc[-1]['close']
            print(f"✅ البيانات متوفرة - آخر سعر: {latest:.2f}")
            return True
        return False
    except:
        return False

def market_filter(df, last, atr_percent):
    reasons = []
    passed = True
    failed_reasons = []
    
    if last["adx"] < 20:
        msg = f"⚠️ ADX ضعيف: {last['adx']:.1f}"
        reasons.append(msg)
        failed_reasons.append(msg)
        passed = False
    
    if atr_percent < 0.0005:
        msg = f"⚠️ التقلب منخفض: {atr_percent:.4%}"
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

def wait_for_candle_close(df):
    try:
        current_time = datetime.now()
        seconds_remaining = 60 - current_time.second
        if seconds_remaining > 30:
            return False, f"⏳ انتظر {seconds_remaining} ثانية"
        return True, "✅ الشمعة جاهزة"
    except:
        return True, "⚠️ لا يمكن التحقق"

def enhanced_price_action_analysis(df, last):
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
        
        if (prev["close"] < prev["open"] and current["close"] > current["open"] and
            current["open"] < prev["close"] and current["close"] > prev["open"]):
            pattern = "BULLISH_ENGULFING"
            score = 7
            reasons.append("✅ Bullish Engulfing")
        
        elif (prev["close"] > prev["open"] and current["close"] < current["open"] and
              current["open"] > prev["close"] and current["close"] < prev["open"]):
            pattern = "BEARISH_ENGULFING"
            score = 7
            reasons.append("✅ Bearish Engulfing")
        
        elif total_range > 0:
            if lower_shadow > body * 2 and upper_shadow < body * 0.5:
                pattern = "BULLISH_PIN_BAR"
                score = 6
                reasons.append("✅ Bullish Pin Bar")
            
            elif upper_shadow > body * 2 and lower_shadow < body * 0.5:
                pattern = "BEARISH_PIN_BAR"
                score = 6
                reasons.append("✅ Bearish Pin Bar")
        
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
        reasons.append(f"✅ فرق EMA = {atr_ratio:.1%}")
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
    
    if score >= 3:
        direction = "BULLISH" if last["ema9"] > last["ema21"] else "BEARISH"
    else:
        direction = "NEUTRAL"
    
    return direction, score, max_score, reasons

def bollinger_width_filter(df, last):
    try:
        if "bb_high" not in df.columns:
            return True, "⚠️ لا توجد بيانات"
        
        bb_width = (last["bb_high"] - last["bb_low"]) / last["bb_mid"]
        avg_width = ((df["bb_high"] - df["bb_low"]) / df["bb_mid"]).tail(20).mean()
        
        if bb_width > avg_width * 2:
            return False, f"⚠️ عرض البولينجر كبير"
        
        return True, f"✅ عرض البولينجر طبيعي"
    except:
        return True, f"⚠️ خطأ"

def stochastic_rsi_confirmation(df, last, direction):
    reasons = []
    score = 0
    max_score = 3
    
    try:
        stoch = ta.momentum.StochasticOscillator(
            high=df["high"], low=df["low"], close=df["close"],
            window=14, smooth_window=3
        )
        stoch_k = stoch.stoch()
        stoch_d = stoch.stoch_signal()
        
        if len(stoch_k) == 0 or len(stoch_d) == 0:
            return 0, max_score, ["⚠️ لا توجد بيانات"]
        
        current_k = stoch_k.iloc[-1]
        current_d = stoch_d.iloc[-1]
        
        if pd.isna(current_k) or pd.isna(current_d):
            return 0, max_score, ["⚠️ قيم غير صالحة"]
        
        if direction == "BULLISH":
            if current_k > 20 and current_k > current_d:
                score += 1.5
                reasons.append(f"✅ Stochastic صاعد")
            elif current_k < 30:
                score += 1
                reasons.append(f"⚠️ ذروة البيع")
            else:
                reasons.append(f"⚠️ غير داعم")
        else:
            if current_k < 80 and current_k < current_d:
                score += 1.5
                reasons.append(f"✅ Stochastic هابط")
            elif current_k > 70:
                score += 1
                reasons.append(f"⚠️ ذروة الشراء")
            else:
                reasons.append(f"⚠️ غير داعم")
        
        if direction == "BULLISH" and 50 <= last["rsi"] <= 75:
            score += 0.5
            reasons.append(f"✅ RSI متوافق")
        elif direction == "BEARISH" and 25 <= last["rsi"] <= 50:
            score += 0.5
            reasons.append(f"✅ RSI متوافق")
        
        return score, max_score, reasons
    except:
        return 0, max_score, ["⚠️ خطأ"]

def supertrend_filter(df, last, direction):
    try:
        atr_indicator = ta.volatility.AverageTrueRange(
            high=df["high"], low=df["low"], close=df["close"], window=10
        )
        atr_values = atr_indicator.average_true_range()
        
        if len(atr_values) < 2:
            return True, "⚠️ بيانات غير كافية"
        
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
    except:
        return True, "⚠️ خطأ"

def multi_timeframe_analysis(pair):
    try:
        df_5m = get_candles(pair, interval="5min", outputsize=100)
        if df_5m is None or len(df_5m) < 20:
            return None, None, None
        
        df_5m["ema21"] = ta.trend.EMAIndicator(close=df_5m["close"], window=21).ema_indicator()
        df_5m["ema50"] = ta.trend.EMAIndicator(close=df_5m["close"], window=50).ema_indicator()
        adx = ta.trend.ADXIndicator(high=df_5m["high"], low=df_5m["low"], close=df_5m["close"], window=14)
        df_5m["adx"] = adx.adx()
        df_5m = df_5m.dropna()
        
        if len(df_5m) == 0:
            return None, None, None
        
        last_5m = df_5m.iloc[-1]
        
        is_bullish = last_5m["ema21"] > last_5m["ema50"] and last_5m["adx"] >= 18
        is_bearish = last_5m["ema21"] < last_5m["ema50"] and last_5m["adx"] >= 18
        
        if is_bullish:
            direction_5m = "BULLISH"
        elif is_bearish:
            direction_5m = "BEARISH"
        else:
            direction_5m = "NEUTRAL"
        
        print(f"📊 اتجاه 5 دقائق: {direction_5m}")
        
        df_1m = get_candles(pair, interval="1min", outputsize=100)
        if df_1m is None or len(df_1m) < 20:
            return None, None, None
        
        return df_1m, df_5m, direction_5m
    except:
        return None, None, None

# =============================================
# ✅ الدالة الرئيسية
# =============================================
def analyze_market(pair, send_alerts=True):
    global trades_today
    
    try:
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
        print(f"🔍 جاري تحليل: {pair}")
        print(f"📊 الصفقات اليوم: {trades_today}/{DAILY_TARGET}")
        print(f"{'=' * 50}")
        
        if not check_data_availability(pair):
            print(f"❌ فشل تحليل {pair}")
            return None
        
        df, df_5m, direction_5m = multi_timeframe_analysis(pair)
        
        if df is None or len(df) < 20:
            return None
        
        if direction_5m == "NEUTRAL":
            print("⚠️ اتجاه 5 دقائق محايد - نستخدم 1 دقيقة")
        
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
                high=df["high"], low=df["low"], close=df["close"], window=14
            )
            df["atr"] = atr.average_true_range()
            
        except Exception as e:
            print(f"❌ خطأ في المؤشرات: {e}")
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
        
        # تحديد الإشارة
        if strength_percent >= 50:
            signal = "BUY" if direction == "BULLISH" else "SELL"
            duration = 10
            strength_text = "قوية"
        elif strength_percent >= 35:
            signal = "BUY" if direction == "BULLISH" else "SELL"
            duration = 5
            strength_text = "متوسطة"
        else:
            signal = "WAIT"
            duration = 0
            strength_text = "ضعيفة"
        
        if signal != "WAIT":
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
                "pair": pair
            }
            
            record_trade(result)
            
            if send_alerts:
                send_telegram_alert(result)
                save_signal_to_file(result)
            
            print(f"\n🚨🚨🚨 إشارة {signal} لـ {pair}!")
            print(f"   💪 القوة: {strength_percent:.1f}% ({strength_text})")
            print(f"   💰 السعر: {last['close']:.5f}")
            print(f"   📊 الصفقة رقم {trades_today}/{DAILY_TARGET}")
            
            return result
        
        return {
            "signal": "WAIT",
            "strength": round(strength_percent),
            "duration": 0,
            "price": float(last["close"]),
            "reason": f"قوة الإشارة {strength_percent:.1f}%",
            "timestamp": datetime.now().isoformat(),
            "pair": pair
        }

    except Exception as e:
        print(f"❌ خطأ: {e}")
        import traceback
        traceback.print_exc()
        return None

# =============================================
# ✅ التشغيل الرئيسي - كل شيء جاهز!
# =============================================
if __name__ == "__main__":
    print("🚀 بدء تشغيل بوت التداول...")
    print(f"🎯 هدف اليوم: {DAILY_TARGET} صفقات")
    print("=" * 60)
    
    # ✅ التحقق من إعدادات البوت
    if TELEGRAM_BOT_TOKEN:
        print("✅ تم تعيين توكن البوت")
    else:
        print("❌ توكن البوت غير موجود!")
    
    if TELEGRAM_CHAT_ID:
        print(f"✅ تم تعيين Chat ID: {TELEGRAM_CHAT_ID}")
    else:
        print("❌ Chat ID غير موجود!")
    
    # ✅ إرسال رسالة اختبار
    print("\n📤 جاري إرسال رسالة اختبار...")
    send_test_message()
    
    print("\n⏳ بدء التحليل المستمر...")
    print("📍 سيتم إرسال الإشارات إلى تلغرام فور ظهورها")
    print("=" * 60)
    
    pairs = [
        "XAU/USD",
        "EUR/USD",
        "GBP/JPY",
        "AUD/JPY"
    ]
    
    while True:
        try:
            for pair in pairs:
                if trades_today >= DAILY_TARGET:
                    print(f"⏸ تم تحقيق الهدف! انتظار حتى الغد...")
                    time.sleep(60)
                    continue
                
                result = analyze_market(pair, send_alerts=True)
                
                if result and result['signal'] != 'WAIT':
                    print(f"✅ إشارة {result['signal']} لـ {pair}")
                    # التنبيه يرسل تلقائياً داخل analyze_market
                
                time.sleep(5)  # بين كل زوج
            
            print(f"\n⏳ انتظار 15 ثانية...")
            time.sleep(15)
            
        except KeyboardInterrupt:
            print("\n🛑 تم الإيقاف بواسطة المستخدم")
            
            # عرض تقرير اليوم
            print(f"\n📊 تقرير اليوم:")
            print(f"   - عدد الصفقات: {trades_today}/{DAILY_TARGET}")
            print(f"   - الأزواج: {', '.join(set([t['pair'] for t in trades_history]))}")
            
            break
        except Exception as e:
            print(f"❌ خطأ: {e}")
            time.sleep(15)
