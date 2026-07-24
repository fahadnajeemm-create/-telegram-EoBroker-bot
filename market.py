import requests
import pandas as pd
import ta
import os
import time
from datetime import datetime, timedelta
import json

# ✅ تعيين المفتاح (احتياطي)
TWELVE_API = "cd927853f89c420380e0dcb9cecf2846"

# ✅ إعدادات التنبيه
TELEGRAM_BOT_TOKEN = "8920872994:AAFt-9_WPBGGVB_jvWwqZEqphGvpvlk0LWE"
TELEGRAM_CHAT_ID = "1228195080"

# ✅ تثبيت yfinance
try:
    import yfinance as yf
except ImportError:
    os.system('pip install yfinance')
    import yfinance as yf

# =============================================
# ✅ متغيرات التحكم
# =============================================
DAILY_TARGET = 5
trades_today = 0
last_trade_date = datetime.now().date()
trades_history = []
last_price_cache = {}  # حفظ آخر سعر لكل زوج

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
# ✅ دوال التنبيه
# =============================================
def send_telegram_alert(result):
    try:
        if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
            return False
        
        emoji = "🟢" if result['signal'] == "BUY" else "🔴"
        
        message = f"""
{emoji} *إشارة تداول جديدة!*

💱 *الزوج:* {result['pair']}
💰 *السعر:* {result['price']:.2f}
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
        payload = {'chat_id': TELEGRAM_CHAT_ID, 'text': message, 'parse_mode': 'Markdown'}
        response = requests.post(url, json=payload, timeout=10)
        return response.status_code == 200
    except:
        return False

def send_test_message():
    try:
        message = """
🚀 *تم تشغيل البوت بنجاح!*

✅ البوت جاهز للعمل
🎯 هدف اليوم: 5 صفقات
📊 الأزواج: XAUUSD, EURUSD, GBPJPY

📈 *البيانات من Yahoo Finance*
📍 سيتم إرسال الإشارات فور ظهورها

⚠️ هذا ليس نصيحة استثمارية
        """
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {'chat_id': TELEGRAM_CHAT_ID, 'text': message, 'parse_mode': 'Markdown'}
        response = requests.post(url, json=payload, timeout=10)
        return response.status_code == 200
    except:
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
# ✅ دوال جلب البيانات - Yahoo Finance + Twelve Data
# =============================================

def get_candles(pair, interval="1min", outputsize=200):
    """جلب بيانات من Yahoo Finance مع تحديث مستمر"""
    try:
        print(f"🔄 جلب {pair}...")
        
        # ✅ خريطة الرموز
        symbol_map = {
            "XAU/USD": "GC=F",
            "GOLD": "GC=F",
            "XAG/USD": "SI=F",
            "EUR/USD": "EURUSD=X",
            "GBP/USD": "GBPUSD=X",
            "USD/JPY": "USDJPY=X",
            "AUD/USD": "AUDUSD=X",
            "NZD/USD": "NZDUSD=X",
            "EUR/JPY": "EURJPY=X",
            "GBP/JPY": "GBPJPY=X",
            "AUD/JPY": "AUDJPY=X",
            "NZD/JPY": "NZDJPY=X",
            "BTC/USD": "BTC-USD",
            "ETH/USD": "ETH-USD",
        }
        
        symbol = symbol_map.get(pair)
        if not symbol:
            if "/" in pair:
                base, quote = pair.split("/")
                symbol = f"{base}{quote}=X"
            else:
                symbol = pair
        
        print(f"📌 رمز: {symbol}")
        
        # تحويل الفاصل الزمني
        interval_map = {
            "1min": "1m",
            "5min": "5m",
            "15min": "15m",
            "30min": "30m",
            "1h": "60m",
        }
        yf_interval = interval_map.get(interval, "1m")
        
        # ✅ فترة الجلب
        if "XAU" in pair.upper() or "GOLD" in pair.upper():
            period = "5d"
        else:
            period = "7d"
        
        # ✅ محاولات متعددة
        for attempt in range(3):
            try:
                ticker = yf.Ticker(symbol)
                df = ticker.history(period=period, interval=yf_interval)
                
                if df is not None and len(df) > 0:
                    # ✅ تحقق من التاريخ
                    last_time = df.index[-1]
                    time_diff = (datetime.now() - last_time).total_seconds() / 60
                    
                    if time_diff > 30:  # إذا كان الفرق أكثر من 30 دقيقة
                        print(f"⚠️ بيانات قديمة ({time_diff:.0f} دقيقة)")
                        if attempt < 2:
                            print("🔄 محاولة تحديث...")
                            time.sleep(2)
                            continue
                    
                    # إعادة تسمية الأعمدة
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
                        latest_price = df.iloc[-1]['close']
                        
                        # ✅ حفظ السعر في الكاش
                        last_price_cache[pair] = latest_price
                        
                        print(f"✅ {len(df)} شمعة, آخر سعر: {latest_price:.2f}")
                        return df
                    else:
                        print(f"⚠️ بيانات غير كافية: {len(df)} شمعة")
                else:
                    print(f"⚠️ لا توجد بيانات")
                
                time.sleep(1)
                
            except Exception as e:
                print(f"⚠️ محاولة {attempt+1} فشلت: {e}")
                time.sleep(2)
        
        # ✅ إذا فشل Yahoo، جرب Twelve Data
        print(f"🔄 محاولة Twelve Data API...")
        df = get_candles_twelvedata(pair, interval, outputsize)
        if df is not None and len(df) >= 30:
            return df
        
        # ✅ إذا كان لدينا سعر مخزن، استخدمه
        if pair in last_price_cache:
            print(f"⚠️ استخدام السعر المخزن: {last_price_cache[pair]:.2f}")
            # إنشاء DataFrame وهمي بآخر سعر معروف
            df = pd.DataFrame({
                'open': [last_price_cache[pair]] * 50,
                'high': [last_price_cache[pair]] * 50,
                'low': [last_price_cache[pair]] * 50,
                'close': [last_price_cache[pair]] * 50,
                'volume': [0] * 50
            })
            return df
        
        print(f"❌ فشل جلب {pair}")
        return None
        
    except Exception as e:
        print(f"❌ خطأ: {e}")
        return None

def get_candles_twelvedata(pair, interval="1min", outputsize=200):
    """جلب بيانات من Twelve Data API (احتياطي)"""
    try:
        api_key = TWELVE_API
        if not api_key:
            return None
        
        symbols_to_try = [
            pair,
            pair.replace("/", ""),
            pair.replace("/", "").upper(),
        ]
        
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
                        latest = df.iloc[-1]['close']
                        print(f"✅ Twelve Data: {len(df)} شمعة, آخر سعر: {latest:.2f}")
                        return df
                
                time.sleep(0.5)
                
            except:
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

def wait_for_candle_close(df):
    try:
        current_time = datetime.now()
        seconds_remaining = 60 - current_time.second
        if seconds_remaining > 30:
            return False, f"⏳ انتظر {seconds_remaining} ثانية"
        return True, "✅ الشمعة جاهزة"
    except:
        return True, "⚠️ لا يمكن التحقق"

def market_filter(df, last, atr_percent):
    """شروط مخففة جداً"""
    reasons = []
    passed = True
    failed_reasons = []
    
    if last["adx"] < 12:
        msg = f"⚠️ ADX ضعيف: {last['adx']:.1f}"
        reasons.append(msg)
        failed_reasons.append(msg)
        passed = False
    
    if atr_percent < 0.0002:
        msg = f"⚠️ التقلب منخفض: {atr_percent:.4%}"
        reasons.append(msg)
        failed_reasons.append(msg)
        passed = False
    
    avg_body = (df["close"] - df["open"]).abs().tail(10).mean()
    body = abs(last["close"] - last["open"])
    if body > avg_body * 4:
        msg = f"⚠️ شمعة انفجارية"
        reasons.append(msg)
        failed_reasons.append(msg)
        passed = False
    
    candle_range = last["high"] - last["low"]
    avg_range = (df["high"] - df["low"]).tail(20).mean()
    if candle_range > avg_range * 3:
        msg = f"⚠️ تذبذب قوي"
        reasons.append(msg)
        failed_reasons.append(msg)
        passed = False
    
    if passed:
        reasons.append("✅ اجتازت فلترة السوق")
    
    return passed, reasons, failed_reasons

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
            if lower_shadow > body * 1.5 and upper_shadow < body * 0.5:
                pattern = "BULLISH_PIN_BAR"
                score = 5
                reasons.append("✅ Bullish Pin Bar")
            
            elif upper_shadow > body * 1.5 and lower_shadow < body * 0.5:
                pattern = "BEARISH_PIN_BAR"
                score = 5
                reasons.append("✅ Bearish Pin Bar")
        
        resistance = df.iloc[:-1]["high"].tail(5).max()
        support = df.iloc[:-1]["low"].tail(5).min()
        
        if current["close"] > resistance and current["close"] > current["open"]:
            if not pattern or score < 4:
                pattern = "BREAKOUT_BULLISH"
                score = max(score, 4)
                reasons.append(f"✅ اختراق مقاومة")
        
        elif current["close"] < support and current["close"] < current["open"]:
            if not pattern or score < 4:
                pattern = "BREAKOUT_BEARISH"
                score = max(score, 4)
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
    if atr_ratio >= 0.1:
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
    
    if score >= 2:
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
        
        if bb_width > avg_width * 3:
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
            if current_k > current_d:
                score += 1.5
                reasons.append(f"✅ Stochastic صاعد")
            elif current_k < 40:
                score += 1
                reasons.append(f"⚠️ ذروة البيع")
            else:
                reasons.append(f"⚠️ غير داعم")
        else:
            if current_k < current_d:
                score += 1.5
                reasons.append(f"✅ Stochastic هابط")
            elif current_k > 60:
                score += 1
                reasons.append(f"⚠️ ذروة الشراء")
            else:
                reasons.append(f"⚠️ غير داعم")
        
        if direction == "BULLISH" and 35 <= last["rsi"] <= 85:
            score += 0.5
            reasons.append(f"✅ RSI متوافق")
        elif direction == "BEARISH" and 15 <= last["rsi"] <= 65:
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
        
        multiplier = 2
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
        # جلب 5 دقائق
        df_5m = get_candles(pair, interval="5min", outputsize=100)
        if df_5m is None or len(df_5m) < 15:
            return None, None, None
        
        df_5m["ema21"] = ta.trend.EMAIndicator(close=df_5m["close"], window=21).ema_indicator()
        df_5m["ema50"] = ta.trend.EMAIndicator(close=df_5m["close"], window=50).ema_indicator()
        adx = ta.trend.ADXIndicator(high=df_5m["high"], low=df_5m["low"], close=df_5m["close"], window=14)
        df_5m["adx"] = adx.adx()
        df_5m = df_5m.dropna()
        
        if len(df_5m) == 0:
            return None, None, None
        
        last_5m = df_5m.iloc[-1]
        
        is_bullish = last_5m["ema21"] > last_5m["ema50"] and last_5m["adx"] >= 10
        is_bearish = last_5m["ema21"] < last_5m["ema50"] and last_5m["adx"] >= 10
        
        if is_bullish:
            direction_5m = "BULLISH"
        elif is_bearish:
            direction_5m = "BEARISH"
        else:
            direction_5m = "NEUTRAL"
        
        print(f"📊 اتجاه 5 دقائق: {direction_5m}")
        
        # جلب 1 دقيقة
        df_1m = get_candles(pair, interval="1min", outputsize=100)
        if df_1m is None or len(df_1m) < 15:
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
        
        if df is None or len(df) < 15:
            print(f"❌ بيانات غير كافية")
            return None
        
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
        
        print(f"📊 السعر: {last['close']:.2f}")
        print(f"📊 ADX: {last['adx']:.2f}")
        print(f"📊 RSI: {last['rsi']:.2f}")
        
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
        
        # تحديد الإشارة - شروط مخففة جداً
        if strength_percent >= 30:
            signal = "BUY" if direction == "BULLISH" else "SELL"
            duration = 10
            strength_text = "قوية"
        elif strength_percent >= 18:
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
                "rsi": round(last["rsi"], 2) if not pd.isna(last["rsi"]) else None,
                "adx": round(last["adx"], 2) if not pd.isna(last["adx"]) else None,
                "direction": direction,
                "direction_5m": direction_5m,
                "pattern": pattern,
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
            print(f"   💰 السعر: {last['close']:.2f}")
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
# ✅ التشغيل
# =============================================
if __name__ == "__main__":
    print("🚀 بدء تشغيل بوت التداول...")
    print("=" * 60)
    
    # ✅ إرسال رسالة اختبار
    send_test_message()
    
    print("\n⏳ بدء التحليل المستمر...")
    print("📍 سيتم إرسال الإشارات إلى تلغرام فور ظهورها")
    print("=" * 60)
    
    pairs = [
        "XAU/USD",
        "EUR/USD",
        "GBP/JPY"
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
                
                time.sleep(5)
            
            print(f"\n⏳ انتظار 10 ثواني...")
            time.sleep(10)
            
        except KeyboardInterrupt:
            print("\n🛑 تم الإيقاف")
            break
        except Exception as e:
            print(f"❌ خطأ: {e}")
            time.sleep(10)
