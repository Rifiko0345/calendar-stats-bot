from datetime import timezone
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import locale
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
from google_calendar import CATEGORY_ICONS, MONTHS_RU

load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

STATE_MAIN = "main"
STATE_STATS_MENU = "stats_menu"
STATE_REPORT = "report"
STATE_COMPARE = "compare"
STATE_COMPARE_YEAR_FIRST = "COMPARE_YEAR_FIRST"
STATE_COMPARE_YEAR_SECOND = "COMPARE_YEAR_SECOND"
STATE_COMPARE_YEAR_RESULT = "COMPARE_YEAR_RESULT"

locale.setlocale(locale.LC_TIME, "ru_RU.UTF-8")
MOSCOW_TZ = ZoneInfo("Europe/Moscow")

MONTH_NAMES = {
    1: "Январь", 2: "Февраль", 3: "Март", 4: "Апрель",
    5: "Май", 6: "Июнь", 7: "Июль", 8: "Август",
    9: "Сентябрь", 10: "Октябрь", 11: "Ноябрь", 12: "Декабрь",
}

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

def get_month_period(year, month):

    start = datetime(
        year,
        month,
        1,
        tzinfo=timezone.utc
    )

    if month == 12:
        end = datetime(
            year + 1,
            1,
            1,
            tzinfo=timezone.utc
        )
    else:
        end = datetime(
            year,
            month + 1,
            1,
            tzinfo=timezone.utc
        )

    return start, end

def get_year_period(year):

    start = datetime(
        year,
        1,
        1,
        tzinfo=timezone.utc
    )

    end = datetime(
        year + 1,
        1,
        1,
        tzinfo=timezone.utc
    )

    return start, end

def format_compare_first_month(context):
    year = context.user_data["compare_first_year"]
    month = context.user_data["compare_first_month"]
    return f"✅ Первый месяц: {MONTH_NAMES[month]} {year}"

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
        icon = CATEGORY_ICONS.get(category, "⚪")
        report += f"{icon} {category}: {hours:.1f} ч\n"

    report += f"\nВсего времени: {total_hours:.1f} ч"

    return report

def build_compare_report(stats_first, stats_second, label_first, label_second):

    all_categories = set(stats_first) | set(stats_second)
    sorted_categories = sorted(
        all_categories,
        key=lambda c: max(stats_first.get(c, 0), stats_second.get(c, 0)),
        reverse=True
    )

    total_first = sum(stats_first.values())
    total_second = sum(stats_second.values())
    diff_total = total_second - total_first

    report = f"⚖️ {label_first} → {label_second}\n\n"

    for category in sorted_categories:
        hours_first = stats_first.get(category, 0)
        hours_second = stats_second.get(category, 0)
        diff = hours_second - hours_first
        icon = CATEGORY_ICONS.get(category, "⚪")
        diff_sign = "+" if diff > 0 else ""
        report += (
            f"{icon} {category}: "
            f"{hours_first:.1f} → {hours_second:.1f} ч "
            f"({diff_sign}{diff:.1f})\n"
        )

    total_sign = "+" if diff_total > 0 else ""
    report += (
        f"\nВсего: {total_first:.1f} → {total_second:.1f} ч "
        f"({total_sign}{diff_total:.1f})"
    )

    return report

async def send_month_compare(update, context):

    query = update.callback_query

    first_year = context.user_data["compare_first_year"]
    first_month = context.user_data["compare_first_month"]
    second_year = context.user_data["compare_second_year"]
    second_month = context.user_data["compare_second_month"]

    start_first, end_first = get_month_period(first_year, first_month)
    start_second, end_second = get_month_period(second_year, second_month)

    stats_first = get_stats(start_first, end_first)
    stats_second = get_stats(start_second, end_second)

    label_first = f"{MONTH_NAMES[first_month]} {first_year}"
    label_second = f"{MONTH_NAMES[second_month]} {second_year}"

    report = build_compare_report(
        stats_first,
        stats_second,
        label_first,
        label_second
    )

    await query.message.edit_text(
        report,
        reply_markup=get_compare_result_menu()
    )

async def send_report(update, context, start_date, end_date, period_type):

    stats = get_stats(start_date, end_date)
    report = build_report(stats,start_date,end_date,period_type)
    query = update.callback_query

    if query:
        await query.answer()
        menu = get_report_menu()

        if context.user_data.get("state") == "MONTH_REPORT":
            menu = get_month_report_menu()

        await query.message.edit_text(
            report,
            reply_markup=menu
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

def get_year_menu():
    keyboard = [
        [InlineKeyboardButton("2024", callback_data="year_2024")],
        [InlineKeyboardButton("2025", callback_data="year_2025")],
        [InlineKeyboardButton("2026", callback_data="year_2026")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="back_main")]
    ]

    return InlineKeyboardMarkup(keyboard)

def get_month_menu():

    keyboard = [
        [InlineKeyboardButton("Январь", callback_data="month_1")],
        [InlineKeyboardButton("Февраль", callback_data="month_2")],
        [InlineKeyboardButton("Март", callback_data="month_3")],
        [InlineKeyboardButton("Апрель", callback_data="month_4")],
        [InlineKeyboardButton("Май", callback_data="month_5")],
        [InlineKeyboardButton("Июнь", callback_data="month_6")],
        [InlineKeyboardButton("Июль", callback_data="month_7")],
        [InlineKeyboardButton("Август", callback_data="month_8")],
        [InlineKeyboardButton("Сентябрь", callback_data="month_9")],
        [InlineKeyboardButton("Октябрь", callback_data="month_10")],
        [InlineKeyboardButton("Ноябрь", callback_data="month_11")],
        [InlineKeyboardButton("Декабрь", callback_data="month_12")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="period_menu")]
    ]

    return InlineKeyboardMarkup(keyboard)

def get_period_report_menu():

    return InlineKeyboardMarkup([
        [InlineKeyboardButton(
            "⬅️ Назад",
            callback_data="period_menu"
        )]
    ])

async def handle_menu(update, context):

    query = update.callback_query

    try:
        await query.answer()
    except Exception as e:
        print("query.answer error:", e)

    data = query.data

    state = context.user_data.get("state", "MAIN")

    # =====================================================
    # ГЛАВНОЕ МЕНЮ
    # Переходы из стартового экрана в основные разделы бота.
    # =====================================================
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
        await query.edit_message_text(
            "⚖️ Выберите тип сравнения:",
            reply_markup=get_compare_menu()

        )
    # =====================================================
    # СРАВНЕНИЕ МЕСЯЦЕВ
    # Начало сценария сравнения двух месяцев.
    # Пользователь сначала выбирает год первого месяца.
    # =====================================================
    elif data == "compare_months":
        context.user_data["state"] = "COMPARE_MONTH_FIRST_YEAR"
        await query.edit_message_text(
            "Выберите год первого месяца:",
            reply_markup=get_compare_year_menu(back_callback="compare_menu")
        )
    # =====================================================
    # СРАВНЕНИЕ ГОДОВ
    # Начало сценария сравнения двух годов.
    # Первый шаг — выбор первого года.
    # =====================================================
    elif data == "compare_years":
        context.user_data["state"] = STATE_COMPARE_YEAR_FIRST
        await query.edit_message_text(
            "Выберите первый год:",
            reply_markup=get_compare_year_menu(
                back_callback="compare_menu"
            )
        )


    # =====================================================
    # ВЫБОР ГОДА ДЛЯ СРАВНЕНИЯ
    #
    # Одна и та же клавиатура используется сразу
    # в двух разных сценариях:
    #
    # 1. Сравнение месяцев
    # 2. Сравнение годов
    #
    # Поэтому сначала смотрим текущее состояние (state),
    # чтобы понять, какой именно год сейчас выбирает пользователь.
    # =====================================================
    elif data.startswith("compare_year_"):
        selected_year = int(data.split("_")[2])
        state = context.user_data.get("state")

        if state == STATE_COMPARE_YEAR_FIRST:
            # Пользователь выбрал первый год.
            # Запоминаем его и переходим к выбору второго года.
            context.user_data["compare_year_first"] = selected_year
            context.user_data["state"] = STATE_COMPARE_YEAR_SECOND

            await query.edit_message_text(
                f"✅ Первый год: {selected_year}\n\n"
                "Выберите второй год:",
                reply_markup=get_compare_year_menu(
                    back_callback="compare_menu"
                )
            )

        elif state == STATE_COMPARE_YEAR_SECOND:
            # Пользователь выбрал второй год.
            # После этого можно будет сформировать отчёт сравнения.
            context.user_data["compare_year_second"] = selected_year
            context.user_data["state"] = STATE_COMPARE_YEAR_RESULT

        if state == "COMPARE_MONTH_SECOND_YEAR":
            # Пользователь находится в сценарии сравнения месяцев.
            # Сейчас выбирается год второго месяца.
            context.user_data["compare_second_year"] = selected_year
            context.user_data["state"] = "COMPARE_MONTH_SECOND_MONTH"
            await query.edit_message_text(
                f"{format_compare_first_month(context)}\n\n"
                f"Выберите второй месяц ({selected_year}):",
                reply_markup=get_compare_month_menu(
                    back_callback="compare_back_second_year"
                )
            )
        else:
            # Иначе это первый год для первого месяца.
            # После него пользователь должен выбрать сам месяц.
            context.user_data["compare_first_year"] = selected_year
            context.user_data["state"] = "COMPARE_MONTH_FIRST_MONTH"
            await query.edit_message_text(
                f"Выберите первый месяц ({selected_year}):",
                reply_markup=get_compare_month_menu(
                    back_callback="compare_months"
                )
            )

    # =====================================================
    # ВЫБОР МЕСЯЦА ДЛЯ СРАВНЕНИЯ
    #
    # В зависимости от состояния определяем,
    # выбирает пользователь первый месяц
    # или второй месяц.
    # =====================================================
    elif data.startswith("compare_month_"):
        selected_month = int(data.split("_")[2])
        state = context.user_data.get("state")

        if state == "COMPARE_MONTH_SECOND_MONTH":
            # Второй месяц выбран.
            # Можно строить отчёт сравнения.
            context.user_data["compare_second_month"] = selected_month
            context.user_data["state"] = "COMPARE_RESULT"
            await send_month_compare(update, context)
        else:
            # Первый месяц выбран.
            # Теперь необходимо выбрать год второго месяца.
            context.user_data["compare_first_month"] = selected_month
            context.user_data["state"] = "COMPARE_MONTH_SECOND_YEAR"
            first_year = context.user_data["compare_first_year"]
            await query.edit_message_text(
                f"✅ Первый месяц: {MONTH_NAMES[selected_month]} {first_year}\n\n"
                f"Выберите год второго месяца:",
                reply_markup=get_compare_year_menu(
                    back_callback="compare_back_first_month"
                )
            )

    elif data == "compare_back_first_month":
        context.user_data["state"] = "COMPARE_MONTH_FIRST_MONTH"
        year = context.user_data["compare_first_year"]
        await query.edit_message_text(
            f"Выберите первый месяц ({year}):",
            reply_markup=get_compare_month_menu(back_callback="compare_months")
        )

    elif data == "compare_back_second_year":
        context.user_data["state"] = "COMPARE_MONTH_SECOND_YEAR"
        await query.edit_message_text(
            f"{format_compare_first_month(context)}\n\n"
            f"Выберите год второго месяца:",
            reply_markup=get_compare_year_menu(
                back_callback="compare_back_first_month"
            )
        )

    elif data == "back_main":
        context.user_data["state"] = "MAIN"
        await query.edit_message_text(
            "Выберите действие:",
            reply_markup=get_main_menu()
        )

    # =====================================================
    # ПРОСМОТР СТАТИСТИКИ ЗА ПРОИЗВОЛЬНЫЙ МЕСЯЦ
    #
    # Пользователь выбрал год.
    # Следующий экран — выбор месяца.
    # =====================================================
    elif data.startswith("year_"):
        selected_year = int(data.split("_")[1])
        context.user_data["selected_year"] = selected_year
        context.user_data["state"] = "MONTH_MENU"
        await query.edit_message_text(
            f"Выберите месяц ({selected_year}):",
            reply_markup=get_month_menu()
        )
    # =====================================================
    # ПРОСМОТР СТАТИСТИКИ
    #
    # После выбора месяца получаем его период
    # и формируем отчёт.
    # =====================================================
    elif data.startswith("month_"):

        selected_month = int(data.split("_")[1])

        selected_year = context.user_data["selected_year"]

        start, end = get_month_period(
            selected_year,
            selected_month
        )
        context.user_data["state"] = "MONTH_REPORT"
        await send_report(
            update,
            context,
            start,
            end,
            "month"
        )
    elif data == "back_to_months":

        selected_year = context.user_data["selected_year"]

        await query.edit_message_text(
            f"Выберите месяц ({selected_year}):",
            reply_markup=get_month_menu()
        )


    # =====================================================
    # БЫСТРАЯ СТАТИСТИКА
    #
    # Кнопки "Текущая неделя",
    # "Текущий месяц",
    # "Текущий год".
    # =====================================================
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

def get_compare_menu():

    keyboard = [
        [InlineKeyboardButton(
            "📆 Сравнить месяцы",
            callback_data="compare_months"
        )],
        [InlineKeyboardButton(
            "🗓 Сравнить годы",
            callback_data="compare_years"
        )],
        [InlineKeyboardButton(
            "⬅️ Назад",
            callback_data="back_main"
        )]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_compare_year_menu(back_callback="compare_menu"):

    keyboard = [
        [InlineKeyboardButton("2024", callback_data="compare_year_2024")],
        [InlineKeyboardButton("2025", callback_data="compare_year_2025")],
        [InlineKeyboardButton("2026", callback_data="compare_year_2026")],
        [InlineKeyboardButton("⬅️ Назад", callback_data=back_callback)]
    ]

    return InlineKeyboardMarkup(keyboard)

def get_compare_month_menu(back_callback="compare_months"):

    keyboard = [
        [InlineKeyboardButton(MONTH_NAMES[m], callback_data=f"compare_month_{m}")]
        for m in range(1, 13)
    ]
    keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data=back_callback)])

    return InlineKeyboardMarkup(keyboard)

def get_compare_result_menu():

    return InlineKeyboardMarkup([
        [InlineKeyboardButton(
            "⬅️ Изменить второй месяц",
            callback_data="compare_back_second_year"
        )],
        [InlineKeyboardButton(
            "⬅️ Начать заново",
            callback_data="compare_months"
        )],
        [InlineKeyboardButton(
            "⬅️ В меню сравнения",
            callback_data="compare_menu"
        )]
    ])

def get_report_menu():
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад",callback_data="stats_menu")]])


def get_month_report_menu():

    return InlineKeyboardMarkup([
        [InlineKeyboardButton(
            "⬅️ Назад",
            callback_data="back_to_months"
        )]
    ])

app = Application.builder().token(TELEGRAM_TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("week", week))
app.add_handler(CommandHandler("month", month))
app.add_handler(CommandHandler("year", year))

app.add_handler(CallbackQueryHandler(handle_menu))

app.run_polling()

# TO DO
# Добавить "Качалка" в поиск слота зал
# Добавить в бота кнопки события: статистика этого месяца, недели, года
# Сравнение месяцев
# графики
# По возможноси оптимизировать Map?
# Добавить думание, при больших расчетах
# Доработка выбора периода от одного до другого месяца прпарвамвмв




