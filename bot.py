# bot.py - النسخة المحسنة بالكامل

import telebot
from telebot import types
from datetime import datetime
from zoneinfo import ZoneInfo
import logging
import time
import json
import os
import threading
import schedule
from functools import wraps
from typing import Dict, Optional, List, Any
from collections import defaultdict
import sys

# استيراد الإعدادات والدوال
from config import BOT_TOKEN, PAIRS, LOG_LEVEL, MAX_RETRIES, SIGNAL_TIMEOUT, NOTIFICATION_INTERVAL
from market import analyze_market

# =============================================
# إعداد التسجيل المحسن
# =============================================
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# =============================================
# إدارة الحالة والبيانات
# =============================================

class UserState:
    """إدارة حالة المستخدم"""
    def __init__(self):
        self.language: str = 'ar'
        self.pair: str = PAIRS[0] if PAIRS else 'EUR/USD'
        self.last_signal_time: float = 0
        self.subscribed: bool = False
        self.notification_pair: Optional[str] = None
        self.notification_interval: int = NOTIFICATION_INTERVAL
        self.risk_level: str = 'medium'  # low, medium, high
        self.timeframe: str = '15m'
        self.total_signals: int = 0
        self.calls: int = 0
        self.puts: int = 0
        self.wins: int = 0
        self.losses: int = 0

class DataStore:
    """تخزين بيانات المستخدمين"""
    def __init__(self, filename='user_data.json'):
        self.filename = filename
        self.data = self.load()
    
    def load(self) -> Dict:
        if os.path.exists(self.filename):
            try:
                with open(self.filename, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading data: {e}")
                return {}
        return {}
    
    def save(self):
        try:
            with open(self.filename, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Error saving data: {e}")
    
    def get_user(self, chat_id: int) -> Dict:
        return self.data.get(str(chat_id), {})
    
    def update_user(self, chat_id: int, data: Dict):
        self.data[str(chat_id)] = data
        self.save()
    
    def get_user_state(self, chat_id: int) -> UserState:
        user_data = self.get_user(chat_id)
        state = UserState()
        for key, value in user_data.items():
            if hasattr(state, key):
                setattr(state, key, value)
        return state
    
    def save_user_state(self, chat_id: int, state: UserState):
        self.update_user(chat_id, state.__dict__)

data_store = DataStore()
user_states: Dict[int, UserState] = {}

def get_user_state(chat_id: int) -> UserState:
    """الحصول على حالة المستخدم"""
    if chat_id not in user_states:
        user_states[chat_id] = data_store.get_user_state(chat_id)
    return user_states[chat_id]

def save_user_state(chat_id: int):
    """حفظ حالة المستخدم"""
    if chat_id in user_states:
        data_store.save_user_state(chat_id, user_states[chat_id])

# =============================================
# نظام الحماية من التكرار
# =============================================

class RateLimiter:
    """نظام حماية متقدم من التكرار"""
    def __init__(self):
        self.requests: Dict[int, List[float]] = defaultdict(list)
        self.limits = {
            'signal': {'max_requests': 5, 'time_window': 60},
            'auto_signal': {'max_requests': 20, 'time_window': 300},
            'analysis': {'max_requests': 3, 'time_window': 30}
        }
    
    def is_allowed(self, chat_id: int, request_type: str) -> bool:
        now = time.time()
        limit = self.limits.get(request_type, {'max_requests': 10, 'time_window': 60})
        
        # تنظيف الطلبات القديمة
        self.requests[chat_id] = [
            req_time for req_time in self.requests[chat_id]
            if now - req_time < limit['time_window']
        ]
        
        if len(self.requests[chat_id]) >= limit['max_requests']:
            return False
        
        self.requests[chat_id].append(now)
        return True

rate_limiter = RateLimiter()

# =============================================
# دوال مساعدة
# =============================================

def get_rsi_status(rsi: float) -> str:
    """تقييم حالة RSI"""
    if rsi >= 70:
        return "🟥 تشبع شرائي"
    elif rsi <= 30:
        return "🟩 تشبع بيعي"
    elif rsi >= 50:
        return "🟨 اتجاه صاعد"
    else:
        return "🟦 اتجاه هابط"

def get_adx_status(adx: float) -> str:
    """تقييم قوة الاتجاه"""
    if adx >= 40:
        return "🔥 اتجاه قوي جداً"
    elif adx >= 25:
        return "💪 اتجاه متوسط"
    else:
        return "👀 اتجاه ضعيف"

def get_extra_tips(analysis: Dict) -> str:
    """نصائح إضافية حسب التحليل"""
    tips = []
    
    if analysis.get('signal') == 'CALL':
        tips.append("📍 ضع أمر الشراء عند السعر الحالي")
        tips.append("🛑 ضع وقف الخسارة تحت أقرب دعم")
        tips.append("🎯 استهدف المقاومة التالية")
    else:
        tips.append("📍 ضع أمر البيع عند السعر الحالي")
        tips.append("🛑 ضع وقف الخسارة فوق أقرب مقاومة")
        tips.append("🎯 استهدف الدعم التالي")
    
    strength = analysis.get('strength', 0)
    if strength > 70:
        tips.append("⭐ إشارة قوية - يمكن زيادة حجم الصفقة")
    elif strength < 30:
        tips.append("⚠️ إشارة ضعيفة - استخدم حجم صفقة صغير")
    
    if analysis.get('rsi', 50) > 70 or analysis.get('rsi', 50) < 30:
        tips.append("🔄 مؤشر RSI يشير إلى انعكاس محتمل")
    
    return "\n".join(f"• {tip}" for tip in tips)

# =============================================
# دوال إعادة المحاولة
# =============================================

def retry_on_error(max_retries: int = MAX_RETRIES, delay: int = 1):
    """مزين لإعادة المحاولة عند الخطأ"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    logger.error(f"Attempt {attempt + 1} failed: {e}")
                    if attempt < max_retries - 1:
                        time.sleep(delay * (attempt + 1))  # تأخير متزايد
                    else:
                        raise
        return wrapper
    return decorator

@retry_on_error(max_retries=3, delay=2)
def safe_send_message(chat_id: int, text: str, **kwargs):
    """إرسال رسالة مع إعادة المحاولة"""
    return bot.send_message(chat_id, text, **kwargs)

# =============================================
# تنسيق الإشارات
# =============================================

def format_signal_message(pair: str, analysis: Dict, state: UserState) -> str:
    """تنسيق رسالة الإشارة بشكل احترافي"""
    
    signal_emoji = "🟢" if analysis["signal"] == "CALL" else "🔴"
    signal_text = "شراء" if analysis["signal"] == "CALL" else "بيع"
    
    # تقييم جودة الإشارة
    strength = analysis.get('strength', 0)
    if strength >= 80:
        quality = "🔥 ممتازة"
    elif strength >= 60:
        quality = "💪 جيدة"
    elif strength >= 40:
        quality = "👍 مقبولة"
    else:
        quality = "👀 ضعيفة"
    
    # معلومات إضافية
    market_condition = "📈 صاعد" if analysis.get('trend') == 'up' else "📉 هابط" if analysis.get('trend') == 'down' else "🔄 جانبي"
    
    return f"""
{signal_emoji} *إشارة تداول - {quality}*

📊 *الزوج:* {pair}
💰 *السعر:* {analysis.get('price', 'N/A')}
🎯 *الاتجاه:* {signal_text}
📈 *القوة:* {strength}%
📊 *حالة السوق:* {market_condition}

📈 *المؤشرات الفنية:*
• EMA9: {analysis.get('ema9', 'N/A')}
• EMA21: {analysis.get('ema21', 'N/A')}
• RSI: {analysis.get('rsi', 'N/A')} - {get_rsi_status(analysis.get('rsi', 50))}
• MACD: {analysis.get('macd', 'N/A')}
• ADX: {analysis.get('adx', 'N/A')} - {get_adx_status(analysis.get('adx', 25))}

⏱ *المدة الموصى بها:* {analysis.get('duration', 60)} ثانية
⏰ *وقت التحليل:* {datetime.now(ZoneInfo('Asia/Riyadh')).strftime('%H:%M:%S')}

💡 *سبب الإشارة:* {analysis.get('reason', 'تحليل فني شامل')}

📝 *نصائح إضافية:*
{get_extra_tips(analysis)}

{'─' * 20}
⚠️ *تنبيه:* هذه المعلومات لأغراض تعليمية فقط
🎯 {state.total_signals} إشارة سابقة | 🏆 {state.wins} ربح | ❌ {state.losses} خسارة
"""

def format_wait_message(pair: str, analysis: Dict) -> str:
    """تنسيق رسالة الانتظار"""
    return f"""
⏸ *لا توجد فرصة قوية حالياً*

💱 *الزوج:* {pair}
💰 *السعر:* {analysis.get('price', 'N/A')}

📊 *المؤشرات الفنية:*
• EMA9: {analysis.get('ema9', 'N/A')}
• EMA21: {analysis.get('ema21', 'N/A')}
• RSI: {analysis.get('rsi', 'N/A')} - {get_rsi_status(analysis.get('rsi', 50))}
• MACD: {analysis.get('macd', 'N/A')}
• ADX: {analysis.get('adx', 'N/A')} - {get_adx_status(analysis.get('adx', 25))}

💡 *السبب:* {analysis.get('reason', 'لا توجد إشارة واضحة حالياً')}

📌 *نصيحة:* انتظر حتى تتكون إشارة واضحة
"""

# =============================================
# إعداد البوت
# =============================================

bot = telebot.TeleBot(BOT_TOKEN)

# =============================================
# دوال القوائم
# =============================================

def main_menu(chat_id: int):
    """القائمة الرئيسية المحسنة"""
    try:
        state = get_user_state(chat_id)
        keyboard = types.InlineKeyboardMarkup(row_width=2)
        
        # الصف الأول - الإشارات
        keyboard.add(
            types.InlineKeyboardButton("📊 إشارة فورية", callback_data="signal"),
            types.InlineKeyboardButton("🔄 إشارة دورية", callback_data="auto_signal")
        )
        
        # الصف الثاني - الإعدادات
        keyboard.add(
            types.InlineKeyboardButton("💱 تغيير الزوج", callback_data="pairs"),
            types.InlineKeyboardButton("⚙️ إعدادات", callback_data="settings")
        )
        
        # الصف الثالث - الإحصائيات والمساعدة
        keyboard.add(
            types.InlineKeyboardButton("📈 إحصائياتي", callback_data="stats"),
            types.InlineKeyboardButton("ℹ️ مساعدة", callback_data="help")
        )
        
        # الصف الرابع - إشعارات
        notify_status = "🔔 مفعل" if state.subscribed else "🔕 معطل"
        keyboard.add(
            types.InlineKeyboardButton(f"الإشعارات: {notify_status}", callback_data="toggle_notify")
        )
        
        # معلومات المستخدم
        user_info = f"""
🏠 *القائمة الرئيسية*

👤 المستخدم: {chat_id}
💱 الزوج الحالي: {state.pair}
🌐 اللغة: {'العربية' if state.language == 'ar' else 'English'}
⚖️ مستوى المخاطرة: {state.risk_level}
📊 الإشارات: {state.total_signals}
📈 الربح: {state.wins} | 📉 الخسارة: {state.losses}

اختر من القائمة:
"""
        
        safe_send_message(
            chat_id,
            user_info,
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Error in main_menu: {e}")
        safe_send_message(chat_id, "❌ حدث خطأ في القائمة الرئيسية")

def settings_menu(chat_id: int):
    """قائمة الإعدادات"""
    state = get_user_state(chat_id)
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    
    # مخاطرة
    risk_emojis = {'low': '🟢', 'medium': '🟡', 'high': '🔴'}
    keyboard.add(
        types.InlineKeyboardButton(
            f"{risk_emojis.get(state.risk_level, '⚖️')} المخاطرة: {state.risk_level}",
            callback_data="risk_settings"
        )
    )
    
    # الإطار الزمني
    keyboard.add(
        types.InlineKeyboardButton(
            f"⏱ الإطار: {state.timeframe}",
            callback_data="timeframe_settings"
        )
    )
    
    # مدة الإشعارات
    keyboard.add(
        types.InlineKeyboardButton(
            f"⏰ مدة الإشعار: {state.notification_interval//60} دقيقة",
            callback_data="notify_interval"
        )
    )
    
    keyboard.add(
        types.InlineKeyboardButton("🔙 رجوع", callback_data="back")
    )
    
    safe_send_message(
        chat_id,
        "⚙️ *الإعدادات*\nقم بتخصيص تجربتك:",
        reply_markup=keyboard,
        parse_mode='Markdown'
    )

# =============================================
# معالجة الأوامر
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
        
        safe_send_message(
            chat_id,
            "🌍 *اختر اللغة / Choose language:*\n\n"
            "🤖 بوت الإشارات المالية\n"
            "📊 تحليل فني دقيق للأسواق",
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Error in start: {e}")

@bot.message_handler(commands=["help"])
def help_command(message):
    """معالج أمر المساعدة"""
    try:
        help_text = """
🤖 *بوت الإشارات المالية v2.0*

*📋 الأوامر المتاحة:*
/start - بدء البوت واختيار اللغة
/help - عرض هذه المساعدة
/stats - عرض إحصائياتك
/pair - تغيير الزوج الحالي
/settings - فتح الإعدادات

*📊 كيفية الاستخدام:*
1️⃣ اختر اللغة المناسبة
2️⃣ اختر زوج العملات من القائمة
3️⃣ احصل على إشارة التداول الفورية
4️⃣ أو فعّل الإشعارات التلقائية

*💱 الأزواج المتاحة:* 
{} 

*📈 المؤشرات المستخدمة:*
• EMA9 & EMA21 - المتوسطات المتحركة
• RSI - مؤشر القوة النسبية
• MACD - مؤشر الماكد
• ADX - مؤشر الاتجاه

*⚠️ تنبيه مهم:*
هذا البوت لأغراض تعليمية فقط
ليس نصيحة مالية استثمارية

🔄 *آخر تحديث:* v2.0
""".format(", ".join(PAIRS))

        safe_send_message(
            message.chat.id,
            help_text,
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Error in help_command: {e}")

@bot.message_handler(commands=["stats"])
def stats_command(message):
    """عرض الإحصائيات"""
    try:
        chat_id = message.chat.id
        state = get_user_state(chat_id)
        
        win_rate = (state.wins / max(state.total_signals, 1)) * 100
        stats_text = f"""
📊 *إحصائياتك الشخصية*

📈 *إجمالي الإشارات:* {state.total_signals}
🟢 *إشارات شراء:* {state.calls}
🔴 *إشارات بيع:* {state.puts}
🏆 *عدد الأرباح:* {state.wins}
📉 *عدد الخسائر:* {state.losses}
📊 *نسبة النجاح:* {win_rate:.1f}%

💱 *الزوج المفضل:* {state.pair}
⚖️ *مستوى المخاطرة:* {state.risk_level}
⏱ *الإطار الزمني:* {state.timeframe}
🔔 *الإشعارات:* {'مفعلة' if state.subscribed else 'معطلة'}
"""
        safe_send_message(chat_id, stats_text, parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Error in stats_command: {e}")

@bot.message_handler(commands=["pair"])
def pair_command(message):
    """تغيير الزوج"""
    try:
        chat_id = message.chat.id
        show_pairs_menu(chat_id)
    except Exception as e:
        logger.error(f"Error in pair_command: {e}")

@bot.message_handler(commands=["settings"])
def settings_command(message):
    """فتح الإعدادات"""
    try:
        chat_id = message.chat.id
        settings_menu(chat_id)
    except Exception as e:
        logger.error(f"Error in settings_command: {e}")

# =============================================
# دوال عرض الأزواج
# =============================================

def show_pairs_menu(chat_id: int, message_id: Optional[int] = None):
    """عرض قائمة الأزواج"""
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    
    for pair in PAIRS:
        keyboard.add(
            types.InlineKeyboardButton(pair, callback_data=f"pair_{pair}")
        )
    
    keyboard.add(
        types.InlineKeyboardButton("🔙 رجوع", callback_data="back")
    )
    
    text = "💱 *اختر زوج العملات:*"
    
    if message_id:
        bot.edit_message_text(
            text,
            chat_id,
            message_id,
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
    else:
        safe_send_message(
            chat_id,
            text,
            reply_markup=keyboard,
            parse_mode='Markdown'
        )

# =============================================
# دوال الإشارات
# =============================================

def send_signal(chat_id: int, pair: str, analysis: Dict):
    """إرسال إشارة للمستخدم"""
    try:
        state = get_user_state(chat_id)
        
        # تحديث الإحصائيات
        state.total_signals += 1
        if analysis["signal"] == "CALL":
            state.calls += 1
        else:
            state.puts += 1
        save_user_state(chat_id)
        
        # تنسيق وإرسال الإشارة
        if analysis["signal"] == "WAIT":
            message = format_wait_message(pair, analysis)
        else:
            message = format_signal_message(pair, analysis, state)
        
        safe_send_message(chat_id, message, parse_mode='Markdown')
        
        # تحديث آخر إشارة
        state.last_signal_time = time.time()
        save_user_state(chat_id)
        
    except Exception as e:
        logger.error(f"Error sending signal: {e}")

def process_signal_request(chat_id: int, pair: str):
    """معالجة طلب الإشارة"""
    try:
        # التحقق من حد التكرار
        if not rate_limiter.is_allowed(chat_id, 'signal'):
            safe_send_message(
                chat_id,
                "⏳ تم تجاوز حد الطلبات. انتظر دقيقة ثم حاول مرة أخرى."
            )
            return
        
        # إرسال رسالة انتظار
        waiting_msg = safe_send_message(
            chat_id,
            "⏳ *جاري تحليل السوق...*\nيرجى الانتظار قليلاً",
            parse_mode='Markdown'
        )
        
        try:
            # تحليل السوق
            analysis = analyze_market(pair)
            
            # حذف رسالة الانتظار
            bot.delete_message(chat_id, waiting_msg.message_id)
            
            if analysis:
                send_signal(chat_id, pair, analysis)
            else:
                safe_send_message(
                    chat_id,
                    f"❌ *فشل تحليل الزوج* {pair}\n"
                    "يرجى المحاولة مرة أخرى لاحقاً",
                    parse_mode='Markdown'
                )
                
        except Exception as e:
            logger.error(f"Error analyzing {pair}: {e}")
            try:
                bot.delete_message(chat_id, waiting_msg.message_id)
            except:
                pass
            
            safe_send_message(
                chat_id,
                f"❌ *حدث خطأ أثناء التحليل*\n"
                f"الزوج: {pair}\n"
                f"الخطأ: {str(e)}\n"
                f"يرجى المحاولة مرة أخرى",
                parse_mode='Markdown'
            )
            
    except Exception as e:
        logger.error(f"Error in process_signal_request: {e}")

# =============================================
# نظام الإشعارات التلقائية
# =============================================

notifications_active = True
notification_thread = None

def run_notification_scheduler():
    """تشغيل جدول الإشعارات"""
    global notifications_active
    while notifications_active:
        try:
            schedule.run_pending()
            time.sleep(1)
        except Exception as e:
            logger.error(f"Error in notification scheduler: {e}")

def start_notifications(chat_id: int, pair: str, interval: int = NOTIFICATION_INTERVAL):
    """بدء الإشعارات التلقائية للمستخدم"""
    def notify():
        try:
            state = get_user_state(chat_id)
            if state.subscribed:
                analysis = analyze_market(pair)
                if analysis and analysis.get('signal') in ['CALL', 'PUT']:
                    send_signal(chat_id, pair, analysis)
        except Exception as e:
            logger.error(f"Error in notification: {e}")
    
    # إلغاء أي جدولة سابقة
    schedule.clear(f"notify_{chat_id}")
    
    # جدولة الإشعارات الجديدة
    schedule.every(interval).seconds.do(notify).tag(f"notify_{chat_id}")
    
    # بدء الخيط إذا لم يكن قيد التشغيل
    global notification_thread
    if notification_thread is None or not notification_thread.is_alive():
        notification_thread = threading.Thread(
            target=run_notification_scheduler,
            daemon=True
        )
        notification_thread.start()

def stop_notifications(chat_id: int):
    """إيقاف الإشعارات التلقائية للمستخدم"""
    schedule.clear(f"notify_{chat_id}")
    state = get_user_state(chat_id)
    state.subscribed = False
    save_user_state(chat_id)

# =============================================
# معالج الأزرار (المحسن)
# =============================================

@bot.callback_query_handler(func=lambda call: True)
def callback(call):
    """معالج جميع الأزرار"""
    try:
        chat_id = call.message.chat.id
        message_id = call.message.message_id
        state = get_user_state(chat_id)
        
        # اللغة
        if call.data == "ar":
            state.language = "ar"
            save_user_state(chat_id)
            bot.edit_message_text(
                "✅ *تم اختيار العربية*",
                chat_id,
                message_id,
                parse_mode='Markdown'
            )
            main_menu(chat_id)
            
        elif call.data == "en":
            state.language = "en"
            save_user_state(chat_id)
            bot.edit_message_text(
                "✅ *English selected*",
                chat_id,
                message_id,
                parse_mode='Markdown'
            )
            main_menu(chat_id)
        
        # الأزواج
        elif call.data == "pairs":
            show_pairs_menu(chat_id, message_id)
            
        elif call.data.startswith("pair_"):
            pair = call.data.replace("pair_", "")
            state.pair = pair
            save_user_state(chat_id)
            
            bot.edit_message_text(
                f"✅ *تم اختيار الزوج*\n💱 {pair}",
                chat_id,
                message_id,
                parse_mode='Markdown'
            )
            main_menu(chat_id)
        
        # الإشارات
        elif call.data == "signal":
            pair = state.pair
            process_signal_request(chat_id, pair)
            
        elif call.data == "auto_signal":
            if state.subscribed:
                stop_notifications(chat_id)
                bot.edit_message_text(
                    "🔕 *تم إيقاف الإشعارات التلقائية*",
                    chat_id,
                    message_id,
                    parse_mode='Markdown'
                )
            else:
                state.subscribed = True
                save_user_state(chat_id)
                start_notifications(
                    chat_id,
                    state.pair,
                    state.notification_interval
                )
                bot.edit_message_text(
                    f"🔔 *تم تفعيل الإشعارات التلقائية*\n"
                    f"💱 الزوج: {state.pair}\n"
                    f"⏱ كل {state.notification_interval//60} دقيقة",
                    chat_id,
                    message_id,
                    parse_mode='Markdown'
                )
            main_menu(chat_id)
        
        # الإعدادات
        elif call.data == "settings":
            settings_menu(chat_id)
            
        elif call.data == "risk_settings":
            # مستويات المخاطرة
            keyboard = types.InlineKeyboardMarkup(row_width=3)
            for risk in ['low', 'medium', 'high']:
                emoji = {'low': '🟢', 'medium': '🟡', 'high': '🔴'}.get(risk, '⚖️')
                keyboard.add(
                    types.InlineKeyboardButton(
                        f"{emoji} {risk}",
                        callback_data=f"risk_{risk}"
                    )
                )
            keyboard.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="settings"))
            
            bot.edit_message_text(
                "⚖️ *اختر مستوى المخاطرة:*\n"
                "🟢 منخفض - إشارات آمنة\n"
                "🟡 متوسط - توازن بين الأمان والربح\n"
                "🔴 عالي - إشارات ذات مخاطرة عالية",
                chat_id,
                message_id,
                reply_markup=keyboard,
                parse_mode='Markdown'
            )
            
        elif call.data.startswith("risk_"):
            risk = call.data.replace("risk_", "")
            state.risk_level = risk
            save_user_state(chat_id)
            bot.edit_message_text(
                f"✅ *تم تعيين مستوى المخاطرة:* {risk}",
                chat_id,
                message_id,
                parse_mode='Markdown'
            )
            settings_menu(chat_id)
            
        elif call.data == "timeframe_settings":
            keyboard = types.InlineKeyboardMarkup(row_width=3)
            for tf in ['5m', '15m', '30m', '1h', '4h', '1d']:
                keyboard.add(
                    types.InlineKeyboardButton(tf, callback_data=f"tf_{tf}")
                )
            keyboard.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="settings"))
            
            bot.edit_message_text(
                "⏱ *اختر الإطار الزمني:*",
                chat_id,
                message_id,
                reply_markup=keyboard,
                parse_mode='Markdown'
            )
            
        elif call.data.startswith("tf_"):
            tf = call.data.replace("tf_", "")
            state.timeframe = tf
            save_user_state(chat_id)
            bot.edit_message_text(
                f"✅ *تم تعيين الإطار الزمني:* {tf}",
                chat_id,
                message_id,
                parse_mode='Markdown'
            )
            settings_menu(chat_id)
            
        elif call.data == "notify_interval":
            keyboard = types.InlineKeyboardMarkup(row_width=3)
            for interval in [60, 180, 300, 600, 1800]:  # 1, 3, 5, 10, 30 دقيقة
                minutes = interval // 60
                keyboard.add(
                    types.InlineKeyboardButton(
                        f"{minutes} دقيقة" if minutes > 0 else f"{interval} ثانية",
                        callback_data=f"interval_{interval}"
                    )
                )
            keyboard.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="settings"))
            
            bot.edit_message_text(
                "⏰ *اختر مدة الإشعارات:*",
                chat_id,
                message_id,
                reply_markup=keyboard,
                parse_mode='Markdown'
            )
            
        elif call.data.startswith("interval_"):
            interval = int(call.data.replace("interval_", ""))
            state.notification_interval = interval
            save_user_state(chat_id)
            
            # تحديث الإشعارات إذا كانت مفعلة
            if state.subscribed:
                start_notifications(chat_id, state.pair, interval)
            
            bot.edit_message_text(
                f"✅ *تم تعيين مدة الإشعارات:* {interval//60} دقيقة" if interval >= 60 else f"✅ *تم تعيين مدة الإشعارات:* {interval} ثانية",
                chat_id,
                message_id,
                parse_mode='Markdown'
            )
            settings_menu(chat_id)
            
        elif call.data == "toggle_notify":
            state.subscribed = not state.subscribed
            save_user_state(chat_id)
            
            if state.subscribed:
                start_notifications(chat_id, state.pair, state.notification_interval)
                bot.answer_callback_query(
                    call.id,
                    "🔔 تم تفعيل الإشعارات",
                    show_alert=True
                )
            else:
                stop_notifications(chat_id)
                bot.answer_callback_query(
                    call.id,
                    "🔕 تم إيقاف الإشعارات",
                    show_alert=True
                )
            main_menu(chat_id)
        
        # الإحصائيات
        elif call.data == "stats":
            stats_command(call.message)
        
        # المساعدة
        elif call.data == "help":
            help_command(call.message)
        
        # الرجوع
        elif call.data == "back":
            main_menu(chat_id)
        
        # أي خيار آخر
        else:
            bot.answer_callback_query(
                call.id,
                "❌ خيار غير معروف",
                show_alert=True
            )
            
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
        safe_send_message(
            message.chat.id,
            "❓ استخدم /start للبدء أو /help للمساعدة\n"
            "📊 للحصول على إشارة استخدم القائمة الرئيسية"
        )
    except Exception as e:
        logger.error(f"Error in handle_all_messages: {e}")

# =============================================
# تشغيل البوت
# =============================================

def main():
    """الوظيفة الرئيسية لتشغيل البوت"""
    try:
        print("🚀 Bot is running...")
        logger.info("Bot started successfully")
        logger.info(f"Available pairs: {PAIRS}")
        
        # بدء الإشعارات التلقائية للمستخدمين المفعلين
        for chat_id_str, user_data in data_store.data.items():
            if user_data.get('subscribed', False):
                chat_id = int(chat_id_str)
                pair = user_data.get('pair', PAIRS[0])
                interval = user_data.get('notification_interval', NOTIFICATION_INTERVAL)
                start_notifications(chat_id, pair, interval)
                logger.info(f"Started notifications for user {chat_id}")
        
        # تشغيل البوت
        bot.infinity_polling(
            timeout=60,
            long_polling_timeout=60,
            skip_pending=True
        )
        
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
        print("\n🛑 Bot stopped")
        
    except Exception as e:
        logger.error(f"Bot crashed: {e}")
        print(f"❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
