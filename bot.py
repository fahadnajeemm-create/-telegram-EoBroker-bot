    elif call.data.startswith("pair_"):
        pair = call.data.replace("pair_", "")
        user_pair[chat_id] = pair

        bot.send_message(
            chat_id,
            f"تم اختيار الزوج ✅\n{pair}",
        )

        main_menu(chat_id)

    elif call.data == "signal":
        pair = user_pair.get(chat_id, "EUR/USD")

        price = get_price(pair)
        candles = get_candles(pair)

        if price is not None and candles:

            closes = []
            for candle in candles:
                closes.append(float(candle["close"]))

            last_close = closes[0]
            previous_close = closes[1]

            if last_close > previous_close:
                signal = "🟢 شراء (CALL)"
                duration = "30 ثانية"

            elif last_close < previous_close:
                signal = "🔴 بيع (PUT)"
                duration = "45 ثانية"

            else:
                signal = "⏸ انتظار"
                duration = "30 ثانية"

            bot.send_message(
                chat_id,
                f"💱 الزوج: {pair}\n"
                f"💰 السعر الحالي: {price}\n"
                f"📊 الإشارة: {signal}\n"
                f"⏱ مدة الصفقة: {duration}\n"
                f"⏰ الوقت: {datetime.now(ZoneInfo('Asia/Riyadh')).strftime('%H:%M')}",
            )

        else:
            bot.send_message(
                chat_id,
                f"❌ لم يتم جلب البيانات للزوج {pair}",
            )
