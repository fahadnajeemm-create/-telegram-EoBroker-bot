import telebot
from telebot import types
import random
from datetime import datetime

TOKEN = "8920872994:AAEroNdwptEOqUb1ercwdLqRI1ATlGALNUE"

bot = telebot.TeleBot(TOKEN)

user_language = {}

signals_ar = [
    "📈 إشارة: CALL\nالزوج: EUR/USD\nالمدة: 30 دقيقة",
    "📉 إشارة: PUT\nالزوج: GBP/USD\nالمدة: 45 دقيقة",
    "📈 إشارة: CALL\nالزوج: XAU/USD (ذهب)\nالمدة: 30 دقيقة"
]

signals_en = [
    "📈 Signal: CALL\nPair: EUR/USD\nDuration: 30 minutes",
    "📉 Signal: PUT\nPair: GBP/USD\nDuration: 45 minutes",
    "📈 Signal: CALL\nPair: XAU/USD (Gold)\nDuration: 30 minutes"
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


@bot.callback_query_handler(func=lambda call: True)
def language(call):
    if call.data == "ar":
        user_language[call.message.chat.id] = "ar"
        bot.send_message(
            call.message.chat.id,
            "تم اختيار العربية ✅\nاكتب /signal للحصول على إشارة"
        )

    elif call.data == "en":
        user_language[call.message.chat.id] = "en"
        bot.send_message(
            call.message.chat.id,
            "English selected ✅\nType /signal to get a signal"
        )


@bot.message_handler(commands=['signal'])
def signal(message):

    lang = user_language.get(message.chat.id, "ar")

    if lang == "ar":
        text = random.choice(signals_ar)
    else:
        text = random.choice(signals_en)

    bot.send_message(
        message.chat.id,
        f"{text}\n\n⏰ الوقت: {datetime.now().strftime('%H:%M')}"
    )


print("Bot is running...")
bot.infinity_polling()
