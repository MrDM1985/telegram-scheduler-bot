from telegram import Update
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext
import os
import json
import datetime
import pytz
import time
import threading

# 🛠 Конфигурация
PLANNER_FILE = "planner.json"
DEFAULT_START_TIME = "06:00"
DEFAULT_INTERVAL = 120  
DEFAULT_POSTS_PER_DAY = 6  
POST_CHANNEL = "@lifemotiv1"  
TIMEZONE = pytz.timezone("Europe/Bratislava")  


# Загружаем планировщик (или создаем пустой, если файла нет)
if os.path.exists(PLANNER_FILE):
    with open(PLANNER_FILE, "r", encoding="utf-8") as f:
        try:
            planner = json.load(f)
        except json.JSONDecodeError:
            planner = {}  # Если файл поврежден, создаем пустой словарь
else:
    planner = {}

# Проверяем, что "settings" есть в planner
DEFAULT_SETTINGS = {
    "st": "06:00",  # Время первого поста
    "in": 120,  # Интервал между постами (в минутах)
    "po": 6  # Количество постов в день
}

if "settings" not in planner:
    planner["settings"] = DEFAULT_SETTINGS
else:
    # Если каких-то настроек нет — добавляем их
    for key, value in DEFAULT_SETTINGS.items():
        if key not in planner["settings"]:
            planner["settings"][key] = value

# Функция сохранения планировщика
def save_planner():
    with open(PLANNER_FILE, "w", encoding="utf-8") as f:
        json.dump(planner, f, indent=4, ensure_ascii=False)

save_planner()  # Сохраняем обновленные настройки


# Загружаем токен из переменной среды (лучше, чем хранить в коде!)
BOT_TOKEN = os.getenv("BOT_TOKEN", "7897333136:AAGA3U4VAnWWbbtjU-FBFWWCoTA1KP3Bvcc")

# Загружаем или создаём настройки
if os.path.exists(PLANNER_FILE):
    with open(PLANNER_FILE, "r", encoding="utf-8") as f:
        planner = json.load(f)
else:
    planner = {}

# 💾 Функция сохранения
def save_planner():
    with open(PLANNER_FILE, "w", encoding="utf-8") as f:
        json.dump(planner, f, indent=4, ensure_ascii=False)

settings = planner["settings"]  # Обновляем переменную settings

# 📆 Функция дня недели
def get_weekday(date_str):
    weekdays = ["пнд", "втр", "срд", "чет", "птн", "суб", "вск"]
    date_obj = datetime.datetime.strptime(date_str, "%d%m%y")
    return weekdays[date_obj.weekday()]

# 🎛 Команда /start
def start(update: Update, context: CallbackContext):
    message = update.message if update.message else update.effective_message
    message.reply_text(
        "🤖 *Планировщик активен!*\n"
       f"📅 Время начала: {planner['settings']['st']}\n"
       f"⏳ Интервал: {planner['settings']['in']} минут\n"
       f"📝 Постов в день: {planner['settings']['po']}\n"
        ,
        parse_mode="Markdown"
    )
    show_schedule(update, context)

# 📅 Команда /d (выбор дня планирования)
def day_command(update: Update, context: CallbackContext):
    if len(context.args) != 1 or not context.args[0].isdigit() or len(context.args[0]) != 4:
        update.message.reply_text("⚠ Используйте: /d DDMM")
        return

    day_month = context.args[0]
    now = datetime.datetime.now(TIMEZONE)
    current_year = now.year  
    date = f"{day_month}{str(current_year)[-2:]}"  

    try:
        datetime.datetime.strptime(date, "%d%m%y")
    except ValueError:
        update.message.reply_text("❌ Некорректная дата. Введите в формате DDMM.")
        return

    if datetime.datetime.strptime(date, "%d%m%y").date() < now.date():
        update.message.reply_text("⛔ Нельзя планировать посты на прошедшую дату.")
        return

    if date == now.strftime("%d%m%y"):
        update.message.reply_text("⛔ Нельзя планировать посты на сегодняшний день.")
        return

    context.user_data["current_day"] = date
    if date not in planner:
        planner[date] = []
        save_planner()

    weekday = get_weekday(date)
    update.message.reply_text(f"✅ К планированию готов {date[:2]}.{date[2:4]}.{date[4:]} {weekday}.")



def show_schedule(update: Update, context: CallbackContext):
    """Отображает расписание постов в хронологическом порядке, включая пустые дни."""
    global planner
    if not planner or len(planner.keys()) == 1:
        update.message.reply_text("📭 Запланированных постов нет.")
        return

    now = datetime.datetime.now(TIMEZONE).replace(tzinfo=None)  # Убираем offset для корректного сравнения

    # Очистка прошедших дат и постов
    updated_planner = {}
    for date, posts in planner.items():
        if date == "settings":
            continue
        try:
            date_obj = datetime.datetime.strptime(date, "%d%m%y")  # Преобразуем дату
            if date_obj >= now.replace(hour=0, minute=0, second=0, microsecond=0):  # Если дата не прошла
                updated_posts = [post for post in posts if datetime.datetime.strptime(f"{date} {post['time']}", "%d%m%y %H:%M") > now]
                if updated_posts:
                    updated_planner[date] = updated_posts
        except ValueError:
            continue

    # Перезаписываем planner без старых дат
    planner = {"settings": planner.get("settings", DEFAULT_SETTINGS)}
    planner.update(updated_planner)
    save_planner()

    # Получаем список всех дат в planner
    scheduled_days = sorted(
        [datetime.datetime.strptime(date, "%d%m%y") for date in planner.keys() if date.isdigit()]
    )

    # Если нет доступных дат — сообщаем об этом
    if not scheduled_days:
        update.message.reply_text("📭 Запланированных постов нет.")
        return

    # Формируем диапазон от первой до последней запланированной даты
    full_date_range = []
    current_date = scheduled_days[0]
    while current_date <= scheduled_days[-1]:
        full_date_range.append(current_date)
        current_date += datetime.timedelta(days=1)

    # Словарь русских названий дней недели
    ru_weekdays = {
        "Mon": "пнд", "Tue": "втр", "Wed": "срд", "Thu": "чтв",
        "Fri": "птн", "Sat": "суб", "Sun": "вск"
    }

    # 🔥 Формируем текст расписания
    schedule_text = "📆 *Расписание постов:*\n"
    for date in full_date_range:
        formatted_date = date.strftime('%d.%m.%y')
        weekday_name = date.strftime("%a")
        weekday_rus = ru_weekdays.get(weekday_name, weekday_name)
        date_key = date.strftime("%d%m%y")

        if date_key in planner and planner[date_key]:  # Если есть посты
            schedule_text += f"\n📅 *{formatted_date} {weekday_rus}:*\n"
            for idx, post in enumerate(planner[date_key], start=1):
                schedule_text += f"  {idx}) {post['time']} - ОК\n"
        else:  # Если на этот день ничего нет
            schedule_text += f"\n📅 *{formatted_date} {weekday_rus}:* ❌ ПУСТО\n"

    update.message.reply_text(schedule_text, parse_mode="Markdown")





def handle_files(update: Update, context: CallbackContext):
    if "current_day" not in context.user_data:
        update.message.reply_text("Сначала выберите день командой /d DDMM.")
        return

    date = context.user_data["current_day"]
    if len(planner.get(date, [])) >= planner["settings"]["po"]:
        update.message.reply_text("❌ Все посты на этот день уже запланированы! Выберите следующий день командой /d DDMM.")
        return

    now = datetime.datetime.now(TIMEZONE)

    # Определяем время начала постов
    if date == now.strftime("%d%m%y"):
        start_time = now + datetime.timedelta(minutes=2)  # Ближайшее возможное время для сегодня
    else:
        start_time = datetime.datetime.strptime(planner["settings"]["st"], "%H:%M")  # Для будущих дней

    # Вычисляем время следующего поста с учетом интервала
    if not planner.get(date):  # Если в этот день постов еще нет
        post_time = start_time
    else:
        post_time = datetime.datetime.combine(now.date(), start_time.time()) + datetime.timedelta(
            minutes=len(planner[date]) * planner["settings"]["in"]
        )

    # Проверяем, чтобы не планировать на прошедшее время
    if date == now.strftime("%d%m%y") and post_time < now.replace(tzinfo=None):
        post_time = now  # Если сегодня, но время уже прошло — публикуем сразу

        post_content = update.message.caption if update.message.caption else update.message.text

    if update.message.photo:
        post_type = "photo"
        post_content = update.message.photo[-1].file_id
    elif update.message.video:
        post_type = "video"
        post_content = update.message.video.file_id
    else:
        post_type = "text"
        post_content = update.message.text if update.message.text else "[медиа файл]"

    print(f"📝 Сохранение поста: {post_content} (тип: {post_type})")  # <-- Добавлено для отладки

    planner.setdefault(date, []).append({
        "time": post_time.strftime("%H:%M"),
        "type": post_type,
        "content": post_content
    })
    save_planner()


    # 📝 Коррекция формата даты
    formatted_date = datetime.datetime.strptime(date, "%d%m%y").strftime('%d.%m.%y')

    update.message.reply_text(f"✅ Запланировано на {post_time.strftime('%H:%M')} {formatted_date}.")

    # Если это последний возможный пост за день, бот сообщает об этом
    if len(planner.get(date, [])) >= planner["settings"]["po"]:
        update.message.reply_text("🎯 **Все посты на этот день запланированы!** Выберите следующий день командой /d DDMM.")


def set_start_time(update: Update, context: CallbackContext):
    """Изменяет время первого поста и сохраняет настройку."""
    if len(context.args) != 1 or not context.args[0].isdigit():
        update.message.reply_text("❌ Используйте команду так: /st HHMM (например, /st 0930).")
        return

    time_input = context.args[0]
    if len(time_input) == 4:
        hour, minute = int(time_input[:2]), int(time_input[2:])
        if hour >= 24 or minute >= 60:
            update.message.reply_text("⚠️ Неверный формат времени. Используйте HHMM (например, 0930).")
            return

        new_time = f"{hour:02d}:{minute:02d}"
        planner["settings"]["st"] = new_time
        save_planner()  # Сохраняем изменения в JSON

        update.message.reply_text(f"⏰ Время первого поста изменено на {new_time}.")
    else:
        update.message.reply_text("❌ Неверный формат. Используйте HHMM (например, 0930).")

def set_interval(update: Update, context: CallbackContext):
    """Изменяет интервал между постами и сохраняет настройку."""
    if len(context.args) != 1 or not context.args[0].isdigit():
        update.message.reply_text("❌ Используйте команду так: /in [интервал в минутах]")
        return

    new_interval = int(context.args[0])
    if new_interval < 10 or new_interval > 300:
        update.message.reply_text("⚠️ Интервал должен быть от 10 до 300 минут.")
        return

    planner["settings"]["in"] = new_interval
    save_planner()  # Сохраняем изменения в JSON

    update.message.reply_text(f"⏳ Интервал между постами изменен на {new_interval} минут.")

def set_posts_per_day(update: Update, context: CallbackContext):
    """Изменяет количество постов в день и сохраняет настройку."""
    if len(context.args) != 1 or not context.args[0].isdigit():
        update.message.reply_text("❌ Используйте команду так: /po [число постов]")
        return

    new_po = int(context.args[0])
    if new_po < 1 or new_po > 10:
        update.message.reply_text("⚠️ Количество постов должно быть от 1 до 10.")
        return

    planner["settings"]["po"] = new_po
    save_planner()  # Сохраняем изменения в JSON

    update.message.reply_text(f"📝 Количество постов в день изменено на {new_po}.")


# 🗑 Команда /cla (очистка ВСЕГО планировщика)
def clear_all(update: Update, context: CallbackContext):
    planner.clear()
    save_planner()
    update.message.reply_text("✅ Все запланированные посты удалены.")

# 🗑 Команда /c (очистка конкретного дня)
def clear_day(update: Update, context: CallbackContext):
    if len(context.args) != 1 or not context.args[0].isdigit() or len(context.args[0]) != 4:
        update.message.reply_text("⚠ Используйте: /c DDMM")
        return

    day_month = context.args[0]
    current_year = datetime.datetime.now(TIMEZONE).year  # Текущий год
    date = f"{day_month}{str(current_year)[-2:]}"  # Формируем дату в формате DDMMYY

    if date in planner:
        del planner[date]
        save_planner()
        update.message.reply_text(f"🗑 Посты на {date[:2]}.{date[2:4]}.{date[4:]} удалены.")
    else:
        update.message.reply_text(f"📭 На {date[:2]}.{date[2:4]}.{date[4:]} постов нет.")


# ⏳ Команда /time (показ текущего времени у бота)
def time_command(update: Update, context: CallbackContext):
    now = datetime.datetime.now(TIMEZONE).strftime("%d.%m.%Y %H:%M")
    update.message.reply_text(f"🕒 Текущее время (Братислава): {now}")


def post_scheduler(context: CallbackContext):
    """Функция проверяет запланированные посты и публикует их в нужное время."""
    now = datetime.datetime.now(TIMEZONE).replace(second=0, microsecond=0)
    for date, posts in list(planner.items()):
        if date == "settings":
            continue
        for post in list(posts):  # Используем копию списка, чтобы безопасно удалять элементы
            post_time = datetime.datetime.strptime(f"{date} {post['time']}", "%d%m%y %H:%M").replace(second=0, microsecond=0)
            if post_time <= now.replace(tzinfo=None):
                try:
                    # Определяем тип контента
                    if isinstance(post["content"], str):
                        context.bot.send_message(POST_CHANNEL, f"\n\n{post['content']}")
                    else:
                        context.bot.send_photo(POST_CHANNEL, post["content"])

                    # Удаляем опубликованный пост из планировщика
                    posts.remove(post)
                    save_planner()
                    print(f"✅ Опубликован пост на {post_time.strftime('%H:%M %d.%m.%y')}")
                except Exception as e:
                    print(f"⚠️ Ошибка при публикации поста: {e}")


if __name__ == "__main__":
    updater = Updater("7897333136:AAGA3U4VAnWWbbtjU-FBFWWCoTA1KP3Bvcc", use_context=True)
    dp = updater.dispatcher
    
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("d", day_command))
    dp.add_handler(CommandHandler("ss", show_schedule))
    dp.add_handler(CommandHandler("st", set_start_time))
    dp.add_handler(CommandHandler("in", set_interval))
    dp.add_handler(CommandHandler("po", set_posts_per_day))
    dp.add_handler(CommandHandler("cla", clear_all))
    dp.add_handler(CommandHandler("c", clear_day))
    dp.add_handler(CommandHandler("time", time_command))
    dp.add_handler(MessageHandler(Filters.all, handle_files))

 # 🕒 Запускаем планировщик
    job_queue = updater.job_queue
    job_queue.run_repeating(post_scheduler, interval=60, first=10)

    print("🤖 Бот запущен!")
    updater.start_polling()
    updater.idle()

