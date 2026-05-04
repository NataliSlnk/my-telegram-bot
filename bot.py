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
    {"name": "Моб.связь", "amount": 0},
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
    btn1 = types.KeyboardButton("• Задачи на день")
    btn2 = types.KeyboardButton("• Задачи на неделю")
    btn3 = types.KeyboardButton("• Платежи")
    btn4 = types.KeyboardButton("• Не курю")
    btn5 = types.KeyboardButton("• Дневник")
    btn6 = types.KeyboardButton("• Благодарность")
    btn7 = types.KeyboardButton("• Отчёт")
    markup.add(btn1, btn2, btn3, btn4, btn5, btn6, btn7)
    return markup

def get_cancel_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("• Отмена"))
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

    if message.text == "• Отмена":
        bot.send_message(user_id, "Возвращаюсь в главное меню.", reply_markup=main_menu())
        return

    if message.text == "• Задачи на день":
        show_tasks(message, 'day')
    elif message.text == "• Задачи на неделю":
        show_tasks(message, 'week')
    elif message.text == "• Платежи":
        ensure_monthly_payments(user_id)
        show_payments(message)
    elif message.text == "• Не курю":
        check_smoke(message)
    elif message.text == "• Дневник":
        bot.send_message(user_id, "Напиши, как прошёл день, или пришли фото (подпись к фото сохранится как текст).",
                         reply_markup=get_cancel_keyboard())
        bot.register_next_step_handler(message, save_diary)
    elif message.text == "• Благодарность":
        bot.send_message(user_id, "Напиши, за что ты сегодня благодарна:",
                         reply_markup=get_cancel_keyboard())
        bot.register_next_step_handler(message, save_gratitude)
    elif message.text == "• Отчёт":
        generate_report(message)
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

    text = f"• Задачи на {type_name.lower()}:\n\n"
    for task in tasks:
        text += f"  [ ] {task[1]}  /done_{task[0]}\n"
    text += "\nНапиши текст, чтобы добавить задачу.\n/done_номер — отметить выполненной."

    bot.send_message(user_id, text, reply_markup=get_cancel_keyboard())
    bot.register_next_step_handler(message, add_task, task_type)

def add_task(message, task_type):
    user_id = message.chat.id

    if message.text == "• Отмена":
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
    bot.send_message(user_id, f"+ Добавлено: {task_text}", reply_markup=main_menu())

@bot.message_handler(func=lambda msg: msg.text and msg.text.startswith('/done_'))
def complete_task(message):
    user_id = message.chat.id
    task_id = message.text.split('_')[1]
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

    # Основные платежи
    c.execute("SELECT id, name, amount, completed FROM payments WHERE user_id=? AND month=? AND is_extra=0 ORDER BY id",
              (user_id, month_str))
    plan = c.fetchall()

    # Дополнительные платежи
    c.execute("SELECT id, name, amount, completed FROM payments WHERE user_id=? AND month=? AND is_extra=1 ORDER BY id",
              (user_id, month_str))
    extra = c.fetchall()
    conn.close()

    text = f"• Платежи ({month_str}):\n\n"

    if plan:
        text += "  Основные:\n"
        for p in plan:
            status = "[x]" if p[3] else "[ ]"
            amount_str = f" — {p[2]} руб." if p[2] > 0 else ""
            text += f"    {status} {p[1]}{amount_str}  /pay_{p[0]}\n"

    if extra:
        text += "\n  Дополнительные:\n"
        for p in extra:
            status = "[x]" if p[3] else "[ ]"
            text += f"    {status} {p[1]} — {p[2]} руб.  /pay_{p[0]}\n"

    if not plan and not extra:
        text += "  Платежей пока нет.\n"

    text += "\n  + доп. платёж: Название, Сумма"
    text += "\n  /pay_номер — отметить оплаченным"

    bot.send_message(user_id, text, reply_markup=get_cancel_keyboard())
    bot.register_next_step_handler(message, add_payment)

def add_payment(message):
    user_id = message.chat.id

    if message.text == "• Отмена":
        bot.send_message(user_id, "Возвращаюсь в главное меню.", reply_markup=main_menu())
        return

    if message.text and message.text.startswith('/'):
        return

    if message.text.strip() == "+":
        bot.send_message(user_id, "Напиши: Название, Сумма\nНапример: Ремонт авто, 3500",
                         reply_markup=get_cancel_keyboard())
        bot.register_next_step_handler(message, add_extra_payment)
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
        bot.send_message(user_id, f"+ Добавлен платёж: {name}, {amount} руб.", reply_markup=main_menu())
    except:
        bot.send_message(user_id, "Неверный формат.\nПопробуй так: Название, Сумма\nНапример: Интернет, 500",
                         reply_markup=get_cancel_keyboard())
        bot.register_next_step_handler(message, add_extra_payment)

def add_extra_payment(message):
    add_payment(message)

@bot.message_handler(func=lambda msg: msg.text and msg.text.startswith('/pay_'))
def complete_payment(message):
    user_id = message.chat.id
    pay_id = message.text.split('_')[1]
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
        bot.send_message(user_id, "• Дней без курения: 1\nПродолжай в том же духе.", reply_markup=main_menu())
    else:
        last = datetime.strptime(data[1], "%Y-%m-%d").date()
        if last == today:
            bot.send_message(user_id, "Ты уже отмечалась сегодня.", reply_markup=main_menu())
        else:
            c.execute("UPDATE no_smoke SET last_check=?, streak=streak+1 WHERE user_id=?",
                      (today, user_id))
            c.execute("SELECT streak FROM no_smoke WHERE user_id=?", (user_id,))
            new_streak = c.fetchone()[0]
            bot.send_message(user_id, f"• Дней без курения: {new_streak}\nТак держать.", reply_markup=main_menu())
    conn.commit()
    conn.close()

# --- ДНЕВНИК ---
def save_diary(message):
    user_id = message.chat.id

    if message.text == "• Отмена":
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
        bot.send_message(user_id, "+ Запись с фото сохранена.", reply_markup=main_menu())
    elif message.text:
        conn = sqlite3.connect('my_life.db')
        c = conn.cursor()
        c.execute("INSERT INTO diary (user_id, date, text) VALUES (?,?,?)",
                  (user_id, date.today(), message.text))
        conn.commit()
        conn.close()
        bot.send_message(user_id, "+ Запись сохранена.", reply_markup=main_menu())

# --- БЛАГОДАРНОСТЬ ---
def save_gratitude(message):
    user_id = message.chat.id

    if message.text == "• Отмена":
        bot.send_message(user_id, "Возвращаюсь в главное меню.", reply_markup=main_menu())
        return

    conn = sqlite3.connect('my_life.db')
    c = conn.cursor()
    c.execute("INSERT INTO gratitude (user_id, date, text) VALUES (?,?,?)",
              (user_id, date.today(), message.text))
    conn.commit()
    conn.close()
    bot.send_message(user_id, "+ Благодарность записана.", reply_markup=main_menu())

# --- ОТЧЁТ ---
def generate_report(message):
    user_id = message.chat.id
    month_str = date.today().strftime("%Y-%m")
    conn = sqlite3.connect('my_life.db')
    c = conn.cursor()

    # Задачи
    c.execute("SELECT count(*) FROM tasks WHERE user_id=? AND completed=1", (user_id,))
    done = c.fetchone()[0]
    c.execute("SELECT count(*) FROM tasks WHERE user_id=?", (user_id,))
    total = c.fetchone()[0]

    # Платежи
    c.execute("SELECT SUM(amount) FROM payments WHERE user_id=? AND month=? AND completed=1",
              (user_id, month_str))
    sum_paid = c.fetchone()[0] or 0.0
    c.execute("SELECT count(*) FROM payments WHERE user_id=? AND month=?", (user_id, month_str))
    total_pay = c.fetchone()[0]
    c.execute("SELECT SUM(amount) FROM payments WHERE user_id=? AND month=?",
              (user_id, month_str))
    total_sum = c.fetchone()[0] or 0.0
    c.execute("SELECT SUM(amount) FROM payments WHERE user_id=? AND month=? AND completed=0",
              (user_id, month_str))
    unpaid_sum = c.fetchone()[0] or 0.0

    # Не курю
    c.execute("SELECT streak FROM no_smoke WHERE user_id=?", (user_id,))
    streak = c.fetchone()
    streak_days = streak[0] if streak else 0

    # Дневник / Благодарности
    c.execute("SELECT count(*) FROM diary WHERE user_id=? AND strftime('%Y-%m', date)=?", (user_id, month_str))
    diary_count = c.fetchone()[0]
    c.execute("SELECT count(*) FROM gratitude WHERE user_id=? AND strftime('%Y-%m', date)=?", (user_id, month_str))
    grat_count = c.fetchone()[0]

    conn.close()

    report_text = f"• Отчёт за {month_str}\n\n"
    report_text += f"  Задачи: {done} из {total} выполнено\n"
    report_text += f"  Платежи: оплачено {sum_paid} руб. из {total_sum} руб.\n"
    report_text += f"    (оплачено {total_pay - (total_pay - sum_paid)} из {total_pay} шт.)\n"
    report_text += f"    Осталось оплатить: {unpaid_sum} руб.\n"
    report_text += f"  Дней без курения: {streak_days}\n"
    report_text += f"  Записей в дневнике: {diary_count}\n"
    report_text += f"  Благодарностей: {grat_count}"

    bot.send_message(user_id, report_text, reply_markup=main_menu())

# --- ЗАПУСК ---
if __name__ == '__main__':
    print("Бот запущен...")
    bot.polling(none_stop=True)
