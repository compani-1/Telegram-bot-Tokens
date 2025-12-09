"""
Telegram Travel Bot - Улучшенная версия с расширенным диалогом оформления
"""

import telebot
import logging
from telebot import types
from config import TELEGRAM_TOKEN, BOT_CONFIG, LOG_FILE, LOG_LEVEL
from advanced_bot import TravelBot, DatabaseManager
from datetime import datetime
import json
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
            return random.choice(BOT_CONFIG['checkout_dialogue'][phrase_type])
        return ""
    
    @staticmethod
    def get_scenario_dialogue(scenario_id):
        """Получить диалог для сценария"""
        if scenario_id in BOT_CONFIG['scenarios']:
            scenario_data = BOT_CONFIG['scenarios'][scenario_id]
            if 'dialogue' in scenario_data:
                return random.choice(scenario_data['dialogue'])
            return scenario_data['description']
        return ""
    
    @staticmethod
    def enhance_order_summary(order_summary):
        """Улучшить сводку заказа с диалоговыми элементами"""
        enhanced_summary = DialogueManager.get_random_phrase('order_summary')
        enhanced_summary += order_summary
        return enhanced_summary
    
    @staticmethod
    def enhance_confirmation_prompt(confirmation_text):
        """Улучшить запрос подтверждения"""
        enhanced_prompt = DialogueManager.get_random_phrase('ask_confirmation')
        enhanced_prompt += "\n\n"
        enhanced_prompt += confirmation_text
        enhanced_prompt += "\n\n"
        enhanced_prompt += DialogueManager.get_random_phrase('confirm_prompt')
        return enhanced_prompt


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
    def create_scenarios_keyboard():
        """Создает клавиатуру для выбора сценариев"""
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        
        scenarios = BOT_CONFIG['scenarios']
        
        # Первые 3 сценария
        for i in range(1, min(4, len(scenarios) + 1)):
            scenario_name = list(scenarios.values())[i-1]['name']
            keyboard.add(types.KeyboardButton(f"🎯 {i}. {scenario_name}"))
        
        # Остальные сценарии
        if len(scenarios) > 3:
            keyboard.row(
                types.KeyboardButton(f"🎯 4. {list(scenarios.values())[3]['name']}"),
                types.KeyboardButton(f"🎯 5. {list(scenarios.values())[4]['name']}")
            )
        
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


class InlineKeyboardManager:
    """Менеджер для inline-клавиатур"""
    
    @staticmethod
    def create_scenarios_inline():
        """Создает inline-клавиатуру для сценариев"""
        keyboard = types.InlineKeyboardMarkup(row_width=1)
        
        scenarios = BOT_CONFIG['scenarios']
        
        for i, (scenario_id, scenario_data) in enumerate(scenarios.items(), 1):
            keyboard.add(
                types.InlineKeyboardButton(
                    text=f"{i}. {scenario_data['name']} - {scenario_data['discount']}% скидка",
                    callback_data=f"scenario_{scenario_id}"
                )
            )
        
        return keyboard
    
    @staticmethod
    def create_promotions_inline():
        """Создает inline-клавиатуру для акций"""
        keyboard = types.InlineKeyboardMarkup(row_width=1)
        
        promotions = BOT_CONFIG['promotions']
        
        for i, promo in enumerate(promotions, 1):
            keyboard.add(
                types.InlineKeyboardButton(
                    text=f"{i}. {promo['short']}",
                    callback_data=f"promo_{promo['id']}"
                )
            )
        
        return keyboard
    
    @staticmethod
    def create_cart_actions_inline():
        """Создает inline-клавиатуру для действий с корзиной"""
        keyboard = types.InlineKeyboardMarkup(row_width=2)
        
        keyboard.add(
            types.InlineKeyboardButton(text="✅ Оформить заказ", callback_data="action_checkout"),
            types.InlineKeyboardButton(text="🎁 Добавить акцию", callback_data="action_add_promo")
        )
        
        keyboard.add(
            types.InlineKeyboardButton(text="🗑️ Очистить корзину", callback_data="action_clear_cart"),
            types.InlineKeyboardButton(text="🎫 Посмотреть билет", callback_data="action_view_ticket")
        )
        
        keyboard.add(
            types.InlineKeyboardButton(text="ℹ️ Помощь", callback_data="action_help"),
            types.InlineKeyboardButton(text="🔙 Назад", callback_data="action_back")
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

🎯 **Сценарии путешествий:**
1. 🏙️ Городской исследователь - для туристов
2. 🏛️ Культурный вояж - для ценителей искусства
3. 🌲 Природный отдых - для любителей природы
4. 💼 Деловая поездка - для бизнес-путешественников
5. 🎉 Отдых выходного дня - для коротких поездок

🎁 **Акции и промо-коды:**
• Скидки на первый заказ
• Акции для постоянных клиентов
• Сезонные предложения
• Специальные условия

🔄 **Управление:**
• "Сброс" - начать заново
• "Помощь" - показать справку

💡 **Совет:** Используйте кнопки для быстрого доступа к функциям бота!
"""
    
    bot.send_message(
        message.chat.id,
        help_text,
        parse_mode='Markdown',
        reply_markup=CustomReplyKeyboard.create_help_keyboard()
    )


@bot.message_handler(commands=['cart'])
def handle_cart(message):
    """Обработчик команды /cart"""
    state = travel_bot.get_state(message.from_user.id)
    cart_message = travel_bot.show_cart(state)
    
    bot.send_message(
        message.chat.id,
        cart_message,
        parse_mode='Markdown',
        reply_markup=CustomReplyKeyboard.create_cart_keyboard()
    )


@bot.message_handler(commands=['ticket'])
def handle_ticket(message):
    """Обработчик команды /ticket"""
    state = travel_bot.get_state(message.from_user.id)
    ticket_message = travel_bot.show_ticket(state)
    
    bot.send_message(
        message.chat.id,
        ticket_message,
        parse_mode='Markdown',
        reply_markup=CustomReplyKeyboard.create_main_keyboard()
    )


@bot.message_handler(commands=['reset'])
def handle_reset(message):
    """Обработчик команды /reset"""
    state = travel_bot.get_state(message.from_user.id)
    state.reset(clear_cart=True)
    
    bot.send_message(
        message.chat.id,
        "✅ Состояние сброшено. Начнем заново! 🔄",
        reply_markup=CustomReplyKeyboard.create_main_keyboard()
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
    
    # Получаем текущее состояние
    state = travel_bot.get_state(message.from_user.id)
    text = message.text
    
    # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Проверяем состояния подтверждения ПЕРВЫМ делом
    is_awaiting_confirmation = state.context.get('awaiting_confirmation')
    is_awaiting_order_confirmation = state.context.get('awaiting_order_confirmation')
    
    if is_awaiting_confirmation or is_awaiting_order_confirmation:
        if text in ["✅ Да, подтверждаю", "❌ Нет, отменить"]:
            # Обрабатываем через логику бота
            response = travel_bot.process_message(text, user_data)
            
            # Сбрасываем состояния после обработки
            state.context['awaiting_confirmation'] = False
            state.context['awaiting_order_confirmation'] = False
            
            # Улучшаем ответы с использованием диалоговых фраз
            if "Билет забронирован!" in response or "Заказ оформлен!" in response:
                # Добавляем завершающий диалог
                response = DialogueManager.get_random_phrase('order_confirmed')
                response += DialogueManager.get_random_phrase('ticket_generated')
                response += "\n"
                response += DialogueManager.get_random_phrase('thank_you')
                response += "\n\n"
                response += DialogueManager.get_random_phrase('next_steps')
                response += "\n\n"
                response += DialogueManager.get_random_phrase('special_offer')
            
            # Определяем клавиатуру на основе ответа
            if "ПОДТВЕРЖДЕНИЕ ЗАКАЗА" in response or "ПОДТВЕРЖДИТЕ ОФОРМЛЕНИЕ" in response:
                # Если нужно подтверждение заказа
                state.context['awaiting_order_confirmation'] = True
                reply_markup = CustomReplyKeyboard.create_confirmation_keyboard()
            elif "Билет забронирован!" in response or "Заказ оформлен!" in response:
                # После успешного оформления
                reply_markup = CustomReplyKeyboard.create_main_keyboard()
            elif "ВАША КОРЗИНА" in response:
                reply_markup = CustomReplyKeyboard.create_cart_keyboard()
            else:
                reply_markup = CustomReplyKeyboard.create_main_keyboard()
            
            bot.send_message(
                message.chat.id,
                response,
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
            return
    
    # Обрабатываем остальные команды
    if text == "ℹ️ Помощь":
        handle_help(message)
        return
    
    elif text == "🔙 Назад":
        # Сбрасываем все состояния ожидания
        state.context['awaiting_confirmation'] = False
        state.context['awaiting_order_confirmation'] = False
        state.context['awaiting_scenario_selection'] = False
        state.context['awaiting_promo_selection'] = False
        
        bot.send_message(
            message.chat.id,
            "Возвращаемся к основному меню...",
            reply_markup=CustomReplyKeyboard.create_main_keyboard()
        )
        return
    
    elif text == "🛒 Корзина":
        handle_cart(message)
        return
    
    elif text == "🎫 Мой билет":
        handle_ticket(message)
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
            scenarios_details = travel_bot._show_scenarios(state, short=False)
            bot.send_message(
                message.chat.id,
                scenarios_details,
                parse_mode='Markdown',
                reply_markup=InlineKeyboardManager.create_scenarios_inline()
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
            reply_markup=InlineKeyboardManager.create_promotions_inline()
        )
        return
    
    elif text == "✅ Оформить":
        state = travel_bot.get_state(message.from_user.id)
        # Сбрасываем состояния перед оформлением
        state.context['awaiting_confirmation'] = False
        state.context['awaiting_order_confirmation'] = False
        
        # Получаем сообщение о заказе
        order_message = travel_bot.process_order(state)
        
        if "ПОДТВЕРЖДЕНИЕ ЗАКАЗА" in order_message or "ПОДТВЕРЖДИТЕ ОФОРМЛЕНИЕ" in order_message:
            state.context['awaiting_order_confirmation'] = True
            
            # Улучшаем диалог оформления
            enhanced_message = DialogueManager.get_random_phrase('start_checkout')
            enhanced_message += "\n\n"
            enhanced_message += DialogueManager.enhance_order_summary(order_message)
            enhanced_message += "\n"
            enhanced_message += DialogueManager.enhance_confirmation_prompt("")
            
            bot.send_message(
                message.chat.id,
                enhanced_message,
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
    
    elif text == "🔄 Сброс":
        handle_reset(message)
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
    
    # Обработка других команд помощи
    elif text == "🛒 Команды корзины":
        cart_help = """
🛒 **КОМАНДЫ ДЛЯ РАБОТЫ С КОРЗИНОЙ:**

• "Корзина" - посмотреть содержимое корзины
• "Очистить корзину" - удалить все товары
• "Оформить заказ" - завершить покупку
• "Продолжить" - вернуться к выбору товаров
• "Удалить [номер]" - удалить конкретный товар

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
• "Выбрать дату" - указать конкретную дату
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

**1. 🏙️ Городской исследователь**
   - Для: Туристов, любителей экскурсий
   - Включает: Гид, карты, транспорт
   - Скидка: 10%

**2. 🏛️ Культурный вояж**
   - Для: Ценителей искусства, музеев
   - Включает: Билеты в музеи, экскурсии
   - Скидка: 15%

**3. 🌲 Природный отдых**
   - Для: Любителей природы, походов
   - Включает: Снаряжение, гида, питание
   - Скидка: 20%

**4. 💼 Деловая поездка**
   - Для: Бизнес-путешественников
   - Включает: Трансфер, Wi-Fi, переговорные
   - Скидка: 25%

**5. 🎉 Отдых выходного дня**
   - Для: Коротких поездок на 2-3 дня
   - Включает: Проживание, питание, развлечения
   - Скидка: 30%

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
   - После 3-х успешных бронирований
   - Действует всегда

3. **Сезонная скидка - 20%**
   - В несезонные периоды
   - Уточняйте даты действия

4. **Групповая поездка - 25%**
   - При бронировании от 3-х человек
   - На все билеты группы

5. **Раннее бронирование - 30%**
   - При покупке за 60+ дней
   - На определенные направления

6. **Специальное предложение - 35%**
   - Ограниченное количество
   - По промо-коду

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

**📍 Адрес офиса:**
Москва, ул. Тверская, д. 1

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


# Обработчики inline-кнопок
@bot.callback_query_handler(func=lambda call: True)
def handle_callback_query(call):
    """Обработчик inline-кнопок"""
    user_data = {
        'user_id': call.from_user.id,
        'username': call.from_user.username,
        'first_name': call.from_user.first_name,
        'last_name': call.from_user.last_name
    }
    
    state = travel_bot.get_state(call.from_user.id)
    
    if call.data.startswith("scenario_"):
        # Обработка выбора сценария
        scenario_id = call.data.replace("scenario_", "")
        
        if scenario_id in BOT_CONFIG['scenarios']:
            # Сбрасываем состояния ожидания
            state.context['awaiting_confirmation'] = False
            state.context['awaiting_order_confirmation'] = False
            
            state.apply_scenario(scenario_id)
            state.context['awaiting_scenario_selection'] = False
            
            scenario_data = BOT_CONFIG['scenarios'][scenario_id]
            
            # Используем диалоговые фразы для сценария
            scenario_dialogue = DialogueManager.get_scenario_dialogue(scenario_id)
            
            response = f"✅ **Выбран сценарий: {scenario_data['name']}**\n\n"
            response += f"✨ {scenario_dialogue}\n\n"
            response += f"💰 **Скидка по сценарию: {scenario_data['discount']}%**\n\n"
            
            cart_summary = state.get_cart_summary()
            response += "🛍️ **В корзину добавлены:**\n"
            for product in cart_summary['products']:
                response += f"• {product['name']} - {product.get('base_price', 0)} руб.\n"
            
            if cart_summary['tickets']:
                for ticket in cart_summary['tickets']:
                    response += f"• Билет {ticket['destination']} - {ticket['price']} руб.\n"
            
            response += f"\n💵 **Общая стоимость: {cart_summary['total_price']:.2f} руб.**\n\n"
            response += "✅ Добавить в корзину и продолжить?"
            
            state.context['awaiting_confirmation'] = True
            
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=response,
                parse_mode='Markdown'
            )
            
            bot.send_message(
                call.message.chat.id,
                "Подтвердите добавление сценария в корзину:",
                reply_markup=CustomReplyKeyboard.create_confirmation_keyboard()
            )
    
    elif call.data.startswith("promo_"):
        # Обработка выбора промо-акции
        promo_id = int(call.data.replace("promo_", ""))
        
        # Сбрасываем состояния
        state.context['awaiting_confirmation'] = False
        state.context['awaiting_order_confirmation'] = False
        
        # Находим промо-акцию
        promo = None
        for p in BOT_CONFIG['promotions']:
            if p['id'] == promo_id:
                promo = p
                break
        
        if promo:
            state.add_to_cart('promo', promo['id'], promo)
            state.context['awaiting_promo_selection'] = False
            
            response = f"✅ **Добавлена акция: {promo['short']}**\n\n"
            response += f"{promo['full']}\n\n"
            
            cart_summary = state.get_cart_summary()
            if cart_summary['item_count'] > 0:
                response += f"🛒 В корзине: {cart_summary['item_count']} товаров\n"
                response += f"💵 Общая стоимость: {cart_summary['total_price']:.2f} руб.\n\n"
            
            response += "Хотите добавить еще акции?"
            state.context['awaiting_confirmation'] = True
            
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=response,
                parse_mode='Markdown'
            )
            
            bot.send_message(
                call.message.chat.id,
                "Подтвердите добавление акции:",
                reply_markup=CustomReplyKeyboard.create_confirmation_keyboard()
            )
    
    elif call.data == "action_checkout":
        # Оформление заказа через inline-кнопку
        state.context['awaiting_confirmation'] = False
        state.context['awaiting_order_confirmation'] = False
        
        # Получаем сообщение о заказе
        order_message = travel_bot.process_order(state)
        
        if "ПОДТВЕРЖДЕНИЕ ЗАКАЗА" in order_message or "ПОДТВЕРЖДИТЕ ОФОРМЛЕНИЕ" in order_message:
            state.context['awaiting_order_confirmation'] = True
            
            # Улучшаем диалог оформления
            enhanced_message = DialogueManager.get_random_phrase('start_checkout')
            enhanced_message += "\n\n"
            enhanced_message += DialogueManager.enhance_order_summary(order_message)
            enhanced_message += "\n"
            enhanced_message += DialogueManager.enhance_confirmation_prompt("")
            
            bot.send_message(
                call.message.chat.id,
                enhanced_message,
                parse_mode='Markdown',
                reply_markup=CustomReplyKeyboard.create_confirmation_keyboard()
            )
        else:
            bot.send_message(
                call.message.chat.id,
                order_message,
                parse_mode='Markdown',
                reply_markup=CustomReplyKeyboard.create_main_keyboard()
            )
    
    elif call.data == "action_add_promo":
        # Добавление промо-акции через inline-кнопку
        state.context['awaiting_confirmation'] = False
        state.context['awaiting_order_confirmation'] = False
        state.context['awaiting_promo_selection'] = True
        
        promotions_text = """
🎁 **ТЕКУЩИЕ АКЦИИ И ПРЕДЛОЖЕНИЯ**

Выберите акцию, которую хотите применить:
"""
        bot.send_message(
            call.message.chat.id,
            promotions_text,
            parse_mode='Markdown',
            reply_markup=CustomReplyKeyboard.create_promotions_keyboard()
        )
        
        promotions_details = travel_bot._show_promotions(state)
        bot.send_message(
            call.message.chat.id,
            promotions_details,
            parse_mode='Markdown',
            reply_markup=InlineKeyboardManager.create_promotions_inline()
        )
    
    elif call.data == "action_clear_cart":
        # Очистка корзины через inline-кнопку
        state.clear_cart()
        state.context['awaiting_confirmation'] = False
        state.context['awaiting_order_confirmation'] = False
        
        bot.send_message(
            call.message.chat.id,
            "🛒 Корзина очищена! Теперь вы можете добавить новые товары.",
            reply_markup=CustomReplyKeyboard.create_main_keyboard()
        )
    
    elif call.data == "action_view_ticket":
        # Просмотр билета через inline-кнопку
        state.context['awaiting_confirmation'] = False
        state.context['awaiting_order_confirmation'] = False
        ticket_message = travel_bot.show_ticket(state)
        
        bot.send_message(
            call.message.chat.id,
            ticket_message,
            parse_mode='Markdown',
            reply_markup=CustomReplyKeyboard.create_main_keyboard()
        )
    
    elif call.data == "action_help":
        # Показать помощь через inline-кнопку
        handle_help(call.message)
    
    elif call.data == "action_back":
        # Назад через inline-кнопку
        state.context['awaiting_confirmation'] = False
        state.context['awaiting_order_confirmation'] = False
        state.context['awaiting_scenario_selection'] = False
        state.context['awaiting_promo_selection'] = False
        
        bot.send_message(
            call.message.chat.id,
            "Возвращаемся...",
            reply_markup=CustomReplyKeyboard.create_main_keyboard()
        )
    
    elif call.data == "action_email_ticket":
        # Отправка билета на email через inline-кнопку
        state.context['awaiting_confirmation'] = False
        state.context['awaiting_order_confirmation'] = False
        
        response = "📧 **Отправка билета на email**\n\n"
        response += "Для отправки билета на email, пожалуйста, укажите ваш email адрес.\n\n"
        response += "Отправьте сообщение в формате: `email:ваш_email@example.com`"
        
        bot.send_message(
            call.message.chat.id,
            response,
            parse_mode='Markdown',
            reply_markup=CustomReplyKeyboard.create_main_keyboard()
        )
    
    elif call.data == "action_save_ticket":
        # Сохранение билета через inline-кнопку
        state.context['awaiting_confirmation'] = False
        state.context['awaiting_order_confirmation'] = False
        
        response = "📱 **Сохранение билета**\n\n"
        response += "✅ Ваш билет сохранен в истории заказов.\n"
        response += "Вы всегда можете посмотреть его, нажав '🎫 Мой билет'.\n\n"
        response += DialogueManager.get_random_phrase('next_steps')
        
        bot.send_message(
            call.message.chat.id,
            response,
            parse_mode='Markdown',
            reply_markup=CustomReplyKeyboard.create_main_keyboard()
        )
    
    elif call.data == "action_print_ticket":
        # Печать билета через inline-кнопку
        state.context['awaiting_confirmation'] = False
        state.context['awaiting_order_confirmation'] = False
        
        response = "🖨️ **Печать билета**\n\n"
        response += "Для печати билета:\n"
        response += "1. Сохраните изображение ниже\n"
        response += "2. Отправьте его на печать\n"
        response += "3. Или покажите QR-код на экране при посадке\n\n"
        response += "📄 Ваш билет готов к печати!"
        
        bot.send_message(
            call.message.chat.id,
            response,
            parse_mode='Markdown',
            reply_markup=CustomReplyKeyboard.create_main_keyboard()
        )
    
    elif call.data == "action_refresh_ticket":
        # Обновление билета через inline-кнопку
        state.context['awaiting_confirmation'] = False
        state.context['awaiting_order_confirmation'] = False
        
        ticket_message = travel_bot.show_ticket(state)
        
        bot.send_message(
            call.message.chat.id,
            ticket_message,
            parse_mode='Markdown',
            reply_markup=CustomReplyKeyboard.create_main_keyboard()
        )
    
    # Отвечаем на callback, чтобы убрать "часики" у кнопки
    bot.answer_callback_query(call.id)


class StateManager:
    """Менеджер для управления состояниями бота"""
    
    @staticmethod
    def reset_all_states(state):
        """Сбрасывает все состояния ожидания"""
        state.context['awaiting_confirmation'] = False
        state.context['awaiting_order_confirmation'] = False
        state.context['awaiting_scenario_selection'] = False
        state.context['awaiting_promo_selection'] = False
        state.context['awaiting_email'] = False
        state.context['awaiting_date'] = False
        return state


class OrderConfirmationHandler:
    """Обработчик подтверждения заказа"""
    
    @staticmethod
    def handle_confirmation_response(state, text, user_data):
        """Обрабатывает ответ на подтверждение"""
        if text == "✅ Да, подтверждаю":
            # Обрабатываем подтверждение заказа
            response = travel_bot.process_message(text, user_data)
            
            if "Билет забронирован!" in response or "Заказ оформлен!" in response:
                # Создаем улучшенное сообщение об успешном оформлении
                success_message = DialogueManager.get_random_phrase('order_confirmed')
                success_message += DialogueManager.get_random_phrase('ticket_generated')
                success_message += "\n\n"
                success_message += f"**Детали заказа:**\n"
                success_message += f"• Направление: {state.context.get('destination', 'Не указано')}\n"
                success_message += f"• Дата: {state.context.get('date_text', 'Не указана')}\n"
                success_message += f"• Сценарий: {state.context.get('scenario_name', 'Не выбран')}\n\n"
                success_message += DialogueManager.get_random_phrase('thank_you')
                success_message += "\n\n"
                success_message += DialogueManager.get_random_phrase('next_steps')
                success_message += "\n\n"
                success_message += DialogueManager.get_random_phrase('special_offer')
                
                return success_message
            return response
        
        elif text == "❌ Нет, отменить":
            return DialogueManager.get_random_phrase('order_cancelled')
        
        return ""


def handle_user_input_flow(message, user_data, text):
    """Обрабатывает поток пользовательского ввода"""
    state = travel_bot.get_state(message.from_user.id)
    
    # Проверяем, ожидаем ли мы email
    if state.context.get('awaiting_email'):
        if text.startswith('email:'):
            email = text.replace('email:', '').strip()
            if '@' in email and '.' in email:
                # Сохраняем email
                state.user_data['email'] = email
                response = f"✅ Email сохранен: {email}\n\n"
                response += "Билет будет отправлен на указанный адрес."
                state.context['awaiting_email'] = False
            else:
                response = "❌ Неверный формат email. Пожалуйста, введите email в формате: email:ваш_email@example.com"
        else:
            response = "Пожалуйста, укажите email в формате: `email:ваш_email@example.com`"
        
        bot.send_message(
            message.chat.id,
            response,
            parse_mode='Markdown',
            reply_markup=CustomReplyKeyboard.create_main_keyboard()
        )
        return True
    
    # Проверяем, ожидаем ли мы дату
    if state.context.get('awaiting_date'):
        if len(text) >= 5:  # Минимальная длина для даты
            state.context['date_text'] = text
            state.context['awaiting_date'] = False
            response = f"📅 Дата выбрана: {text}\n\n"
            response += "Теперь вы можете выбрать сценарий путешествия!"
            
            bot.send_message(
                message.chat.id,
                response,
                parse_mode='Markdown',
                reply_markup=CustomReplyKeyboard.create_main_keyboard()
            )
        else:
            bot.send_message(
                message.chat.id,
                "Пожалуйста, введите дату в текстовом формате (например: '15 января', 'завтра', 'через неделю')",
                reply_markup=CustomReplyKeyboard.create_main_keyboard()
            )
        return True
    
    return False


# Дополнительные хендлеры для специальных случаев
@bot.message_handler(content_types=['text'])
def handle_text_messages(message):
    """Обработчик текстовых сообщений (дублирующий для надежности)"""
    text = message.text
    
    # Если сообщение начинается с email:, обрабатываем отдельно
    if text.startswith('email:'):
        state = travel_bot.get_state(message.from_user.id)
        user_data = {
            'user_id': message.from_user.id,
            'username': message.from_user.username,
            'first_name': message.from_user.first_name,
            'last_name': message.from_user.last_name
        }
        
        email = text.replace('email:', '').strip()
        if '@' in email and '.' in email:
            state.user_data['email'] = email
            response = f"✅ Email сохранен: {email}\n\n"
            response += "Билет будет отправлен на указанный адрес."
        else:
            response = "❌ Неверный формат email. Пожалуйста, введите email в формате: email:ваш_email@example.com"
        
        bot.send_message(
            message.chat.id,
            response,
            parse_mode='Markdown',
            reply_markup=CustomReplyKeyboard.create_main_keyboard()
        )
        return


def setup_bot_handlers():
    """Настраивает дополнительные обработчики бота"""
    
    @bot.message_handler(func=lambda m: m.text in ["📅 Выбрать дату"])
    def handle_custom_date(message):
        """Обработчик выбора даты"""
        state = travel_bot.get_state(message.from_user.id)
        state.context['awaiting_date'] = True
        
        response = "📅 **Введите дату поездки:**\n\n"
        response += "Вы можете указать дату в любом формате:\n"
        response += "• 'завтра'\n"
        response += "• '15 января'\n"
        response += "• 'через неделю'\n"
        response += "• 'на выходные'\n"
        response += "• '1 марта 2024'\n\n"
        response += "Просто напишите дату в чат:"
        
        bot.send_message(
            message.chat.id,
            response,
            parse_mode='Markdown',
            reply_markup=types.ReplyKeyboardRemove()
        )


def main():
    """Основная функция запуска бота"""
    logger.info("Запуск Telegram Travel Bot...")
    
    # Настраиваем дополнительные обработчики
    setup_bot_handlers()
    
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