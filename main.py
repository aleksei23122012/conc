import os
import logging
import time
from functools import wraps
from datetime import datetime # ДОБАВЛЕНО: для работы с датой
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler
from supabase import create_client, Client

# --- БЛОК 1: ИНИЦИАЛИЗАЦИЯ И КОНФИГУРАЦИЯ ---
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

try:
    BOT_TOKEN = os.environ['BOT_TOKEN']
    SUPABASE_URL = os.environ['SUPABASE_URL']
    SUPABASE_KEY = os.environ['SUPABASE_KEY']
except KeyError:
    logger.error("КРИТИЧЕСКАЯ ОШИБКА: Ключи доступа не найдены! Укажите их в переменных окружения.")
    exit()

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- БЛОК 2: КОНФИГУРАЦИЯ НАЗВАНИЙ КОЛОНОК В SUPABASE ---
USERS_TABLE_TG_ID_COLUMN = 'tg_id'
USERS_TABLE_TG_USERNAME_COLUMN = 'tg'

# Таблица persinfo
PERSINFO_TABLE_TG_USERNAME_COLUMN = 'tg'
PERSINFO_TABLE_FULL_NAME_COLUMN = 'operator'
PERSINFO_TABLE_CITY_COLUMN = 'city'
PERSINFO_TABLE_TEAM_COLUMN = 'team'
PERSINFO_TABLE_DOLG_COLUMN = 'dolg'
PERSINFO_TABLE_PLAN_LID_COLUMN = 'plan_lid' # Новая колонка
PERSINFO_TABLE_RGTM_COLUMN = 'tg_rgtm' # Новая колонка
PERSINFO_TABLE_TEAMLEAD_COLUMN = 'tg_teamlid' # Новая колонка

# Таблица TMday
TMDAY_TABLE_TG_USERNAME_COLUMN = 'tg'
TMDAY_TABLE_LID_COLUMN = 'lid'
TMDAY_TABLE_TRAFIC_COLUMN = 'trafic'
TMDAY_TABLE_KZ_COLUMN = 'kz'


# --- БЛОК 3: URL ДЛЯ WEB APPS И ССЫЛОК ---
URL_KNOWLEDGE_BASE = "https://aleksei23122012.teamly.ru/space/00647e86-cd4b-46ef-9903-0af63964ad43/article/17e16e2a-92ff-463c-8bf4-eaaf202c0bc7"
URL_DASHBOARD = "https://aleksei23122012.github.io/DMdashbordbot/conc/conc.html"
URL_ALMANAC = "https://aleksei23122012.github.io/DMdashbordbot/ov/ov.html"
URL_OTZIV = "https://forms.gle/KML4YXA4osd6aaWS7"
URL_GAMIFICATION = "https://marketing-house-appp.vercel.app/" # Новая ссылка

# --- БЛОК 4: ДЕКОРАТОР ДЛЯ ПРОВЕРКИ АДМИНА ---
def admin_only(func):
    @wraps(func)
    async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user = update.effective_user
        if not user or not user.username:
            await update.message.reply_text("Для использования админ-команд у вас должен быть установлен логин (username) в Telegram.")
            return
        try:
            response = supabase.table('persinfo').select(PERSINFO_TABLE_DOLG_COLUMN).eq(PERSINFO_TABLE_TG_USERNAME_COLUMN, user.username).single().execute()
            if response.data and response.data.get(PERSINFO_TABLE_DOLG_COLUMN) == "Админ":
                return await func(update, context, *args, **kwargs)
            else:
                await update.message.reply_text("У вас нет прав для выполнения этой команды.")
                return
        except Exception as e:
            logger.error(f"Ошибка при проверке прав администратора для {user.username}: {e}")
            await update.message.reply_text("Произошла ошибка при проверке прав доступа.")
            return
    return wrapped

# --- БЛОК 5: ОСНОВНЫЕ ФУНКЦИИ ДЛЯ ПОЛЬЗОВАТЕЛЕЙ ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not user.username:
        await update.message.reply_text("Для авторизации в системе, пожалуйста, установите себе логин (username) в настройках Telegram.")
        return
    logger.info(f"Пользователь {user.username} (ID: {user.id}) нажал /start.")
    try:
        supabase.table('users').insert({USERS_TABLE_TG_ID_COLUMN: user.id, USERS_TABLE_TG_USERNAME_COLUMN: user.username}).execute()
    except Exception:
        pass
    try:
        select_query = f"{PERSINFO_TABLE_FULL_NAME_COLUMN}, {PERSINFO_TABLE_CITY_COLUMN}, {PERSINFO_TABLE_TEAM_COLUMN}, {PERSINFO_TABLE_DOLG_COLUMN}"
        response = supabase.table('persinfo').select(select_query).eq(PERSINFO_TABLE_TG_USERNAME_COLUMN, user.username).single().execute()
        if not response.data:
            await update.message.reply_text("Здравствуйте! Я не смог найти вас в базе сотрудников. Обратитесь к администратору.")
            return
        full_name = response.data.get(PERSINFO_TABLE_FULL_NAME_COLUMN, 'N/A')
        city = response.data.get(PERSINFO_TABLE_CITY_COLUMN, 'N/A')
        team = response.data.get(PERSINFO_TABLE_TEAM_COLUMN, 'N/A')
        dolg = response.data.get(PERSINFO_TABLE_DOLG_COLUMN, 'N/A')
        # ИЗМЕНЕНО: Формат приветствия
        text = f"Здравствуйте, {full_name}! ✋\nВы {dolg} из {team}, из города {city}, верно?"
        keyboard = [[InlineKeyboardButton("Да, всё верно", callback_data="auth_yes"), InlineKeyboardButton("Нет, не верно", callback_data="auth_no")]]
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    except Exception as e:
        logger.error(f"Ошибка при поиске пользователя в 'persinfo': {e}")
        await update.message.reply_text("Произошла внутренняя ошибка.")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    if query.data == "auth_yes":
        await query.edit_message_text(text="Авторизация прошла успешно. Загружаю меню...")
        await send_welcome_message_with_menu(update, context)
    elif query.data == "auth_no":
        # ИЗМЕНЕНО: Текст при неверных данных
        await query.edit_message_text(text="Не удивительно, я еще обучаюсь. Пожалуйста, напишите администратору @mikiooshi")

async def send_welcome_message_with_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    chat_id = update.effective_chat.id

    # ИЗМЕНЕНО: Кнопки теперь включают обычную ссылку и новую кнопку
    keyboard = [
        [InlineKeyboardButton("Дашборд", web_app=WebAppInfo(url=URL_DASHBOARD))],
        [InlineKeyboardButton("Отработка возражений", web_app=WebAppInfo(url=URL_ALMANAC))],
        [InlineKeyboardButton("База знаний", url=URL_KNOWLEDGE_BASE)], # <-- WebApp убран, теперь это обычная ссылка
        [InlineKeyboardButton("Геймификация", url=URL_GAMIFICATION)], # <-- Новая кнопка-ссылка
        [InlineKeyboardButton("Отзывы и предложения", web_app=WebAppInfo(url=URL_OTZIV))]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_text = (
        "Твой персональный Консьерж на связи. 🤵\n\n"
        "Выбирай, что хочешь узнать или сделать:\n\n"
        "✨ Дашборд — вся важная информация у тебя под рукой 📊\n"
        "✨ Отработка возражений — шаблоны и рекомендации ⛔️\n"
        "✨ База знаний — полезные статьи и советы 📒\n"
        "✨ Отзывы и предложения — поделись обратной связью ✍️\n"
        "✨ Команды для отчетов: /breakfast /lunch /dinner 🥨\n"
        "✨ Не забудь включить уведомления для сообщений 🔔"
    )
    
    # ИЗМЕНЕНО: Проверяем, является ли пользователь админом, чтобы добавить доп. строку
    try:
        response = supabase.table('persinfo').select(PERSINFO_TABLE_DOLG_COLUMN).eq(PERSINFO_TABLE_TG_USERNAME_COLUMN, user.username).single().execute()
        if response.data and response.data.get(PERSINFO_TABLE_DOLG_COLUMN) == "Админ":
            welcome_text += "\n✨ Памятка по админским командам здесь /admin 🎮"
    except Exception as e:
        logger.warning(f"Не удалось проверить роль для пользователя {user.username}: {e}")

    await context.bot.send_message(chat_id=chat_id, text=welcome_text, reply_markup=reply_markup)

async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await send_welcome_message_with_menu(update, context)

# --- БЛОК 5.1: ОБНОВЛЕННЫЕ ФУНКЦИИ ОТЧЕТОВ ---
async def breakfast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not user.username:
        await update.message.reply_text("Не могу найти ваш username, пожалуйста, установите его в настройках Telegram.")
        return
    try:
        # Получаем данные из persinfo
        select_query = f"{PERSINFO_TABLE_FULL_NAME_COLUMN}, {PERSINFO_TABLE_TEAM_COLUMN}, {PERSINFO_TABLE_RGTM_COLUMN}, {PERSINFO_TABLE_TEAMLEAD_COLUMN}, {PERSINFO_TABLE_PLAN_LID_COLUMN}"
        persinfo_response = supabase.table('persinfo').select(select_query).eq(PERSINFO_TABLE_TG_USERNAME_COLUMN, user.username).single().execute()
        
        if not persinfo_response.data:
            await update.message.reply_text("Не удалось найти ваши данные в базе сотрудников.")
            return

        data = persinfo_response.data
        current_date = datetime.now().strftime("%d.%m.%Y")
        plan_lid = data.get(PERSINFO_TABLE_PLAN_LID_COLUMN, 0)
        operator_name = data.get(PERSINFO_TABLE_FULL_NAME_COLUMN, "ИмяФамилия")
        hashtag_name = operator_name.replace(" ", "")
        team = data.get(PERSINFO_TABLE_TEAM_COLUMN, "Команда")
        rgtm = data.get(PERSINFO_TABLE_RGTM_COLUMN, "логин_ргтм")
        teamlid = data.get(PERSINFO_TABLE_TEAMLEAD_COLUMN, "логин_тимлида")
        
        # Собираем шаблон
        breakfast_text = (
            "Не забудь скорректировать данные на свои!\n\n\n"
            f"ПЛАН {current_date}\n\n"
            f"Лиды: {plan_lid}\n"
            "Трафик: 03:00:00\n" # Эти данные статичны по вашему ТЗ
            "КЗ: 300\n\n"
            f"<b>#{hashtag_name}</b>\n"
            f"#{team}\n"
            f"@{rgtm}\n"
            f"@{teamlid}"
        )
        await update.message.reply_text(breakfast_text, parse_mode='HTML')
    except Exception as e:
        logger.error(f"Ошибка в /breakfast для {user.username}: {e}")
        await update.message.reply_text("Произошла ошибка при формировании отчета.")

async def lunch(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not user.username:
        await update.message.reply_text("Не могу найти ваш username.")
        return
    try:
        # Сначала получаем данные из persinfo
        persinfo_select = f"{PERSINFO_TABLE_FULL_NAME_COLUMN}, {PERSINFO_TABLE_TEAM_COLUMN}, {PERSINFO_TABLE_RGTM_COLUMN}, {PERSINFO_TABLE_TEAMLEAD_COLUMN}"
        persinfo_response = supabase.table('persinfo').select(persinfo_select).eq(PERSINFO_TABLE_TG_USERNAME_COLUMN, user.username).single().execute()
        
        # Затем данные из TMday
        tmday_select = f"{TMDAY_TABLE_LID_COLUMN}, {TMDAY_TABLE_TRAFIC_COLUMN}, {TMDAY_TABLE_KZ_COLUMN}"
        tmday_response = supabase.table('TMday').select(tmday_select).eq(TMDAY_TABLE_TG_USERNAME_COLUMN, user.username).single().execute()

        if not persinfo_response.data or not tmday_response.data:
            await update.message.reply_text("Не удалось найти все необходимые данные для отчета.")
            return

        p_data = persinfo_response.data
        t_data = tmday_response.data
        current_date = datetime.now().strftime("%d.%m.%Y")
        
        lid = t_data.get(TMDAY_TABLE_LID_COLUMN, 0)
        trafic = t_data.get(TMDAY_TABLE_TRAFIC_COLUMN, "00:00:00")
        kz = t_data.get(TMDAY_TABLE_KZ_COLUMN, 0)
        operator_name = p_data.get(PERSINFO_TABLE_FULL_NAME_COLUMN, "ИмяФамилия")
        hashtag_name = operator_name.replace(" ", "")
        team = p_data.get(PERSINFO_TABLE_TEAM_COLUMN, "Команда")
        rgtm = p_data.get(PERSINFO_TABLE_RGTM_COLUMN, "логин_ргтм")
        teamlid = p_data.get(PERSINFO_TABLE_TEAMLEAD_COLUMN, "логин_тимлида")
        
        lunch_text = (
            f"ПРЕДВАРИТЕЛЬНЫЙ ОТЧЁТ {current_date}\n\n"
            f"Лиды: {lid}\n"
            f"Трафик: {trafic}\n"
            f"КЗ: {kz}\n\n"
            f"<b>#{hashtag_name}</b>\n"
            f"#{team}\n"
            f"@{rgtm}\n"
            f"@{teamlid}"
        )
        await update.message.reply_text(lunch_text, parse_mode='HTML')
    except Exception as e:
        logger.error(f"Ошибка в /lunch для {user.username}: {e}")
        await update.message.reply_text("Произошла ошибка при формировании отчета.")

async def dinner(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not user.username:
        await update.message.reply_text("Не могу найти ваш username.")
        return
    try:
        persinfo_select = f"{PERSINFO_TABLE_FULL_NAME_COLUMN}, {PERSINFO_TABLE_TEAM_COLUMN}, {PERSINFO_TABLE_RGTM_COLUMN}, {PERSINFO_TABLE_TEAMLEAD_COLUMN}"
        persinfo_response = supabase.table('persinfo').select(persinfo_select).eq(PERSINFO_TABLE_TG_USERNAME_COLUMN, user.username).single().execute()
        
        tmday_select = f"{TMDAY_TABLE_LID_COLUMN}, {TMDAY_TABLE_TRAFIC_COLUMN}, {TMDAY_TABLE_KZ_COLUMN}"
        tmday_response = supabase.table('TMday').select(tmday_select).eq(TMDAY_TABLE_TG_USERNAME_COLUMN, user.username).single().execute()

        if not persinfo_response.data or not tmday_response.data:
            await update.message.reply_text("Не удалось найти все необходимые данные для отчета.")
            return

        p_data = persinfo_response.data
        t_data = tmday_response.data
        current_date = datetime.now().strftime("%d.%m.%Y")
        
        lid = t_data.get(TMDAY_TABLE_LID_COLUMN, 0)
        trafic = t_data.get(TMDAY_TABLE_TRAFIC_COLUMN, "00:00:00")
        kz = t_data.get(TMDAY_TABLE_KZ_COLUMN, 0)
        operator_name = p_data.get(PERSINFO_TABLE_FULL_NAME_COLUMN, "ИмяФамилия")
        hashtag_name = operator_name.replace(" ", "")
        team = p_data.get(PERSINFO_TABLE_TEAM_COLUMN, "Команда")
        rgtm = p_data.get(PERSINFO_TABLE_RGTM_COLUMN, "логин_ргтм")
        teamlid = p_data.get(PERSINFO_TABLE_TEAMLEAD_COLUMN, "логин_тимлида")
        
        dinner_text = (
            f"ИТОГОВЫЙ ОТЧЁТ {current_date}\n\n"
            f"Лиды: {lid}\n"
            f"Трафик: {trafic}\n"
            f"КЗ: {kz}\n\n"
            "Время прихода: 08:30\n"
            "Время ухода: 18:00\n\n"
            f"<b>#{hashtag_name}</b>\n"
            f"#{team}\n"
            f"@{rgtm}\n"
            f"@{teamlid}"
        )
        await update.message.reply_text(dinner_text, parse_mode='HTML')
    except Exception as e:
        logger.error(f"Ошибка в /dinner для {user.username}: {e}")
        await update.message.reply_text("Произошла ошибка при формировании отчета.")


# --- БЛОК 6: АДМИНИСТРАТОРСКИЕ ФУНКЦИИ (без изменений) ---
# ... (все функции от admin_help до broadcast_dolg остаются такими же, как в прошлой версии) ...


# --- БЛОК 7: ОСНОВНАЯ ФУНКЦИЯ ЗАПУСКА И РЕГИСТРАЦИЯ КОМАНД (без изменений) ---
def main() -> None:
    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(CommandHandler("menu", menu))
    application.add_handler(CommandHandler("breakfast", breakfast))
    application.add_handler(CommandHandler("lunch", lunch))
    application.add_handler(CommandHandler("dinner", dinner))
    
    application.add_handler(CommandHandler("admin", admin_help))
    application.add_handler(CommandHandler("stats", stats))
    application.add_handler(CommandHandler("broadcast", broadcast))
    application.add_handler(CommandHandler("broadcast_team", broadcast_team))
    application.add_handler(CommandHandler("broadcast_city", broadcast_city))
    application.add_handler(CommandHandler("broadcast_dolg", broadcast_dolg))

    print("Бот успешно запущен...")
    application.run_polling()

if __name__ == "__main__":
    main()
