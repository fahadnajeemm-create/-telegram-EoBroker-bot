import telebot
from telebot import types
import random
from datetime import datetime

8920872994:AAEroNdwptEOqUb1ercwdLqRI1ATlGALNUE

bot = telebot.TeleBot(TOKEN)

user_language = {}
user_pair = {}

pairs = [
    "EUR/USD",
    "GBP/USD",
    "USD/JPY",
    "USD/CAD",
    "AUD/USD",
    "NZD/USD",
    "EUR/JPY",
    "GBP/JPY",
    "EUR/GBP",
    "USD/CHF",
    "XAU/USD (ذهب)"
]

signals_ar = [
    "📈 حركة سعرية\nالزوج: {pair}\nالمدة: 30 دقيقة",
    "📉 حركة سعرية\nالزوج: {pair}\nالمدة: 45 دقيقة"
]

signals_en = [
    "📈 Market update\nPair: {pair}\nDuration: 30 minutes",
    "📉 Market update\nPair: {pair}\nDuration: 45 minutes"
]


@bot.message_handler(commands=['start'])
def start(message):
    keyboard = types.InlineKeyboardMarkup()

    keyboard.add(
        types.InlineKeyboardButton("العربية 🇸🇦", callback_data="ar"),
        types.InlineKeyboardButton("English 🇬🇧", callback_data="en")
    )

    bot.send_message(
        message.chat.id,
        "اختر اللغة / Choose language:",
        reply_markup=keyboard
    )


def main_menu(chat_id):
    keyboard = types.InlineKeyboardMarkup()

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


@bot.callback_query_handler(func=lambda call: True)
def callback(call):

    chat_id = call.message.chat.id

    if call.data in ["ar", "en"]:
        user_language[chat_id] = call.data

        if call.data == "ar":
            bot.send_message(chat_id, "تم اختيار العربية ✅")
        else:
            bot.send_message(chat_id, "English selected ✅")

        main_menu(chat_id)


    elif call.data == "pairs":

        keyboard = types.InlineKeyboardMarkup()

        for pair in pairs:
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
        lang = user_language.get(chat_id, "ar")

        if lang == "ar":
            text = random.choice(signals_ar)
        else:
            text = random.choice(signals_en)

        text = text.format(pair=pair)

        bot.send_message(
            chat_id,
            f"{text}\n\n⏰ الوقت: {datetime.now().strftime('%H:%M')}"
        )


print("Bot is running...")
bot.infinity_polling()
