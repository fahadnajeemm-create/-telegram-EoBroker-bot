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

# =============================================
# التحسين 1: دالة للتحقق من صحة البيانات
# =============================================
def validate_analysis(analysis):
    """التحقق من اكتمال بيانات التحليل"""
    if not analysis or not isinstance(analysis, dict):
        return False
    required_keys = ['signal', 'price', 'strength', 'ema9', 'ema21', 'rsi', 'macd', 'adx', 'duration', 'reason']
    return all(key in analysis for key in required_keys)

# =============================================
# التحسين 2: دالة معدل الطلبات مع رسائل محسنة
# =============================================
def rate_limit(seconds=30):
    """تحديد معدل الطلبات المسموح بها"""
    def decorator(func):
        @wraps(func)
        def wrapper(call):
            chat_id = call.message.chat.id
            current_time = time.time()
            
            if chat_id in user_last_signal:
                elapsed = current_time - user_last_signal[chat_id]
                if elapsed < seconds:
                    remaining = int(seconds - elapsed)
                    bot.answer_callback_query(
                        call.id,
                        f"⏳ يرجى الانتظار {remaining} ثانية",
                        show_alert=True
                    )
                    return
            
            user_last_signal[chat_id] = current_time
            return func(call)
        return wrapper
    return decorator

# =============================================
# التحسين 3: دالة مساعدة لإرسال الرسائل بأمان
# =============================================
def safe_send_message(chat_id, text, **kwargs):
    """إرسال رسالة مع معالجة الأخطاء"""
    try:
        return bot.send_message(chat_id, text, **kwargs)
    except Exception as e:
        logger.error(f"Error sending message: {e}")
        return None

# =============================================
# التحسين 4: القائمة الرئيسية المحسنة
# =============================================
def main_menu(chat_id):
    """عرض القائمة الرئيسية"""
    try:
        keyboard = types.InlineKeyboardMarkup(row_width=2)
        
        # إضافة أزرار إضافية
        keyboard.add(
            types.InlineKeyboardButton("📊 إشارة فورية", callback_data="signal")
        )
        keyboard.add(
            types.InlineKeyboardButton("💱 تغيير الزوج", callback_data="pairs")
        )
        keyboard.add(
            types.InlineKeyboardButton("📈 إحصائياتي", callback_data="stats")
        )
        keyboard.add(
            types.InlineKeyboardButton("ℹ️ المساعدة", callback_data="help")
        )

        # عرض الزوج الحالي
        current_pair = user_pair.get(chat_id, PAIRS[0] if PAIRS else "EUR/USD")
        
        bot.send_message(
            chat_id,
            f"🏠 *القائمة الرئيسية*\n"
            f"💱 الزوج الحالي: {current_pair}\n\n"
            f"اختر من القائمة:",
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Error in main_menu: {e}")
        safe_send_message(chat_id, "❌ حدث خطأ في القائمة الرئيسية")

# =============================================
# التحسين 5: عرض إحصائيات المستخدم (تم إصلاح الخطأ)
# =============================================
def show_stats(chat_id):
    """عرض إحصائيات المستخدم"""
    try:
        # حساب الإحصائيات من البيانات المتاحة
        total_signals = len(user_last_signal)  # عدد الطلبات
        
        # تم إزالة النص العربي الذي كان يسبب المشكلة
        stats_text = f"""
📊 *إحصائياتك الشخصية*

📈 *إجمالي الإشارات:* {total_signals}
💱 *الزوج الحالي:* {user_pair.get(chat_id, 'غير محدد')}
🌐 *اللغة:* {user_language.get(chat_id, 'غير محددة')}

📊 *نصائح:*
• استخدم الإشارات بحذر
• التداول يحمل مخاطر
• استثمر فقط ما يمكنك تحمل خسارته
"""
        safe_send_message(chat_id, stats_text, parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Error in show_stats: {e}")
        safe_send_message(chat_id, "❌ حدث خطأ في عرض الإحصائيات")

# =============================================
# التحسين 6: دالة تنسيق رسالة الإشارة
# =============================================
def format_signal_message(pair, analysis):
    """تنسيق رسالة الإشارة بشكل محسن"""
    try:
        # تحديد نوع الإشارة
        if analysis["signal"] == "CALL":
            signal = "🟢 شراء (CALL)"
            emoji = "📈"
        elif analysis["signal"] == "PUT":
            signal = "🔴 بيع (PUT)"
            emoji = "📉"
        else:
            signal = "⏸ انتظار (WAIT)"
            emoji = "⏸"

        # حساب قوة الإشارة
        strength = analysis.get('strength', 0)
        if strength >= 80:
            strength_level = "🔥 قوي جداً"
        elif strength >= 60:
            strength_level = "💪 قوي"
        elif strength >= 40:
            strength_level = "👍 متوسط"
        else:
            strength_level = "👀 ضعيف"

        # تنسيق الرسالة
        message = f"""
{emoji} *إشارة تداول*
━━━━━━━━━━━━━━━
💱 *الزوج:* {pair}
💰 *السعر:* {analysis.get('price', 'N/A')}
📊 *الإشارة:* {signal}
🔥 *القوة:* {strength}% ({strength_level})
━━━━━━━━━━━━━━━
📈 *EMA9:* {analysis.get('ema9', 'N/A')}
📉 *EMA21:* {analysis.get('ema21', 'N/A')}
📊 *RSI:* {analysis.get('rsi', 'N/A')}
📊 *MACD:* {analysis.get('macd', 'N/A')}
📊 *ADX:* {analysis.get('adx', 'N/A')}
━━━━━━━━━━━━━━━
⏱ *المدة:* {analysis.get('duration', 60)} ثانية
⏰ *الوقت:* {datetime.now(ZoneInfo('Asia/Riyadh')).strftime('%H:%M:%S')}
━━━━━━━━━━━━━━━
💡 *السبب:* {analysis.get('reason', 'تحليل فني')}
━━━━━━━━━━━━━━━
⚠️ *تنبيه:* هذا ليس نصيحة استثمارية
"""
        return message
    except Exception as e:
        logger.error(f"Error formatting signal: {e}")
        return None

# =============================================
# معالجة أوامر البوت
# =============================================

@bot.message_handler(commands=["start"])
def start(message):
    """معالج أمر البدء"""
    try:
        chat_id = message.chat.id
        keyboard = types.InlineKeyboardMarkup(row_width=2)

        keyboard.add(
            types.InlineKeyboardButton("العربية 🇸🇦", callback_data="ar"),
            types.InlineKeyboardButton("English 🇬🇧", callback_data="en")
        )

        welcome_text = """
🌍 *اختر اللغة / Choose language:*

🤖 *بوت الإشارات المالية*

📊 *مميزات البوت:*
• تحليل فني دقيق
• إشارات تداول فورية
• مؤشرات متعددة (RSI, MACD, ADX)

⚠️ *تنبيه:* للاستخدام التعليمي فقط
"""
        bot.send_message(
            chat_id,
            welcome_text,
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Error in start: {e}")

@bot.message_handler(commands=["help"])
def help_command(message):
    """معالج أمر المساعدة"""
    try:
        help_text = f"""
🤖 *بوت الإشارات المالية v1.0*

*📋 الأوامر المتاحة:*
/start - بدء البوت واختيار اللغة
/help - عرض هذه المساعدة

*📊 كيفية الاستخدام:*
1️⃣ اختر اللغة المناسبة
2️⃣ اختر زوج العملات من القائمة
3️⃣ احصل على إشارة التداول

*💱 الأزواج المتاحة:* 
{", ".join(PAIRS)}

*📈 المؤشرات المستخدمة:*
• EMA9 & EMA21 - المتوسطات المتحركة
• RSI - مؤشر القوة النسبية
• MACD - مؤشر الماكد
• ADX - مؤشر الاتجاه

*⚠️ تنبيه مهم:*
هذا البوت لأغراض تعليمية فقط
ليس نصيحة مالية استثمارية
"""
        safe_send_message(message.chat.id, help_text, parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Error in help_command: {e}")

# =============================================
# معالج الأزرار (المحسن)
# =============================================

@bot.callback_query_handler(func=lambda call: True)
def callback(call):
    """معالج جميع الأزرار"""
    try:
        chat_id = call.message.chat.id
        message_id = call.message.message_id

        # ==========================================
        # معالجة اختيار اللغة
        # ==========================================
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

        # ==========================================
        # معالجة اختيار الزوج
        # ==========================================
        elif call.data == "pairs":
            keyboard = types.InlineKeyboardMarkup(row_width=2)
            
            # عرض الأزواج المتاحة
            for pair in PAIRS:
                # وضع علامة على الزوج المحدد حالياً
                label = f"✅ {pair}" if user_pair.get(chat_id) == pair else pair
                keyboard.add(
                    types.InlineKeyboardButton(
                        label,
                        callback_data=f"pair_{pair}"
                    )
                )
            
            keyboard.add(
                types.InlineKeyboardButton("🔙 رجوع", callback_data="back")
            )

            bot.edit_message_text(
                "💱 *اختر الزوج:*\n"
                f"الزوج الحالي: {user_pair.get(chat_id, 'غير محدد')}",
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

        # ==========================================
        # العودة للقائمة الرئيسية
        # ==========================================
        elif call.data == "back":
            main_menu(chat_id)

        # ==========================================
        # عرض المساعدة
        # ==========================================
        elif call.data == "help":
            help_command(call.message)

        # ==========================================
        # عرض الإحصائيات
        # ==========================================
        elif call.data == "stats":
            show_stats(chat_id)

        # ==========================================
        # معالجة طلب الإشارة
        # ==========================================
        elif call.data == "signal":
            @rate_limit(seconds=30)
            def process_signal(call):
                chat_id = call.message.chat.id
                pair = user_pair.get(chat_id, PAIRS[0] if PAIRS else "EUR/USD")
                
                # إرسال رسالة انتظار
                waiting_msg = bot.send_message(
                    chat_id,
                    "⏳ *جاري تحليل السوق...*\nيرجى الانتظار",
                    parse_mode='Markdown'
                )

                try:
                    # تحليل السوق
                    analysis = analyze_market(pair)
                    
                    # حذف رسالة الانتظار
                    bot.delete_message(chat_id, waiting_msg.message_id)
                    
                    if analysis and validate_analysis(analysis):
                        # معالجة حالة الانتظار
                        if analysis["signal"] == "WAIT":
                            bot.send_message(
                                chat_id,
                                f"⏸ *لا توجد فرصة قوية حالياً*\n\n"
                                f"💱 *الزوج:* {pair}\n"
                                f"💰 *السعر:* {analysis.get('price', 'N/A')}\n\n"
                                f"📊 *RSI:* {analysis.get('rsi', 'N/A')}\n"
                                f"📊 *ADX:* {analysis.get('adx', 'N/A')}\n\n"
                                f"💡 *السبب:*\n{analysis.get('reason', 'لا يوجد سبب محدد')}",
                                parse_mode='Markdown'
                            )
                            return

                        # تنسيق وإرسال الإشارة
                        signal_message = format_signal_message(pair, analysis)
                        if signal_message:
                            bot.send_message(
                                chat_id,
                                signal_message,
                                parse_mode='Markdown'
                            )
                        else:
                            bot.send_message(
                                chat_id,
                                "❌ حدث خطأ في تنسيق الإشارة",
                                parse_mode='Markdown'
                            )
                    else:
                        bot.send_message(
                            chat_id,
                            f"❌ *فشل تحليل الزوج* {pair}\n"
                            f"البيانات غير مكتملة أو غير صالحة",
                            parse_mode='Markdown'
                        )
                        logger.error(f"Invalid analysis data for {pair}: {analysis}")
                        
                except Exception as e:
                    logger.error(f"Error analyzing {pair}: {e}")
                    try:
                        bot.delete_message(chat_id, waiting_msg.message_id)
                    except:
                        pass
                    
                    bot.send_message(
                        chat_id,
                        f"❌ *حدث خطأ أثناء التحليل*\n"
                        f"الزوج: {pair}\n"
                        f"الخطأ: {str(e)}",
                        parse_mode='Markdown'
                    )
            
            process_signal(call)

    except Exception as e:
        logger.error(f"Error in callback: {e}")
        try:
            bot.answer_callback_query(
                call.id,
                f"❌ حدث خطأ: {str(e)}",
                show_alert=True
            )
        except:
            pass

# =============================================
# معالج الرسائل العامة
# =============================================

@bot.message_handler(func=lambda message: True)
def handle_all_messages(message):
    """معالج جميع الرسائل الأخرى"""
    try:
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(
            types.InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="back")
        )
        
        bot.send_message(
            message.chat.id,
            "❓ استخدم الأزرار للتنقل أو /start للبدء\n"
            "📊 للحصول على إشارة اختر من القائمة",
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Error in handle_all_messages: {e}")

# =============================================
# تشغيل البوت
# =============================================

if __name__ == "__main__":
    try:
        print("🚀 Bot is running...")
        logger.info("Bot started successfully")
        logger.info(f"Available pairs: {PAIRS}")
        bot.infinity_polling(timeout=60, long_polling_timeout=60)
    except KeyboardInterrupt:
        print("\n🛑 Bot stopped by user")
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Bot crashed: {e}")
        print(f"❌ Error: {e}")
