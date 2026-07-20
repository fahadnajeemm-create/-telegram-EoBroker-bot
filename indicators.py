import pandas as pd
import ta


def analyze_indicators(df):
    try:
        df["close"] = df["close"].astype(float)

        # EMA
        df["ema9"] = ta.trend.EMAIndicator(
            close=df["close"],
            window=9
        ).ema_indicator()

        df["ema21"] = ta.trend.EMAIndicator(
            close=df["close"],
            window=21
        ).ema_indicator()

        # RSI
        df["rsi"] = ta.momentum.RSIIndicator(
            close=df["close"],
            window=14
        ).rsi()

        # MACD
        macd = ta.trend.MACD(
            close=df["close"]
        )

        df["macd"] = macd.macd()
        df["macd_signal"] = macd.macd_signal()

        last = df.iloc[-1]

        score = 0
        reasons = []

        # EMA
        if last["ema9"] > last["ema21"]:
            score += 30
            reasons.append("EMA صاعد ✅")
        else:
            score -= 30
            reasons.append("EMA هابط ❌")

        # RSI
        if last["rsi"] > 55:
            score += 25
            reasons.append("RSI إيجابي ✅")
        elif last["rsi"] < 45:
            score -= 25
            reasons.append("RSI سلبي ❌")

        # MACD
        if last["macd"] > last["macd_signal"]:
            score += 30
            reasons.append("MACD إيجابي ✅")
        else:
            score -= 30
            reasons.append("MACD سلبي ❌")

        if score >= 0:
            direction = "🟢 شراء (CALL)"
        else:
            direction = "🔴 بيع (PUT)"

        strength = min(abs(score) + 20, 95)

        return {
            "signal": direction,
            "strength": strength,
            "reasons": reasons
        }

    except Exception as e:
        return {
            "signal": "❌ خطأ",
            "strength": 0,
            "reasons": [str(e)]
        }
