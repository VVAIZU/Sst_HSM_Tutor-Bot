import telebot
from telebot import types
import requests
from datetime import datetime
import schedule
import threading
import json
import time

TOKEN = ""
NOTION_TOKEN = ""
DATABASE_ID = ""

bot = telebot.TeleBot(TOKEN)

@bot.message_handler(commands=['start'])
def start(message):
    sticker_id = 'CAACAgIAAxkBAAELVsllw5pTSd2BwWfjsIZNEZQXlV-gbQAC1R8AAjM5uUpr1A6eTkIGiTQE'
    bot.send_sticker(message.chat.id, sticker_id)

    welcome_message = (
        "Привет! С помощью этого бота ты можешь <b>назначить тьюторскую встречу</b>\n"
        "Чтобы создать встречу напиши <i>встреча</i> , или <i>помощь</i> - чтобы понять как бот работает\n"
    )
    bot.send_message(message.chat.id, welcome_message, parse_mode='HTML')

@bot.message_handler(func=lambda message: message.text.lower() in ['встреча', 'помощь'])
def handle_command(message):
    help_message = (
        "Этот бот помогает <b>запланировать тьюторскую встречу</b>.\n"
        " \n"
        "Напиши <b>встреча</b>, чтобы начать запись.\n"
        " \n"
        "Далее бот спросит <b>какая это встреча по счету</b>. <i>Введи 1 - если первая, 2 - если вторая и так далее</i>\n"
        " \n"
        "После бот спросит про <b>дату встречи</b>. <i>Вводи обязательно в формате ДД/ММ/ГГГГ. Например: 07/02/2024</i>\n"
        " \n"
        "<b>Поздравляю! Встреча записана.</b> В назначенную дату бот пришлет сообщение-напоминание. <i>В этом же сообщении, пожалуйста, нажми на кнопку <b>Проведу встречу</b> или <b>Отменю встречу</b></i>\n"
        " \n"
        " \n"
        "<i>Хочешь изменить дату встречи?</i> Просто создай новую запись встречи с тем же номером, но новой датой.\n"
    )
    if message.text.lower() == 'встреча':
        bot.send_message(message.chat.id, "Введите номер тьюторской встречи:")
        bot.register_next_step_handler(message, ask_date)
    elif message.text.lower() == 'помощь':
        # Здесь вы можете написать код для обработки команды "помощь"
        bot.send_message(message.chat.id, help_message, parse_mode='HTML')


def ask_date(message):
    chat_id = message.chat.id
    m_number = message.text
    bot.send_message(chat_id, "Теперь введите дату вашей встречи в формате ДД/ММ/ГГГГ:")
    bot.register_next_step_handler(message, lambda msg: save_meeting(msg, m_number))

def save_meeting(message, m_number):
    chat_id = message.chat.id
    date_str = message.text
    try:
        # Преобразование строки даты в объект datetime
        date_obj = datetime.strptime(date_str, "%d/%m/%Y")
        # Преобразование объекта datetime в строку в формате ISO 8601
        date_iso = date_obj.strftime("%Y-%m-%d")
        
        send_to_notion(message.chat.id, m_number, date_iso, message.from_user.username)
    except Exception as e:
        bot.send_message(chat_id, f"Произошла ошибка: {e}")

def get_pages():
    global NOTION_TOKEN, DATABASE_ID
    headers = {
        "Authorization": "Bearer " + NOTION_TOKEN,
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28",
    }

    # Формируем запрос для поиска записи по имени пользователя
    url = f"https://api.notion.com/v1/databases/{DATABASE_ID}/query"
    
    payload = {"page_size": 100}
    response = requests.post(url, json=payload, headers=headers)

    data = response.json()

    results = data["results"]
    return results

def send_to_notion(chat_id, m_number, date, username):
    global NOTION_TOKEN, DATABASE_ID
    headers = {
        "Authorization": "Bearer " + NOTION_TOKEN,
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28",
    }

    # Проверяем, существует ли запись для данного пользователя
    pages = get_pages()
    for page in pages: 
        page_id = page["id"]
        props = page["properties"]
        p_usern = props["Username"]["title"][0]["text"]["content"]
        pm_num = props["MeetingNumber"]["rich_text"][0]["text"]["content"]
        if username == p_usern and pm_num == m_number:
            bot.send_message(chat_id, "Данные о встрече успешно обновлены!")
            update_existing_page(page_id, date, "Запланирована")
            return  # Заканчиваем выполнение функции, так как запись уже существует
    #u
    create_new_page(chat_id, username, date, m_number)

def update_existing_page(page_id, new_date, status):
    global NOTION_TOKEN
    headers = {
        "Authorization": "Bearer " + NOTION_TOKEN,
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28",
    }

    update_url = f"https://api.notion.com/v1/pages/{page_id}"
    payload = {
        "properties": {
            "Meeting Date": {"date": {"start": new_date, "end": None}},
            "Meeting Status": {"select": {"name": status}}
        }
    }

    res = requests.patch(update_url, headers=headers, json=payload)

    if res.status_code == 200:
        print("Запись успешно обновлена в Notion.")
    else:
        print("Ошибка при обновлении записи в Notion:", res.text)

def create_new_page(chat_id, username, date, m_number):
    global NOTION_TOKEN, DATABASE_ID
    headers = {
        "Authorization": "Bearer " + NOTION_TOKEN,
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28",
    }

    senddata = {
        "Username": {"title": [{"text": {"content": username}}]},
        "MeetingNumber": {"rich_text": [{"text": {"content": m_number}}]},
        "Meeting Date": {"date": {"start": date, "end": None}},
        "Meeting Status": {"select": {"name": "Запланирована"}},
        "chatId": {"rich_text": [{"text": {"content": str(chat_id)}}]}
    }

    create_url = "https://api.notion.com/v1/pages"

    payload = {"parent": {"database_id": DATABASE_ID}, "properties": senddata}

    res = requests.post(create_url, headers=headers, json=payload)

    if res.status_code == 200:
        bot.send_message(chat_id, "Встреча успешно записана!")
        print("Данные успешно отправлены в Notion.")
    else:
        bot.send_message(chat_id, f"Произошла ошибка при отправке данных в Notion: {res.text}")
        print("Ошибка при отправке данных в Notion:", res.text)


def send_reminders():
    global bot, NOTION_TOKEN, DATABASE_ID
    # Получаем записи из базы данных Notion
    pages = get_pages()
    for page in pages: 
        page_id = page["id"]
        props = page["properties"]
        p_date = props["Meeting Date"]["date"]["start"]
        username = "@" + props["Username"]["title"][0]["text"]["content"]  # Получаем имя пользователя из столбца "Username"
        chat = props["chatId"]["rich_text"][0]["text"]["content"]
        # Проверяем, если сегодняшняя дата совпадает с датой встречи
        if datetime.now().strftime("%Y-%m-%d") == p_date:
             # Создаем инлайн-клавиатуру
            keyboard = types.InlineKeyboardMarkup()
            keyboard.row(
                types.InlineKeyboardButton("Проведу встречу", callback_data=f"confirm_meeting_{page_id}"),
                types.InlineKeyboardButton("Отказ от встречи", callback_data=f"cancel_meeting_{page_id}")
            )
            # Отправляем сообщение о встрече с клавиатурой
            bot.send_message(chat, f"Напоминаю! Сегодня у вас встреча!",  reply_markup=keyboard)

# Обработка callback-запросов
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    global NOTION_TOKEN
    # Получаем id страницы из callback-запроса
    page_id = call.data.split("_")[-1]
    # Обновляем статус встречи в базе данных Notion в зависимости от нажатой кнопки
    if call.data.startswith("confirm_meeting"):
        update_meeting_status(page_id, "Проведена")
        bot.send_message(call.message.chat.id, "Статус встречи - Проведена сегодня.")
    elif call.data.startswith("cancel_meeting"):
        cancel_meeting_with_new_date(call.message, page_id)


def cancel_meeting_with_new_date(message, page_id):
    bot.send_message(message.chat.id, "Вы отменили встречу. Пожалуйста, введите новую дату встречи в формате dd/mm/yyyy:")
    bot.register_next_step_handler(message, lambda msg: update_meeting_date(msg, page_id))


def update_meeting_date(message, page_id):
    date_str = message.text
    try:
        # Преобразование строки даты в объект datetime
        date_obj = datetime.strptime(date_str, "%d/%m/%Y")
        # Преобразование объекта datetime в строку в формате ISO 8601
        new_date_iso = date_obj.strftime("%Y-%m-%d")
        update_existing_page(page_id, new_date_iso, "Отменена")
        bot.send_message(message.chat.id, "Новая дата встречи успешно обновлена!")
    except Exception as e:
        bot.send_message(message.chat.id, f"Произошла ошибка: {e}")

# Функция для обновления статуса встречи в базе данных Notion
def update_meeting_status(page_id, status):
    headers = {
        "Authorization": "Bearer " + NOTION_TOKEN,
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28",
    }
    update_url = f"https://api.notion.com/v1/pages/{page_id}"
    payload = {
        "properties": {
            "Meeting Status": {"select": {"name": status}}
        }
    }
    res = requests.patch(update_url, headers=headers, json=payload)
    if res.status_code == 200:
        print("Статус встречи обновлен в Notion.")
    else:
        print("Ошибка при обновлении статуса встречи в Notion:", res.text)

# Регистрируем функцию для выполнения каждый день в полночь
schedule.every().day.at("00:19").do(send_reminders)

# Определение функции, которая будет выполнять планировщик в отдельном потоке
def schedule_thread():
    global schedule
    while True:
        schedule.run_pending()
        time.sleep(1)

# Создание и запуск потока
schedule_thread = threading.Thread(target=schedule_thread)
schedule_thread.start()

# Запуск бота
bot.polling()
