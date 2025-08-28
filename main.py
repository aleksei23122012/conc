import os
import logging
import time
from functools import wraps
from datetime import datetime
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
PERSINFO_TABLE_TG_USERNAME_COLUMN = 'tg'
PERSINFO_TABLE_FULL_NAME_COLUMN = 'operator'
PERSINFO_TABLE_CITY_COLUMN = 'city'
PERSINFO_TABLE_TEAM_COLUMN = 'team'
PERSINFO_TABLE_DOLG_COLUMN = 'dolg'
PERSINFO_TABLE_PLAN_LID_COLUMN = 'plan_lid'
PERSINFO_TABLE_RGTM_COLUMN = 'tg_rgtm'
PERSINFO_TABLE_TEAMLEAD_COLUMN = 'tg_teamlid'
PERSINFO_TABLE_URL_COLUMN = 'url' # <-- НОВАЯ КОЛОНКА

TMDAY_TABLE_TG_USERNAME_COLUMN = 'tg'
TMDAY_TABLE_LID_COLUMN = 'lid'
TMDAY_TABLE_TRAFIC_COLUMN = 'trafic'
TMDAY_TABLE_KZ_COLUMN = 'kz'

TMMONTH_TABLE_TG_USERNAME_COLUMN = 'tg'
TMMONTH_TABLE_COS_COLUMN = 'cos'
TMMONTH_TABLE_MOLNII_COLUMN = 'molnii'

# --- БЛОК 3: URL ДЛЯ WEB APPS И ССЫЛОК ---
URL_KNOWLEDGE_BASE = "https://aleksei23122012.teamly.ru/space/00647e86-cd4b-46ef-9903-0af63964ad43/article/17e16e2a-92ff-463c-8bf4-eaaf202c0bc7"
URL_DASHBOARD = "https://aleksei23122012.github.io/DMdashbordbot/conc/conc.html"
URL_ALMANAC = "https://aleksei23122012.github.io/DMdashbordbot/ov/ov.html"
URL_YUMMY_FORM = "https://forms.gle/KML4YXA4osd6aaWS7"
URL_GAMIFICATION = "https://marketing-house-appp.vercel.app/"

# --- БЛОК 4: ДЕКОРАТОР ДЛЯ ПРОВЕРКИ АДМИНА ---
def admin_only(func):
    @wraps(func)
    async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user = update.effective_user
        if not user or not user.username:
            await update.message.reply_text("Для использования админ-команд у вас должен быть установлен логин (username) в Telegram.")
            return
        try:
            response = supabase.table('persinfo').select(PERSINFO_TABLE_DOLG_COLUMN).eq(PERSINFO_TABLE_TG_USERNAME_COLUMN, user.username).execute()
            if response.data and response.data[0].get(PERSINFO_TABLE_DOLG_COLUMN) == "Админ":
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
        response = supabase.table('persinfo').select(f"{PERSINFO_TABLE_FULL_NAME_COLUMN}, {PERSINFO_TABLE_CITY_COLUMN}, {PERSINFO_TABLE_TEAM_COLUMN}, {PERSINFO_TABLE_DOLG_COLUMN}").eq(PERSINFO_TABLE_TG_USERNAME_COLUMN, user.username).execute()
        if not response.data:
            await update.message.reply_text("Здравствуйте! Я не смог найти вас в базе сотрудников. Обратитесь к администратору.")
            return
        data = response.data[0]
        full_name = data.get(PERSINFO_TABLE_FULL_NAME_COLUMN, 'N/A')
        city = data.get(PERSINFO_TABLE_CITY_COLUMN, 'N/A')
        team = data.get(PERSINFO_TABLE_TEAM_COLUMN, 'N/A')
        dolg = data.get(PERSINFO_TABLE_DOLG_COLUMN, 'N/A')
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
        await query.edit_message_text(text="Не удивительно, я еще обучаюсь. Пожалуйста, напишите администратору @mikiooshi")

async def send_welcome_message_with_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    chat_id = update.effective_chat.id
    keyboard_layout = []
    
    try:
        response = supabase.table('persinfo').select(PERSINFO_TABLE_URL_COLUMN).eq(PERSINFO_TABLE_TG_USERNAME_COLUMN, user.username).execute()
        if response.data:
            crm_url = response.data[0].get(PERSINFO_TABLE_URL_COLUMN)
            if crm_url:
                keyboard_layout.append([InlineKeyboardButton("CRM", url=crm_url)])
    except Exception as e:
        logger.error(f"Не удалось сформировать кнопку CRM для {user.username}: {e}")
        
    keyboard_layout.extend([
        [InlineKeyboardButton("Дашборд", web_app=WebAppInfo(url=URL_DASHBOARD))],
        [InlineKeyboardButton("Отработка возражений", web_app=WebAppInfo(url=URL_ALMANAC))],
        [InlineKeyboardButton("База знаний", url=URL_KNOWLEDGE_BASE)],
        [InlineKeyboardButton("Геймификация", web_app=WebAppInfo(url=URL_GAMIFICATION))]
    ])
    reply_markup = InlineKeyboardMarkup(keyboard_layout)
    
    welcome_text = (
        "Твой персональный Консьерж на связи. 🤵\n\n"
        "Выбирай, что хочешь узнать или сделать:\n\n"
        "✨ CRM - ссылка на CRM вашей команды 💼\n"
        "✨ Дашборд — вся важная информация у тебя под рукой 📊\n"
        "✨ Отработка возражений — шаблоны и рекомендации ⛔️\n"
        "✨ База знаний — полезные статьи и советы 📒\n"
        "✨ Узнать свои КОСы и молнии: /cos ⚖️\n"
        "✨ Отзывы и предложения: /yummy ✍️\n"
        "✨ Команды для отчетов: /breakfast /lunch /dinner 🥨\n"
        "✨ Не забудь включить уведомления для сообщений 🔔"
    )
    try:
        response = supabase.table('persinfo').select(PERSINFO_TABLE_DOLG_COLUMN).eq(PERSINFO_TABLE_TG_USERNAME_COLUMN, user.username).execute()
        if response.data and response.data[0].get(PERSINFO_TABLE_DOLG_COLUMN) == "Админ":
            welcome_text += "\n✨ Памятка по админским командам здесь /admin 🎮"
    except Exception as e:
        logger.warning(f"Не удалось проверить роль для пользователя {user.username}: {e}")
    await context.bot.send_message(chat_id=chat_id, text=welcome_text, reply_markup=reply_markup)

async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await send_welcome_message_with_menu(update, context)

async def breakfast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not user.username:
        await update.message.reply_text("Не могу найти ваш username, пожалуйста, установите его в настройках Telegram.")
        return
    try:
        response = supabase.table('persinfo').select(f"{PERSINFO_TABLE_FULL_NAME_COLUMN}, {PERSINFO_TABLE_TEAM_COLUMN}, {PERSINFO_TABLE_RGTM_COLUMN}, {PERSINFO_TABLE_TEAMLEAD_COLUMN}, {PERSINFO_TABLE_PLAN_LID_COLUMN}").eq(PERSINFO_TABLE_TG_USERNAME_COLUMN, user.username).execute()
        if not response.data:
            await update.message.reply_text("Не удалось найти ваши данные в базе сотрудников.")
            return
        data = response.data[0]
        current_date = datetime.now().strftime("%d.%m.%Y")
        plan_lid = data.get(PERSINFO_TABLE_PLAN_LID_COLUMN, 0)
        operator_name = data.get(PERSINFO_TABLE_FULL_NAME_COLUMN, "ИмяФамилия")
        hashtag_name = operator_name.replace(" ", "")
        team = data.get(PERSINFO_TABLE_TEAM_COLUMN, "Команда")
        rgtm = data.get(PERSINFO_TABLE_RGTM_COLUMN, "логин_ргтм")
        teamlid = data.get(PERSINFO_TABLE_TEAMLEAD_COLUMN, "логин_тимлида")
        breakfast_text = (
            f"ПЛАН {current_date}\n\n"
            f"Лиды: {plan_lid}\n"
            "Трафик: 03:00:00\n"
            "КЗ: 300\n\n"
            f"#{hashtag_name}\n"
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
        persinfo_response = supabase.table('persinfo').select(f"{PERSINFO_TABLE_FULL_NAME_COLUMN}, {PERSINFO_TABLE_TEAM_COLUMN}, {PERSINFO_TABLE_RGTM_COLUMN}, {PERSINFO_TABLE_TEAMLEAD_COLUMN}").eq(PERSINFO_TABLE_TG_USERNAME_COLUMN, user.username).execute()
        tmday_response = supabase.table('TMday').select(f"{TMDAY_TABLE_LID_COLUMN}, {TMDAY_TABLE_TRAFIC_COLUMN}, {TMDAY_TABLE_KZ_COLUMN}").eq(TMDAY_TABLE_TG_USERNAME_COLUMN, user.username).execute()
        if not persinfo_response.data or not tmday_response.data:
            await update.message.reply_text("Не удалось найти все необходимые данные для отчета.")
            return
        p_data = persinfo_response.data[0]
        t_data = tmday_response.data[0]
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
            f"#{hashtag_name}\n"
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
        persinfo_response = supabase.table('persinfo').select(f"{PERSINFO_TABLE_FULL_NAME_COLUMN}, {PERSINFO_TABLE_TEAM_COLUMN}, {PERSINFO_TABLE_RGTM_COLUMN}, {PERSINFO_TABLE_TEAMLEAD_COLUMN}").eq(PERSINFO_TABLE_TG_USERNAME_COLUMN, user.username).execute()
        tmday_response = supabase.table('TMday').select(f"{TMDAY_TABLE_LID_COLUMN}, {TMDAY_TABLE_TRAFIC_COLUMN}, {TMDAY_TABLE_KZ_COLUMN}").eq(TMDAY_TABLE_TG_USERNAME_COLUMN, user.username).execute()
        if not persinfo_response.data or not tmday_response.data:
            await update.message.reply_text("Не удалось найти все необходимые данные для отчета.")
            return
        p_data = persinfo_response.data[0]
        t_data = tmday_response.data[0]
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
            f"#{hashtag_name}\n"
            f"#{team}\n"
            f"@{rgtm}\n"
            f"@{teamlid}"
        )
        await update.message.reply_text(dinner_text, parse_mode='HTML')
    except Exception as e:
        logger.error(f"Ошибка в /dinner для {user.username}: {e}")
        await update.message.reply_text("Произошла ошибка при формировании отчета.")

async def yummy(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = f'Вы можете передать пожелания шеф-повару по <a href="{URL_YUMMY_FORM}">ссылке</a> 📋'
    await update.message.reply_text(text, parse_mode='HTML')

async def cos(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not user.username:
        await update.message.reply_text("Не могу найти ваш username.")
        return
    try:
        response = supabase.table('TMmonth').select(f"{TMMONTH_TABLE_COS_COLUMN}, {TMMONTH_TABLE_MOLNII_COLUMN}").eq(TMMONTH_TABLE_TG_USERNAME_COLUMN, user.username).execute()
        if not response.data:
            await update.message.reply_text("К сожалению, не нашел ваших данных по КОСам и молниям за этот месяц.")
            return
        data = response.data[0]
        cos_count = data.get(TMMONTH_TABLE_COS_COLUMN, 0)
        molnii_count = data.get(TMMONTH_TABLE_MOLNII_COLUMN, 0)
        text = f"У вас {cos_count} косов 👎 и {molnii_count} молний ⚡️"
        await update.message.reply_text(text)
    except Exception as e:
        logger.error(f"Ошибка в /cos для {user.username}: {e}")
        await update.message.reply_text("Произошла ошибка при получении данных.")

# --- БЛОК 6: АДМИНИСТРАТОРСКИЕ ФУНКЦИИ ---
@admin_only
async def admin_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    admin_text = (
        "Команды администратора:\n"
        "/stats - количество людей в БД\n"
        "/broadcast <текст> - отправить сообщение всем в БД\n"
        "/broadcast_team <команда> <текст> - отправить сообщение всей указанной команде\n"
        "/broadcast_city <город> <текст> - отправить сообщение всем в указанном городе\n"
        "/broadcast_dolg <должность> <текст> - отправить сообщение всем указанной должности"
    )
    await update.message.reply_text(admin_text)

@admin_only
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        response = supabase.table('users').select('*', count='exact').execute()
        await update.message.reply_text(f"📊 Всего пользователей в базе данных: {response.count}")
    except Exception as e:
        await update.message.reply_text(f"Ошибка при получении статистики: {e}")

async def _do_broadcast(target_ids, message_text, update, context):
    sent_count = 0
    for user_id in target_ids:
        try:
            await context.bot.send_message(chat_id=user_id, text=message_text)
            sent_count += 1
            time.sleep(0.1)
        except Exception as e:
            logger.error(f"Не удалось отправить сообщение пользователю {user_id}: {e}")
    return sent_count

@admin_only
async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message_text = " ".join(context.args)
    if not message_text:
        await update.message.reply_text("Использование: /broadcast <текст для всех>")
        return
    try:
        response = supabase.table('users').select(USERS_TABLE_TG_ID_COLUMN).execute()
        user_ids = [user[USERS_TABLE_TG_ID_COLUMN] for user in response.data]
        await update.message.reply_text(f"Начинаю рассылку для {len(user_ids)} пользователей...")
        sent_count = await _do_broadcast(user_ids, message_text, update, context)
        await update.message.reply_text(f"✅ Рассылка завершена. Отправлено: {sent_count}/{len(user_ids)}")
    except Exception as e:
        await update.message.reply_text(f"Ошибка при рассылке: {e}")

async def _get_users_by_filter(filter_column, filter_value):
    persinfo_resp = supabase.table('persinfo').select(PERSINFO_TABLE_TG_USERNAME_COLUMN).eq(filter_column, filter_value).execute()
    usernames = [user[PERSINFO_TABLE_TG_USERNAME_COLUMN] for user in persinfo_resp.data]
    if not usernames:
        return None
    users_resp = supabase.table('users').select(USERS_TABLE_TG_ID_COLUMN).in_(USERS_TABLE_TG_USERNAME_COLUMN, usernames).execute()
    return [user[USERS_TABLE_TG_ID_COLUMN] for user in users_resp.data]

@admin_only
async def broadcast_team(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if len(context.args) < 2:
        await update.message.reply_text("Использование: /broadcast_team <Команда> <текст>")
        return
    team_name, message_text = context.args[0], " ".join(context.args[1:])
    try:
        user_ids = await _get_users_by_filter(PERSINFO_TABLE_TEAM_COLUMN, team_name)
        if user_ids is None:
            await update.message.reply_text(f"Не найдено сотрудников в команде '{team_name}'.")
            return
        await update.message.reply_text(f"Начинаю рассылку для команды '{team_name}' ({len(user_ids)} пользователей)...")
        sent_count = await _do_broadcast(user_ids, message_text, update, context)
        await update.message.reply_text(f"✅ Рассылка для команды '{team_name}' завершена. Отправлено: {sent_count}/{len(user_ids)}")
    except Exception as e:
        await update.message.reply_text(f"Ошибка при рассылке по команде: {e}")

@admin_only
async def broadcast_city(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if len(context.args) < 2:
        await update.message.reply_text("Использование: /broadcast_city <Город> <текст>")
        return
    city_name, message_text = context.args[0], " ".join(context.args[1:])
    try:
        user_ids = await _get_users_by_filter(PERSINFO_TABLE_CITY_COLUMN, city_name)
        if user_ids is None:
            await update.message.reply_text(f"Не найдено сотрудников из города '{city_name}'.")
            return
        await update.message.reply_text(f"Начинаю рассылку для города '{city_name}' ({len(user_ids)} пользователей)...")
        sent_count = await _do_broadcast(user_ids, message_text, update, context)
        await update.message.reply_text(f"✅ Рассылка для города '{city_name}' завершена. Отправлено: {sent_count}/{len(user_ids)}")
    except Exception as e:
        await update.message.reply_text(f"Ошибка при рассылке по городу: {e}")

@admin_only
async def broadcast_dolg(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if len(context.args) < 2:
        await update.message.reply_text("Использование: /broadcast_dolg <Должность> <текст>")
        return
    dolg_name, message_text = context.args[0], " ".join(context.args[1:])
    try:
        user_ids = await _get_users_by_filter(PERSINFO_TABLE_DOLG_COLUMN, dolg_name)
        if user_ids is None:
            await update.message.reply_text(f"Не найдено сотрудников с должностью '{dolg_name}'.")
            return
        await update.message.reply_text(f"Начинаю рассылку для должности '{dolg_name}' ({len(user_ids)} пользователей)...")
        sent_count = await _do_broadcast(user_ids, message_text, update, context)
        await update.message.reply_text(f"✅ Рассылка для должности '{dolg_name}' завершена. Отправлено: {sent_count}/{len(user_ids)}")
    except Exception as e:
        await update.message.reply_text(f"Ошибка при рассылке по должности: {e}")

# --- БЛОК 7: ОСНОВНАЯ ФУНКЦИЯ ЗАПУСКА И РЕГИСТРАЦИЯ КОМАНД ---
def main() -> None:
    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(CommandHandler("menu", menu))
    application.add_handler(CommandHandler("breakfast", breakfast))
    application.add_handler(CommandHandler("lunch", lunch))
    application.add_handler(CommandHandler("dinner", dinner))
    application.add_handler(CommandHandler("yummy", yummy))
    application.add_handler(CommandHandler("cos", cos))
    
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
