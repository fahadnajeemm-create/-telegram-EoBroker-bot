import telebot
from telebot import types
from datetime import datetime, timedelta
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
import random

# استيراد الإعدادات والدوال
from config import BOT_TOKEN, PAIRS
from market import analyze_market

# =============================================
# إعداد التسجيل
# =============================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('binary_bot.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# =============================================
# إدارة الحالة والبيانات للتداول الثنائي
# =============================================

class BinaryTradeState:
    """حالة التداول الثنائي للمستخدم"""
    def __init__(self):
        self.language: str = 'ar'
        self.pair: str = PAIRS[0] if PAIRS else 'EUR/USD'
        self.last_signal_time: float = 0
        self.subscribed: bool = False
        self.notification_interval: int = 300
        
        # إعدادات التداول
        self.risk_level: str = 'medium'  # low, medium, high
        self.expiry_time: int = 60  # ثانية
        self.investment_amount: float = 10.0
        self.trade_strategy: str = 'standard'  # standard, martingale, fibonacci
        self.max_investment: float = 100.0
        
        # إحصائيات التداول
        self.total_signals: int = 0
        self.calls: int = 0
        self.puts: int = 0
        self.wins: int = 0
        self.losses: int = 0
        self.profit: float = 0.0
        self.total_invested: float = 0.0
        self.win_rate: float = 0.0
        
        # تتبع الصفقات
        self.trades: List[Dict] = []
        self.current_trade: Optional[Dict] = None

class DataStore:
    """تخزين بيانات المستخدمين"""
    def __init__(self, filename='binary_user_data.json'):
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
    
    def get_user_state(self, chat_id: int) -> BinaryTradeState:
        user_data = self.get_user(chat_id)
        state = BinaryTradeState()
        for key, value in user_data.items():
            if hasattr(state, key):
                setattr(state, key, value)
        return state
    
    def save_user_state(self, chat_id: int, state: BinaryTradeState):
        state_dict = state.__dict__.copy()
        self.update_user(chat_id, state_dict)

data_store = DataStore()
user_states: Dict[int, BinaryTradeState] = {}

def get_user_state(chat_id: int) -> BinaryTradeState:
    """الحصول على حالة المستخدم"""
    if chat_id not in user_states:
        user_states[chat_id] = data_store.get_user_state(chat_id)
    return user_states[chat_id]

def save_user_state(chat_id: int):
    """حفظ حالة المستخدم"""
    if chat_id in user_states:
        data_store.save_user_state(chat_id, user_states[chat_id])

# =============================================
# نظام إدارة الصفقات للتداول الثنائي
# =============================================

class TradeManager:
    """إدارة صفقات التداول الثنائي"""
    
    def __init__(self, chat_id: int):
        self.chat_id = chat_id
        self.state = get_user_state(chat_id)
    
    def open_trade(self, pair: str, signal: str, price: float, expiry: int, investment: float) -> Dict:
        """فتح صفقة جديدة"""
        trade = {
            'id': len(self.state.trades) + 1,
            'pair': pair,
            'signal': signal,
            'entry_price': price,
            'expiry': expiry,
            'investment': investment,
            'open_time': datetime.now(ZoneInfo('Asia/Riyadh')).isoformat(),
            'close_time': None,
            'result': None,
            'profit': 0.0,
            'status': 'active'
        }
        
        self.state.trades.append(trade)
        self.state.total_invested += investment
        self.state.current_trade = trade
        save_user_state(self.chat_id)
        
        return trade
    
    def close_trade(self, trade_id: int, result: str, profit: float):
        """إغلاق صفقة"""
        for trade in self.state.trades:
            if trade['id'] == trade_id:
                trade['status'] = 'closed'
                trade['close_time'] = datetime.now(ZoneInfo('Asia/Riyadh')).isoformat()
                trade['result'] = result
                trade['profit'] = profit
                
                if result == 'win':
                    self.state.wins += 1
                    self.state.profit += profit
                else:
                    self.state.losses += 1
                
                self.state.total_signals += 1
                self.state.current_trade = None
                
                # تحديث نسبة الفوز
                total = self.state.wins + self.state.losses
                if total > 0:
                    self.state.win_rate = (self.state.wins / total) * 100
                
                save_user_state(self.chat_id)
                break
    
    def get_active_trades(self) -> List[Dict]:
        """الحصول على الصفقات النشطة"""
        return [t for t in self.state.trades if t['status'] == 'active']
    
    def get_trade_stats(self) -> Dict:
        """الحصول على إحصائيات التداول"""
        return {
            'total_trades': self.state.total_signals,
            'wins': self.state.wins,
            'losses': self.state.losses,
            'win_rate': self.state.win_rate,
            'profit': self.state.profit,
            'total_invested': self.state.total_invested,
            'roi': (self.state.profit / max(self.state.total_invested, 1)) * 100
        }

# =============================================
# دوال تحليل السوق للتداول الثنائي
# =============================================

def get_binary_signal(analysis: Dict) -> Dict:
    """تحويل التحليل الفني إلى إشارة تداول ثنائي"""
    
    signal = {
        'direction': 'WAIT',
        'confidence': 0,
        'expiry': 60,
        'reason': '',
        'entry_price': analysis.get('price', 0)
    }
    
    # استخراج المؤشرات
    rsi = analysis.get('rsi', 50)
    macd = analysis.get('macd', 0)
    adx = analysis.get('adx', 25)
    ema9 = analysis.get('ema9', 0)
    ema21 = analysis.get('ema21', 0)
    strength = analysis.get('strength', 0)
    
    # إشارة CALL (شراء)
    if (rsi < 70 and rsi > 30 and 
        macd > 0 and 
        ema9 > ema21 and 
        adx > 25 and 
        strength > 50):
        signal['direction'] = 'CALL'
        signal['confidence'] = min(100, strength + random.randint(0, 10))
        signal['expiry'] = 60
        signal['reason'] = 'المؤشرات تشير إلى اتجاه صاعد قوي'
    
    # إشارة PUT (بيع)
    elif (rsi < 70 and rsi > 30 and 
          macd < 0 and 
          ema9 < ema21 and 
          adx > 25 and 
          strength > 50):
        signal['direction'] = 'PUT'
        signal['confidence'] = min(100, strength + random.randint(0, 10))
        signal['expiry'] = 60
        signal['reason'] = 'المؤشرات تشير إلى اتجاه هابط قوي'
    
    # إشارة CALL مع تشبع شرائي
    elif (rsi > 70 and 
          macd < 0 and 
          adx > 30 and 
          strength > 60):
        signal['direction'] = 'PUT'
        signal['confidence'] = 70
        signal['expiry'] = 120
        signal['reason'] = 'تشبع شرائي مع انعكاس محتمل للهبوط'
    
    # إشارة PUT مع تشبع بيعي
    elif (rsi < 30 and 
          macd > 0 and 
          adx > 30 and 
          strength > 60):
        signal['direction'] = 'CALL'
        signal['confidence'] = 70
        signal['expiry'] = 120
        signal['reason'] = 'تشبع بيعي مع انعكاس محتمل للصعود'
    
    else:
        signal['reason'] = 'لا توجد إشارة واضحة حالياً'
        signal['confidence'] = strength
    
    return signal

# =============================================
# دوال التداول الثنائي
# =============================================

def calculate_investment(state: BinaryTradeState) -> float:
    """حساب مبلغ الاستثمار حسب استراتيجية التداول"""
    
    base_amount = state.investment_amount
    
    if state.trade_strategy == 'martingale':
        # مضاعفة المبلغ بعد الخسارة
        last_trades = state.trades[-5:]
        losses = sum(1 for t in last_trades if t.get('result') == 'loss')
        multiplier = 2 ** losses
        return min(base_amount * multiplier, state.max_investment)
    
    elif state.trade_strategy == 'fibonacci':
        # استراتيجية فيبوناتشي
        fib_numbers = [1, 1, 2, 3, 5, 8, 13, 21, 34, 55]
        losses = sum(1 for t in state.trades[-10:] if t.get('result') == 'loss')
        idx = min(losses, len(fib_numbers) - 1)
        return min(base_amount * fib_numbers[idx], state.max_investment)
    
    else:  # standard
        return base_amount

def execute_binary_trade(chat_id: int, pair: str, analysis: Dict, bot_instance) -> Dict:
    """تنفيذ صفقة تداول ثنائي"""
    
    state = get_user_state(chat_id)
    trade_manager = TradeManager(chat_id)
    
    # الحصول على إشارة التداول
    signal = get_binary_signal(analysis)
    
    if signal['direction'] == 'WAIT':
        return {
            'status': 'wait',
            'message': 'لا توجد فرصة تداول مناسبة حالياً',
            'analysis': analysis
        }
    
    # حساب مبلغ الاستثمار
    investment = calculate_investment(state)
    
    # فتح الصفقة
    trade = trade_manager.open_trade(
        pair=pair,
        signal=signal['direction'],
        price=signal['entry_price'],
        expiry=signal['expiry'],
        investment=investment
    )
    
    # جدولة إغلاق الصفقة
    schedule_close_trade(chat_id, trade['id'], signal['direction'], signal['entry_price'], bot_instance)
    
    return {
        'status': 'executed',
        'trade': trade,
        'signal': signal,
        'analysis': analysis
    }

def schedule_close_trade(chat_id: int, trade_id: int, direction: str, entry_price: float, bot_instance):
    """جدولة إغلاق الصفقة"""
    
    state = get_user_state(chat_id)
    expiry = state.expiry_time
    
    def close_trade():
        try:
            # محاكاة نتيجة الصفقة
            result, profit = simulate_trade_result(direction, entry_price)
            
            trade_manager = TradeManager(chat_id)
            trade_manager.close_trade(trade_id, result, profit)
            
            # الحصول على الصفقة المغلقة
            state = get_user_state(chat_id)
            trade = next((t for t in state.trades if t['id'] == trade_id), None)
            
            if trade:
                # إرسال النتيجة
                message = format_trade_result(trade, result, profit)
                try:
                    bot_instance.send_message(chat_id, message, parse_mode='Markdown')
                except Exception as e:
                    logger.error(f"Error sending trade result: {e}")
                    
        except Exception as e:
            logger.error(f"Error closing trade: {e}")
    
    # جدولة الإغلاق بعد المدة المحددة
    timer = threading.Timer(expiry, close_trade)
    timer.daemon = True
    timer.start()

def simulate_trade_result(direction: str, entry_price: float) -> tuple:
    """محاكاة نتيجة الصفقة"""
    
    # محاكاة حركة السعر
    price_change = random.uniform(-0.005, 0.005)
    current_price = entry_price * (1 + price_change)
    
    # تحديد النتيجة
    if direction == 'CALL':
        win = current_price > entry_price
    else:  # PUT
        win = current_price < entry_price
    
    # حساب الربح/الخسارة
    investment = 10.0  # سيتم جلبها من البيانات الفعلية
    if win:
        profit = investment * 0.8
        return 'win', profit
    else:
        profit = -investment
        return 'loss', profit

# =============================================
# تنسيق رسائل التداول الثنائي
# =============================================

def format_binary_signal(pair: str, analysis: Dict, signal: Dict, state: BinaryTradeState) -> str:
    """تنسيق رسالة الإشارة للتداول الثنائي"""
    
    direction_emoji = "🟢" if signal['direction'] == 'CALL' else "🔴" if signal['direction'] == 'PUT' else "⏸"
    direction_text = "شراء (CALL)" if signal['direction'] == 'CALL' else "بيع (PUT)" if signal['direction'] == 'PUT' else "انتظار"
    
    confidence = signal['confidence']
    if confidence >= 80:
        confidence_level = "🔥 عالية جداً"
    elif confidence >= 60:
        confidence_level = "💪 عالية"
    elif confidence >= 40:
        confidence_level = "👍 متوسطة"
    else:
        confidence_level = "👀 منخفضة"
    
    expiry_minutes = signal['expiry'] // 60
    expiry_text = f"{expiry_minutes} دقيقة" if expiry_minutes > 0 else f"{signal['expiry']} ثانية"
    
    return f"""
{direction_emoji} *إشارة تداول ثنائي*

📊 *الزوج:* {pair}
💰 *سعر الدخول:* {signal['entry_price']:.5f}
🎯 *الاتجاه:* {direction_text}
📈 *الثقة:* {confidence}% ({confidence_level})

📊 *المؤشرات الفنية:*
• RSI: {analysis.get('rsi', 'N/A')}
• MACD: {analysis.get('macd', 'N/A')}
• ADX: {analysis.get('adx', 'N/A')}
• EMA9: {analysis.get('ema9', 'N/A')}
• EMA21: {analysis.get('ema21', 'N/A')}

⏱ *مدة الصفقة:* {expiry_text}
💡 *السبب:* {signal['reason']}

{'─' * 20}
📊 *إحصائياتك:*
• إجمالي الصفقات: {state.total_signals}
• أرباح: {state.wins} | خسائر: {state.losses}
• نسبة الفوز: {state.win_rate:.1f}%
• الربح الإجمالي: ${state.profit:.2f}

⚠️ *تحذير:* التداول الثنائي ينطوي على مخاطر عالية
"""

def format_trade_result(trade: Dict, result: str, profit: float) -> str:
    """تنسيق نتيجة الصفقة"""
    
    if result == 'win':
        emoji = "🎉"
        status = "ربح"
        color = "🟢"
    else:
        emoji = "😔"
        status = "خسارة"
        color = "🔴"
    
    roi = (profit / trade['investment']) * 100 if trade['investment'] > 0 else 0
    
    return f"""
{emoji} *نتيجة الصفقة - {status}*

{color} *الزوج:* {trade['pair']}
💰 *المبلغ المستثمر:* ${trade['investment']:.2f}
📊 *النتيجة:* {status} ({roi:.1f}%)
{'✅' if result == 'win' else '❌'} *الربح/الخسارة:* ${profit:.2f}

⏱ *وقت الدخول:* {trade['open_time'][:19]}
⏰ *وقت الخروج:* {datetime.now(ZoneInfo('Asia/Riyadh')).strftime('%Y-%m-%d %H:%M:%S')}

📈 *نصيحة:* {
    '🌟 استمر بنفس الاستراتيجية' if result == 'win' else 
    '💡 راجع استراتيجيتك وحاول مرة أخرى'
}
"""

# =============================================
# إعداد البوت
# =============================================

bot = telebot.TeleBot(BOT_TOKEN)

# =============================================
# دوال القوائم
# =============================================

def main_menu(chat_id: int):
    """القائمة الرئيسية للتداول الثنائي"""
    try:
        state = get_user_state(chat_id)
        keyboard = types.InlineKeyboardMarkup(row_width=2)
        
        keyboard.add(
            types.InlineKeyboardButton("📊 إشارة تداول", callback_data="signal"),
            types.InlineKeyboardButton("💱 تغيير الزوج", callback_data="pairs")
        )
        
        keyboard.add(
            types.InlineKeyboardButton("⚙️ إعدادات التداول", callback_data="settings"),
            types.InlineKeyboardButton("📈 إحصائياتي", callback_data="stats")
        )
        
        notify_status = "🔔 مفعل" if state.subscribed else "🔕 معطل"
        keyboard.add(
            types.InlineKeyboardButton(f"الإشعارات: {notify_status}", callback_data="toggle_notify")
        )
        
        keyboard.add(
            types.InlineKeyboardButton("🛡 إدارة المخاطر", callback_data="risk_management"),
            types.InlineKeyboardButton("ℹ️ مساعدة", callback_data="help")
        )
        
        user_info = f"""
🏠 *القائمة الرئيسية - تداول ثنائي*

💱 الزوج الحالي: {state.pair}
⏱ مدة الصفقة: {state.expiry_time} ثانية
💰 المبلغ الافتراضي: ${state.investment_amount}
⚖️ مستوى المخاطرة: {state.risk_level}
📊 استراتيجية: {state.trade_strategy}

📈 *إحصائيات سريعة:*
• الصفقات: {state.total_signals}
• الربح: {state.wins} | الخسارة: {state.losses}
• نسبة الفوز: {state.win_rate:.1f}%
• إجمالي الربح: ${state.profit:.2f}

اختر من القائمة:
"""
        
        bot.send_message(
            chat_id,
            user_info,
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Error in main_menu: {e}")
        bot.send_message(chat_id, "❌ حدث خطأ في القائمة الرئيسية")

def settings_menu(chat_id: int):
    """قائمة إعدادات التداول"""
    state = get_user_state(chat_id)
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    
    keyboard.add(
        types.InlineKeyboardButton(
            f"💰 المبلغ: ${state.investment_amount}",
            callback_data="investment_amount"
        )
    )
    keyboard.add(
        types.InlineKeyboardButton(
            f"⏱ المدة: {state.expiry_time}s",
            callback_data="expiry_time"
        )
    )
    keyboard.add(
        types.InlineKeyboardButton(
            f"⚖️ المخاطرة: {state.risk_level}",
            callback_data="risk_level"
        )
    )
    keyboard.add(
        types.InlineKeyboardButton(
            f"📊 استراتيجية: {state.trade_strategy}",
            callback_data="trade_strategy"
        )
    )
    keyboard.add(
        types.InlineKeyboardButton("🔙 رجوع", callback_data="back")
    )
    
    bot.send_message(
        chat_id,
        "⚙️ *إعدادات التداول الثنائي*\nقم بتخصيص إعدادات التداول الخاصة بك:",
        reply_markup=keyboard,
        parse_mode='Markdown'
    )

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
    
    text = "💱 *اختر زوج العملات للتداول:*"
    
    if message_id:
        bot.edit_message_text(
            text,
            chat_id,
            message_id,
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
    else:
        bot.send_message(
            chat_id,
            text,
            reply_markup=keyboard,
            parse_mode='Markdown'
        )

# =============================================
# معالجة الأوامر
# =============================================

@bot.message_handler(commands=["start"])
def start(message):
    try:
        chat_id = message.chat.id
        keyboard = types.InlineKeyboardMarkup(row_width=2)
        
        keyboard.add(
            types.InlineKeyboardButton("العربية 🇸🇦", callback_data="ar"),
            types.InlineKeyboardButton("English 🇬🇧", callback_data="en")
        )
        
        welcome_text = """
🌍 *اختر اللغة / Choose language:*

🤖 *بوت التداول الثنائي v3.0*

📊 *مميزات البوت:*
• تحليل فني دقيق للأسواق
• إشارات تداول ثنائي احترافية
• إدارة متقدمة للمخاطر
• إحصائيات دقيقة للأداء

⚠️ *تنبيه مهم:* 
التداول الثنائي ينطوي على مخاطر عالية
استثمر فقط ما يمكنك تحمل خسارته
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
    try:
        help_text = """
🤖 *بوت التداول الثنائي v3.0*

*📋 الأوامر المتاحة:*
/start - بدء البوت
/help - عرض هذه المساعدة
/stats - عرض إحصائياتك

*💱 الأزواج المتاحة:* 
{} 

*⏱ مدة الصفقات:*
• 60 ثانية (1 دقيقة)
• 120 ثانية (2 دقيقة)
• 300 ثانية (5 دقائق)

*⚠️ تحذير هام:*
هذا البوت لأغراض تعليمية فقط
التداول الثنائي يحمل مخاطر عالية
استثمر بحكمة
""".format(", ".join(PAIRS))

        bot.send_message(
            message.chat.id,
            help_text,
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Error in help_command: {e}")

@bot.message_handler(commands=["stats"])
def stats_command(message):
    try:
        chat_id = message.chat.id
        state = get_user_state(chat_id)
        
        stats_text = f"""
📊 *إحصائيات التداول الخاصة بك*

📈 *إجمالي الصفقات:* {state.total_signals}
🟢 *صفقات ربح:* {state.wins}
🔴 *صفقات خسارة:* {state.losses}
📊 *نسبة الفوز:* {state.win_rate:.1f}%

💰 *الإحصائيات المالية:*
• إجمالي الاستثمار: ${state.total_invested:.2f}
• إجمالي الربح: ${state.profit:.2f}
• العائد على الاستثمار: {(state.profit / max(state.total_invested, 1)) * 100:.1f}%

⚙️ *إعدادات التداول:*
• الزوج المفضل: {state.pair}
• مدة الصفقة: {state.expiry_time} ثانية
• مبلغ الاستثمار: ${state.investment_amount}
• مستوى المخاطرة: {state.risk_level}
• استراتيجية التداول: {state.trade_strategy}

📊 *آخر 5 صفقات:*
"""
        recent_trades = state.trades[-5:]
        if recent_trades:
            for trade in recent_trades:
                result_emoji = "✅" if trade.get('result') == 'win' else "❌" if trade.get('result') == 'loss' else "⏳"
                stats_text += f"\n{result_emoji} {trade['pair']} | {trade.get('result', 'قيد التنفيذ')} | ${trade.get('profit', 0):.2f}"
        else:
            stats_text += "\nلا توجد صفقات حتى الآن"
        
        bot.send_message(chat_id, stats_text, parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Error in stats_command: {e}")

# =============================================
# معالج الأزرار
# =============================================

@bot.callback_query_handler(func=lambda call: True)
def callback(call):
    try:
        chat_id = call.message.chat.id
        message_id = call.message.message_id
        state = get_user_state(chat_id)
        
        # معالجة اللغة
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
        
        # معالجة الأزواج
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
        
        # معالجة الإشارات
        elif call.data == "signal":
            pair = state.pair
            
            waiting_msg = bot.send_message(
                chat_id,
                "⏳ *جاري تحليل السوق...*\nيرجى الانتظار",
                parse_mode='Markdown'
            )
            
            try:
                analysis = analyze_market(pair)
                bot.delete_message(chat_id, waiting_msg.message_id)
                
                if analysis:
                    result = execute_binary_trade(chat_id, pair, analysis, bot)
                    
                    if result['status'] == 'wait':
                        bot.send_message(
                            chat_id,
                            f"⏸ *لا توجد فرصة تداول مناسبة*\n\n"
                            f"💱 الزوج: {pair}\n"
                            f"💡 السبب: {result['message']}",
                            parse_mode='Markdown'
                        )
                    else:
                        signal_msg = format_binary_signal(
                            pair,
                            result['analysis'],
                            result['signal'],
                            state
                        )
                        bot.send_message(chat_id, signal_msg, parse_mode='Markdown')
                else:
                    bot.send_message(
                        chat_id,
                        f"❌ *خطأ في تحليل الزوج* {pair}",
                        parse_mode='Markdown'
                    )
                    
            except Exception as e:
                logger.error(f"Error in signal processing: {e}")
                try:
                    bot.delete_message(chat_id, waiting_msg.message_id)
                except:
                    pass
                bot.send_message(
                    chat_id,
                    f"❌ *حدث خطأ أثناء التحليل*\n{str(e)}",
                    parse_mode='Markdown'
                )
        
        # معالجة الإعدادات
        elif call.data == "settings":
            settings_menu(chat_id)
            
        elif call.data == "investment_amount":
            keyboard = types.InlineKeyboardMarkup(row_width=3)
            for amount in [5, 10, 25, 50, 100]:
                keyboard.add(
                    types.InlineKeyboardButton(f"${amount}", callback_data=f"inv_{amount}")
                )
            keyboard.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="settings"))
            
            bot.edit_message_text(
                "💰 *اختر مبلغ الاستثمار:*",
                chat_id,
                message_id,
                reply_markup=keyboard,
                parse_mode='Markdown'
            )
            
        elif call.data.startswith("inv_"):
            amount = float(call.data.replace("inv_", ""))
            state.investment_amount = amount
            save_user_state(chat_id)
            bot.edit_message_text(
                f"✅ *تم تعيين مبلغ الاستثمار:* ${amount}",
                chat_id,
                message_id,
                parse_mode='Markdown'
            )
            settings_menu(chat_id)
            
        elif call.data == "expiry_time":
            keyboard = types.InlineKeyboardMarkup(row_width=3)
            for time in [60, 120, 300]:
                minutes = time // 60
                label = f"{minutes} دقيقة" if minutes > 0 else f"{time} ثانية"
                keyboard.add(
                    types.InlineKeyboardButton(label, callback_data=f"exp_{time}")
                )
            keyboard.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="settings"))
            
            bot.edit_message_text(
                "⏱ *اختر مدة الصفقة:*",
                chat_id,
                message_id,
                reply_markup=keyboard,
                parse_mode='Markdown'
            )
            
        elif call.data.startswith("exp_"):
            expiry = int(call.data.replace("exp_", ""))
            state.expiry_time = expiry
            save_user_state(chat_id)
            minutes = expiry // 60
            label = f"{minutes} دقيقة" if minutes > 0 else f"{expiry} ثانية"
            bot.edit_message_text(
                f"✅ *تم تعيين مدة الصفقة:* {label}",
                chat_id,
                message_id,
                parse_mode='Markdown'
            )
            settings_menu(chat_id)
            
        elif call.data == "risk_level":
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
                "🟢 منخفض - استثمار آمن\n"
                "🟡 متوسط - توازن\n"
                "🔴 عالي - مخاطرة عالية",
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
            
        elif call.data == "trade_strategy":
            keyboard = types.InlineKeyboardMarkup(row_width=2)
            keyboard.add(
                types.InlineKeyboardButton("📊 Standard", callback_data="strat_standard"),
                types.InlineKeyboardButton("📈 Martingale", callback_data="strat_martingale"),
                types.InlineKeyboardButton("🔢 Fibonacci", callback_data="strat_fibonacci")
            )
            keyboard.add(types.InlineKeyboardButton("🔙 رجوع", callback_data="settings"))
            
            bot.edit_message_text(
                "📊 *اختر استراتيجية التداول:*\n"
                "• Standard - استراتيجية قياسية\n"
                "• Martingale - مضاعفة بعد الخسارة\n"
                "• Fibonacci - استراتيجية فيبوناتشي",
                chat_id,
                message_id,
                reply_markup=keyboard,
                parse_mode='Markdown'
            )
            
        elif call.data.startswith("strat_"):
            strategy = call.data.replace("strat_", "")
            state.trade_strategy = strategy
            save_user_state(chat_id)
            bot.edit_message_text(
                f"✅ *تم تعيين استراتيجية التداول:* {strategy}",
                chat_id,
                message_id,
                parse_mode='Markdown'
            )
            settings_menu(chat_id)
            
        elif call.data == "toggle_notify":
            state.subscribed = not state.subscribed
            save_user_state(chat_id)
            status = "مفعلة" if state.subscribed else "معطلة"
            bot.answer_callback_query(
                call.id,
                f"🔔 الإشعارات {status}",
                show_alert=True
            )
            main_menu(chat_id)
            
        elif call.data == "risk_management":
            risk_management_menu(chat_id, message_id)
            
        elif call.data == "stats":
            stats_command(call.message)
            
        elif call.data == "help":
