
def post_now(update: Update, context: CallbackContext):
    """Публикует контент немедленно в канал, минуя планировщик."""
    bot = context.bot
    message = update.message

    if not message:
        return

    # Если пользователь просто ввел /now, бот сообщает, что ждет контент
    if message.text and message.text.strip() == "/now":
        message.reply_text("📢 Отправьте текст, фото или видео для мгновенной публикации.")
        return  # Ждем следующее сообщение

    # Мгновенно публикуем контент без проверки планировщика
    if message.text and not message.text.startswith("/now"):
        bot.send_message(POST_CHANNEL, f"\n\n{message.text}", parse_mode="Markdown")
        message.reply_text("✅ Текст опубликован!")

    elif message.photo:
        file_id = message.photo[-1].file_id
        caption = message.caption if message.caption else ""
        bot.send_photo(POST_CHANNEL, file_id, caption=f"\n\n{caption}", parse_mode="Markdown")
        message.reply_text("✅ Фото опубликовано!")

    elif message.video:
        file_id = message.video.file_id
        caption = message.caption if message.caption else ""
        bot.send_video(POST_CHANNEL, file_id, caption=f"\n\n{caption}", parse_mode="Markdown")
        message.reply_text("✅ Видео опубликовано!")

    else:
        message.reply_text("⚠️ Этот тип контента пока не поддерживается.")











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
    """Обработка входящих сообщений и файлов"""
    if "current_day" not in context.user_data:
        update.message.reply_text("Сначала выберите день командой /d DDMM.")
        return

    date = context.user_data["current_day"]
    if len(planner.get(date, [])) >= planner["settings"]["po"]:
        update.message.reply_text("❌ Все посты на этот день уже запланированы! Выберите следующий день командой /d DDMM.")
        return

    now = datetime.datetime.now(TIMEZONE)

    # Определяем время публикации
    if not planner.get(date):
        post_time = now + datetime.timedelta(minutes=2)  # Первый пост в ближайшее время
    else:
        last_post_time = datetime.datetime.strptime(planner[date][-1]["time"], "%H:%M")
        post_time = last_post_time + datetime.timedelta(minutes=planner["settings"]["in"])  # Интервал между постами

    # Определяем тип контента
    post_type = "text"
    post_content = update.message.text if update.message.text else "ОК"

    if update.message.photo:
        post_type = "photo"
        post_content = update.message.photo[-1].file_id  # Сохраняем file_id для фото

    if update.message.video:
        post_type = "video"
        post_content = update.message.video.file_id  # Сохраняем file_id для видео

    # Записываем пост в JSON
    post_data = {
        "time": post_time.strftime("%H:%M"),
        "type": post_type,
        "content": post_content
    }

    planner[date].append(post_data)
    save_planner()

    update.message.reply_text(f"✅ Запланировано на {post_time.strftime('%H:%M')} {datetime.datetime.strptime(date, '%d%m%y').strftime('%d.%m.%y')}.")

    # Если день заполнен, сообщаем об этом
    if len(planner[date]) >= planner["settings"]["po"]:
        update.message.reply_text("🎯 Все посты на этот день запланированы! Выберите следующий день командой /d DDMM.")





# ⏰ Команда /st (время старта)
def set_start_time(update: Update, context: CallbackContext):
    if len(context.args) != 1 or not context.args[0].isdigit():
        update.message.reply_text("Используйте: /st HHMM (например, 0930).")
        return
    
    time_input = context.args[0]
    if len(time_input) == 4:
        hour, minute = int(time_input[:2]), int(time_input[2:])
        if hour >= 24 or minute >= 60:
            update.message.reply_text("⚠️ Неверный формат времени.")
            return
        
        settings["start_time"] = f"{hour:02d}:{minute:02d}"
        update.message.reply_text(f"⏰ Установлено время первого поста: {settings['start_time']}")

# 🔄 Команда /in (интервал)
def set_interval(update: Update, context: CallbackContext):
    if len(context.args) != 1 or not context.args[0].isdigit():
        update.message.reply_text("Используйте: /in <минуты> (например, /in 180).")
        return
    
    interval = int(context.args[0])
    settings["interval"] = interval
    update.message.reply_text(f"🔄 Интервал между постами установлен на {interval} минут.")

# 📊 Команда /po (постов в день)
def set_posts_per_day(update: Update, context: CallbackContext):
    if len(context.args) != 1 or not context.args[0].isdigit():
        update.message.reply_text("Используйте: /po <количество> (например, /po 4).")
        return
    
    posts_per_day = int(context.args[0])
    settings["posts_per_day"] = posts_per_day
    update.message.reply_text(f"📊 Количество постов в день установлено на {posts_per_day}.")

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


# 📢 Функция автоматической публикации постов
def post_scheduler():
    while True:
        now = datetime.datetime.now(TIMEZONE).strftime("%d%m%y %H:%M")

        for date, posts in list(planner.items()):
            if date == "settings":
                continue
            for post in posts[:]:  # Копируем список постов, чтобы изменять оригинальный
                scheduled_time = f"{date} {post['time']}"
                if scheduled_time <= now:
                    try:
                        if post["type"] == "text":
                            updater.bot.send_message(chat_id=POST_CHANNEL, text=post["content"])
                        elif post["type"] == "photo":
                            updater.bot.send_photo(chat_id=POST_CHANNEL, photo=post["content"])
                        elif post["type"] == "video":
                            updater.bot.send_video(chat_id=POST_CHANNEL, video=post["content"])

                        posts.remove(post)  # Удаляем пост после публикации
                        save_planner()  # Сохраняем изменения
                        print(f"✅ Опубликован пост на {date} в {post['time']}")
                    except Exception as e:
                        print(f"❌ Ошибка публикации поста: {e}")

        time.sleep(60)  # Проверяем расписание каждую минуту



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

    print("🤖 Бот запущен!")
    updater.start_polling()
    updater.idle()

