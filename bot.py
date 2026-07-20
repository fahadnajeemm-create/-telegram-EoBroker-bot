import telebot

TOKEN = "8920872994:AAG0t2VC48sfLIBznsjn9OUEV6A5VpKgnlc"

bot = telebot.TeleBot(TOKEN)

@bot.message_handler(func=lambda message: True)
def echo(message):
    print("وصلت رسالة:", message.text)
    bot.reply_to(message, "وصلت رسالتك ✅")

print("Bot is running...")
bot.infinity_polling()
