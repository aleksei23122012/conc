import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler
from supabase import create_client, Client

# Включаем логирование
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Получаем ключи доступа из переменных окружения (более безопасно) ---
try:
    BOT_TOKEN = os.environ['BOT_TOKEN']
    SUPABASE_URL = os.environ['SUPABASE_URL']
    SUPABASE_KEY = os.environ['SUPABASE_KEY']
except KeyError:
    logger.error("Ключи не найдены! Добавьте BOT_TOKEN, SUPABASE_URL, SUPABASE_KEY в переменные окружения.")
    exit()

# --- Инициализируем клиент Supabase ---
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- URL для Web Apps (из вашего кода) ---
URL_KNOWLEDGE_BASE = "https://aleksei23122012.teamly.ru/space/00647e86-cd4b-46ef-9903-0af63964ad43/article/17e16e2a-92ff-463c-8bf4-eaaf202c0bc7"
URL_DASHBOARD = "https://aleksei23122012.github.io/DMdashbordbot/conc/conc.html"
URL_ALMANAC = "https://aleksei23122012.github.io/DMdashbordbot/ov/ov.html"
URL_OTZIV = "https://forms.gle/KML4YXA4osd6aaWS7"

# --- НОВЫЙ ФУНКЦИОНАЛ: АВТОРИЗАЦИЯ ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обработчик команды /start. Начинает процесс верификации пользователя.
    """
    user = update.effective_user
    logger.info(f"Пользователь {user.username} (ID: {user.id}) нажал /start.")

    # 1. Сохраняем информацию о пользователе в таблицу 'users'
    try:
        supabase.table('users').insert({
            'telegram_id': user.id,
            'telegram_username': user.username
        }).execute()
        logger.info(f"Пользователь {user.username} добавлен/обновлен в таблице 'users'.")
    except Exception as e:
        logger.error(f"Ошибка при добавлении пользователя в 'users': {e}")
        # Не останавливаем процесс, даже если запись не удалась (например, из-за дубликата)

    # 2. Ищем пользователя в таблице 'persinfo' по его telegram_username
    try:
        response = supabase.table('persinfo').select('full_name, city, team').eq('telegram_username', user.username).execute()
        
        if not response.data:
            # Если пользователь не найден в таблице persinfo
            await update.message.reply_text(
                "Здравствуйте! Я не смог найти вас в базе сотрудников. "
                "Пожалуйста, убедитесь, что ваш логин в Telegram указан верно, и обратитесь к администратору @Aleksei_Li_Radievich"
            )
            return

        # 3. Если найден, формируем сообщение с подтверждением
        employee_data = response.data[0]
        full_name = employee_data.get('full_name', 'Имя не найдено')
        city = employee_data.get('city', 'Город не найден')
        team = employee_data.get('team', 'Команда не найдена')
        
        # Сохраняем данные в контекст для последующего использования
        context.user_data['employee_info'] = employee_data

        text = f"Здравствуйте, {full_name}! Вы из города {city}, Команда {team}, верно?"
        
        keyboard = [
            [
                InlineKeyboardButton("Да, всё верно", callback_data="auth_yes"),
                InlineKeyboardButton("Нет, не верно", callback_data="auth_no"),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(text, reply_markup=reply_markup)

    except Exception as e:
        logger.error(f"Ошибка при поиске пользователя в 'persinfo': {e}")
        await update.message.reply_text("Произошла внутренняя ошибка. Пожалуйста, попробуйте позже или свяжитесь с администратором.")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обрабатывает нажатия на inline-кнопки.
    """
    query = update.callback_query
    await query.answer() # Обязательно, чтобы убрать "часики" с кнопки

    if query.data == "auth_yes":
        # Если пользователь подтвердил свои данные, отправляем приветственное сообщение
        await query.edit_message_text(text="Отлично! Рад знакомству.")
        await send_welcome_and_menu(update, context)
    
    elif query.data == "auth_no":
        # Если пользователь не подтвердил данные
        await query.edit_message_text(text="Хм, странно. Пожалуйста, напишите администратору @Aleksei_Li_Radievich")

async def send_welcome_and_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Отправляет приветственное сообщение и основное меню.
    Это ваш старый обработчик /start.
    """
    # Используем update.effective_chat.id, так как после кнопки update.message будет None
    chat_id = update.effective_chat.id
    
    welcome_text = (
        "Привет! 👋\n\nЯ - твой персональный консьерж🤵. Чтобы открыть меню с основными функциями, нажми на кнопку 🪄 Меню или отправь в чат команду /menu\n\n"
        "✨Чтобы получить шаблон для отправки отчета введи \n"
        "/breakfast , /lunch или /dinner 🥨\n\n"
        "✨Я буду передавать для тебя важные сообщения, так что не забудь включить уведомления 🔔\n\n"
        "✨Также я помогу тебе просматривать свои показатели, буду давать тебе советы, помогу с отработкой возражений 📒\n\n"
        "✨А если ты захочешь предоставить обратную связь - я обязательно передам ее администратору ✍️\n\n"
        "Хорошего дня!☀️"
    )
    await context.bot.send_message(chat_id=chat_id, text=welcome_text)
    # Можно сразу же отправить и меню
    await menu(update, context)


# --- ВАШИ СТАРЫЕ ФУНКЦИИ (остаются без изменений) ---

async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    keyboard = [
        [InlineKeyboardButton("Дашборд", web_app={"url": URL_DASHBOARD})],
        [InlineKeyboardButton("Отработка возражений", web_app={"url": URL_ALMANAC})],
        [InlineKeyboardButton("База знаний", web_app={"url": URL_KNOWLEDGE_BASE})],
        [InlineKeyboardButton("Отзывы и предложения", web_app={"url": URL_OTZIV})]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.effective_chat.send_message( # Используем effective_chat для универсальности
        "Консьерж на связи. 🤵\n\nВыбирай, что хочешь узнать или сделать:\n\n"
        "✨ Дашборд — вся важная информация у тебя под рукой.\n"
        "✨ Отработка возражений — лайфхаки и рекомендации.\n"
        "✨ База знаний — полезные статьи и советы.\n"
        "✨ Отзывы и предложения — поделись обратной связью!\n"
        "✨ Команды для отчетов: /breakfast /lunch /dinner\n",
        reply_markup=reply_markup
    )

# ... (здесь ваши функции breakfast, lunch, dinner, admin - я их убрал для краткости, просто скопируйте их из вашего старого кода) ...
async def breakfast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отправляет шаблон для завтрака."""
    breakfast_text = (
        "Не забудь скорректировать данные на свои!\n\n\n"
        "ПЛАН 26.06.2025\n\n"
        "ЛИДЫ: 6\n"
        "ТРАФИК: 03:00:00\n"
        "КЗ: 300\n\n"
        "<b>#ИмяФамилия</b>\n"
        "#Алексей\n"
        "#СПБ\n"
        "#СТ\n"
        "@Aleksei_Li_Radievich\n"
        "@Логин тимлида в ТГ (если есть)"
    )
    await update.message.reply_text(breakfast_text, parse_mode='HTML')

async def lunch(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отправляет шаблон для обеда."""
    lunch_text = (
        "Не забудь скорректировать данные на свои!\n\n\n"
        "ПРЕДВАРИТЕЛЬНЫЙ ОТЧЁТ 26.06.2025\n\n"
        "Лиды: 10\n"
        "Трафик: 01:54:39\n"
        "КЗ: 172\n\n"
        "#<b>ИмяФамилия</b>\n"
        "#Алексей\n"
        "@Aleksei_Li_Radievich\n"
        "@Логин тимлида в ТГ (если есть)"
    )
    await update.message.reply_text(lunch_text, parse_mode='HTML')

async def dinner(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отправляет шаблон для ужина."""
    dinner_text = (
        "Не забудь скорректировать данные на свои!\n\n\n"
        "ОТЧЁТ 26.06.2025\n\n"
        "Лиды: 22\n"
        "Трафик: 03:47:56\n"
        "КЗ: 288\n\n"
        "Время прихода: 8:30\n"
        "Время ухода: 18:00\n\n"
        "<b>#ИмяФамилия</b>\n"
        "#Алексей\n"
        "#отчетОТМ\n"
        "@Aleksei_Li_Radievich\n"
        "@Логин тимлида в ТГ (если есть)"
    )
    await update.message.reply_text(dinner_text, parse_mode='HTML')

async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отправляет подсказку по командам."""
    admin_hint_text = (
        "<b>⚙️ Подсказка по командам</b>\n\n"
        "• /start - приветствие\n"
        "• /menu - основное меню с кнопками\n"
        "• /breakfast - шаблон утреннего отчета\n"
        "• /lunch - шаблон дневного отчета\n"
        "• /dinner - шаблон вечернего отчета\n"
    )
    await update.message.reply_text(admin_hint_text, parse_mode='HTML')


def main() -> None:
    """Основная функция для запуска бота."""
    application = Application.builder().token(BOT_TOKEN).build()

    # --- РЕГИСТРАЦИЯ ОБРАБОТЧИКОВ ---
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_callback)) # Новый обработчик кнопок
    application.add_handler(CommandHandler("menu", menu))
    application.add_handler(CommandHandler("breakfast", breakfast))
    application.add_handler(CommandHandler("lunch", lunch))
    application.add_handler(CommandHandler("dinner", dinner))
    application.add_handler(CommandHandler("admin", admin))
    
    print("Бот успешно запущен...")
    application.run_polling()

if __name__ == "__main__":
    main()
