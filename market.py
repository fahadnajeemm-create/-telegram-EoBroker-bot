# =============================================
# الدالة الرئيسية - الكاملة مع الجزء الناقص
# =============================================
def analyze_market(pair):
    """تحليل السوق باستخدام جميع الفلاتر المحسنة"""
    try:
        print(f"\n{'=' * 50}")
        print(f"🔍 جاري تحليل الزوج: {pair}")
        print(f"{'=' * 50}")
        
        # فلتر الأخبار
        print("\n📰 التحسين 1: فحص الأخبار الاقتصادية...")
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
        
        # التحليل متعدد الفريمات
        print("\n📊 التحليل متعدد الفريمات...")
        df, df_5m, direction_5m = multi_timeframe_analysis(pair)
        
        if df is None:
            print(f"❌ فشل جلب البيانات لـ {pair}")
            return None
        
        if len(df) < 100:
            print(f"❌ بيانات غير كافية لتحليل {pair}")
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
        
        # انتظار إغلاق الشمعة
        print("\n⏳ التحسين 3: التحقق من إغلاق الشمعة...")
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
        
        print("🔄 حساب المؤشرات الفنية على 1 دقيقة...")
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
        
        # المرحلة 1: فلترة السوق
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
        
        # المرحلة 2: تحديد الاتجاه
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
        
        # المرحلة 3: Price Action
        print("\n🔍 المرحلة 3: تحليل Price Action (وزن 25%)")
        pattern, pa_score, pa_max, pa_reasons = enhanced_price_action_analysis(df, last)
        
        for reason in pa_reasons:
            print(f"  {reason}")
        
        print(f"📊 نقاط Price Action: {pa_score}/{pa_max}")
        all_reasons.extend(pa_reasons)
        
        # المرحلة 4: Stochastic & RSI
        print("\n🔍 المرحلة 4: تأكيد Stochastic و RSI")
        stoch_score, stoch_max, stoch_reasons = stochastic_rsi_confirmation(df, last, direction)
        
        for reason in stoch_reasons:
            print(f"  {reason}")
        
        print(f"📊 نقاط Stochastic: {stoch_score:.1f}/{stoch_max}")
        all_reasons.extend(stoch_reasons)
        
        # المرحلة 5: SuperTrend
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
        
        # ============================================
        # الجزء الناقص: حساب القوة وتحديد الإشارة
        # ============================================
        print("\n📊 حساب قوة الإشارة النهائية...")
        
        # حساب القوة النهائية
        total_weight = 30 + 25 + 15 + 15 + 15  # الاتجاه + PA + Stochastic + RSI + SuperTrend
        
        # حساب النقاط الموزونة
        weighted_score = (
            (trend_score / trend_max) * 30 +
            (pa_score / pa_max) * 25 +
            (stoch_score / stoch_max) * 15 +
            15 +  # RSI (ثابت لأنه تم تأكيده)
            15   # SuperTrend (ثابت لأنه تم تأكيده)
        )
        
        strength_percent = (weighted_score / total_weight) * 100
        
        print(f"📊 قوة الإشارة: {strength_percent:.1f}%")
        
        # تحديد الإشارة بناءً على القوة
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
        
        # ============================================
        # النتيجة النهائية
        # ============================================
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
# دالة اختبار سريع
# =============================================
if __name__ == "__main__":
    # اختبار الدالة على زوج EUR/USD
    print("🧪 اختبار تحليل السوق...")
    result = analyze_market("EUR/USD")
    
    if result:
        print("\n✅ تم التحليل بنجاح!")
        print(json.dumps(result, indent=2, default=str))
    else:
        print("❌ فشل التحليل")
