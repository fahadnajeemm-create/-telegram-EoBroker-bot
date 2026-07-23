import telebot
from telebot import types
from datetime import datetime
from zoneinfo import ZoneInfo
import logging
import time
from functools import wraps

from config import BOT_TOKEN, PAIRS
from market import analyze_market

# إعداد التسجيل
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

bot = telebot.TeleBot(BOT_TOKEN)
user_language = {}
user_pair = {}
user_last_signal = {}  # لمنع الطلبات المتكررة

# دالة للتحقق من وجود بيانات التحليل
def validate_analysis(analysis):
    required_keys = ['signal', 'price', 'strength', 'ema9', 'ema21', 'rsi', 'macd', 'adx', 'duration', 'reason']
    return all(key in analysis for key in required_keys)

# دالة لتحديد مدة الانتظار بين الإشارات (بالثواني)
def rate_limit(seconds=30):
    def decorator(func):
        @wraps(func)
        def wrapper(call):
            chat_id = call.message.chat.id
            current_time = time.time()
            
            if chat_id in user_last_signal:
                elapsed = current_time - user_last_signal[chat_id]
                if elapsed < seconds:
                    remaining = int(seconds - elapsed)
                    bot.send_message(
                        chat_id,
                        f"⏳ يرجى الانتظار {remaining} ثانية قبل طلب إشارة جديدة"
                    )
                    return
            
            user_last_signal[chat_id] = current_time
            return func(call)
        return wrapper
    return decorator

def main_menu(chat_id):
    try:
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
        
        keyboard.add(
            types.InlineKeyboardButton(
                "ℹ️ المساعدة",
                callback_data="help"
            )
        )

        bot.send_message(
            chat_id,
            "🏠 *القائمة الرئيسية*\nاختر من القائمة:",
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Error in main_menu: {e}")
        bot.send_message(chat_id, "❌ حدث خطأ في القائمة الرئيسية")

@bot.message_handler(commands=["start"])
def start(message):
    try:
        keyboard = types.InlineKeyboardMarkup(row_width=2)

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
            "🌍 *اختر اللغة / Choose language:*",
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Error in start: {e}")

@bot.message_handler(commands=["help"])
def help_command(message):
    try:
        help_text = """🤖 *بوت الإشارات trading*

*الأوامر المتاحة:*
/start - بدء البوت واختيار اللغة
/help - عرض هذه المساعدة

*كيفية الاستخدام:*
1️⃣ اختر اللغة المناسبة
2️⃣ اختر زوج العملات من القائمة
3️⃣ احصل على إشارة التداول

*الأزواج المتاحة:* 
{}""".format(", ".join(PAIRS))

        bot.send_message(
            message.chat.id,
            help_text,
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Error in help_command: {e}")

@bot.callback_query_handler(func=lambda call: True)
def callback(call):
    try:
        chat_id = call.message.chat.id
        message_id = call.message.message_id

        if call.data == "ar":
            user_language[chat_id] = "ar"
            bot.edit_message_text(
                "✅ *تم اختيار العربية*",
                chat_id,
                message_id,
                parse_mode='Markdown'
            )
            main_menu(chat_id)

        elif call.data == "en":
            user_language[chat_id] = "en"
            bot.edit_message_text(
                "✅ *English selected*",
                chat_id,
                message_id,
                parse_mode='Markdown'
            )
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
            
            # زر العودة
            keyboard.add(
                types.InlineKeyboardButton(
                    "🔙 رجوع",
                    callback_data="back"
                )
            )

            bot.edit_message_text(
                "💱 *اختر الزوج:*",
                chat_id,
                message_id,
                reply_markup=keyboard,
                parse_mode='Markdown'
            )

        elif call.data.startswith("pair_"):
            pair = call.data.replace("pair_", "")
            user_pair[chat_id] = pair

            bot.edit_message_text(
                f"✅ *تم اختيار الزوج*\n💱 {pair}",
                chat_id,
                message_id,
                parse_mode='Markdown'
            )

            main_menu(chat_id)
            
        elif call.data == "back":
            main_menu(chat_id)

        elif call.data == "help":
            help_text = """ℹ️ *معلومات البوت*

📊 *الإشارات تعتمد على:*
• المتوسطات المتحركة (EMA9, EMA21)
• مؤشر القوة النسبية (RSI)
• مؤشر الماكد (MACD)
• مؤشر الاتجاه (ADX)

⏱ *مدة الصفقة:* تحدد تلقائياً حسب التحليل

⚠️ *تنبيه مهم:*
هذا البوت لأغراض تعليمية فقط
ليس نصيحة مالية استثمارية

🔄 *تحديثات البوت:* v1.0"""
            
            bot.send_message(
                chat_id,
                help_text,
                parse_mode='Markdown'
            )

        elif call.data == "signal":
            pair = user_pair.get(chat_id, PAIRS[0] if PAIRS else "EUR/USD")
            
            # إرسال رسالة انتظار
            waiting_msg = bot.send_message(
                chat_id,
                "⏳ *جاري تحليل السوق...*\nيرجى الانتظار",
                parse_mode='Markdown'
            )

            try:
                analysis = analyze_market(pair)
                
                # حذف رسالة الانتظار
                bot.delete_message(chat_id, waiting_msg.message_id)
                
                if analysis and validate_analysis(analysis):
                    if analysis["signal"] == "WAIT":
                        bot.send_message(
                            chat_id,
                            f"⏸ *لا توجد فرصة قوية حالياً*\n\n"
                            f"💱 *الزوج:* {pair}\n"
                            f"💰 *السعر:* {analysis.get('price', 'N/A')}\n\n"
                            f"📈 *EMA9:* {analysis.get('ema9', 'N/A')}\n"
                            f"📉 *EMA21:* {analysis.get('ema21', 'N/A')}\n"
                            f"📊 *RSI:* {analysis.get('rsi', 'N/A')}\n"
                            f"📊 *MACD:* {analysis.get('macd', 'N/A')}\n"
                            f"📊 *ADX:* {analysis.get('adx', 'N/A')}\n\n"
                            f"💡 *السبب:*\n{analysis.get('reason', 'لا يوجد سبب محدد')}",
                            parse_mode='Markdown'
                        )
                        return

                    # تحديد نوع الإشارة
                    if analysis["signal"] == "CALL":
                        signal = "🟢 شراء (CALL)"
                        emoji = "📈"
                    else:
                        signal = "🔴 بيع (PUT)"
                        emoji = "📉"

                    # حساب قوة الإشارة بالنقاط
                    strength = analysis.get('strength', 0)
                    if strength >= 80:
                        strength_level = "🔥 قوي جداً"
                    elif strength >= 60:
                        strength_level = "💪 قوي"
                    elif strength >= 40:
                        strength_level = "👍 متوسط"
                    else:
                        strength_level = "👀 ضعيف"

                    bot.send_message(
                        chat_id,
                        f"{emoji} *إشارة تداول*\n"
                        f"━━━━━━━━━━━━━━━\n"
                        f"💱 *الزوج:* {pair}\n"
                        f"💰 *السعر:* {analysis.get('price', 'N/A')}\n"
                        f"📊 *الإشارة:* {signal}\n"
                        f"🔥 *القوة:* {strength}% ({strength_level})\n"
                        f"━━━━━━━━━━━━━━━\n"
                        f"📈 *EMA9:* {analysis.get('ema9', 'N/A')}\n"
                        f"📉 *EMA21:* {analysis.get('ema21', 'N/A')}\n"
                        f"📊 *RSI:* {analysis.get('rsi', 'N/A')}\n"
                        f"📊 *MACD:* {analysis.get('macd', 'N/A')}\n"
                        f"📊 *ADX:* {analysis.get('adx', 'N/A')}\n"
                        f"━━━━━━━━━━━━━━━\n"
                        f"⏱ *المدة:* {analysis.get('duration', 60)} ثانية\n"
                        f"⏰ *الوقت:* {datetime.now(ZoneInfo('Asia/Riyadh')).strftime('%H:%M:%S')}\n"
                        f"━━━━━━━━━━━━━━━\n"
                        f"⚠️ *تنبيه:* هذا ليس نصيحة استثمارية",
                        parse_mode='Markdown'
                    )
                else:
                    bot.send_message(
                        chat_id,
                        f"❌ *خطأ في تحليل الزوج* {pair}\n"
                        f"البيانات غير مكتملة أو غير صالحة",
                        parse_mode='Markdown'
                    )
                    logger.error(f"Invalid analysis data for {pair}: {analysis}")
                    
            except Exception as e:
                logger.error(f"Error analyzing {pair}: {e}")
                bot.send_message(
                    chat_id,
                    f"❌ *حدث خطأ أثناء التحليل*\n"
                    f"الزوج: {pair}\n"
                    f"الخطأ: {str(e)}",
                    parse_mode='Markdown'
                )

    except Exception as e:
        logger.error(f"Error in callback: {e}")
        try:
            bot.send_message(
                chat_id,
                f"❌ حدث خطأ غير متوقع: {str(e)}",
                parse_mode='Markdown'
            )
        except:
            pass

@bot.message_handler(func=lambda message: True)
def handle_all_messages(message):
    try:
        bot.send_message(
            message.chat.id,
            "❓ استخدم /start للبدء أو /help للمساعدة"
        )
    except Exception as e:
        logger.error(f"Error in handle_all_messages: {e}")

if __name__ == "__main__":
    try:
        print("🚀 Bot is running...")
        logger.info("Bot started successfully")
        bot.infinity_polling(timeout=60, long_polling_timeout=60)
    except Exception as e:
        logger.error(f"Bot crashed: {e}")
        print(f"❌ Error: {e}")
