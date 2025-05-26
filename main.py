import os
import configparser
from datetime import datetime
import json
import time
import logging
from google import genai
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Logging sozlash
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Global variables
history = []
client = None
context_data = ""

def load_config():
    """Konfiguratsiya faylini yuklash"""
    base_dir = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.getcwd()
    config_path = os.path.join(base_dir, "config.ini")
    config = configparser.ConfigParser()
    config.read(config_path)
    return config, base_dir

def initialize_gemini():
    """Gemini API ni ishga tushirish"""
    global client
    config, base_dir = load_config()

    # Gemini API key ni o'qish
    gemini_api_key = config.get('DEFAULT', 'gemini_api_key', fallback=None)
    if gemini_api_key is None:
        for section in config.sections():
            if config.has_option(section, 'gemini_api_key'):
                gemini_api_key = config.get(section, 'gemini_api_key')
                break
        if gemini_api_key is None:
            gemini_api_key = os.getenv("GOOGLE_API_KEY")

    if not gemini_api_key:
        raise RuntimeError(
            "Gemini API key topilmadi. config.ini ga 'gemini_api_key' qo'shing yoki GOOGLE_API_KEY env variable o'rnating.")

    # Client ni ishga tushirish
    client = genai.Client(api_key=gemini_api_key)
    return base_dir

def load_data_and_history():
    """Ma'lumotlar va tarixni yuklash"""
    global history, context_data
    config, base_dir = load_config()

    # Tarixni yuklash
    history_path = os.path.join(base_dir, "history.json")
    if os.path.isfile(history_path):
        try:
            with open(history_path, "r", encoding="utf-8") as f:
                history = json.load(f)
        except json.JSONDecodeError:
            history = []

    # Data fayllarini yuklash
    context_data = ""
    data_dir = os.path.join(base_dir, "data")
    if os.path.isdir(data_dir):
        for filename in os.listdir(data_dir):
            if filename.endswith(".txt"):
                file_path = os.path.join(data_dir, filename)
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        context_data += f.read() + "\n"
                except Exception:
                    continue

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start komandasi"""
    welcome_message = """
🎓 **PDP University AI Yordamchisi**

Assalomu alaykum! Men PDP Universiteti haqidagi savollaringizga javob beraman.

🔍 **Nima haqida so'rashingiz mumkin:**
📚 Fakultetlar va yo'nalishlar
📝 Qabul jarayoni
🎯 O'quv dasturlari
📊 Imtihonlar va baholash tizimi
💳 To'lov va stipendiyalar
🏫 Universitet hayoti va imkoniyatlari
👥 Talabalar uchun xizmatlar
🌟 Amaliyot va ish joylari

💬 Savolingizni yozing va men sizga tafsilotli javob beraman!

⚡ **Maslahat:** Aniq savollar bering, men sizga eng yaxshi javobni taqdim etaman.
    """
    await update.message.reply_text(welcome_message, parse_mode='Markdown')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Yordam komandasi"""
    help_message = """
🆘 **Yordam va Ko'rsatmalar**

🤖 **Mavjud komandalar:**
• `/start` - Botni qayta ishga tushirish
• `/help` - Bu yordam sahifasini ko'rsatish
• `/history` - Oxirgi savollaringizni ko'rish

📝 **Qanday ishlatish:**
Shunchaki savolingizni yozing va men professional javob beraman!

💡 **Savol misollari:**
• "Qabul haqida batafsil ma'lumot bering"
• "IT fakultetida qanday mutaxassisliklar bor?"
• "Kontrakt to'lovi qancha?"
• "Imtihon jadvalini ko'rsating"
• "Grant asosida o'qish mumkinmi?"

⚡ **Maslahat:** Qanchalik aniq savol bersangiz, shunchalik to'liq javob olasiz!

🔄 Agar javob sizni qoniqtirmasa, savolingizni boshqacha ifodalab qayta so'rang.
    """
    await update.message.reply_text(help_message, parse_mode='Markdown')

async def history_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Tarix komandasi"""
    global history

    if not history:
        await update.message.reply_text("📭 Hali hech qanday savol berilmagan.\n\n💡 Birinchi savolingizni yozing!")
        return

    # Oxirgi 5 ta savolni ko'rsatish
    recent_history = history[-5:]
    history_text = "📋 **Oxirgi savollaringiz:**\n\n"

    for i, entry in enumerate(recent_history, 1):
        history_text += f"**{i}.** 📝 {entry['question']}\n"
        history_text += f"🕐 *{entry['time']}*\n\n"

    history_text += "💡 Eski savollaringizni qayta berish ham mumkin!"

    await update.message.reply_text(history_text, parse_mode='Markdown')

def format_response(text: str, question: str) -> str:
    """AI javobini chiroyli Telegram formatiga o'tkazish"""

    # Agar javob juda qisqa bo'lsa, oddiy formatda qaytarish
    if len(text) < 50:
        return f"💭 **Javob:** {text}"

    # Javobni qismlarga ajratish
    sentences = text.split('.')
    sentences = [s.strip() for s in sentences if s.strip()]

    if len(sentences) <= 2:
        # Qisqa javoblar uchun
        return f"💡 **{sentences[0].strip()}**\n\n{'. '.join(sentences[1:]).strip()}"

    # Uzun javoblar uchun strukturali format
    first_sentence = sentences[0].strip()
    remaining = '. '.join(sentences[1:]).strip()

    # Agar raqamlar yoki ro'yxat bo'lsa
    if any(keyword in text.lower() for keyword in ['som', 'kredit', 'soat', 'yil', 'oy']):
        icon = "💰"
    elif any(keyword in text.lower() for keyword in ['imtihon', 'test', 'ball']):
        icon = "📊"
    elif any(keyword in text.lower() for keyword in ['fakultet', 'yo\'nalish', 'dastur']):
        icon = "🎓"
    elif any(keyword in text.lower() for keyword in ['qabul', 'ariza', 'hujjat']):
        icon = "📝"
    else:
        icon = "💡"

    # Chiroyli format
    formatted = f"{icon} **Javob:**\n{first_sentence}.\n\n"

    if remaining:
        # Remaining textni bullet pointlarga ajratish
        if len(remaining) > 100:
            # Uzun textni qismlarga bo'lish
            parts = remaining.split(',')
            if len(parts) > 2:
                formatted += "**Tafsilotlar:**\n"
                for part in parts[:3]:  # Faqat birinchi 3 qismni olish
                    if part.strip():
                        formatted += f"• {part.strip()}\n"
                if len(parts) > 3:
                    formatted += f"• {', '.join(parts[3:]).strip()}\n"
            else:
                formatted += f"**Ma'lumot:** {remaining}"
        else:
            formatted += f"**Ma'lumot:** {remaining}"

    # Qo'shimcha ma'lumot uchun bo'limni qidirish
    if "bog'laning" in text.lower() or "universitet bilan" in text.lower():
        formatted += "\n\n📞 *Qo'shimcha ma'lumot uchun universitet bilan bog'laning*"

    return formatted

def ask_gemini(user_question: str) -> str:
    """Gemini AI dan javob olish"""
    global history, client, context_data

    if not context_data:
        return "Ma'lumotlar bazasi yuklanmagan. data papkasidagi .txt fayllarni tekshiring."

    # Prompt yaratish
    prompt = f"""You are an expert AI assistant based on the PDP University information database.
Your task is to provide accurate, useful, and correct answers to user questions.

## USER QUESTION:
{user_question}

## AVAILABLE INFORMATION:
{context_data}

## ANSWERING RULES:

### 1. SOURCE OF ANSWER
- ONLY and STRICTLY use the information given above
- Give detailed answers. If the information is incomplete, use the related available data and add:
  "For more details, please contact the university"
- Never add your own ideas or guesses

### 2. QUESTION ANALYSIS
- Carefully analyze the user's question. For example, if it is about exams, prioritize that first
- If the question is unclear, give the most relevant information
- If numbers are requested (like time, credits, price), give specific values

### 3. RESPONSE FORMAT
- Write the answer in Markdown format
- Headings: Use ## or ###
- Lists: Use - or 1., 2., 3.
- Highlight key information in **bold**
- If needed, use markdown table format

### 4. LANGUAGE AND STYLE
- Answer in Uzbek, but do not translate subject names or technical terms
  (like "Submission", "Remodule", etc.)
- Write in a friendly and professional tone
- Use clear and simple expressions
- Avoid unnecessary words

### 5. SPECIAL CASES
- If general keywords are given, provide the main available information about that topic
- If calculation is needed, gather all relevant data and calculate it clearly
- If there is no info in the database:
  "Sorry, there is no information available about this.
  For more details, please contact PDP University directly."

### 6. ANSWER STRUCTURE
Write your answer in the following order:
1. Short and clear summary. If the info is long:
   - Short intro (2-3 sentences)
   - Main info (with headings and bullet points)
   - Extra helpful info (if available)
   - Conclusion or next steps (if relevant)

IMPORTANT: Always use only the given information and respond as a professional and friendly assistant.
"""

    # Gemini dan javob olish
    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt
        )
        raw_answer = response.text.strip()
        # Javobni chiroyli formatga o'tkazish
        answer_text = format_response(raw_answer, user_question)
    except Exception as e:
        if "quota" in str(e).lower():
            answer_text = "⚠️ **API limit tugadi**\n\n🕐 Iltimos, bir necha daqiqadan so'ng qayta urinib ko'ring.\n\n📞 Yoki bevosita universitet bilan bog'laning!"
        else:
            answer_text = f"❌ **Xatolik yuz berdi**\n\n🛠️ Texnik nosozlik\n\n🔄 Iltimos, qayta urinib ko'ring."

    # Tarixga saqlash
    entry = {
        "question": user_question,
        "answer": answer_text,
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    history.append(entry)

    # Tarixni faylga saqlash
    try:
        config, base_dir = load_config()
        history_path = os.path.join(base_dir, "history.json")
        with open(history_path, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=4)
    except Exception as e:
        logger.error(f"Tarixni saqlashda xatolik: {e}")

    return answer_text

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Foydalanuvchi xabarlarini qayta ishlash"""
    user_question = update.message.text
    user_name = update.effective_user.first_name

    # "AI ishlamoqda..." xabarini yuborish
    loading_message = await update.message.reply_text(
        "🤖 **AI ishlamoqda...**\n\n⏳ Savolingizni tahlil qilmoqda va javob tayyorlamoqda...",
        parse_mode='Markdown'
    )

    # "Typing..." ko'rsatish
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    try:
        # Javob olish
        answer = ask_gemini(user_question)

        # Loading xabarini o'chirish
        await context.bot.delete_message(
            chat_id=update.effective_chat.id,
            message_id=loading_message.message_id
        )

        # Javobni yuborish (Telegram 4096 belgi cheklovi bor)
        if len(answer) > 4000:
            # Uzun javoblarni bo'lib yuborish
            await update.message.reply_text(
                "📄 **Javob uzun bo'lgani sababli, qismlarga bo'lib yuboryapman:**\n",
                parse_mode='Markdown'
            )

            parts = [answer[i:i+3800] for i in range(0, len(answer), 3800)]
            for i, part in enumerate(parts, 1):
                header = f"📋 **Qism {i}/{len(parts)}:**\n\n" if len(parts) > 1 else ""
                await update.message.reply_text(header + part, parse_mode='Markdown')
                time.sleep(0.5)  # Spam himoyasi uchun
        else:
            await update.message.reply_text(answer, parse_mode='Markdown')

    except Exception as e:
        # Xatolik yuz berganda loading xabarini o'chirish
        try:
            await context.bot.delete_message(
                chat_id=update.effective_chat.id,
                message_id=loading_message.message_id
            )
        except:
            pass

        logger.error(f"Xabarni qayta ishlashda xatolik: {e}")
        await update.message.reply_text(
            "❌ **Kechirasiz, xatolik yuz berdi**\n\n🔄 Iltimos, qayta urinib ko'ring.\n\n💡 Agar muammo davom etsa, savolingizni boshqacha ifodalab ko'ring.",
            parse_mode='Markdown'
        )

def main():
    """Asosiy funksiya"""
    try:
        # Konfiguratsiyani yuklash
        config, base_dir = load_config()

        # Telegram bot tokenini olish
        bot_token = config.get('DEFAULT', 'telegram_bot_token', fallback=None)
        if bot_token is None:
            for section in config.sections():
                if config.has_option(section, 'telegram_bot_token'):
                    bot_token = config.get(section, 'telegram_bot_token')
                    break
            if bot_token is None:
                bot_token = os.getenv("TELEGRAM_BOT_TOKEN")

        if not bot_token:
            raise RuntimeError(
                "Telegram bot token topilmadi. config.ini ga 'telegram_bot_token' qo'shing yoki TELEGRAM_BOT_TOKEN env variable o'rnating.")

        # Gemini va ma'lumotlarni yuklash
        initialize_gemini()
        load_data_and_history()

        print("🤖 Bot ishga tushmoqda...")
        print(f"📂 Ma'lumotlar bazasi yuklandi: {len(context_data)} belgi")
        print(f"📜 Tarix yuklandi: {len(history)} ta yozuv")
        print("🎯 Telegram uchun optimallashtirilgan")

        # Bot applicationni yaratish
        app = Application.builder().token(bot_token).build()

        # Handlerlarni qo'shish
        app.add_handler(CommandHandler("start", start_command))
        app.add_handler(CommandHandler("help", help_command))
        app.add_handler(CommandHandler("history", history_command))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

        # Botni ishga tushirish
        print("✅ Bot muvaffaqiyatli ishga tushdi!")
        print("🔗 Telegram botingizga /start yuboring")
        print("⛔ Bot to'xtatish uchun Ctrl+C bosing")

        app.run_polling(allowed_updates=Update.ALL_TYPES)

    except Exception as e:
        print(f"❌ Xatolik: {e}")
        return

if __name__ == "__main__":
    main()