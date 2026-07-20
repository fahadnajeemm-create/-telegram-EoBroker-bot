import telebot
from telebot import types
from datetime import datetime
from zoneinfo import ZoneInfo
from market import get_price 
from database import ( add_subscription,remove_subscription,check_subscription,days_left,all_users)
TOKEN = "8920872994:AAG0t2VC48sfLIBznsjn9OUEV6A5VpKgnlc"
ADMIN_ID = 1228195080
bot = telebot.TeleBot(TOKEN)
user_language = {}
user_pair = {}
last_prices = {}
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
    "XAU/USD",
]

signals_ar = [
    "📈 حركة سعرية\nالزوج: {pair}\nالمدة: 30 ثانية",
    "📉 حركة سعرية\nالزوج: {pair}\nالمدة: 45 ثانية",
]

signals_en = [
    "📈 Market update\nPair: {pair}\nDuration: 30 second",
    "📉 Market update\nPair: {pair}\nDuration: 45 second",
]


@bot.message_handler(commands=["start"])
def start(message):
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(
        types.InlineKeyboardButton("العربية 🇸🇦", callback_data="ar"),
        types.InlineKeyboardButton("English 🇬🇧", callback_data="en"),
    )

    bot.send_message(
        message.chat.id,
        "اختر اللغة / Choose language:",
        reply_markup=keyboard,
    )
if check_subscription(message.chat.id):
    bot.send_message(
        message.chat.id,
        f"✅ اشتراكك فعال\n"
        f"الأيام المتبقية: {days_left(message.chat.id)}"
    )
else:
    bot.send_message(
        message.chat.id,
        "❌ لا يوجد لديك اشتراك."
    )

def main_menu(chat_id):
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(
        types.InlineKeyboardButton(
            "📊 الحصول على إشارة",
            callback_data="signal",
        )
    )
    keyboard.add(
        types.InlineKeyboardButton(
            "💱 اختيار الزوج",
            callback_data="pairs",
        )
    )

    bot.send_message(
        chat_id,
        "اختر من القائمة:",
        reply_markup=keyboard,
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
                    callback_data=f"pair_{pair}",
                )
            )

        bot.send_message(
            chat_id,
            "اختر الزوج:",
            reply_markup=keyboard,
        )

    elif call.data.startswith("pair_"):
        pair = call.data.replace("pair_", "")
        user_pair[chat_id] = pair

        bot.send_message(
            chat_id,
            f"تم اختيار الزوج ✅\n{pair}",
        )

        main_menu(chat_id)

    elif call.data == "signal":
        if not check_subscription(chat_id):

    bot.send_message(
        chat_id,
        "❌ ليس لديك اشتراك فعال.\n\n"
        "للاشتراك تواصل مع الإدارة."
    )

    return
        pair = user_pair.get(chat_id, "EUR/USD")
        price = get_price(pair)

        if price is not None:
            old_price = last_prices.get(pair)

            if old_price is None:
                signal = "⏳ جمع البيانات..."
            else:
                if price > old_price:
                    signal = "🟢 شراء (CALL)"
                elif price < old_price:
                    signal = "🔴 بيع (PUT)"
                else:
                    signal = "⏸ انتظار"

            last_prices[pair] = price

            bot.send_message(
                chat_id,
                f"💱 الزوج: {pair}\n"
                f"💰 السعر الحالي: {price}\n"
                f"📊 الإشارة: {signal}\n"
                f"⏱ مدة الصفقة: 30 ثانية\n"
                f"⏰ الوقت: {datetime.now(ZoneInfo('Asia/Riyadh')).strftime('%H:%M')}",
            )

        else:
            bot.send_message(
                chat_id,
                f"❌ لم يتم جلب السعر للزوج {pair}",
            )
@bot.message_handler(commands=["add"])
def add_user(message):

    if message.from_user.id != ADMIN_ID:
        return

    try:
        _, uid, days = message.text.split()

        add_subscription(
            int(uid),
            int(days)
        )

        bot.reply_to(
            message,
            "✅ تم تفعيل الاشتراك."
        )

    except:
        bot.reply_to(
            message,
            "الاستخدام:\n/add user_id days"
        )


@bot.message_handler(commands=["remove"])
def remove_user(message):

    if message.from_user.id != ADMIN_ID:
        return

    try:
        _, uid = message.text.split()

        remove_subscription(int(uid))

        bot.reply_to(
            message,
            "✅ تم حذف الاشتراك."
        )

    except:
        bot.reply_to(
            message,
            "الاستخدام:\n/remove user_id"
        )


@bot.message_handler(commands=["check"])
def check_user(message):

    if message.from_user.id != ADMIN_ID:
        return

    try:
        _, uid = message.text.split()

        if check_subscription(int(uid)):
            bot.reply_to(
                message,
                f"✅ الاشتراك فعال\nالأيام المتبقية: {days_left(int(uid))}"
            )
        else:
            bot.reply_to(
                message,
                "❌ لا يوجد اشتراك."
            )

    except:
        bot.reply_to(
            message,
            "الاستخدام:\n/check user_id"
        )


@bot.message_handler(commands=["users"])
def users(message):

    if message.from_user.id != ADMIN_ID:
        return

    text = "📋 المشتركون:\n\n"

    for uid, expire in all_users():
        text += f"{uid} | {expire}\n"

    bot.send_message( message.chat.id, text)

print("Bot is running...")
bot.infinity_polling()
