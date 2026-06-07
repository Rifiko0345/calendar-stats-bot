from googleapiclient.discovery import build
from collections import defaultdict
from telegram import Bot
from datetime import timezone
import asyncio
import os.path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import locale
import re
import os
from dotenv import load_dotenv
from google_calendar import get_stats
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler
)
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup
)

ORANGE_COLOR_ID = "6"   # Мандарин → работа
LAVENDER_COLOR_ID = "1" # Лаванда → учёба
SAGE_COLOR_ID = "2" # Шалфей - врач/больница
GRAPHITE_COLOR_ID = "8" # Пропуск

MONTHS_RU = {
    1: "января",
    2: "февраля",
    3: "марта",
    4: "апреля",
    5: "мая",
    6: "июня",
    7: "июля",
    8: "августа",
    9: "сентября",
    10: "октября",
    11: "ноября",
    12: "декабря",
}

load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

STATE_MAIN = "main"
STATE_STATS_MENU = "stats_menu"
STATE_REPORT = "report"
STATE_COMPARE = "compare"

locale.setlocale(locale.LC_TIME, "ru_RU.UTF-8")
MOSCOW_TZ = ZoneInfo("Europe/Moscow")

# ==========================================
# АВТОРИЗАЦИЯ GOOGLE CALENDAR
# ==========================================
SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']

creds = None

if os.path.exists("token.json"):
    creds = Credentials.from_authorized_user_file(
        "token.json",
        SCOPES
    )

if not creds or not creds.valid:

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())

    else:
        flow = InstalledAppFlow.from_client_secrets_file(
            "credentials.json",
            SCOPES
        )

        creds = flow.run_local_server(port=0)

    with open("token.json", "w") as token:
        token.write(creds.to_json())



now = datetime.now(timezone.utc)

start_of_week = now - timedelta(days=now.weekday())
start_of_week = start_of_week.replace(
    hour=0, minute=0, second=0, microsecond=0
)

timeMin = start_of_week.isoformat()
timeMax = now.isoformat()

# ТЕКУЩАЯ НЕДЕЛЯ (ПОНЕДЕЛЬНИК -> СЕЙЧАС)
def get_current_week():
    now = datetime.now(timezone.utc)

    start = now - timedelta(days=now.weekday())

    start = start.replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0
    )

    return start, now

# ТЕКУЩИЙ МЕСЯЦ (1 ЧИСЛО -> СЕЙЧАС)
def get_current_month():
    now = datetime.now(timezone.utc)

    start = now.replace(
        day=1,
        hour=0,
        minute=0,
        second=0,
        microsecond=0
    )

    return start, now

def get_current_year():

    now = datetime.now(timezone.utc)

    start = now.replace(
        month=1,
        day=1,
        hour=0,
        minute=0,
        second=0,
        microsecond=0
    )

    return start, now

# ==========================================
# ФОРМИРОВАНИЕ ОТЧЁТА
# ==========================================

def build_report(stats, start_date, end_date, period_type="week"):

    title_map = {
        "week": "Неделя",
        "month": "Месяц",
        "year": "Год"
    }
    title = title_map.get(period_type, "Период")

    total_hours = sum(stats.values())

    sorted_stats = sorted(
        stats.items(),
        key=lambda item: item[1],
        reverse=True
    )

    period_start = start_date
    period_end = end_date

    if period_start.month == period_end.month:
        month = MONTHS_RU[period_start.month]
        report_header = (
            f" {period_start.day}–{period_end.day} {month}"
        )
    else:
        report_header = (
            f" {period_start.day} {MONTHS_RU[period_start.month]} – "
            f"{period_end.day} {MONTHS_RU[period_end.month]}"
        )

    report = f"📊 {title}: {report_header}\n\n"

    for category, hours in sorted_stats:
        report += f"{category}: {hours:.1f} ч\n"

    report += f"\nВсего времени: {total_hours:.1f} ч"

    return report

async def send_report(update, context, start_date, end_date, period_type):

    stats = get_stats(start_date, end_date)
    report = build_report(stats,start_date,end_date,period_type)
    query = update.callback_query

    if query:
        await query.answer()
        await query.message.edit_text(report,reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Назад", callback_data="stats_menu")]
            ])
        )
    else:
        await update.message.reply_text(report)

async def send_period(update, context, period):
    mapping = {
        "week": get_current_week,
        "month": get_current_month,
        "year": get_current_year,
    }

    start, end = mapping[period]()
    await send_report(update, context, start, end, period)

async def week(update, context):
    await send_period(update, context, "week")

async def month(update, context):
    await send_period(update, context, "month")

async def year(update, context):
    await send_period(update, context, "year")


async def handle_menu(update, context):

    query = update.callback_query
    await query.answer()

    data = query.data

    state = context.user_data.get("state", "MAIN")

    # =========================
    # ГЛАВНОЕ МЕНЮ
    # =========================
    if data == "stats_menu":
        context.user_data["state"] = "STATS_MENU"
        await query.edit_message_text(
            "📊 Выберите период:",
            reply_markup=get_stats_menu()
        )

    elif data == "period_menu":
        context.user_data["state"] = "YEAR_MENU"
        await query.edit_message_text(
            "📅 Выберите год:",
            reply_markup=get_year_menu()
        )

    elif data == "compare_menu":
        context.user_data["state"] = "COMPARE_MENU"
        await query.edit_message_text("Сравнение в разработке")

    elif data == "back_main":
        context.user_data["state"] = "MAIN"
        await query.edit_message_text(
            "Выберите действие:",
            reply_markup=get_main_menu()
        )

    # =========================
    # ВЫБОР ГОДА
    # =========================
    elif data.startswith("year_"):
        selected_year = int(data.split("_")[1])
        context.user_data["selected_year"] = selected_year

        await query.edit_message_text(
            f"Выбран год: {selected_year}\nТеперь выбери месяц (следующий шаг будет позже)"
        )

    # =========================
    # СТАТИСТИКА
    # =========================
    elif data in ("week", "month", "year"):
        context.user_data["state"] = "REPORT"
        await send_period(update, context, data)

# При нажатии "/start"
async def start(update, context):
    context.user_data["state"] = STATE_MAIN

    await update.message.reply_text(
        "Выберите действие:",
        reply_markup=get_main_menu()
    )

def get_main_menu():
    keyboard = [
        [InlineKeyboardButton("📊 Статистика", callback_data="stats_menu")],
        [InlineKeyboardButton("📅 Выбрать период", callback_data="period_menu")],
        [InlineKeyboardButton("⚖️ Сравнение", callback_data="compare_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)

# При нажатии 📊 Статистика"
def get_stats_menu():
    keyboard = [
        [InlineKeyboardButton("📅 Текущая неделя", callback_data="week")],
        [InlineKeyboardButton("📆 Текущий месяц", callback_data="month")],
        [InlineKeyboardButton("🗓 Текущий год", callback_data="year")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="back_main")]
    ]

    return InlineKeyboardMarkup(keyboard)

def get_year_menu():
    keyboard = [
        [InlineKeyboardButton("2024", callback_data="year_2024")],
        [InlineKeyboardButton("2025", callback_data="year_2025")],
        [InlineKeyboardButton("2026", callback_data="year_2026")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="back_main")]
    ]

    return InlineKeyboardMarkup(keyboard)

def get_report_menu():
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data="stats_menu")]])

app = Application.builder().token(TELEGRAM_TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("week", week))
app.add_handler(CommandHandler("month", month))
app.add_handler(CommandHandler("year", year))

app.add_handler(CallbackQueryHandler(handle_menu))

app.run_polling()

# TO DO
#
# Добавить в бота кнопки события: статистика этого месяца, недели, года
# Сравнение месяцев
# графики




