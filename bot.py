import os
import json
from pathlib import Path
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import pickle
import io

TOKEN = os.getenv("TELEGRAM_TOKEN")
TASKS_FILE = Path(__file__).parent / "tasks.json"
CALENDAR_CREDS_FILE = Path(__file__).parent / "calendar_credentials.json"
CALENDAR_TOKEN_FILE = Path(__file__).parent / "calendar_token.pickle"
CALENDAR_SCOPES = ["https://www.googleapis.com/auth/calendar"]

CATEGORIES = {
    'medical': Path(__file__).parent / "medical_reminders",
    'personnel': Path(__file__).parent / "production_personnel",
    'equipment': Path(__file__).parent / "production_equipment",
    'pm': Path(__file__).parent / "production_pm",
    'production': Path(__file__).parent / "production_core",
    'personal': Path(__file__).parent / "personal",
    'general': Path(__file__).parent / "general_tasks",
}

def load_tasks(category='all'):
    if category == 'all':
        all_tasks = []
        for cat_path in CATEGORIES.values():
            cat_file = cat_path / "tasks.json"
            if cat_file.exists():
                with open(cat_file, 'r', encoding='utf-8') as f:
                    tasks = json.load(f)
                    for t in tasks:
                        t['category'] = cat_file.parent.name
                    all_tasks.extend(tasks)
        return all_tasks
    else:
        cat_path = CATEGORIES.get(category)
        if not cat_path:
            return []
        cat_file = cat_path / "tasks.json"
        if cat_file.exists():
            with open(cat_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return []

def save_tasks(category, tasks):
    cat_path = CATEGORIES.get(category)
    if cat_path:
        cat_path.mkdir(parents=True, exist_ok=True)
        cat_file = cat_path / "tasks.json"
        with open(cat_file, 'w', encoding='utf-8') as f:
            json.dump(tasks, f, ensure_ascii=False, indent=2)

def get_calendar_service():
    creds = None
    if CALENDAR_TOKEN_FILE.exists():
        with open(CALENDAR_TOKEN_FILE, 'rb') as token:
            creds = pickle.load(token)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(CALENDAR_CREDS_FILE), CALENDAR_SCOPES)
            creds = flow.run_local_server(port=0)
        with open(CALENDAR_TOKEN_FILE, 'wb') as token:
            pickle.dump(creds, token)
    return build('calendar', 'v3', credentials=creds)

def add_event_to_calendar(task_text, zoom_link=None):
    try:
        service = get_calendar_service()
        description = f'Завдання: {task_text}'
        if zoom_link:
            description += f'\n\n🎥 Zoom: {zoom_link}'
        
        event = {
            'summary': task_text,
            'description': description,
            'start': {
                'dateTime': datetime.now().isoformat(),
                'timeZone': 'Europe/Kyiv',
            },
            'end': {
                'dateTime': (datetime.now() + timedelta(hours=1)).isoformat(),
                'timeZone': 'Europe/Kyiv',
            },
        }
        event = service.events().insert(calendarId='primary', body=event).execute()
        return True
    except Exception as e:
        print(f"Помилка при додаванні в Calendar: {e}")
        return False

def transcribe_voice_to_text(voice_file_path):
    """Конвертує голосовий файл в текст через Google Speech-to-Text (OAuth)"""
    try:
        creds = None
        if CALENDAR_TOKEN_FILE.exists():
            with open(CALENDAR_TOKEN_FILE, 'rb') as token:
                creds = pickle.load(token)
        
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
        
        client = speech.SpeechClient(credentials=creds)
        
        with open(voice_file_path, 'rb') as audio_file:
            content = audio_file.read()
        
        audio = speech.RecognitionAudio(content=content)
        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.OGG_OPUS,
            sample_rate_hertz=48000,
            language_code="uk-UA",
        )
        
        response = client.recognize(config=config, audio=audio)
        
        if response.results:
            transcript = response.results[0].alternatives[0].transcript
            return transcript
        else:
            return None
            
    except Exception as e:
        print(f"❌ Помилка при розпізнаванню голосу: {e}")
        return None

async def start(update, context):
    name = update.effective_user.first_name
    await update.message.reply_text(
        f"Привіт, {name}! 👋\n\n"
        f"**Команди:**\n"
        f"/add_task <текст> — додати завдання\n"
        f"/med_reminder <текст> — медичне\n"
        f"/prod_personnel <текст> — персонал/ЗП\n"
        f"/prod_equipment <текст> — обладнання\n"
        f"/prod_pm <текст> — плани/KPI\n"
        f"/prod_core <текст> — ключові рішення\n"
        f"/personal <текст> — personal\n"
        f"/general <текст> — general\n"
        f"/stats — статистика\n"
        f"/top3 — топ-3 сьогодні\n"
        f"/zoom <посилання> <текст> — Zoom\n"
        f"/tasks — список завдань\n\n"
        f"🎤 **Голос:** просто надішли голосове повідомлення — бот конвертує в текст!",
        parse_mode='Markdown'
    )

async def add_task(update, context):
    if not context.args:
        await update.message.reply_text("Використання: /add_task <текст завдання>")
        return
    task_text = ' '.join(context.args)
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    tasks = load_tasks('general')
    tasks.append({"date": now, "task": task_text, "status": "Нове", "priority": "normal"})
    save_tasks('general', tasks)
    
    if add_event_to_calendar(task_text):
        await update.message.reply_text(f"✅ Завдання додано: {task_text}\n📅 Додано в календар")
    else:
        await update.message.reply_text(f"✅ Завдання додано: {task_text}")

async def add_medical(update, context):
    if not context.args:
        await update.message.reply_text("Використання: /med_reminder <текст: медикамент/прийом/запис до лікаря>")
        return
    task_text = ' '.join(context.args)
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    tasks = load_tasks('medical')
    tasks.append({"date": now, "task": task_text, "status": "Нове", "type": "medical"})
    save_tasks('medical', tasks)
    
    await update.message.reply_text(f"💊 Медичне завдання: {task_text}\n✅ Збережено")

async def add_personnel(update, context):
    if not context.args:
        await update.message.reply_text("Використання: /prod_personnel <текст: найм/ЗП/розвиток>")
        return
    task_text = ' '.join(context.args)
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    tasks = load_tasks('personnel')
    tasks.append({"date": now, "task": task_text, "status": "Нове"})
    save_tasks('personnel', tasks)
    
    await update.message.reply_text(f"👥 Персонал: {task_text}\n✅ Збережено")

async def add_equipment(update, context):
    if not context.args:
        await update.message.reply_text("Використання: /prod_equipment <текст: обслуговування/закупівля>")
        return
    task_text = ' '.join(context.args)
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    tasks = load_tasks('equipment')
    tasks.append({"date": now, "task": task_text, "status": "Нове"})
    save_tasks('equipment', tasks)
    
    await update.message.reply_text(f"⚙️ Обладнання: {task_text}\n✅ Збережено")

async def add_pm(update, context):
    if not context.args:
        await update.message.reply_text("Використання: /prod_pm <текст: план/KPI/якість>")
        return
    task_text = ' '.join(context.args)
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    tasks = load_tasks('pm')
    tasks.append({"date": now, "task": task_text, "status": "Нове"})
    save_tasks('pm', tasks)
    
    await update.message.reply_text(f"📊 PM: {task_text}\n✅ Збережено")

async def add_production(update, context):
    if not context.args:
        await update.message.reply_text("Використання: /prod_core <текст: ключове рішення>")
        return
    task_text = ' '.join(context.args)
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    tasks = load_tasks('production')
    tasks.append({"date": now, "task": task_text, "status": "Нове", "priority": "high"})
    save_tasks('production', tasks)
    
    await update.message.reply_text(f"🏭 Ключове: {task_text}\n✅ Збережено")

async def add_personal(update, context):
    if not context.args:
        await update.message.reply_text("Використання: /personal <текст: сім'я/розвиток/переїзд>")
        return
    task_text = ' '.join(context.args)
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    tasks = load_tasks('personal')
    tasks.append({"date": now, "task": task_text, "status": "Нове"})
    save_tasks('personal', tasks)
    
    await update.message.reply_text(f"🏠 personal: {task_text}\n✅ Збережено")

async def add_general(update, context):
    if not context.args:
        await update.message.reply_text("Використання: /general <текст>")
        return
    task_text = ' '.join(context.args)
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    tasks = load_tasks('general')
    tasks.append({"date": now, "task": task_text, "status": "Нове"})
    save_tasks('general', tasks)
    
    await update.message.reply_text(f"📝 general: {task_text}\n✅ Збережено")

async def show_stats(update, context):
    all_tasks = load_tasks('all')
    completed = len([t for t in all_tasks if t.get('status') == 'Завершено'])
    pending = len([t for t in all_tasks if t.get('status') != 'Завершено'])
    
    by_category = {}
    for t in all_tasks:
        cat = t.get('category', 'unknown')
        by_category[cat] = by_category.get(cat, 0) + 1
    
    message = f"📊 **Статистика завдань**\n\n"
    message += f"✅ Завершено: {completed}\n"
    message += f"⏳ Залишилось: {pending}\n"
    message += f"📌 Всього: {len(all_tasks)}\n\n"
    message += f"**По категоріям:**\n"
    for cat, count in sorted(by_category.items()):
        message += f"  {cat}: {count}\n"
    
    await update.message.reply_text(message, parse_mode='Markdown')

async def show_top3(update, context):
    all_tasks = load_tasks('all')
    pending = [t for t in all_tasks if t.get('status') != 'Завершено']
    priority_high = [t for t in pending if t.get('priority') == 'high']
    
    top_tasks = (priority_high + pending)[:3]
    
    if not top_tasks:
        await update.message.reply_text("🎯 Немає активних завдань!")
        return
    
    message = "🎯 **Топ-3 сьогодні:**\n\n"
    for i, task in enumerate(top_tasks, 1):
        message += f"{i}. {task['task']}\n   [{task.get('category', 'general')}] {task['date']}\n\n"
    
    await update.message.reply_text(message, parse_mode='Markdown')

async def add_zoom(update, context):
    if len(context.args) < 2:
        await update.message.reply_text("Використання: /zoom <посилання> <текст завдання>")
        return
    
    zoom_link = context.args[0]
    task_text = ' '.join(context.args[1:])
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    tasks = load_tasks('general')
    tasks.append({"date": now, "task": task_text, "status": "Нове", "zoom": zoom_link})
    save_tasks('general', tasks)
    
    if add_event_to_calendar(task_text, zoom_link):
        await update.message.reply_text(f"🎥 Zoom завдання: {task_text}\n📅 Додано в календар з посиланням")
    else:
        await update.message.reply_text(f"🎥 Zoom завдання: {task_text}\n⚠️ Календар недоступен")

async def list_tasks(update, context):
    tasks = load_tasks('all')
    if not tasks:
        await update.message.reply_text("📝 Немає завдань")
        return
    
    message = "📋 **Все завдання:**\n\n"
    for i, task in enumerate(tasks, 1):
        cat = task.get('category', 'general')
        message += f"{i}. [{cat}] {task['task']}\n   {task['status']} | {task['date']}\n\n"
    
    await update.message.reply_text(message, parse_mode='Markdown')

async def help_command(update, context):
    await update.message.reply_text(
        "📖 **Всі команди:**\n"
        "/start — меню\n"
        "/add_task <текст> — завдання\n"
        "/med_reminder <текст> — здоров'я\n"
        "/prod_personnel <текст> — люди\n"
        "/prod_equipment <текст> — техніка\n"
        "/prod_pm <текст> — плани\n"
        "/prod_core <текст> — ключові\n"
        "/personal <текст> — personal\n"
        "/general <текст> — інше\n"
        "/stats — статистика\n"
        "/top3 — топ-3\n"
        "/zoom <посилання> <текст>\n"
        "/tasks — список\n\n"
        "🎤 **Голос:** надішли голосове повідомлення для розпізнавання",
        parse_mode='Markdown'
    )

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик голосових повідомлень"""
    try:
        print("🔍 DEBUG: Голос отримано! Обробляю...")
        voice = update.message.voice
        voice_file = await context.bot.get_file(voice.file_id)
        voice_path = Path(__file__).parent / f"voice_{voice.file_id}.ogg"
        
        await voice_file.download_to_drive(str(voice_path))
        
        await update.message.reply_text("🎤 Обробляю голос...")
        transcript = transcribe_voice_to_text(str(voice_path))
        
        if transcript:
            await update.message.reply_text(f"✅ Розпізнано:\n\n**{transcript}**\n\nДодати як завдання? Відповідь: /add_task {transcript}", parse_mode='Markdown')
        else:
            await update.message.reply_text("❌ Не вдалось розпізнати голос. Спробуй ще раз.")
        
        if voice_path.exists():
            voice_path.unlink()
            
    except Exception as e:
        print(f"❌ ПОМИЛКА В handle_voice: {e}")
        await update.message.reply_text(f"❌ Помилка: {e}")

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("add_task", add_task))
    app.add_handler(CommandHandler("med_reminder", add_medical))
    app.add_handler(CommandHandler("prod_personnel", add_personnel))
    app.add_handler(CommandHandler("prod_equipment", add_equipment))
    app.add_handler(CommandHandler("prod_pm", add_pm))
    app.add_handler(CommandHandler("prod_core", add_production))
    app.add_handler(CommandHandler("personal", add_personal))
    app.add_handler(CommandHandler("general", add_general))
    app.add_handler(CommandHandler("stats", show_stats))
    app.add_handler(CommandHandler("top3", show_top3))
    app.add_handler(CommandHandler("zoom", add_zoom))
    app.add_handler(CommandHandler("tasks", list_tasks))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    print("🤖 Бот запущено. Щоб зупинити, натисніть Ctrl+C.")
    app.run_polling()

if __name__ == "__main__":
    main()
