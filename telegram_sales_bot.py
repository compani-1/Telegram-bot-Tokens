from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext
from advanced_bot import advanced_bot, dialog_state, DatabaseManager
import logging
import json
import os

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def create_adaptive_keyboard():
    """Создает адаптивную клавиатуру на основе состояния диалога"""
    current_state = dialog_state.current_state
    context = dialog_state.context
    
    # Базовые кнопки, которые всегда доступны
    base_buttons = [
        [KeyboardButton("🎫 Мой билет"), KeyboardButton("🎁 Акции")],
        [KeyboardButton("🎯 Сценарии"), KeyboardButton("🛒 Корзина")],
        [KeyboardButton("ℹ️ Помощь")]
    ]

    # Основные состояния диалога
    if current_state in ["start", "mood_known"]:
        keyboard = [
            [KeyboardButton("🚂 Начать бронирование")],
            [KeyboardButton("📍 Выбрать направление"), KeyboardButton("📅 Выбрать дату")],
            *base_buttons,
            [KeyboardButton("📊 Статистика")]
        ]
    
    elif current_state in ["interested_in_travel", "select_destination"]:
        keyboard = [
            [KeyboardButton("Москва 🏙️"), KeyboardButton("Санкт-Петербург 🏛️"), KeyboardButton("Сочи 🌴")],
            [KeyboardButton("🔙 Назад"), KeyboardButton("ℹ️ Помощь")]
        ]
    
    elif current_state in ["destination_selected", "select_date"]:
        destination = context.get('destination', '')
        keyboard = [
            [KeyboardButton("На завтра 📅"), KeyboardButton("На выходные 🗓️")],
            [KeyboardButton(f"📍 {destination}"), KeyboardButton("🔙 Назад")],
            [KeyboardButton("ℹ️ Помощь")]
        ]
    
    elif current_state == "ready_for_booking":
        destination = context.get('destination', 'Направление')
        date_text = context.get('date_text', 'Дата')
        keyboard = [
            [KeyboardButton("✅ Да, бронировать"), KeyboardButton("❌ Нет, изменить")],
            [KeyboardButton(f"📍 {destination}"), KeyboardButton(f"📅 {date_text}")],
            [KeyboardButton("🔙 Назад"), KeyboardButton("ℹ️ Помощь")]
        ]
    
    elif current_state == "booking_confirmed" and not context.get('promo_shown'):
        keyboard = [
            [KeyboardButton("1️⃣"), KeyboardButton("2️⃣"), KeyboardButton("3️⃣")],
            [KeyboardButton("4️⃣"), KeyboardButton("5️⃣"), KeyboardButton("6️⃣")],
            [KeyboardButton("🎫 Мой билет"), KeyboardButton("🚫 Завершить")],
            [KeyboardButton("ℹ️ Помощь")]
        ]
    
    elif current_state in ["showing_promotions", "showing_promo_details"] or context.get('awaiting_promo_selection'):
        keyboard = [
            [KeyboardButton("1️⃣"), KeyboardButton("2️⃣"), KeyboardButton("3️⃣")],
            [KeyboardButton("4️⃣"), KeyboardButton("5️⃣"), KeyboardButton("6️⃣")],
            [KeyboardButton("🔄 Другие"), KeyboardButton("🚫 Завершить")],
            [KeyboardButton("✅ Оформить"), KeyboardButton("🎫 Мой билет")]
        ]
    
    elif context.get('awaiting_scenario_selection'):
        keyboard = [
            [KeyboardButton("1"), KeyboardButton("2"), KeyboardButton("3")],
            [KeyboardButton("4"), KeyboardButton("5")],
            [KeyboardButton("🔙 Назад"), KeyboardButton("ℹ️ Помощь")]
        ]
    
    elif context.get('booking_confirmed'):
        keyboard = [
            [KeyboardButton("🎫 Мой билет"), KeyboardButton("🎁 Акции")],
            [KeyboardButton("🚂 Новое бронирование"), KeyboardButton("📊 Статистика")],
            [KeyboardButton("🎯 Сценарии"), KeyboardButton("🛒 Корзина")],
            [KeyboardButton("ℹ️ Помощь")]
        ]
    
    else:
        # Стандартная клавиатура по умолчанию
        keyboard = [
            [KeyboardButton("🚂 Начать бронирование")],
            [KeyboardButton("📍 Выбрать направление"), KeyboardButton("📅 Выбрать дату")],
            *base_buttons,
            [KeyboardButton("📊 Статистика")]
        ]
    
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def process_user_input(text):
    """Обрабатывает пользовательский ввод и преобразует кнопки в текст"""
    button_mappings = {
        # Направления
        "Москва 🏙️": "Москва",
        "Санкт-Петербург 🏛️": "Санкт-Петербург",
        "Сочи 🌴": "Сочи",
        
        # Даты
        "На завтра 📅": "завтра",
        "На выходные 🗓️": "выходные",
        
        # Подтверждения
        "✅ Да, бронировать": "да",
        "❌ Нет, изменить": "нет",
        
        # Акции
        "1️⃣": "1", "2️⃣": "2", "3️⃣": "3", "4️⃣": "4", "5️⃣": "5", "6️⃣": "6",
        
        # Действия
        "✅ Оформить": "оформить",
        "🔄 Другие": "другие",
        "🚫 Завершить": "завершить",
        "🎫 Мой билет": "мой билет",
        "🎁 Акции": "акции",
        "🎯 Сценарии": "сценарии",
        "🛒 Корзина": "корзина",
        "🚂 Начать бронирование": "начать бронирование",
        "📍 Выбрать направление": "выбрать направление",
        "📅 Выбрать дату": "выбрать дату",
        "📊 Статистика": "статистика",
        "🔙 Назад": "назад",
        "ℹ️ Помощь": "помощь",
        "🚂 Новое бронирование": "новое бронирование"
    }
    
    return button_mappings.get(text, text)

def handle_quick_access(text):
    """Обрабатывает быстрый доступ к функциям"""
    # Обработка новых кнопок
    if text == "🎯 Сценарии":
        return advanced_bot("сценарии")
    
    elif text == "🛒 Корзина":
        return advanced_bot("корзина")
    
    elif text == "📍 Выбрать направление":
        dialog_state.current_state = "select_destination"
        return "📍 **ВЫБЕРИТЕ НАПРАВЛЕНИЕ**\n\nКуда хотите поехать?"
    
    elif text == "📅 Выбрать дату":
        if dialog_state.context.get('destination'):
            dialog_state.current_state = "select_date"
            return "📅 **ВЫБЕРИТЕ ДАТУ**\n\nКогда планируете поездку?"
        else:
            dialog_state.current_state = "select_destination"
            return "📅 Сначала выберите направление!\n\n📍 **ВЫБЕРИТЕ НАПРАВЛЕНИЕ:**"
    
    elif text == "🚂 Начать бронирование":
        dialog_state.current_state = "start"
        return advanced_bot("начать бронирование")
    
    elif text == "🎫 Мой билет":
        return advanced_bot("мой билет")
    
    elif text == "🎁 Акции":
        return advanced_bot("акции")
    
    elif text == "📊 Статистика":
        return advanced_bot("статистика")
    
    elif text == "🔙 Назад":
        dialog_state.current_state = "start"
        return "🔄 Возвращаемся в главное меню!\n\nЧем могу помочь?"
    
    elif text == "🚂 Новое бронирование":
        dialog_state.reset()
        return "🔄 Начинаем новое бронирование!\n\nКак ваше настроение сегодня? 🚂"
    
    return None

async def start(update: Update, context: CallbackContext) -> None:
    """Обработчик команды /start"""
    user = update.effective_user
    
    # Сбрасываем состояние диалога
    dialog_state.reset()
    
    welcome_text = (
        f"👋 Привет, {user.first_name}!\n\n"
        "🚂 Я - ваш персональный помощник по путешествиям!\n\n"
        "Я помогу вам:\n"
        "• 🎫 Забронировать билеты на поезда\n"
        "• 🏨 Найти отели\n"
        "• 🛡️ Оформить страховку\n"
        "• 🍽️ Подобрать питание\n"
        "• 🚗 Организовать трансфер\n"
        "• 🎭 Найти развлечения\n\n"
        "💡 **Быстрый доступ:**\n"
        "• 📍 Выбрать направление - сразу к выбору города\n"
        "• 📅 Выбрать дату - сразу к выбору даты\n"
        "• 🚂 Начать бронирование - полный процесс\n"
        "• 🎯 Сценарии - готовые пакеты путешествий\n"
        "• 🛒 Корзина - ваши выбранные товары\n\n"
        "Выберите действие ниже или просто напишите мне!"
    )
    
    await update.message.reply_text(
        welcome_text,
        reply_markup=create_adaptive_keyboard(),
        parse_mode='Markdown'
    )

async def help_command(update: Update, context: CallbackContext) -> None:
    """Обработчик команды /help"""
    help_text = (
        "🤖 **Помощь по боту**\n\n"
        "**Основные команды:**\n"
        "• /start - начать работу\n"
        "• /help - эта справка\n"
        "• /reset - сбросить диалог\n\n"
        "**Быстрые действия:**\n"
        "• 🚂 Начать бронирование - полный процесс бронирования\n"
        "• 📍 Выбрать направление - быстрый выбор города\n"
        "• 📅 Выбрать дату - быстрый выбор даты\n"
        "• 🎫 Мой билет - посмотреть билет\n"
        "• 🎁 Акции - текущие предложения\n"
        "• 🎯 Сценарии - готовые пакеты путешествий\n"
        "• 🛒 Корзина - ваши выбранные товары\n"
        "• 📊 Статистика - ваша активность\n\n"
        "**Доступные направления:**\n"
        "• Москва 🏙️\n"
        "• Санкт-Петербург 🏛️\n"
        "• Сочи 🌴\n\n"
        "**Сценарии путешествий:**\n"
        "1. Семейный отдых 👨‍👩‍👧‍👦\n"
        "2. Деловая поездка 💼\n"
        "3. Романтическое путешествие 💑\n"
        "4. Экономный вариант 💰\n"
        "5. Премиум пакет ⭐\n\n"
        "💡 **Совет:** Используйте кнопки для быстрой навигации!"
    )
    await update.message.reply_text(
        help_text, 
        parse_mode='Markdown',
        reply_markup=create_adaptive_keyboard()
    )

async def reset_command(update: Update, context: CallbackContext) -> None:
    """Обработчик команды /reset"""
    dialog_state.reset()
    response = "🔄 Диалог сброшен. Давайте начнем сначала! Как ваше настроение сегодня? 🚂"
    await update.message.reply_text(
        response,
        reply_markup=create_adaptive_keyboard()
    )

async def stats_command(update: Update, context: CallbackContext) -> None:
    """Обработчик команды /stats"""
    user = update.effective_user
    
    history_count = len(dialog_state.conversation_history)
    current_state = dialog_state.current_state
    booking_confirmed = dialog_state.context.get('booking_confirmed', False)
    selected_products = len(dialog_state.context.get('selected_products', []))
    current_scenario = dialog_state.context.get('current_scenario')
    
    stats_text = (
        f"📊 **Статистика пользователя**\n\n"
        f"👤 Имя: {user.first_name}\n"
        f"🆔 ID: {user.id}\n"
        f"💬 Сообщений в диалоге: {history_count}\n"
        f"🎯 Текущее состояние: {current_state}\n"
        f"✅ Бронирование: {'Подтверждено' if booking_confirmed else 'Не подтверждено'}\n"
        f"🛒 Товаров в корзине: {selected_products}\n"
    )
    
    if current_scenario:
        scenario = dialog_state.BOT_CONFIG['scenarios'].get(current_scenario, {})
        stats_text += f"🎯 Активный сценарий: {scenario.get('name', 'Неизвестно')}\n"
    
    stats_text += f"📅 Время: {dialog_state.datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
    stats_text += "💡 *Статистика обновляется в реальном времени*"
    
    await update.message.reply_text(
        stats_text, 
        parse_mode='Markdown',
        reply_markup=create_adaptive_keyboard()
    )

async def handle_message(update: Update, context: CallbackContext) -> None:
    """Обработчик текстовых сообщений"""
    text = update.message.text
    user = update.effective_user

    logger.info(f"Пользователь {user.id} ({user.first_name}): {text}")

    try:
        # Обработка навигационных кнопок
        if text == "🔙 Назад":
            await start(update, context)
            return
        elif text == "ℹ️ Помощь":
            await help_command(update, context)
            return
        elif text == "📊 Статистика":
            await stats_command(update, context)
            return

        # Обработка быстрого доступа
        quick_response = handle_quick_access(text)
        if quick_response is not None:
            await update.message.reply_text(
                quick_response,
                reply_markup=create_adaptive_keyboard(),
                parse_mode='Markdown'
            )
            return

        # Обработка основного диалога
        processed_input = process_user_input(text)
        
        # Получаем данные пользователя для сохранения в БД
        user_data = {
            'user_id': user.id,
            'username': user.username,
            'first_name': user.first_name,
            'last_name': user.last_name
        }
        
        response = advanced_bot(processed_input, user.id, user_data)
        
        # Всегда отправляем ответ с адаптивной клавиатурой
        await update.message.reply_text(
            response,
            reply_markup=create_adaptive_keyboard(),
            parse_mode='Markdown'
        )

    except Exception as e:
        logger.error(f"Ошибка обработки сообщения: {e}")
        await update.message.reply_text(
            "❌ Произошла ошибка. Попробуйте еще раз.",
            reply_markup=create_adaptive_keyboard()
        )

async def error_handler(update: Update, context: CallbackContext) -> None:
    """Обработчик ошибок"""
    logger.error(f"Ошибка: {context.error}", exc_info=context.error)
    
    try:
        if update and update.effective_message:
            await update.effective_message.reply_text(
                "❌ Произошла ошибка. Используйте /start для перезапуска.",
                reply_markup=create_adaptive_keyboard()
            )
    except Exception as e:
        logger.error(f"Ошибка в обработчике ошибок: {e}")

def main():
    """Запуск бота"""
    try:
        TOKEN = "8243899616:AAGRDASeRKMAfioV-rMU4r9TZK33Pu1HXwA"  # Замените на ваш токен
        
        application = Application.builder().token(TOKEN).build()

        # Обработчики команд
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("reset", reset_command))
        application.add_handler(CommandHandler("stats", stats_command))

        # Обработчики сообщений
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

        # Обработчик ошибок
        application.add_error_handler(error_handler)

        print("=" * 50)
        print("🚀 Бот с адаптивным меню запущен!")
        print("💡 Клавиатура автоматически подстраивается под диалог")
        print("🎯 Доступные направления: Москва, Санкт-Петербург, Сочи")
        print("🛍️ 12 товаров/услуг для бронирования")
        print("🎪 5 сценариев путешествий")
        print("💾 База данных активирована")
        print("🧠 AIML интегрирован")
        print("=" * 50)
        
        application.run_polling(drop_pending_updates=True)
        
    except Exception as e:
        logger.error(f"Ошибка запуска бота: {e}")
        print(f"❌ Ошибка: {e}")

if __name__ == '__main__':
    main()