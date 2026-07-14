from collections import defaultdict
from datetime import datetime
import re
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

ORANGE_COLOR_ID = "6"   # Мандарин → работа
LAVENDER_COLOR_ID = "1" # Лаванда → учёба
SAGE_COLOR_ID = "2" # Шалфей - врач/больница
GRAPHITE_COLOR_ID = "8" # Пропуск

SPORT_WORDS = [
    "зал",
    "качалка",
    "тренажерка",
    "тренажёрка",
    "спортзал",
    "gym",
    "фитнес",
    "тренировка",
    "треня",
    "силовая",
    "кардио",
    "бег",
    "бассейн",
    "плавание",
    "йога",
    "растяжка",
    "бокс",
    "грудь",
    "спина",
    "ноги",
    "плечи",
    "бицепс",
    "трицепс",
    "пресс"
]

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

CATEGORY_ICONS = {
    "Работа": "🟠",
    "Учёба": "🟣",
    "Больница": "🟢",
    "Спорт": "🔵",
    "Другое": "⚪",
}

def get_service():
    SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']
    creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    return build('calendar', 'v3', credentials=creds)

def detect_category(title: str, color_id: str | None):

    if color_id == GRAPHITE_COLOR_ID:
        return None

    if color_id == ORANGE_COLOR_ID:
        return "Работа"

    if color_id == LAVENDER_COLOR_ID:
        return "Учёба"

    if color_id == SAGE_COLOR_ID:
        return "Больница"

    if any(word in title.lower() for word in SPORT_WORDS):
        return "Спорт"

    return "Другое"

def get_stats(start_date, end_date):

    stats = defaultdict(float)

    page_token = None

    while True:
        service = get_service()
        events_result = service.events().list(
            calendarId='primary',
            timeMin=start_date.isoformat(),
            timeMax=end_date.isoformat(),
            singleEvents=True,
            orderBy='startTime',
            pageToken=page_token
        ).execute()

        events = events_result.get('items', [])

        for event in events:

            title = event.get('summary', '').lower()

            start = event['start'].get('dateTime')
            end = event['end'].get('dateTime')
            # пропуск событий на весь день
            if not start or not end:
                continue

            color = str(event.get("colorId"))

            category = detect_category(
                title,
                color
            )

            if category is None:
                continue

            start_dt = datetime.fromisoformat(
                start.replace('Z', '+00:00')
            )

            end_dt = datetime.fromisoformat(
                end.replace('Z', '+00:00')
            )

            hours = (
                end_dt - start_dt
            ).total_seconds() / 3600

            stats[category] += hours

        page_token = events_result.get(
            'nextPageToken'
        )

        if not page_token:
            break

    return stats




