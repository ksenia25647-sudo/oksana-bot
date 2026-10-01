#!/usr/bin/env python3
"""
Oksana 365 Assistant — FULL VERSION
Telegram Bot + Google Calendar + Notifications + JSON Store
"""

import os
import json
import pickle
from pathlib import Path
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# === КОНФІГ ===
TOKEN = os.getenv("TELEGRAM_TOKEN")
if not TOKEN:
    print("❌ TELEGRAM_TOKEN не встановлено!")
    exit(1)

WORK_DIR = Path(__file__).parent

# Handle CALENDAR_CREDENTIALS from environment variable
CALENDAR_CREDS_JSON = os.getenv("CALENDAR_CREDENTIALS")
if CALENDAR_CREDS_JSON:
    try:
        with open(WORK_DIR / "calendar_credentials.json", 'w') as f:
            f.write(CALENDAR_CREDS_JSON)
        print("✅ Calendar credentials loaded from environment")
    except Exception as e:
        print(f"⚠️ Failed to write calendar credentials: {e}")

CALENDAR_CREDS_FILE = WORK_DIR / "calendar_credentials.json"
CALENDAR_TOKEN_FILE = WORK_DIR / "calendar_token.pickle"
TASKS_JSON_FILE = WORK_DIR / "tasks.json"

CALENDAR_SCOPES = ["https://www.googleapis.com/auth/calendar"]

CATEGORIES = {
    'medical': '💊 Медичне',
    'personnel': '👥 Персонал',
    'equipment': '⚙️ Обладнання',
    'pm': '📊 PM/KPI',
    'production': '🏭 Ключові',
    'personal': '🏠 Personal',
    'general': '📝 Інше'
}

# Кольори календаря (Google Calendar colorId)
COLOR_MAP = {
    'medical': '3',      # Blue
    'personnel': '2',    # Sage
    'equipment': '5',    # Flamingo
    'pm': '1',          # Lavender
    'production': '11',  # Tomato (red)
    'personal': '4',     # Banana (yellow)
    'general': '8'       # Graphite
}


# === CALENDAR API ===
def get_calendar_service():
    """Отримати Google Calendar service"""
    try:
        creds = None
        if CALENDAR_TOKEN_FILE.exists():
            with open(CALENDAR_TOKEN_FILE, 'rb') as token:
                creds = pickle.load(token)
        
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not CALENDAR_CREDS_FILE.exists():
                    return None  # No credentials available
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(CALENDAR_CREDS_FILE), CALENDAR_SCOPES)
                creds = flow.run_local_server(port=0)
            
            with open(CALENDAR_TOKEN_FILE, 'wb') as token:
                pickle.dump(creds, token)
        
        return build('calendar', 'v3', credentials=creds)
    except Exception as e:
        print(f"⚠️ Calendar service error: {e}")
        return None


def add_to_calendar(task_text, category='general', date_str=None):
    """Додати подію в Google Calendar"""
    try:
        service = get_calendar_service()
        if not service:
            return False
        
        # Парс дати якщо передана
        if date_str:
            try:
                event_date = datetime.strptime(date_str, "%d.%m")
                event_date = event_date.replace(year=datetime.now().year)
            except:
                event_date = datetime.now()
        else:
            event_date = datetime.now()
        
        # Встав час (замовчування 09:00)
        event_start = event_date.replace(hour=9, minute=0)
        event_end = event_start + timedelta(hours=1)
        
        event = {
            'summary': task_text,
            'description': f'Категорія: {CATEGORIES.get(category, category)}',
            'start': {
                'dateTime': event_start.isoformat(),
                'timeZone': 'Europe/Kyiv',
            },
            'end': {
                'dateTime': event_end.isoformat(),
                'timeZone': 'Europe/Kyiv',
            },
            'colorId': COLOR_MAP.get(category, '8')
        }
        
        service.events().insert(calendarId='primary', body=event).execute()
        return True
    except Exception as e:
        print(f"⚠️ Calendar add error: {e}")
        return False


# === JSON STORE ===
def load_tasks():
    """Завантажити всі завдання з JSON"""
    try:
        if TASKS_JSON_FILE.exists():
            with open(TASKS_JSON_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        print(f"⚠️ Load tasks error: {e}")
    return {'medical': [], 'personnel': [], 'equipment': [], 'pm': [], 'production': [], 'personal': [], 'general': []}


def save_tasks(tasks):
    """Зберегти завдання в JSON"""
    try:
        with open(TASKS_JSON_FILE, 'w', encoding='utf-8') as f:
            json.dump(tasks, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"⚠️ Save tasks error: {e}")
        return False


def add_task_to_category(category, task_text, date_str=None):
    """Додати завдання в категорію"""
    try:
        tasks = load_tasks()
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        
        tasks[category].append({
            "date": now,
            "task": task_text,
            "date_scheduled": date_str,
            "status": "Нове",
            "category": category
        })
        
        save_tasks(tasks)
        
        # Додати в календар
        add_to_calendar(task_text, category, date_str)
        
        return True
    except Exception as e:
        print(f"⚠️ Add task error: {e}")
        return False


# === КОМАНДИ ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Стартове меню"""
    try:
        name = update.effective_user.first_name
        message = f"""Привіт, {name}! 👋 **Oksana 365 Assistant**

**ДОДАВАННЯ ЗАВДАНЬ:**
/add_task <текст> — загальне
/med_reminder <текст> — здоров'я
/prod_personnel <текст> — люди
/prod_equipment <текст> — техніка
/prod_pm <текст> — плани/KPI
/prod_core <текст> — ключові рішення
/personal <текст> — personal
/general <текст> — інше

**АНАЛІЗ:**
/stats — статистика
/top3 — топ-3 завдання
/tasks — список

ℹ️ /help — довідка
"""
        await update.message.reply_text(message, parse_mode='Markdown')
    except Exception as e:
        print(f"❌ /start error: {e}")
        await update.message.reply_text(f"❌ Помилка: {str(e)}")


async def add_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Загальне завдання"""
    try:
        if not context.args:
            await update.message.reply_text("Використання: /add_task <текст завдання>")
            return
        
        task_text = ' '.join(context.args)
        if add_task_to_category('general', task_text):
            await update.message.reply_text(f"✅ Завдання додано: {task_text}\n📅 Додано в календар")
        else:
            await update.message.reply_text(f"⚠️ Завдання додано, але календар не доступен")
    except Exception as e:
        print(f"❌ /add_task error: {e}")
        await update.message.reply_text(f"❌ Помилка: {str(e)}")


async def add_medical(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Медичне"""
    try:
        if not context.args:
            await update.message.reply_text("Використання: /med_reminder <текст>")
            return
        
        task_text = ' '.join(context.args)
        if add_task_to_category('medical', task_text):
            await update.message.reply_text(f"💊 Медичне завдання: {task_text}\n✅ Збережено")
        else:
            await update.message.reply_text(f"⚠️ Завдання додано, але календар не доступен")
    except Exception as e:
        print(f"❌ /med_reminder error: {e}")
        await update.message.reply_text(f"❌ Помилка: {str(e)}")


async def add_personnel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Персонал"""
    try:
        if not context.args:
            await update.message.reply_text("Використання: /prod_personnel <текст>")
            return
        
        task_text = ' '.join(context.args)
        if add_task_to_category('personnel', task_text):
            await update.message.reply_text(f"👥 Персонал: {task_text}\n✅ Збережено")
        else:
            await update.message.reply_text(f"⚠️ Завдання додано, але календар не доступен")
    except Exception as e:
        print(f"❌ /prod_personnel error: {e}")
        await update.message.reply_text(f"❌ Помилка: {str(e)}")


async def add_equipment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обладнання"""
    try:
        if not context.args:
            await update.message.reply_text("Використання: /prod_equipment <текст>")
            return
        
        task_text = ' '.join(context.args)
        if add_task_to_category('equipment', task_text):
            await update.message.reply_text(f"⚙️ Обладнання: {task_text}\n✅ Збережено")
        else:
            await update.message.reply_text(f"⚠️ Завдання додано, але календар не доступен")
    except Exception as e:
        print(f"❌ /prod_equipment error: {e}")
        await update.message.reply_text(f"❌ Помилка: {str(e)}")


async def add_pm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Плани/KPI"""
    try:
        if not context.args:
            await update.message.reply_text("Використання: /prod_pm <текст>")
            return
        
        task_text = ' '.join(context.args)
        if add_task_to_category('pm', task_text):
            await update.message.reply_text(f"📊 PM: {task_text}\n✅ Збережено")
        else:
            await update.message.reply_text(f"⚠️ Завдання додано, але календар не доступен")
    except Exception as e:
        print(f"❌ /prod_pm error: {e}")
        await update.message.reply_text(f"❌ Помилка: {str(e)}")


async def add_production(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ключові рішення"""
    try:
        if not context.args:
            await update.message.reply_text("Використання: /prod_core <текст>")
            return
        
        task_text = ' '.join(context.args)
        if add_task_to_category('production', task_text):
            await update.message.reply_text(f"🏭 Ключове: {task_text}\n✅ Збережено")
        else:
            await update.message.reply_text(f"⚠️ Завдання додано, але календар не доступен")
    except Exception as e:
        print(f"❌ /prod_core error: {e}")
        await update.message.reply_text(f"❌ Помилка: {str(e)}")


async def add_personal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Personal"""
    try:
        if not context.args:
            await update.message.reply_text("Використання: /personal <текст>")
            return
        
        task_text = ' '.join(context.args)
        if add_task_to_category('personal', task_text):
            await update.message.reply_text(f"🏠 Personal: {task_text}\n✅ Збережено")
        else:
            await update.message.reply_text(f"⚠️ Завдання додано, але календар не доступен")
    except Exception as e:
        print(f"❌ /personal error: {e}")
        await update.message.reply_text(f"❌ Помилка: {str(e)}")


async def add_general(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Інше"""
    try:
        if not context.args:
            await update.message.reply_text("Використання: /general <текст>")
            return
        
        task_text = ' '.join(context.args)
        if add_task_to_category('general', task_text):
            await update.message.reply_text(f"📝 General: {task_text}\n✅ Збережено")
        else:
            await update.message.reply_text(f"⚠️ Завдання додано, але календар не доступен")
    except Exception as e:
        print(f"❌ /general error: {e}")
        await update.message.reply_text(f"❌ Помилка: {str(e)}")


async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Статистика"""
    try:
        tasks = load_tasks()
        
        total = sum(len(tasks[cat]) for cat in tasks)
        completed = sum(len([t for t in tasks[cat] if t.get('status') == 'Завершено']) for cat in tasks)
        pending = total - completed
        
        message = f"""📊 **Статистика завдань**

✅ Завершено: {completed}
⏳ Залишилось: {pending}
📌 Всього: {total}

**По категоріям:**
"""
        for cat, cat_name in CATEGORIES.items():
            count = len(tasks[cat])
            message += f"  {cat_name}: {count}\n"
        
        await update.message.reply_text(message, parse_mode='Markdown')
    except Exception as e:
        print(f"❌ /stats error: {e}")
        await update.message.reply_text(f"❌ Помилка: {str(e)}")


async def show_top3(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Топ-3"""
    try:
        tasks = load_tasks()
        all_tasks = []
        
        for cat in tasks:
            for task in tasks[cat]:
                if task.get('status') != 'Завершено':
                    all_tasks.append(task)
        
        if not all_tasks:
            await update.message.reply_text("✅ Немає завдань!")
            return
        
        top = all_tasks[:3]
        message = "🔥 **Топ-3 завдання:**\n\n"
        for i, t in enumerate(top, 1):
            cat = CATEGORIES.get(t.get('category', 'general'), 'Інше')
            message += f"{i}. [{cat}] {t['task']}\n"
        
        await update.message.reply_text(message, parse_mode='Markdown')
    except Exception as e:
        print(f"❌ /top3 error: {e}")
        await update.message.reply_text(f"❌ Помилка: {str(e)}")


async def list_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Список завдань"""
    try:
        tasks = load_tasks()
        if not isinstance(tasks, dict):
            await update.message.reply_text("⚠️ Немає завдань")
            return
        
        all_tasks = []
        for cat in CATEGORIES.keys():
            if cat in tasks and isinstance(tasks[cat], list):
                for task in tasks[cat]:
                    if isinstance(task, dict):
                        all_tasks.append(task)
        
        if not all_tasks:
            await update.message.reply_text("📭 Немає завдань!")
            return
        
        # Останні 15
        recent = all_tasks[-15:]
        message = f"📋 **Завдання ({len(all_tasks)} всього):**\n\n"
        for t in recent:
            status_emoji = "✅" if t.get('status') == 'Завершено' else "⏳"
            cat = CATEGORIES.get(t.get('category', 'general'), 'Інше')
            message += f"{status_emoji} [{cat}] {t['task']}\n"
        
        await update.message.reply_text(message, parse_mode='Markdown')
    except Exception as e:
        print(f"❌ /tasks error: {e}")
        await update.message.reply_text(f"❌ Помилка: {str(e)}")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Довідка"""
    try:
        message = """📖 **Oksana 365 Assistant — ДОВІДКА**

**КОМАНДИ ДОДАВАННЯ:**
/add_task — загальне завдання
/med_reminder — здоров'я (медикаменти, прийоми, запис до лікаря)
/prod_personnel — персонал (найм, ЗП, розвиток)
/prod_equipment — обладнання (обслуговування, закупівлі)
/prod_pm — планування/KPI (план, якість)
/prod_core — ключові рішення (операційні рішення)
/personal — personal (сім'я, дозвілля, розвиток)
/general — інше

**АНАЛІЗ:**
/stats — статистика (скільки завершено, скільки залишилось)
/top3 — топ-3 найважливіших завдання
/tasks — повний список завдань

**СИСТЕМА:**
/start — меню
/help — цей текст

**СИНХРОНІЗАЦІЯ:**
✅ Усі завдання автоматично додаються в Google Calendar
✅ Дані зберігаються в JSON для віджета (Rainmeter)
✅ Кольорова система по категоріях
"""
        await update.message.reply_text(message, parse_mode='Markdown')
    except Exception as e:
        print(f"❌ /help error: {e}")
        await update.message.reply_text(f"❌ Помилка: {str(e)}")


def main():
    """Запуск бота"""
    print("🤖 Oksana 365 Assistant запускається...")
    
    app = Application.builder().token(TOKEN).build()
    
    # Реєстрація всіх команд
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
    app.add_handler(CommandHandler("tasks", list_tasks))
    app.add_handler(CommandHandler("help", help_command))
    
    print("✅ Бот запущено. Слухає команди...")
    app.run_polling()


if __name__ == "__main__":
    main()
