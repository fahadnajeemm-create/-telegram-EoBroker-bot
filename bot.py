import telebot
from telebot import types
from datetime import datetime
from zoneinfo import ZoneInfo

from config import BOT_TOKEN, PAIRS
from market import get_price, get_candles

bot = telebot.TeleBot(BOT_TOKEN)

user_language = {}
user_pair = {}


def main_menu(chat_id):
    keyboard = types.InlineKeyboardMarkup(row_width=2)

    keyboard.add(
        types.InlineKeyboardButton(
            "📊 الحصول على إشارة",
            callback_data="signal"
        )
    )

    keyboard.add(
        types.InlineKeyboardButton(
            "💱 اختيار الزوج",
            callback_data="pairs"
        )
    )

    bot.send_message(
        chat_id,
        "اختر من القائمة:",
        reply_markup=keyboard
    )


@bot.message_handler(commands=["start"])
def start(message):
    keyboard = types.InlineKeyboardMarkup()

    keyboard.add(
        types.InlineKeyboardButton(
            "العربية 🇸🇦",
            callback_data="ar"
        ),
        types.InlineKeyboardButton(
            "English 🇬🇧",
            callback_data="en"
        )
    )

    bot.send_message(
        message.chat.id,
        "اختر اللغة / Choose language:",
        reply_markup=keyboard
    )


@bot.callback_query_handler(func=lambda call: True)
def callback(call):

    chat_id = call.message.chat.id

    if call.data == "ar":
        user_language[chat_id] = "ar"
        bot.send_message(chat_id, "تم اختيار العربية ✅")
        main_menu(chat_id)

    elif call.data == "en":
        user_language[chat_id] = "en"
        bot.send_message(chat_id, "English selected ✅")
        main_menu(chat_id)

    elif call.data == "pairs":

        keyboard = types.InlineKeyboardMarkup(row_width=2)

        for pair in PAIRS:
            keyboard.add(
                types.InlineKeyboardButton(
                    pair,
                    callback_data=f"pair_{pair}"
                )
            )

        bot.send_message(
            chat_id,
            "اختر الزوج:",
            reply_markup=keyboard
        )

    elif call.data.startswith("pair_"):

        pair = call.data.replace("pair_", "")
        user_pair[chat_id] = pair

        bot.send_message(
            chat_id,
            f"تم اختيار الزوج ✅\n{pair}"
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

            if len(closes) < 2:
                bot.send_message(
                    chat_id,
                    "❌ لا توجد بيانات كافية للتحليل"
                )
                return

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
                f"⏰ الوقت: {datetime.now(ZoneInfo('Asia/Riyadh')).strftime('%H:%M')}"
            )

        else:
            bot.send_message(
                chat_id,
                f"❌ لم يتم جلب البيانات للزوج {pair}"
            )


print("Bot is running...")
bot.infinity_polling()
