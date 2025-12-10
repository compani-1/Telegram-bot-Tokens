"""
Telegram Travel Bot - Версия с полным циклом подтверждения заказа
"""

import telebot
import logging
from telebot import types
from config import TELEGRAM_TOKEN, BOT_CONFIG, LOG_FILE, LOG_LEVEL
from advanced_bot import TravelBot, DatabaseManager
from datetime import datetime
import random

# Настройка логирования
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Инициализация бота
bot = telebot.TeleBot(TELEGRAM_TOKEN)

# Инициализация логики бота
travel_bot = TravelBot()


class DialogueManager:
    """Менеджер диалогов для оформления заказа"""
    
    @staticmethod
    def get_random_phrase(phrase_type):
        """Получить случайную фразу из конфигурации"""
        if 'checkout_dialogue' in BOT_CONFIG and phrase_type in BOT_CONFIG['checkout_dialogue']:
            phrases = BOT_CONFIG['checkout_dialogue'][phrase_type]
            if phrases:
                return random.choice(phrases)
        return ""
    
    @staticmethod
    def get_scenario_dialogue(scenario_id):
        """Получить диалог для сценария"""
        if scenario_id in BOT_CONFIG['scenarios']:
            scenario_data = BOT_CONFIG['scenarios'][scenario_id]
            if 'dialogue' in scenario_data:
                dialogues = scenario_data['dialogue']
                if dialogues:
                    return random.choice(dialogues)
            return scenario_data.get('description', '')
        return ""
    
    @staticmethod
    def get_order_confirmed_message(state, ticket_number):
        """Получить сообщение о подтвержденном заказе"""
        cart_summary = state.get_cart_summary()
        
        # Основное сообщение
        message = "🎉 **БРОНИРОВАНИЕ ПОДТВЕРЖДЕНО!** 🎫\n\n"
        message += "✅ Ваш заказ успешно оформлен!\n\n"
        
        # Детали заказа
        message += "📋 **ДЕТАЛИ ЗАКАЗА:**\n"
        message += f"• Номер билета: `{ticket_number}`\n"
        
        if state.context.get('destination'):
            message += f"• Направление: {state.context['destination']}\n"
        
        if state.context.get('date_text'):
            message += f"• Дата: {state.context['date_text']}\n"
        
        if state.context.get('scenario_name'):
            message += f"• Сценарий: {state.context['scenario_name']}\n"
        
        message += f"• Итоговая стоимость: {cart_summary['total_price']:.2f} руб.\n"
        message += f"• Дата бронирования: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
        
        # Дополнительные услуги
        if 'items' in cart_summary and cart_summary['items']:
            message += "🎁 **ДОПОЛНИТЕЛЬНЫЕ УСЛУГИ:**\n"
            for item in cart_summary['items']:
                if item.get('type') == 'product':
                    message += f"• {item.get('name', 'Услуга')}\n"
            message += "\n"
        
        # Следующие шаги
        message += "🚂 **ЧТО ДАЛЬШЕ?**\n"
        message += "1. Ваш билет сохранен в истории заказов\n"
        message += "2. Чтобы посмотреть билет, нажмите '🎫 Мой билет'\n"
        message += "3. Сохраните номер билета для предъявления\n"
        message += "4. При посадке покажите номер билета\n\n"
        
        # Прощание
        message += "✨ **Приятного путешествия!** 🌍\n"
        message += "Спасибо, что выбрали наш сервис!\n\n"
        message += "Если возникнут вопросы, нажмите 'ℹ️ Помощь'"
        
        return message


class CustomReplyKeyboard:
    """Класс для создания кастомной клавиатуры"""
    
    @staticmethod
    def create_main_keyboard():
        """Создает основную клавиатуру"""
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=3)
        
        # Основные направления
        keyboard.row(
            types.KeyboardButton("📍 Москва"),
            types.KeyboardButton("📍 Санкт-Петербург"),
            types.KeyboardButton("📍 Сочи")
        )
        
        # Даты
        keyboard.row(
            types.KeyboardButton("📅 Завтра"),
            types.KeyboardButton("📅 На выходные"),
            types.KeyboardButton("📅 Выбрать дату")
        )
        
        # Корзина и покупки
        keyboard.row(
            types.KeyboardButton("🛒 Корзина"),
            types.KeyboardButton("🎁 Акции"),
            types.KeyboardButton("✅ Оформить")
        )
        
        # Управление
        keyboard.row(
            types.KeyboardButton("🎯 Сценарии"),
            types.KeyboardButton("ℹ️ Помощь"),
            types.KeyboardButton("🔄 Сброс")
        )
        
        # Дополнительные функции
        keyboard.row(
            types.KeyboardButton("🎫 Мой билет"),
            types.KeyboardButton("📋 Продолжить"),
            types.KeyboardButton("🗑️ Очистить")
        )
        
        return keyboard
    
    @staticmethod
    def create_cart_keyboard():
        """Создает клавиатуру для работы с корзиной"""
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=3)
        
        keyboard.row(
            types.KeyboardButton("✅ Оформить заказ"),
            types.KeyboardButton("🎁 Добавить акции"),
            types.KeyboardButton("🎯 Добавить сценарий")
        )
        
        keyboard.row(
            types.KeyboardButton("🗑️ Очистить корзину"),
            types.KeyboardButton("🔙 Назад"),
            types.KeyboardButton("ℹ️ Помощь")
        )
        
        return keyboard
    
    @staticmethod
    def create_confirmation_keyboard():
        """Создает клавиатуру для подтверждения действий"""
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        
        keyboard.row(
            types.KeyboardButton("✅ Да, подтверждаю"),
            types.KeyboardButton("❌ Нет, отменить")
        )
        
        keyboard.row(
            types.KeyboardButton("🔙 Назад"),
            types.KeyboardButton("ℹ️ Помощь")
        )
        
        return keyboard
    
    @staticmethod
    def create_ticket_keyboard():
        """Создает клавиатуру для работы с билетом"""
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        
        keyboard.row(
            types.KeyboardButton("📧 Отправить на email"),
            types.KeyboardButton("🖨️ Печать билета")
        )
        
        keyboard.row(
            types.KeyboardButton("🔄 Обновить"),
            types.KeyboardButton("🎫 Новый билет")
        )
        
        keyboard.row(
            types.KeyboardButton("🔙 Назад"),
            types.KeyboardButton("ℹ️ Помощь")
        )
        
        return keyboard
    
    @staticmethod
    def create_help_keyboard():
        """Создает клавиатуру для помощи"""
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        
        keyboard.row(
            types.KeyboardButton("🛒 Команды корзины"),
            types.KeyboardButton("🎫 Команды бронирования")
        )
        
        keyboard.row(
            types.KeyboardButton("🎯 Как выбрать сценарий"),
            types.KeyboardButton("🎁 Как использовать акции")
        )
        
        keyboard.row(
            types.KeyboardButton("🔙 Назад к бронированию"),
            types.KeyboardButton("🆘 Связь с поддержкой")
        )
        
        return keyboard
    
    @staticmethod
    def create_scenarios_keyboard():
        """Создает клавиатуру для выбора сценариев"""
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        
        scenarios = BOT_CONFIG['scenarios']
        
        # Показываем сценарии
        for i in range(1, min(6, len(scenarios) + 1)):
            scenario_name = scenarios[str(i)]['name']
            keyboard.add(types.KeyboardButton(f"🎯 {i}. {scenario_name}"))
        
        keyboard.row(
            types.KeyboardButton("🔙 Назад"),
            types.KeyboardButton("ℹ️ Помощь")
        )
        
        return keyboard
    
    @staticmethod
    def create_promotions_keyboard():
        """Создает клавиатуру для выбора акций"""
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        
        promotions = BOT_CONFIG['promotions']
        
        # Показываем первые 6 акций
        for i in range(1, min(7, len(promotions) + 1)):
            promo_text = promotions[i-1]['short']
            keyboard.add(types.KeyboardButton(f"🎁 {i}. {promo_text[:15]}..."))
        
        keyboard.row(
            types.KeyboardButton("🔙 Назад"),
            types.KeyboardButton("ℹ️ Помощь")
        )
        
        return keyboard


# Обработчики команд
@bot.message_handler(commands=['start'])
def handle_start(message):
    """Обработчик команды /start"""
    user_data = {
        'user_id': message.from_user.id,
        'username': message.from_user.username,
        'first_name': message.from_user.first_name,
        'last_name': message.from_user.last_name
    }
    
    welcome_message = """
🚂 **Добро пожаловать в бот путешествий!** 🌍

Я помогу вам:
• 🎫 Забронировать билеты на поезд
• 🎯 Выбрать сценарий путешествия
• 🛍️ Добавить дополнительные услуги
• 🎁 Воспользоваться акциями и скидками
• 🛒 Управлять корзиной покупок

**Как начать:**
1. Выберите направление (Москва, СПб, Сочи)
2. Укажите дату поездки
3. Выберите тип путешествия
4. Добавьте дополнительные услуги
5. Оформите заказ!

Используйте кнопки ниже или пишите сообщения. 
Нажмите 'ℹ️ Помощь' для получения списка команд.
"""
    
    bot.send_message(
        message.chat.id,
        welcome_message,
        parse_mode='Markdown',
        reply_markup=CustomReplyKeyboard.create_main_keyboard()
    )
    
    # Сохраняем пользователя в БД
    DatabaseManager.save_user(user_data)
    logger.info(f"Новый пользователь: {user_data['first_name']} {user_data['last_name']}")


@bot.message_handler(commands=['help'])
def handle_help(message):
    """Обработчик команды /help"""
    help_text = """
🤖 **ПОМОЩЬ ПО КОМАНДАМ БОТА**

📋 **Основные команды:**
/start - начать работу с ботом
/help - показать это сообщение
/cart - показать корзину
/ticket - показать электронный билет
/reset - сбросить текущее бронирование

🛒 **Работа с корзиной:**
• "Корзина" или /cart - просмотр корзины
• "Очистить корзину" - очистить корзину
• "Оформить заказ" - завершить покупку
• "Продолжить" - вернуться к бронированию

🎫 **Бронирование билетов:**
• "Москва", "СПб", "Сочи" - выбрать направление
• "Завтра", "На выходные" - выбрать дату
• "Сценарии" - показать типы поездок
• "Акции" - показать текущие акции
• "Мой билет" - показать электронный билет

🔄 **Процесс оформления:**
1. Добавьте товары в корзину
2. Нажмите "✅ Оформить заказ"
3. Проверьте детали заказа
4. Подтвердите нажатием "✅ Да, подтверждаю"
5. Получите номер билета

💡 **Совет:** Используйте кнопки для быстрого доступа к функциям бота!
"""
    
    bot.send_message(
        message.chat.id,
        help_text,
        parse_mode='Markdown',
        reply_markup=CustomReplyKeyboard.create_help_keyboard()
    )


@bot.message_handler(commands=['ticket'])
def handle_ticket_command(message):
    """Обработчик команды /ticket"""
    state = travel_bot.get_state(message.from_user.id)
    
    # Используем метод из TravelBot для показа билета
    ticket_message = travel_bot.show_ticket(state)
    
    bot.send_message(
        message.chat.id,
        ticket_message,
        parse_mode='Markdown',
        reply_markup=CustomReplyKeyboard.create_ticket_keyboard()
    )


@bot.message_handler(func=lambda message: True)
def handle_all_messages(message):
    """Обработчик всех текстовых сообщений"""
    user_data = {
        'user_id': message.from_user.id,
        'username': message.from_user.username,
        'first_name': message.from_user.first_name,
        'last_name': message.from_user.last_name
    }
    
    text = message.text
    state = travel_bot.get_state(message.from_user.id)
    
    # Обработка специальных команд
    if text == "✅ Да, подтверждаю":
        # Пользователь подтвердил заказ
        if state.context.get('awaiting_order_confirmation'):
            logger.info(f"Пользователь {user_data['user_id']} подтвердил заказ")
            
            # Передаем управление в TravelBot
            response = travel_bot.process_message(text, user_data)
            
            # Если в ответе есть номер билета, значит заказ подтвержден
            if "БРОНИРОВАНИЕ ПОДТВЕРЖДЕНО" in response or "Номер билета:" in response:
                bot.send_message(
                    message.chat.id,
                    response,
                    parse_mode='Markdown',
                    reply_markup=CustomReplyKeyboard.create_main_keyboard()
                )
                logger.info(f"Заказ подтвержден для пользователя {user_data['user_id']}")
            else:
                bot.send_message(
                    message.chat.id,
                    response,
                    parse_mode='Markdown',
                    reply_markup=CustomReplyKeyboard.create_main_keyboard()
                )
            return
        
        # Пользователь подтвердил сценарий
        elif state.context.get('awaiting_confirmation'):
            response = travel_bot.process_message(text, user_data)
            bot.send_message(
                message.chat.id,
                response,
                parse_mode='Markdown',
                reply_markup=CustomReplyKeyboard.create_main_keyboard()
            )
            return
    
    elif text == "❌ Нет, отменить":
        if state.context.get('awaiting_order_confirmation') or state.context.get('awaiting_confirmation'):
            response = travel_bot.process_message(text, user_data)
            bot.send_message(
                message.chat.id,
                response,
                parse_mode='Markdown',
                reply_markup=CustomReplyKeyboard.create_main_keyboard()
            )
            return
    
    # Обработка других кнопок
    elif text == "✅ Оформить":
        handle_checkout(message)
        return
    
    elif text == "🛒 Корзина":
        handle_cart(message)
        return
    
    elif text == "🎫 Мой билет":
        handle_ticket_command(message)
        return
    
    elif text == "🔙 Назад":
        # Сбрасываем все состояния ожидания
        state.context['awaiting_confirmation'] = False
        state.context['awaiting_order_confirmation'] = False
        state.context['awaiting_scenario_selection'] = False
        state.context['awaiting_promo_selection'] = False
        state.context['awaiting_date'] = False
        state.context['awaiting_destination'] = False
        
        bot.send_message(
            message.chat.id,
            "Возвращаемся к основному меню...",
            reply_markup=CustomReplyKeyboard.create_main_keyboard()
        )
        return
    
    elif text == "🔄 Сброс":
        handle_reset(message)
        return
    
    elif text == "ℹ️ Помощь":
        handle_help(message)
        return
    
    elif text == "🎯 Сценарии":
        state = travel_bot.get_state(message.from_user.id)
        if state.context.get('destination') and state.context.get('date_text'):
            # Сбрасываем предыдущие состояния
            state.context['awaiting_confirmation'] = False
            state.context['awaiting_order_confirmation'] = False
            state.context['awaiting_scenario_selection'] = True
            
            scenarios_text = """
🎯 **ДОСТУПНЫЕ СЦЕНАРИИ ПУТЕШЕСТВИЙ**

Выберите тип поездки, который лучше всего подходит для вас:
"""
            bot.send_message(
                message.chat.id,
                scenarios_text,
                parse_mode='Markdown',
                reply_markup=CustomReplyKeyboard.create_scenarios_keyboard()
            )
            
            # Отправляем детали сценариев
            scenarios_details = travel_bot._show_scenarios(state)
            bot.send_message(
                message.chat.id,
                scenarios_details,
                parse_mode='Markdown',
                reply_markup=CustomReplyKeyboard.create_main_keyboard()
            )
        else:
            bot.send_message(
                message.chat.id,
                "Сначала выберите направление и дату, чтобы увидеть подходящие сценарии! 🗺️",
                reply_markup=CustomReplyKeyboard.create_main_keyboard()
            )
        return
    
    elif text == "🎁 Акции":
        state = travel_bot.get_state(message.from_user.id)
        # Сбрасываем предыдущие состояния
        state.context['awaiting_confirmation'] = False
        state.context['awaiting_order_confirmation'] = False
        state.context['awaiting_promo_selection'] = True
        
        promotions_text = """
🎁 **ТЕКУЩИЕ АКЦИИ И ПРЕДЛОЖЕНИЯ**

Выберите акцию, которую хотите применить:
"""
        bot.send_message(
            message.chat.id,
            promotions_text,
            parse_mode='Markdown',
            reply_markup=CustomReplyKeyboard.create_promotions_keyboard()
        )
        
        # Отправляем детали акций
        promotions_details = travel_bot._show_promotions(state)
        bot.send_message(
            message.chat.id,
            promotions_details,
            parse_mode='Markdown',
            reply_markup=CustomReplyKeyboard.create_main_keyboard()
        )
        return
    
    elif text == "🗑️ Очистить":
        state = travel_bot.get_state(message.from_user.id)
        state.clear_cart()
        state.context['awaiting_confirmation'] = False
        state.context['awaiting_order_confirmation'] = False
        
        bot.send_message(
            message.chat.id,
            "🛒 Корзина очищена! Теперь вы можете добавить новые товары.",
            reply_markup=CustomReplyKeyboard.create_main_keyboard()
        )
        return
    
    elif text == "📋 Продолжить":
        state = travel_bot.get_state(message.from_user.id)
        cart_summary = state.get_cart_summary()
        
        # Сбрасываем состояния ожидания
        state.context['awaiting_confirmation'] = False
        state.context['awaiting_order_confirmation'] = False
        
        if cart_summary['item_count'] > 0:
            cart_message = travel_bot.show_cart(state)
            bot.send_message(
                message.chat.id,
                cart_message,
                parse_mode='Markdown',
                reply_markup=CustomReplyKeyboard.create_cart_keyboard()
            )
        else:
            bot.send_message(
                message.chat.id,
                "Корзина пуста. Начните новое бронирование! 🚂",
                reply_markup=CustomReplyKeyboard.create_main_keyboard()
            )
        return
    
    # Обработка выбора сценария через кнопки
    elif text.startswith("🎯 "):
        # Извлекаем номер сценария из текста
        try:
            scenario_num = int(text.split('.')[0].replace('🎯 ', '').strip())
            state = travel_bot.get_state(message.from_user.id)
            
            # Сбрасываем предыдущие состояния
            state.context['awaiting_confirmation'] = False
            state.context['awaiting_order_confirmation'] = False
            
            # Обрабатываем выбор сценария
            response = travel_bot.process_message(str(scenario_num), user_data)
            
            if "Добавить в корзину и продолжить" in response:
                state.context['awaiting_confirmation'] = True
                bot.send_message(
                    message.chat.id,
                    response,
                    parse_mode='Markdown',
                    reply_markup=CustomReplyKeyboard.create_confirmation_keyboard()
                )
            else:
                bot.send_message(
                    message.chat.id,
                    response,
                    parse_mode='Markdown',
                    reply_markup=CustomReplyKeyboard.create_main_keyboard()
                )
        except (ValueError, IndexError):
            # Если не удалось распознать номер, переходим к общей обработке
            pass
    
    # Обработка выбора акций через кнопки
    elif text.startswith("🎁 "):
        # Извлекаем номер акции из текста
        try:
            promo_num = int(text.split('.')[0].replace('🎁 ', '').strip())
            state = travel_bot.get_state(message.from_user.id)
            
            # Сбрасываем предыдущие состояния
            state.context['awaiting_confirmation'] = False
            state.context['awaiting_order_confirmation'] = False
            
            response = travel_bot.process_message(str(promo_num), user_data)
            
            if "Хотите добавить еще акции" in response:
                state.context['awaiting_confirmation'] = True
                bot.send_message(
                    message.chat.id,
                    response,
                    parse_mode='Markdown',
                    reply_markup=CustomReplyKeyboard.create_confirmation_keyboard()
                )
            else:
                bot.send_message(
                    message.chat.id,
                    response,
                    parse_mode='Markdown',
                    reply_markup=CustomReplyKeyboard.create_main_keyboard()
                )
        except (ValueError, IndexError):
            # Если не удалось распознать номер, переходим к общей обработке
            pass
    
    # Обработка выбора направления
    elif text in ["📍 Москва", "📍 Санкт-Петербург", "📍 Сочи"]:
        destination = text.replace("📍 ", "").strip()
        response = travel_bot.process_message(destination, user_data)
        
        # Определяем клавиатуру
        state = travel_bot.get_state(message.from_user.id)
        if state.context.get('awaiting_date'):
            reply_markup = CustomReplyKeyboard.create_main_keyboard()
        else:
            reply_markup = CustomReplyKeyboard.create_main_keyboard()
        
        bot.send_message(
            message.chat.id,
            response,
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
        return
    
    # Обработка выбора даты
    elif text in ["📅 Завтра", "📅 На выходные"]:
        date_text = text.replace("📅 ", "").strip()
        response = travel_bot.process_message(date_text, user_data)
        
        # Определяем клавиатуру
        state = travel_bot.get_state(message.from_user.id)
        if state.context.get('awaiting_scenario_selection'):
            reply_markup = CustomReplyKeyboard.create_scenarios_keyboard()
        else:
            reply_markup = CustomReplyKeyboard.create_main_keyboard()
        
        bot.send_message(
            message.chat.id,
            response,
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
        return
    
    # Обработка других сообщений помощи
    elif text == "🛒 Команды корзины":
        cart_help = """
🛒 **КОМАНДЫ ДЛЯ РАБОТЫ С КОРЗИНОЙ:**

• "Корзина" - посмотреть содержимое корзины
• "Очистить корзину" - удалить все товары
• "Оформить заказ" - завершить покупку
• "Продолжить" - вернуться к выбору товаров

💡 **Советы:**
- Корзина сохраняется между сессиями
- Вы можете добавлять товары из разных сценариев
- Перед оформлением проверьте состав заказа
"""
        bot.send_message(
            message.chat.id,
            cart_help,
            parse_mode='Markdown',
            reply_markup=CustomReplyKeyboard.create_help_keyboard()
        )
        return
    
    elif text == "🎫 Команды бронирования":
        booking_help = """
🎫 **КОМАНДЫ ДЛЯ БРОНИРОВАНИЯ:**

• "Москва"/"СПб"/"Сочи" - выбрать направление
• "Завтра"/"На выходные" - выбрать дату
• "Сценарии" - выбрать тип путешествия
• "Мой билет" - посмотреть электронный билет
• "Акции" - применить промо-коды

📋 **Процесс бронирования:**
1. Выберите направление
2. Укажите дату поездки
3. Выберите сценарий
4. Добавьте дополнительные услуги
5. Примените акции
6. Оформите заказ
"""
        bot.send_message(
            message.chat.id,
            booking_help,
            parse_mode='Markdown',
            reply_markup=CustomReplyKeyboard.create_help_keyboard()
        )
        return
    
    elif text == "🎯 Как выбрать сценарий":
        scenario_help = """
🎯 **КАК ВЫБРАТЬ СЦЕНАРИЙ ПУТЕШЕСТВИЯ:**

**1. 💰 Бюджетный** (5% скидка)
   - Для: Экономных путешественников
   - Включает: Wi-Fi, страховка
   - Идеально: Для коротких поездок

**2. ⭐ Стандартный** (10% скидка)
   - Для: Комфортного путешествия
   - Включает: Wi-Fi, страховка, питание
   - Идеально: Для деловых поездок

**3. 👑 Премиум** (15% скидка)
   - Для: Максимального комфорта
   - Включает: Все основные услуги
   - Идеально: Для особых случаев

💡 **Совет:** Выбирайте сценарий, который лучше всего соответствует цели вашей поездки!
"""
        bot.send_message(
            message.chat.id,
            scenario_help,
            parse_mode='Markdown',
            reply_markup=CustomReplyKeyboard.create_help_keyboard()
        )
        return
    
    elif text == "🎁 Как использовать акции":
        promo_help = """
🎁 **КАК ИСПОЛЬЗОВАТЬ АКЦИИ И ПРОМО-КОДЫ:**

**Доступные акции:**

1. **Первый заказ - 15% скидка**
   - Для новых клиентов
   - Автоматически применяется

2. **Постоянный клиент - 10%**
   - После успешных бронирований
   - Действует всегда

3. **Сезонная скидка - 20%**
   - В несезонные периоды

4. **Групповая поездка - 25%**
   - При бронировании от 3-х человек

5. **Раннее бронирование - 30%**
   - При покупке за 60+ дней

💡 **Как применить:**
1. Нажмите "🎁 Акции"
2. Выберите нужную акцию
3. Подтвердите добавление
4. Скидка применится автоматически
"""
        bot.send_message(
            message.chat.id,
            promo_help,
            parse_mode='Markdown',
            reply_markup=CustomReplyKeyboard.create_help_keyboard()
        )
        return
    
    elif text == "🔙 Назад к бронированию":
        state = travel_bot.get_state(message.from_user.id)
        state.context['awaiting_confirmation'] = False
        state.context['awaiting_order_confirmation'] = False
        
        bot.send_message(
            message.chat.id,
            "Возвращаемся к бронированию...",
            reply_markup=CustomReplyKeyboard.create_main_keyboard()
        )
        return
    
    elif text == "🆘 Связь с поддержкой":
        support_text = """
🆘 **СВЯЗЬ С ТЕХНИЧЕСКОЙ ПОДДЕРЖКОЙ**

Если у вас возникли проблемы:

**📞 Телефон:**
+7 (800) 555-35-35
(бесплатно по России)

**📧 Email:**
support@travelbot.ru

**🕒 Часы работы:**
Пн-Пт: 9:00 - 21:00
Сб-Вс: 10:00 - 18:00

**📱 Мессенджеры:**
Telegram: @travel_support_bot
WhatsApp: +7 (999) 123-45-67

💡 **Перед обращением:**
1. Проверьте, нет ли ответа в разделе "Помощь"
2. Подготовьте номер бронирования (если есть)
3. Опишите проблему максимально подробно

Мы всегда готовы помочь! 🤝
"""
        bot.send_message(
            message.chat.id,
            support_text,
            parse_mode='Markdown',
            reply_markup=CustomReplyKeyboard.create_help_keyboard()
        )
        return
    
    # Обработка обычных текстовых сообщений через логику бота
    response = travel_bot.process_message(text, user_data)
    
    # Определяем, какую клавиатуру показывать
    state = travel_bot.get_state(message.from_user.id)
    
    # Правильное определение клавиатуры
    if state.context.get('awaiting_order_confirmation'):
        reply_markup = CustomReplyKeyboard.create_confirmation_keyboard()
    elif state.context.get('awaiting_confirmation'):
        reply_markup = CustomReplyKeyboard.create_confirmation_keyboard()
    elif state.context.get('awaiting_scenario_selection'):
        reply_markup = CustomReplyKeyboard.create_scenarios_keyboard()
    elif state.context.get('awaiting_promo_selection'):
        reply_markup = CustomReplyKeyboard.create_promotions_keyboard()
    elif "ВАША КОРЗИНА" in response or "Корзина пуста" in response:
        reply_markup = CustomReplyKeyboard.create_cart_keyboard()
    elif "ПОМОЩЬ" in response or "СПРАВКА" in response:
        reply_markup = CustomReplyKeyboard.create_help_keyboard()
    else:
        reply_markup = CustomReplyKeyboard.create_main_keyboard()
    
    bot.send_message(
        message.chat.id,
        response,
        parse_mode='Markdown',
        reply_markup=reply_markup
    )


def handle_checkout(message):
    """Обработчик оформления заказа"""
    state = travel_bot.get_state(message.from_user.id)
    user_data = {
        'user_id': message.from_user.id,
        'username': message.from_user.username,
        'first_name': message.from_user.first_name,
        'last_name': message.from_user.last_name
    }
    
    # Получаем сообщение о заказе
    order_message = travel_bot.process_order(state)
    
    if "ПОДТВЕРЖДЕНИЕ ЗАКАЗА" in order_message or "ПОДТВЕРЖДИТЕ ОФОРМЛЕНИЕ" in order_message:
        # Устанавливаем состояние ожидания подтверждения
        state.context['awaiting_order_confirmation'] = True
        
        # Форматируем сообщение для подтверждения
        confirmation_message = f"""
🎫 **ПОДТВЕРЖДЕНИЕ ЗАКАЗА**

Пожалуйста, подтвердите оформление заказа:

{order_message}

**Подтверждая заказ, вы соглашаетесь с условиями:**
1. Правила перевозки пассажиров
2. Условия возврата билетов
3. Политика конфиденциальности

Для продолжения нажмите "✅ Да, подтверждаю"
Для отмены - "❌ Нет, отменить"
"""
        
        bot.send_message(
            message.chat.id,
            confirmation_message,
            parse_mode='Markdown',
            reply_markup=CustomReplyKeyboard.create_confirmation_keyboard()
        )
    else:
        bot.send_message(
            message.chat.id,
            order_message,
            parse_mode='Markdown',
            reply_markup=CustomReplyKeyboard.create_main_keyboard()
        )


def handle_cart(message):
    """Обработчик просмотра корзины"""
    state = travel_bot.get_state(message.from_user.id)
    cart_message = travel_bot.show_cart(state)
    
    bot.send_message(
        message.chat.id,
        cart_message,
        parse_mode='Markdown',
        reply_markup=CustomReplyKeyboard.create_cart_keyboard()
    )


def handle_reset(message):
    """Обработчик сброса"""
    state = travel_bot.get_state(message.from_user.id)
    state.reset(clear_cart=True)
    
    bot.send_message(
        message.chat.id,
        "✅ Состояние сброшено. Начнем заново! 🔄",
        reply_markup=CustomReplyKeyboard.create_main_keyboard()
    )


def main():
    """Основная функция запуска бота"""
    logger.info("Запуск Telegram Travel Bot...")
    
    try:
        # Запускаем бота
        bot.infinity_polling(timeout=60, long_polling_timeout=60)
    except Exception as e:
        logger.error(f"Ошибка при запуске бота: {e}")
        logger.info("Попытка перезапуска через 10 секунд...")
        import time
        time.sleep(10)
        main()


if __name__ == "__main__":
    main()