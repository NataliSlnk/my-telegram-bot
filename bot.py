import telebot
from telebot import types
import sqlite3
from datetime import date, datetime
import os

BOT_TOKEN = "8611715470:AAH_n04OCwEJ4T-zzF79PXQdZCmLKBIMKbQ"

bot = telebot.TeleBot(BOT_TOKEN)

# ============================================================
# ТВОЙ ГОТОВЫЙ СПИСОК ЕЖЕМЕСЯЧНЫХ ПЛАТЕЖЕЙ
# ============================================================
PLAN_PAYMENTS = [
    {"name": "Садик", "amount": 49000},
    {"name": "Ипотека", "amount": 15000},
    {"name": "Кредит", "amount": 1250},
    {"name": "ЮИТ", "amount": 6000},
    {"name": "ПСК", "amount": 1500},
    {"name": "Интернет", "amount": 680},
    {"name": "Моб.связь", "amount": 370},
    {"name": "VPN", "amount": 299},
    {"name": "Тхэквандо", "amount": 4900},
]
# ============================================================

# --- БАЗА ДАННЫХ ---
def init_db():
    conn = sqlite3.connect('my_life.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS tasks
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER,
                  type TEXT,
                  text TEXT,
                  completed INTEGER DEFAULT 0,
                  created_date DATE)''')
    c.execute('''CREATE TABLE IF NOT EXISTS payments
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER,
                  name TEXT,
                  amount REAL,
                  completed INTEGER DEFAULT 0,
                  month TEXT,
                  is_extra INTEGER DEFAULT 0)''')
    c.execute('''CREATE TABLE IF NOT EXISTS no_smoke
                 (user_id INTEGER PRIMARY KEY,
                  start_date DATE,
                  last_check DATE,
                  streak INTEGER DEFAULT 0)''')
    c.execute('''CREATE TABLE IF NOT EXISTS diary
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER,
                  date DATE,
                  text TEXT,
                  photo_path TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS gratitude
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER,
                  date DATE,
                  text TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS useful
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER,
                  title TEXT,
                  content TEXT,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit()
    conn.close()

init_db()

# --- ПРОВЕРКА И СОЗДАНИЕ ПЛАТЕЖЕЙ НА ТЕКУЩИЙ МЕСЯЦ ---
def ensure_monthly_payments(user_id):
    month_str = date.today().strftime("%Y-%m")
    conn = sqlite3.connect('my_life.db')
    c = conn.cursor()
    c.execute("SELECT count(*) FROM payments WHERE user_id=? AND month=? AND is_extra=0",
              (user_id, month_str))
    count = c.fetchone()[0]
    if count == 0:
        for p in PLAN_PAYMENTS:
            c.execute("INSERT INTO payments (user_id, name, amount, month, is_extra) VALUES (?,?,?,?,0)",
                      (user_id, p["name"], p["amount"], month_str))
    conn.commit()
    conn.close()

# --- ГЛАВНОЕ МЕНЮ ---
def main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        types.KeyboardButton("Задачи на день"),
        types.KeyboardButton("Задачи на неделю"),
        types.KeyboardButton("Платежи"),
        types.KeyboardButton("Не курю"),
        types.KeyboardButton("Дневник"),
        types.KeyboardButton("Благодарность"),
        types.KeyboardButton("Отчёт"),
        types.KeyboardButton("Полезное")
    )
    return markup

def get_cancel_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("Отмена"))
    return markup

# --- СТАРТ ---
@bot.message_handler(commands=['start'])
def start(message):
    ensure_monthly_payments(message.chat.id)
    bot.send_message(message.chat.id, "Привет. Я твой ежедневник.\nВыбери раздел:", reply_markup=main_menu())

# --- ОБРАБОТЧИК МЕНЮ ---
@bot.message_handler(func=lambda message: True)
def handle_menu(message):
    user_id = message.chat.id

    if message.text == "Отмена":
        bot.send_message(user_id, "Возвращаюсь в главное меню.", reply_markup=main_menu())
        return

    if message.text == "Задачи на день":
        show_tasks(message, 'day')
    elif message.text == "Задачи на неделю":
        show_tasks(message, 'week')
    elif message.text == "Платежи":
        ensure_monthly_payments(user_id)
        show_payments(message)
    elif message.text == "Не курю":
        check_smoke(message)
    elif message.text == "Дневник":
        bot.send_message(user_id, "Напиши, как прошёл день, или пришли фото (подпись к фото сохранится как текст).",
                         reply_markup=get_cancel_keyboard())
        bot.register_next_step_handler(message, save_diary)
    elif message.text == "Благодарность":
        bot.send_message(user_id, "Напиши, за что ты сегодня благодарна:",
                         reply_markup=get_cancel_keyboard())
        bot.register_next_step_handler(message, save_gratitude)
    elif message.text == "Отчёт":
        generate_report(message)
    elif message.text == "Полезное":
        show_useful_menu(message)
    else:
        bot.send_message(user_id, "Используй кнопки меню.", reply_markup=main_menu())

# --- ЗАДАЧИ ---
def show_tasks(message, task_type):
    user_id = message.chat.id
    conn = sqlite3.connect('my_life.db')
    c = conn.cursor()
    c.execute("SELECT id, text, completed FROM tasks WHERE user_id=? AND type=? AND completed=0",
              (user_id, task_type))
    tasks = c.fetchall()
    conn.close()

    type_name = "День" if task_type == 'day' else "Неделя"

    if not tasks:
        bot.send_message(user_id, f"Задач на {type_name.lower()} пока нет.\nНапиши текст, чтобы добавить:",
                         reply_markup=get_cancel_keyboard())
        bot.register_next_step_handler(message, add_task, task_type)
        return

    text = f"Задачи на {type_name.lower()}:\n\n"
    for task in tasks:
        text += f"  [ ] {task[1]}  /done-{task[0]}\n"
    text += "\nНапиши текст, чтобы добавить задачу.\n/done-номер — отметить выполненной."

    bot.send_message(user_id, text, reply_markup=get_cancel_keyboard())
    bot.register_next_step_handler(message, add_task, task_type)

def add_task(message, task_type):
    user_id = message.chat.id

    if message.text == "Отмена":
        bot.send_message(user_id, "Возвращаюсь в главное меню.", reply_markup=main_menu())
        return

    if message.text and message.text.startswith('/'):
        return

    task_text = message.text
    conn = sqlite3.connect('my_life.db')
    c = conn.cursor()
    c.execute("INSERT INTO tasks (user_id, type, text, created_date) VALUES (?,?,?,?)",
              (user_id, task_type, task_text, date.today()))
    conn.commit()
    conn.close()
    bot.send_message(user_id, f"Добавлено: {task_text}", reply_markup=main_menu())

@bot.message_handler(func=lambda msg: msg.text and msg.text.startswith('/done-'))
def complete_task(message):
    user_id = message.chat.id
    task_id = message.text.split('-')[1]
    conn = sqlite3.connect('my_life.db')
    c = conn.cursor()
    c.execute("SELECT text FROM tasks WHERE id=?", (task_id,))
    task = c.fetchone()
    if task:
        task_text = task[0]
        c.execute("UPDATE tasks SET completed=1 WHERE user_id=? AND text=? AND completed=0",
                  (user_id, task_text))
        conn.commit()
        bot.send_message(user_id, f"[x] Выполнено: {task_text}")
    conn.close()

# --- ПЛАТЕЖИ ---
def show_payments(message):
    user_id = message.chat.id
    month_str = date.today().strftime("%Y-%m")
    conn = sqlite3.connect('my_life.db')
    c = conn.cursor()

    c.execute("SELECT id, name, amount, completed FROM payments WHERE user_id=? AND month=? AND is_extra=0 ORDER BY id",
              (user_id, month_str))
    plan = c.fetchall()

    c.execute("SELECT id, name, amount, completed FROM payments WHERE user_id=? AND month=? AND is_extra=1 ORDER BY id",
              (user_id, month_str))
    extra = c.fetchall()
    conn.close()

    text = f"Платежи ({month_str}):\n\n"

    if plan:
        text += "  Основные:\n"
        for p in plan:
            status = "[x]" if p[3] else "[ ]"
            amount_str = f" — {p[2]} руб." if p[2] > 0 else ""
            text += f"    {status} {p[1]}{amount_str}  /pay-{p[0]}\n"

    if extra:
        text += "\n  Дополнительные:\n"
        for p in extra:
            status = "[x]" if p[3] else "[ ]"
            text += f"    {status} {p[1]} — {p[2]} руб.  /pay-{p[0]}\n"

    if not plan and not extra:
        text += "  Платежей пока нет.\n"

    text += "\n  + доп. платёж: Название, Сумма"
    text += "\n  /pay-номер — отметить оплаченным"

    bot.send_message(user_id, text, reply_markup=get_cancel_keyboard())
    bot.register_next_step_handler(message, add_payment)

def add_payment(message):
    user_id = message.chat.id

    if message.text == "Отмена":
        bot.send_message(user_id, "Возвращаюсь в главное меню.", reply_markup=main_menu())
        return

    if message.text and message.text.startswith('/'):
        return

    try:
        parts = message.text.split(',')
        name = parts[0].strip()
        amount = float(parts[1].strip().replace(' ', ''))
        month_str = date.today().strftime("%Y-%m")
        conn = sqlite3.connect('my_life.db')
        c = conn.cursor()
        c.execute("INSERT INTO payments (user_id, name, amount, month, is_extra) VALUES (?,?,?,?,1)",
                  (user_id, name, amount, month_str))
        conn.commit()
        conn.close()
        bot.send_message(user_id, f"Добавлен платёж: {name}, {amount} руб.", reply_markup=main_menu())
    except:
        bot.send_message(user_id, "Неверный формат.\nПопробуй так: Название, Сумма\nНапример: Интернет, 500",
                         reply_markup=get_cancel_keyboard())
        bot.register_next_step_handler(message, add_payment)

@bot.message_handler(func=lambda msg: msg.text and msg.text.startswith('/pay-'))
def complete_payment(message):
    user_id = message.chat.id
    pay_id = message.text.split('-')[1]
    conn = sqlite3.connect('my_life.db')
    c = conn.cursor()
    c.execute("SELECT name FROM payments WHERE id=?", (pay_id,))
    pay = c.fetchone()
    if pay:
        c.execute("UPDATE payments SET completed=1 WHERE id=?", (pay_id,))
        conn.commit()
        bot.send_message(user_id, f"[x] Оплачено: {pay[0]}", reply_markup=main_menu())
    conn.close()

# --- НЕ КУРЮ ---
def check_smoke(message):
    user_id = message.chat.id
    today = date.today()
    conn = sqlite3.connect('my_life.db')
    c = conn.cursor()
    c.execute("SELECT streak, last_check FROM no_smoke WHERE user_id=?", (user_id,))
    data = c.fetchone()

    if not data:
        c.execute("INSERT INTO no_smoke (user_id, start_date, last_check, streak) VALUES (?,?,?,?)",
                  (user_id, today, today, 1))
        bot.send_message(user_id, "Дней без курения: 1\nПродолжай в том же духе.", reply_markup=main_menu())
    else:
        last = datetime.strptime(data[1], "%Y-%m-%d").date()
        if last == today:
            bot.send_message(user_id, "Ты уже отмечалась сегодня.", reply_markup=main_menu())
        else:
            c.execute("UPDATE no_smoke SET last_check=?, streak=streak+1 WHERE user_id=?",
                      (today, user_id))
            c.execute("SELECT streak FROM no_smoke WHERE user_id=?", (user_id,))
            new_streak = c.fetchone()[0]
            bot.send_message(user_id, f"Дней без курения: {new_streak}\nТак держать.", reply_markup=main_menu())
    conn.commit()
    conn.close()

# --- ДНЕВНИК ---
def save_diary(message):
    user_id = message.chat.id

    if message.text == "Отмена":
        bot.send_message(user_id, "Возвращаюсь в главное меню.", reply_markup=main_menu())
        return

    if message.photo:
        file_info = bot.get_file(message.photo[-1].file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        if not os.path.exists('photos'):
            os.makedirs('photos')
        photo_name = f"photos/{user_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}.jpg"
        with open(photo_name, 'wb') as new_file:
            new_file.write(downloaded_file)
        caption = message.caption if message.caption else "..."
        conn = sqlite3.connect('my_life.db')
        c = conn.cursor()
        c.execute("INSERT INTO diary (user_id, date, text, photo_path) VALUES (?,?,?,?)",
                  (user_id, date.today(), caption, photo_name))
        conn.commit()
        conn.close()
        bot.send_message(user_id, "Запись с фото сохранена.", reply_markup=main_menu())
    elif message.text:
        conn = sqlite3.connect('my_life.db')
        c = conn.cursor()
        c.execute("INSERT INTO diary (user_id, date, text) VALUES (?,?,?)",
                  (user_id, date.today(), message.text))
        conn.commit()
        conn.close()
        bot.send_message(user_id, "Запись сохранена.", reply_markup=main_menu())

# --- БЛАГОДАРНОСТЬ ---
def save_gratitude(message):
    user_id = message.chat.id

    if message.text == "Отмена":
        bot.send_message(user_id, "Возвращаюсь в главное меню.", reply_markup=main_menu())
        return

    conn = sqlite3.connect('my_life.db')
    c = conn.cursor()
    c.execute("INSERT INTO gratitude (user_id, date, text) VALUES (?,?,?)",
              (user_id, date.today(), message.text))
    conn.commit()
    conn.close()
    bot.send_message(user_id, "Благодарность записана.", reply_markup=main_menu())

# --- ПОЛЕЗНОЕ ---
def show_useful_menu(message):
    user_id = message.chat.id
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    markup.add(
        types.KeyboardButton("Посмотреть всё полезное"),
        types.KeyboardButton("Добавить полезное"),
        types.KeyboardButton("Удалить полезное"),
        types.KeyboardButton("Назад в меню")
    )
    bot.send_message(user_id, "Раздел Полезное:", reply_markup=markup)

@bot.message_handler(func=lambda msg: msg.text == "Назад в меню")
def back_to_menu(message):
    bot.send_message(message.chat.id, "Главное меню:", reply_markup=main_menu())

@bot.message_handler(func=lambda msg: msg.text == "Посмотреть всё полезное")
def show_all_useful(message):
    user_id = message.chat.id
    conn = sqlite3.connect('my_life.db')
    c = conn.cursor()
    c.execute("SELECT id, title, content FROM useful WHERE user_id=? ORDER BY id", (user_id,))
    items = c.fetchall()
    conn.close()

    if not items:
        bot.send_message(user_id, "Пока ничего нет. Добавь через кнопку «Добавить полезное».", 
                         reply_markup=show_useful_menu_reply())
    else:
        text = "Полезное:\n\n"
        for item in items:
            text += f"  {item[1]}\n    {item[2]}\n\n"
        text += "Для удаления нажми кнопку «Удалить полезное»"
        bot.send_message(user_id, text, reply_markup=show_useful_menu_reply())

@bot.message_handler(func=lambda msg: msg.text == "Добавить полезное")
def add_useful_start(message):
    bot.send_message(message.chat.id, "Отправь данные в формате:\nНазвание: содержимое\n\nНапример:\nWiFi: пароль123\nИнтернет ЛК: логин / пароль",
                     reply_markup=get_cancel_keyboard())
    bot.register_next_step_handler(message, save_useful)

def save_useful(message):
    user_id = message.chat.id

    if message.text == "Отмена":
        bot.send_message(user_id, "Возвращаюсь в раздел Полезное.", reply_markup=show_useful_menu_reply())
        return

    try:
        parts = message.text.split(':', 1)
        title = parts[0].strip()
        content = parts[1].strip()
        conn = sqlite3.connect('my_life.db')
        c = conn.cursor()
        c.execute("INSERT INTO useful (user_id, title, content) VALUES (?,?,?)",
                  (user_id, title, content))
        conn.commit()
        conn.close()
        bot.send_message(user_id, f"Сохранено: {title}", reply_markup=show_useful_menu_reply())
    except:
        bot.send_message(user_id, "Неверный формат. Попробуй ещё раз:\nНазвание: содержимое",
                         reply_markup=show_useful_menu_reply())
        bot.register_next_step_handler(message, save_useful)

@bot.message_handler(func=lambda msg: msg.text == "Удалить полезное")
def delete_useful_start(message):
    user_id = message.chat.id
    conn = sqlite3.connect('my_life.db')
    c = conn.cursor()
    c.execute("SELECT id, title FROM useful WHERE user_id=? ORDER BY id", (user_id,))
    items = c.fetchall()
    conn.close()

    if not items:
        bot.send_message(user_id, "Удалять нечего.", reply_markup=show_useful_menu_reply())
        return

    text = "Что удалить? Отправь номер:\n\n"
    for item in items:
        text += f"  /del-{item[0]} — {item[1]}\n"

    bot.send_message(user_id, text, reply_markup=get_cancel_keyboard())
    bot.register_next_step_handler(message, delete_useful)

def delete_useful(message):
    user_id = message.chat.id

    if message.text == "Отмена":
        bot.send_message(user_id, "Возвращаюсь в раздел Полезное.", reply_markup=show_useful_menu_reply())
        return

    if message.text and message.text.startswith('/del-'):
        item_id = message.text.split('-')[1]
        conn = sqlite3.connect('my_life.db')
        c = conn.cursor()
        c.execute("DELETE FROM useful WHERE id=? AND user_id=?", (item_id, user_id))
        conn.commit()
        conn.close()
        bot.send_message(user_id, "Удалено.", reply_markup=show_useful_menu_reply())
    else:
        bot.send_message(user_id, "Отправь команду /del-номер", reply_markup=show_useful_menu_reply())

def show_useful_menu_reply():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    markup.add(
        types.KeyboardButton("Посмотреть всё полезное"),
        types.KeyboardButton("Добавить полезное"),
        types.KeyboardButton("Удалить полезное"),
        types.KeyboardButton("Назад в меню")
    )
    return markup

# --- ОТЧЁТ ---
def generate_report(message):
    user_id = message.chat.id
    month_str = date.today().strftime("%Y-%m")
    conn = sqlite3.connect('my_life.db')
    c = conn.cursor()

    c.execute("SELECT count(*) FROM tasks WHERE user_id=? AND completed=1", (user_id,))
    done = c.fetchone()[0]
    c.execute("SELECT count(*) FROM tasks WHERE user_id=?", (user_id,))
    total = c.fetchone()[0]

    c.execute("SELECT SUM(amount) FROM payments WHERE user_id=? AND month=? AND completed=1",
              (user_id, month_str))
    sum_paid = c.fetchone()[0] or 0.0
    c.execute("SELECT SUM(amount) FROM payments WHERE user_id=? AND month=?",
              (user_id, month_str))
    total_sum = c.fetchone()[0] or 0.0
    c.execute("SELECT SUM(amount) FROM payments WHERE user_id=? AND month=? AND completed=0",
              (user_id, month_str))
    unpaid_sum = c.fetchone()[0] or 0.0

    c.execute("SELECT streak FROM no_smoke WHERE user_id=?", (user_id,))
    streak = c.fetchone()
    streak_days = streak[0] if streak else 0

    c.execute("SELECT count(*) FROM diary WHERE user_id=? AND strftime('%Y-%m', date)=?", (user_id, month_str))
    diary_count = c.fetchone()[0]
    c.execute("SELECT count(*) FROM gratitude WHERE user_id=? AND strftime('%Y-%m', date)=?", (user_id, month_str))
    grat_count = c.fetchone()[0]

    conn.close()

    report_text = f"Отчёт за {month_str}\n\n"
    report_text += f"  Задачи: {done} из {total} выполнено\n"
    report_text += f"  Платежи: оплачено {sum_paid} руб. из {total_sum} руб.\n"
    report_text += f"  Осталось оплатить: {unpaid_sum} руб.\n"
    report_text += f"  Дней без курения: {streak_days}\n"
    report_text += f"  Записей в дневнике: {diary_count}\n"
    report_text += f"  Благодарностей: {grat_count}"

    bot.send_message(user_id, report_text, reply_markup=main_menu())

# --- ЗАПУСК ---
if __name__ == '__main__':
    print("Бот запущен...")
    bot.polling(none_stop=True)
