import random
import re
import aiml
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.svm import LinearSVC
import os
import logging
import difflib
import nltk
from datetime import datetime, timedelta
import json
import sqlite3
from typing import Dict, List, Any

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Инициализация базы данных
def init_database():
    """Инициализация SQLite базы данных для хранения данных"""
    conn = sqlite3.connect('travel_bot.db')
    cursor = conn.cursor()
    
    # Таблица пользователей
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Таблица бронирований
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS bookings (
            booking_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            destination TEXT,
            travel_date TEXT,
            booking_number TEXT UNIQUE,
            status TEXT DEFAULT 'confirmed',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
    ''')
    
    # Таблица промо-акций
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS promo_usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            promo_id INTEGER,
            used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
    ''')
    
    # Таблица сценариев
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS scenario_usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            scenario_id TEXT,
            used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
    ''')
    
    # Таблица выбранных услуг
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS selected_services (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            booking_number TEXT,
            service_id INTEGER,
            service_name TEXT,
            price INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
    ''')
    
    conn.commit()
    conn.close()

# Инициализация базы данных при запуске
init_database()

class DatabaseManager:
    """Менеджер для работы с базой данных"""
    
    @staticmethod
    def save_user(user_data: Dict):
        conn = sqlite3.connect('travel_bot.db')
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT OR REPLACE INTO users (user_id, username, first_name, last_name)
                VALUES (?, ?, ?, ?)
            ''', (user_data['user_id'], user_data.get('username'), 
                  user_data.get('first_name'), user_data.get('last_name')))
            conn.commit()
        except Exception as e:
            logger.error(f"Ошибка сохранения пользователя: {e}")
        finally:
            conn.close()
    
    @staticmethod
    def save_booking(booking_data: Dict):
        conn = sqlite3.connect('travel_bot.db')
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO bookings (user_id, destination, travel_date, booking_number)
                VALUES (?, ?, ?, ?)
            ''', (booking_data['user_id'], booking_data['destination'],
                  booking_data['travel_date'], booking_data['booking_number']))
            conn.commit()
        except Exception as e:
            logger.error(f"Ошибка сохранения бронирования: {e}")
        finally:
            conn.close()
    
    @staticmethod
    def log_promo_usage(user_id: int, promo_id: int):
        conn = sqlite3.connect('travel_bot.db')
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO promo_usage (user_id, promo_id)
                VALUES (?, ?)
            ''', (user_id, promo_id))
            conn.commit()
        except Exception as e:
            logger.error(f"Ошибка логирования промо-акции: {e}")
        finally:
            conn.close()
    
    @staticmethod
    def log_scenario_usage(user_id: int, scenario_id: str):
        conn = sqlite3.connect('travel_bot.db')
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO scenario_usage (user_id, scenario_id)
                VALUES (?, ?)
            ''', (user_id, scenario_id))
            conn.commit()
        except Exception as e:
            logger.error(f"Ошибка логирования сценария: {e}")
        finally:
            conn.close()
    
    @staticmethod
    def save_selected_services(user_id: int, booking_number: str, services: List[Dict]):
        """Сохраняет выбранные услуги в базу данных"""
        conn = sqlite3.connect('travel_bot.db')
        cursor = conn.cursor()
        try:
            for service in services:
                cursor.execute('''
                    INSERT INTO selected_services (user_id, booking_number, service_id, service_name, price)
                    VALUES (?, ?, ?, ?, ?)
                ''', (user_id, booking_number, service['id'], service['name'], service['price']))
            conn.commit()
        except Exception as e:
            logger.error(f"Ошибка сохранения услуг: {e}")
        finally:
            conn.close()

# Инициализация AIML
try:
    kernel = aiml.Kernel()
    
    if os.path.isfile("bot_brain.brn"):
        kernel.bootstrap(brainFile="bot_brain.brn")
        logger.info("AIML brain загружен из файла")
    else:
        # Создание базовых AIML паттернов
        kernel.learn("std-startup.xml")
        kernel.respond("load aiml b")
        kernel.saveBrain("bot_brain.brn")
        logger.info("AIML инициализирован с базовыми паттернами")
except Exception as e:
    logger.error(f"Ошибка инициализации AIML: {e}")
    kernel = None

# Полная конфигурация бота
BOT_CONFIG = {
    'intents': {
        'greeting': {
            'examples': ['привет', 'здравствуй', 'хай', 'добрый день', 'начать', 'start', 'здравствуйте'],
            'responses': ['Привет! Я ваш помощник по путешествиям! 🚂', 'Здравствуйте! Готов помочь с планированием поездки!']
        },
        'mood_good': {
            'examples': ['хорошо', 'отлично', 'прекрасно', 'замечательно', 'нормально', 'супер'],
            'responses': ['Рад слышать!', 'Это прекрасно!']
        },
        'mood_bad': {
            'examples': ['плохо', 'скучно', 'грустно', 'устал', 'не очень', 'ужасно'],
            'responses': ['Понимаю...', 'Жаль это слышать...']
        },
        'travel_interest': {
            'examples': ['хочу путешествие', 'интересно путешествие', 'давай путешествие', 'поехали'],
            'responses': ['Отлично!']
        },
        'destination_moscow': {
            'examples': ['москва', 'мск', 'в москву', 'столица'],
            'responses': ['Москва - отличный выбор! Столица ждет вас!']
        },
        'destination_spb': {
            'examples': ['питер', 'спб', 'санкт-петербург', 'петербург'],
            'responses': ['Санкт-Петербург - культурная столица! Прекрасный выбор!']
        },
        'destination_sochi': {
            'examples': ['сочи', 'в сочи', 'черноморское'],
            'responses': ['Сочи - прекрасный курорт! Идеально для отдыха!']
        },
        'hotel': {
            'examples': ['отель', 'гостиница', 'номер', 'жилье', 'где остановиться'],
            'responses': ['Предлагаем отели разной категории!']
        },
        'insurance': {
            'examples': ['страховка', 'страхование', 'страховку'],
            'responses': ['Важно иметь страховку в путешествии!']
        },
        'food': {
            'examples': ['еда', 'питание', 'ресторан', 'кухня'],
            'responses': ['Закажите питание в поезде или рестораны города!']
        },
        'entertainment': {
            'examples': ['развлечения', 'экскурсия', 'достопримечательности'],
            'responses': ['Много интересных экскурсий ждут вас!']
        },
        'transport': {
            'examples': ['трансфер', 'такси', 'аренда', 'автомобиль'],
            'responses': ['Организуем транспорт в городе!']
        },
        'date_tomorrow': {
            'examples': ['завтра', 'на завтра', 'послезавтра'],
            'responses': ['На завтра есть отличные предложения!']
        },
        'date_weekend': {
            'examples': ['выходные', 'на выходные', 'суббота', 'воскресенье'],
            'responses': ['На выходные всегда есть интересные варианты!']
        },
        'date_specific': {
            'examples': [],
            'responses': ['На указанную дату есть хорошие предложения!']
        },
        'confirm_booking': {
            'examples': ['бронируй', 'оформляй', 'покупай', 'подтверждаю', 'готов', 'готова', 'готово', 'согласен', 'согласна', 'оформить', 'да'],
            'responses': ['Отлично! Оформляю ваши билеты!']
        },
        'positive_response': {
            'examples': ['да', 'конечно', 'разумеется', 'угу', 'ага', 'хочу', 'интересно'],
            'responses': ['Отлично!']
        },
        'negative_response': {
            'examples': ['нет', 'неа', 'не нужно', 'не хочу', 'не интересует', 'пропустим'],
            'responses': ['Понял.']
        },
        'thanks': {
            'examples': ['спасибо', 'благодарю', 'мерси'],
            'responses': ['Пожалуйста! Рад был помочь!']
        },
        'goodbye': {
            'examples': ['пока', 'до свидания', 'прощай', 'всего доброго'],
            'responses': ['До свидания! Хорошего дня!']
        },
        'ticket_inquiry': {
            'examples': ['билеты', 'есть билеты', 'доступны билеты', 'наличие билетов'],
            'responses': ['Проверяю наличие билетов...']
        },
        'promo_interest': {
            'examples': ['акция', 'скидка', 'промо', 'спецпредложение', 'выгодно'],
            'responses': ['Отличный выбор! Расскажу о наших акциях!']
        },
        'promo_selection': {
            'examples': ['1', '2', '3', '4', '5', '6', 'первая', 'вторая', 'третья', 'четвертая', 'пятая', 'шестая'],
            'responses': ['Отлично! Рассказываю подробнее...']
        },
        'show_other_promos': {
            'examples': ['другие', 'другие предложения', 'еще акции', 'следующие', 'показать другие', 'другое'],
            'responses': ['Показываю другие акции...']
        },
        'skip_promos': {
            'examples': ['пропустить', 'не надо', 'хватит', 'достаточно', 'закончить', 'завершить'],
            'responses': ['Хорошо, завершаем с акциями.']
        },
        'view_ticket': {
            'examples': ['билет', 'мой билет', 'покажи билет', 'где билет'],
            'responses': ['Вот ваш электронный билет:']
        }
    },
    'failure_phrases': [
        'Расскажите больше о ваших планах путешествия! 🚂',
        'Может, выберете направление: Москва, Санкт-Петербург или Сочи?',
        'Не совсем понял. Можете уточнить?',
        'Хотите узнать о наших специальных предложениях?'
    ],
    'products': [
        {
            'id': 1,
            'name': 'Билеты на поезд "Стандарт"',
            'category': 'transport',
            'price_range': '1500-3000 руб',
            'description': 'Комфортные места в стандартном вагоне',
            'features': ['Кондиционер', 'Розетки', 'Откидные столики']
        },
        {
            'id': 2,
            'name': 'Билеты на поезд "Комфорт"',
            'category': 'transport',
            'price_range': '3000-5000 руб',
            'description': 'Улучшенные условия в вагоне повышенной комфортности',
            'features': ['Увеличенное пространство', 'Премиум-питание', 'Индивидуальное обслуживание']
        },
        {
            'id': 3,
            'name': 'Отель "Эконом" 3⭐',
            'category': 'accommodation',
            'price_range': '2000-4000 руб/ночь',
            'description': 'Бюджетное размещение с базовыми удобствами',
            'features': ['Wi-Fi', 'Завтрак', 'Холодильник']
        },
        {
            'id': 4,
            'name': 'Отель "Бизнес" 4⭐',
            'category': 'accommodation',
            'price_range': '5000-8000 руб/ночь',
            'description': 'Комфортабельный отель для деловых поездок',
            'features': ['Спа-зона', 'Бизнес-центр', 'Трансфер']
        },
        {
            'id': 5,
            'name': 'Отель "Премиум" 5⭐',
            'category': 'accommodation',
            'price_range': '9000-15000 руб/ночь',
            'description': 'Роскошный отель с премиальным сервисом',
            'features': ['Бассейн', 'Ресторан', 'Консьерж-сервис']
        },
        {
            'id': 6,
            'name': 'Страховка "Базовая"',
            'category': 'insurance',
            'price_range': '500-1000 руб',
            'description': 'Основное медицинское покрытие',
            'features': ['Несчастный случай', 'Медицинские расходы']
        },
        {
            'id': 7,
            'name': 'Страховка "Расширенная"',
            'category': 'insurance',
            'price_range': '1500-2500 руб',
            'description': 'Полное страховое покрытие',
            'features': ['Отмена поездки', 'Потеря багажа', 'Гражданская ответственность']
        },
        {
            'id': 8,
            'name': 'Питание "Стандарт"',
            'category': 'food',
            'price_range': '1000-2000 руб/день',
            'description': 'Трехразовое питание в ресторане отеля',
            'features': ['Шведский стол', 'Напитки включены']
        },
        {
            'id': 9,
            'name': 'Экскурсия "Обзорная"',
            'category': 'entertainment',
            'price_range': '1500-2500 руб',
            'description': 'Обзорная экскурсия по городу',
            'features': ['Профессиональный гид', 'Транспорт', '3-4 часа']
        },
        {
            'id': 10,
            'name': 'Экскурсия "Тематическая"',
            'category': 'entertainment',
            'price_range': '3000-5000 руб',
            'description': 'Специализированная экскурсия',
            'features': ['Эксперт-гид', 'Входные билеты', 'Индивидуальный маршрут']
        },
        {
            'id': 11,
            'name': 'Трансфер "Групповой"',
            'category': 'transport',
            'price_range': '500-1000 руб',
            'description': 'Групповой трансфер из аэропорта/вокзала',
            'features': ['Фиксированное расписание', 'Встреча с табличкой']
        },
        {
            'id': 12,
            'name': 'Трансфер "Индивидуальный"',
            'category': 'transport',
            'price_range': '2000-4000 руб',
            'description': 'Персональный трансфер',
            'features': ['Встреча в зале прилета', 'Детское кресло', 'Комфортный автомобиль']
        }
    ],
    'promotions': [
        {
            'id': 1,
            'short': "🏨 Спецпредложение! При бронировании отеля через нас - скидка 15% на проживание!",
            'full': "🏨 **СПЕЦПРЕДЛОЖЕНИЕ ПО ОТЕЛЯМ!**\n\n• Скидка 15% на все отели категории 3-5 звезд\n• Бесплатный ранний заезд или поздний выезд\n• Комплимент от отеля (фрукты, вино)\n• Бесплатный Wi-Fi на весь период проживания\n\n💡 *Для активации предложения назовите кодовое слово: 'ГОРЯЩИЙ2024'*"
        },
        {
            'id': 2,
            'short': "🛡️ Страховка со скидкой 30%! Полное покрытие на время путешествия!",
            'full': "🛡️ **ВЫГОДНАЯ СТРАХОВКА ДЛЯ ПУТЕШЕСТВЕННИКОВ!**\n\n• Скидка 30% на полис страхования\n• Расширенное покрытие: медицина, багаж, отмена поездки\n• Круглосуточная поддержка на русском языке\n• Быстрое урегулирование страховых случаев\n\n⚡ *Предложение действительно при оплате онлайн*"
        },
        {
            'id': 3,
            'short': "🍽️ Питание включено! Завтраки в отеле бесплатно при раннем бронировании!",
            'full': "🍽️ **ПИТАНИЕ В ПОДАРОК!**\n\n• Бесплатные завтраки 'шведский стол' в отеле\n• Скидка 25% на ужины в ресторанах-партнерах\n• Бесплатный набор напитков в поезде\n• Детское меню со скидкой 50%\n\n🎁 *Забронируйте за 30 дней до поездки и получите максимум выгоды!*"
        },
        {
            'id': 4,
            'short': "🎭 Билеты в театр/кино со скидкой 20% для наших туристов!",
            'full': "🎭 **РАЗВЛЕЧЕНИЯ СО СКИДКОЙ!**\n\n• Скидка 20% на билеты в театры, музеи, кино\n• Бесплатная обзорная экскурсия по городу\n• Приоритетное бронирование популярных экскурсий\n• Специальные цены на развлекательные парки\n\n🏛️ *Покажите электронный билет на поезд для получения скидки*"
        },
        {
            'id': 5,
            'short': "🚗 Трансфер из аэропорта бесплатно при бронировании отеля!",
            'full': "🚗 **КОМФОРТНЫЙ ТРАНСПОРТ!**\n\n• Бесплатный трансфер аэропорт-отель-аэропорт\n• Аренда автомобиля со скидкой 40% на первые 3 дня\n• Скидка 25% на такси по городу\n• Бесплатная парковка в отеле на 2 дня\n\n🏎️ *Для активации предложения забронируйте отель через нашего менеджера*"
        },
        {
            'id': 6,
            'short': "⭐ Бонусная программа! Копите мили за каждую поездку!",
            'full': "⭐ **ПРОГРАММА ЛОЯЛЬНОСТИ 'ПУТЕШЕСТВЕННИК'!**\n\n• 10% кэшбэк бонусными милями за каждую поездку\n• Скидка 10% на следующее путешествие\n• Приоритетное обслуживание 24/7\n• Специальные предложения только для участников\n• Бесплатные апгрейды при накоплении 1000 миль\n\n💎 *Станьте участником программы - это бесплатно!*"
        }
    ],
    'scenarios': {
        'family_vacation': {
            'name': 'Семейный отдых',
            'description': 'Идеальный вариант для отдыха с детьми',
            'products': [1, 3, 6, 9, 11],
            'discount': 15,
            'features': ['Скидка для детей', 'Семейные номера', 'Детское меню']
        },
        'business_trip': {
            'name': 'Деловая поездка',
            'description': 'Все для комфортной бизнес-поездки',
            'products': [2, 4, 7, 12],
            'discount': 10,
            'features': ['Быстрое бронирование', 'Бизнес-услуги', 'Гибкие даты']
        },
        'romantic_getaway': {
            'name': 'Романтическое путешествие',
            'description': 'Незабываемый отдых для пар',
            'products': [2, 5, 7, 10],
            'discount': 12,
            'features': ['Романтический ужин', 'Улучшенный номер', 'Специальные активности']
        },
        'budget_travel': {
            'name': 'Экономный вариант',
            'description': 'Путешествие с максимальной экономией',
            'products': [1, 3, 6, 9],
            'discount': 20,
            'features': ['Раннее бронирование', 'Групповые экскурсии', 'Эконом-размещение']
        },
        'premium_experience': {
            'name': 'Премиум пакет',
            'description': 'Путешествие высшего класса',
            'products': [2, 5, 7, 10, 12],
            'discount': 8,
            'features': ['Индивидуальный гид', 'VIP-обслуживание', 'Эксклюзивные локации']
        }
    }
}

class DialogState:
    def __init__(self, user_id=None):
        self.user_id = user_id
        self.reset()
    
    def reset(self):
        self.current_state = "start"
        self.context = {
            'destination': None,
            'date': None,
            'date_text': None,
            'service_type': None,
            'user_mood': None,
            'booking_confirmed': False,
            'promo_shown': False,
            'awaiting_promo_selection': False,
            'awaiting_scenario_selection': False,
            'promo_cycle_count': 0,
            'ticket_generated': False,
            'booking_number': None,
            'passenger_name': 'Миша Лукин',
            'passenger_email': 'misha@example.com',
            'current_promo_id': None,
            'selected_products': [],
            'current_scenario': None,
            'total_price': 0,
            'used_promos': []
        }
        self.conversation_history = []
        self.current_ticket = None
    
    def add_to_history(self, user_input, bot_response):
        self.conversation_history.append({
            'user': user_input,
            'bot': bot_response,
            'timestamp': datetime.now()
        })
    
    def generate_booking_number(self):
        if not self.context['booking_number']:
            letters = ''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ', k=3))
            numbers = ''.join(random.choices('0123456789', k=6))
            self.context['booking_number'] = f"{letters}-{numbers}"
        return self.context['booking_number']
    
    def add_product(self, product_id):
        """Добавляет товар в корзину"""
        product = next((p for p in BOT_CONFIG['products'] if p['id'] == product_id), None)
        if product and product_id not in self.context['selected_products']:
            self.context['selected_products'].append(product_id)
            self.calculate_total_price()
            return True
        return False
    
    def calculate_total_price(self):
        """Рассчитывает общую стоимость с учетом скидки сценария"""
        base_price = len(self.context['selected_products']) * 2000  # Упрощенный расчет
        discount = 0
        
        if self.context['current_scenario']:
            scenario = BOT_CONFIG['scenarios'][self.context['current_scenario']]
            discount = scenario['discount']
        
        self.context['total_price'] = base_price * (1 - discount / 100)
    
    def apply_scenario(self, scenario_id):
        """Применяет сценарий и добавляет соответствующие товары"""
        if scenario_id in BOT_CONFIG['scenarios']:
            self.context['current_scenario'] = scenario_id
            scenario = BOT_CONFIG['scenarios'][scenario_id]
            
            # Очищаем и добавляем товары сценария
            self.context['selected_products'] = []
            for product_id in scenario['products']:
                self.add_product(product_id)
            
            return True
        return False

    def update_state(self, intent, user_input):
        previous_state = self.current_state
        
        if intent == 'destination_moscow':
            self.context['destination'] = 'Москва'
            self.current_state = "destination_selected"
        elif intent == 'destination_spb':
            self.context['destination'] = 'Санкт-Петербург'
            self.current_state = "destination_selected"
        elif intent == 'destination_sochi':
            self.context['destination'] = 'Сочи'
            self.current_state = "destination_selected"
        elif intent in ['date_tomorrow', 'date_weekend', 'date_specific']:
            self.context['date'] = intent
            self.context['date_text'] = user_input
            if self.context['destination']:
                self.current_state = "ready_for_booking"
            else:
                self.current_state = "date_selected"
        elif intent == 'mood_good':
            self.context['user_mood'] = 'good'
            self.current_state = "mood_known"
        elif intent == 'mood_bad':
            self.context['user_mood'] = 'bad'
            self.current_state = "mood_known"
        elif intent == 'confirm_booking':
            if all([self.context['destination'], self.context['date']]):
                self.current_state = "booking_confirmed"
                self.context['booking_confirmed'] = True
                self.generate_booking_number()
                # Генерируем билет сразу при подтверждении
                self.current_ticket = self.generate_ticket()
            else:
                self.current_state = "need_more_info"
        elif intent == 'positive_response':
            if previous_state == "ready_for_booking":
                self.current_state = "booking_confirmed"
                self.context['booking_confirmed'] = True
                self.generate_booking_number()
                self.current_ticket = self.generate_ticket()
        elif intent == 'promo_interest':
            self.current_state = "showing_promotions"
            self.context['awaiting_promo_selection'] = True
        elif intent == 'promo_selection':
            if self.context['awaiting_promo_selection']:
                self.current_state = "showing_promo_details"
        elif intent == 'show_other_promos':
            if self.context['awaiting_promo_selection']:
                self.current_state = "showing_promotions"
        elif intent == 'skip_promos':
            self.current_state = "promo_completed"
            self.context['awaiting_promo_selection'] = False
        elif intent == 'view_ticket':
            if self.context['booking_confirmed']:
                self.current_state = "showing_ticket"
        
        logger.info(f"Состояние: {previous_state} -> {self.current_state}")
    
    def generate_ticket(self):
        if not self.context['booking_confirmed']:
            return None
            
        booking_number = self.context['booking_number']
        destination = self.context['destination']
        date_text = self.context.get('date_text', 'указанную дату')
        passenger = self.context['passenger_name']
        
        departure_times = {
            'Москва': ['08:30', '12:45', '16:20', '20:15'],
            'Санкт-Петербург': ['09:15', '13:30', '17:45', '21:20'],
            'Сочи': ['07:45', '11:30', '15:15', '19:00']
        }
        
        arrival_times = {
            'Москва': ['14:20', '18:35', '22:10', '02:05'],
            'Санкт-Петербург': ['15:05', '19:20', '23:35', '03:10'],
            'Сочи': ['13:35', '17:20', '21:05', '00:50']
        }
        
        departure_time = random.choice(departure_times.get(destination, ['10:00']))
        arrival_time = random.choice(arrival_times.get(destination, ['16:00']))
        
        train_numbers = {
            'Москва': ['025А', '104С', '228М', '356П'],
            'Санкт-Петербург': ['017Б', '112Р', '245К', '378Н'],
            'Сочи': ['032В', '128Т', '267Л', '394Ф']
        }
        
        train_number = random.choice(train_numbers.get(destination, ['001А']))
        carriage = random.randint(1, 12)
        seat = random.randint(1, 36)
        ticket_price = random.randint(1500, 4500)
        
        stations = {
            'Москва': {'from': 'Станция "Центральная"', 'to': 'Москва (Курский вокзал)'},
            'Санкт-Петербург': {'from': 'Станция "Центральная"', 'to': 'Санкт-Петербург (Московский вокзал)'},
            'Сочи': {'from': 'Станция "Центральная"', 'to': 'Сочи (Железнодорожный вокзал)'}
        }
        
        station_info = stations.get(destination, {'from': 'Станция отправления', 'to': 'Станция назначения'})
        
        # Базовый билет
        ticket = f"""
🎫 ============================================
      ЭЛЕКТРОННЫЙ ЖЕЛЕЗНОДОРОЖНЫЙ БИЛЕТ
============================================ 🎫

📋 НАПРАВЛЕНИЕ:
   🚂 {station_info['from']} → {station_info['to']}

👤 ПАССАЖИР: {passenger}

📅 ДАТА ПОЕЗДКИ: {date_text}
⏰ ВРЕМЯ: {departure_time} - {arrival_time}

🔢 НОМЕР ПОЕЗДА: {train_number}
🚇 ВАГОН: {carriage}
💺 МЕСТО: {seat}

💰 СТОИМОСТЬ БИЛЕТА: {ticket_price} руб.
💳 СТАТУС: ОПЛАЧЕНО ✅

📊 КОД БРОНИРОВАНИЯ: {booking_number}
🆔 ID БИЛЕТА: TK{random.randint(100000, 999999)}
"""
        
        # Добавляем информацию о выбранных услугах, если они есть
        additional_services = []
        total_additional_cost = 0
        
        # Проверяем выбранные продукты в корзине
        if self.context['selected_products']:
            ticket += "\n\n🎁 **ДОПОЛНИТЕЛЬНЫЕ УСЛУГИ:**\n"
            for product_id in self.context['selected_products']:
                product = next((p for p in BOT_CONFIG['products'] if p['id'] == product_id), None)
                if product:
                    service_price = random.randint(500, 2000)  # Примерная цена услуги
                    total_additional_cost += service_price
                    ticket += f"   • {product['name']} - {service_price} руб.\n"
        
        # Проверяем примененный сценарий
        if self.context['current_scenario']:
            scenario = BOT_CONFIG['scenarios'][self.context['current_scenario']]
            ticket += f"\n🎯 **ПАКЕТ УСЛУГ:** {scenario['name']}\n"
            ticket += f"   📝 {scenario['description']}\n"
            ticket += f"   💰 Скидка по пакету: {scenario['discount']}%\n"
        
        # Добавляем информацию о примененных промо-акциях
        if self.context['used_promos']:
            ticket += f"\n🎊 **АКТИВИРОВАННЫЕ АКЦИИ:**\n"
            for promo_id in self.context['used_promos']:
                promo = next((p for p in BOT_CONFIG['promotions'] if p['id'] == promo_id), None)
                if promo:
                    # Извлекаем короткое описание (первую строку)
                    short_desc = promo['short'].split('\n')[0]
                    ticket += f"   • {short_desc}\n"
        # Итоговая стоимость
        total_cost = ticket_price + total_additional_cost
        if total_additional_cost > 0:
            ticket += f"\n💰 **ОБЩАЯ СТОИМОСТЬ:** {total_cost} руб."
            ticket += f"\n   (билет: {ticket_price} руб. + услуги: {total_additional_cost} руб.)"
        else:
            ticket += f"\n💰 **ОБЩАЯ СТОИМОСТЬ:** {total_cost} руб."
        
        # Добавляем стандартную информацию
        ticket += """
        
💡 ПРАВИЛА ПОСАДКИ:
• Прибыть на станцию за 40 минут до отправления
• Иметь при себе документ, удостоверяющий личность
• Распечатать билет или показать на экране устройства

📞 СЛУЖБА ПОДДЕРЖКИ: 8-800-555-35-35

============================================
         СЧАСТЛИВОГО ПУТИ! 🚂✨
============================================
"""
        return ticket

    def get_next_question(self):
        if self.current_state == "booking_confirmed" and not self.context['promo_shown']:
            return None
        
        questions = {
            "start": "Привет! Как ваше настроение сегодня? 🚂",
            "mood_known": {
                'good': "Рад слышать! Хотите отправиться в путешествие? 🚆",
                'bad': "Понимаю... Путешествие поднимет настроение! Хотите поехать? 🚆"
            },
            "interested_in_travel": "Куда хотели бы поехать? (Москва, Санкт-Петербург, Сочи)",
            "destination_selected": f"Отлично - {self.context['destination']}! На когда планируете?",
            "date_selected": "Выберите направление: Москва, Санкт-Петербург или Сочи?",
            "ready_for_booking": "Готовы к бронированию?",
            "need_more_info": "Нужно выбрать направление и дату для бронирования.",
            "showing_promotions": "Выберите номер акции для подробностей (1-6):",
            "showing_promo_details": "Хотите оформить эту услугу, посмотреть другие предложения или завершить? (оформить/другие/завершить)"
        }
        
        question = questions.get(self.current_state)
        if isinstance(question, dict):
            return question.get(self.context['user_mood'], "Хотите путешествие?")
        return question

dialog_state = DialogState()

def get_promo_by_number(number):
    try:
        index = int(number) - 1
        if 0 <= index < len(BOT_CONFIG['promotions']):
            return BOT_CONFIG['promotions'][index]
    except (ValueError, IndexError):
        pass
    return None

def get_promo_response():
    response = "🎉 **СПЕЦИАЛЬНЫЕ ПРЕДЛОЖЕНИЯ!** 🎉\n\n"
    
    for i, promo in enumerate(BOT_CONFIG['promotions'], 1):
        response += f"{i}. {promo['short']}\n"
    
    response += "\n💎 Выберите номер акции (1-6) для подробной информации!"
    return response

def get_other_promos_response():
    response = "🔄 **ДРУГИЕ ПРЕДЛОЖЕНИЯ:**\n\n"
    
    for i, promo in enumerate(BOT_CONFIG['promotions'], 1):
        response += f"{i}. {promo['short']}\n"
    
    response += "\n📋 Выберите номер акции или напишите 'завершить':"
    return response

def clear_phrase(phrase):
    phrase = phrase.lower()
    alphabet = 'абвгдеёжзийклмнопрстуфхцчшщъыьэюя- '
    return ''.join(symbol for symbol in phrase if symbol in alphabet)

def is_date_string(text):
    patterns = [
        r'\b\d{1,2}\.\d{1,2}\.\d{4}\b',
        r'\b\d{1,2}\.\d{1,2}\.\d{2}\b',
        r'\b\d{1,2}\.\d{1,2}\b',
        r'\b\d{1,2}[/-]\d{1,2}[/-]\d{4}\b',
    ]
    if any(re.search(pattern, text.lower()) for pattern in patterns):
        return True
    date_words = ['завтра', 'послезавтра', 'выходные', 'суббота', 'воскресенье']
    return any(word in text.lower() for word in date_words)

def extract_date_type(text):
    text_lower = text.lower()
    if 'завтра' in text_lower or 'послезавтра' in text_lower:
        return 'date_tomorrow'
    elif any(word in text_lower for word in ['выходные', 'суббота', 'воскресенье']):
        return 'date_weekend'
    else:
        return 'date_specific'

def simple_classify_intent(replica):
    replica_lower = replica.lower().strip()
    
    # Проверка просмотра билета
    if any(word in replica_lower for word in ['билет', 'мой билет', 'покажи билет']):
        return 'view_ticket'
    
    # Проверка промо-акций
    if any(word in replica_lower for word in ['другие', 'еще', 'следующие', 'другое']):
        return 'show_other_promos'
    if any(word in replica_lower for word in ['завершить', 'хватит', 'достаточно', 'пропустить']):
        return 'skip_promos'
    if any(word in replica_lower for word in ['оформить', 'брать', 'хочу эту']):
        return 'positive_response'
    
    # Номера промо-акций
    if replica_lower in ['1', '2', '3', '4', '5', '6']:
        return 'promo_selection'
    
    # Даты
    if is_date_string(replica_lower):
        return extract_date_type(replica_lower)
    
    # Подтверждение бронирования
    confirm_keywords = ['готов', 'готова', 'готово', 'бронируй', 'оформляй', 'покупай', 'подтверждаю', 'согласен', 'согласна', 'да']
    if any(keyword in replica_lower for keyword in confirm_keywords):
        return 'confirm_booking'
    
    # Интерес к акциям
    if any(keyword in replica_lower for keyword in ['акция', 'скидка', 'промо', 'спецпредложение']):
        return 'promo_interest'
    
    # Настроение
    mood_keywords = {
        'mood_good': ['хорошо', 'отлично', 'прекрасно', 'замечательно'],
        'mood_bad': ['плохо', 'скучно', 'грустно', 'устал']
    }
    for intent, keywords in mood_keywords.items():
        if any(keyword in replica_lower for keyword in keywords):
            return intent
    
    # Направления
    destination_keywords = {
        'destination_moscow': ['москва', 'мск'],
        'destination_spb': ['питер', 'спб', 'санкт-петербург'],
        'destination_sochi': ['сочи']
    }
    for intent, keywords in destination_keywords.items():
        if any(keyword in replica_lower for keyword in keywords):
            return intent
    
    # Простые ответы
    simple_keywords = {
        'positive_response': ['да', 'конечно', 'угу', 'ага', 'хочу', 'интересно'],
        'negative_response': ['нет', 'неа', 'не хочу', 'не интересует'],
        'thanks': ['спасибо', 'благодарю'],
        'goodbye': ['пока', 'до свидания']
    }
    for intent, keywords in simple_keywords.items():
        if any(keyword in replica_lower for keyword in keywords):
            return intent
    
    return None

def get_contextual_response(intent, user_input, user_id=None):
    dialog_state.update_state(intent, user_input)
    
    # Обработка просмотра билета
    if intent == 'view_ticket':
        if dialog_state.current_ticket:
            response = "🎫 **ВАШ ЭЛЕКТРОННЫЙ БИЛЕТ**\n\n" + dialog_state.current_ticket
            response += "\n📧 Билет также отправлен на вашу электронную почту"
        else:
            response = "❌ Билет еще не оформлен. Давайте сначала завершим бронирование!"
        dialog_state.add_to_history(user_input, response)
        return response
    
    # Обработка промо-акций
    if intent == 'show_other_promos' and dialog_state.context['awaiting_promo_selection']:
        response = get_other_promos_response()
        dialog_state.add_to_history(user_input, response)
        return response
    
    if intent == 'skip_promos':
        if dialog_state.context['booking_confirmed']:
            response = "✅ Хорошо, завершаем с акциями!\n\n"
            response += "🎊 **БРОНИРОВАНИЕ ЗАВЕРШЕНО!**\n\n"
            response += dialog_state.current_ticket if dialog_state.current_ticket else "Билет будет готов скоро!"
            response += "\n\n🌟 Желаем приятного путешествия! 🚂✨"
        else:
            response = "✅ Хорошо, завершаем с акциями!"
        
        dialog_state.context['awaiting_promo_selection'] = False
        dialog_state.add_to_history(user_input, response)
        return response
    
    if intent == 'promo_selection' and dialog_state.context['awaiting_promo_selection']:
        promo = get_promo_by_number(user_input)
        if promo:
            response = "✅ **ВЫБРАНА АКЦИЯ!**\n\n" + promo['full']
            response += "\n\n🎯 Хотите оформить эту услугу, посмотреть другие предложения или завершить? (оформить/другие/завершить)"
            dialog_state.context['current_promo_id'] = promo['id']
            dialog_state.add_to_history(user_input, response)
            return response
    
    # Основное подтверждение бронирования
    if dialog_state.current_state == "booking_confirmed" and not dialog_state.context['promo_shown']:
        dialog_state.context['promo_shown'] = True
        dialog_state.context['awaiting_promo_selection'] = True
        
        response = "🎉 **ПОЗДРАВЛЯЕМ С УСПЕШНЫМ БРОНИРОВАНИЕМ!** 🎉\n\n"
        details = f"📍 Направление: {dialog_state.context['destination']}"
        if dialog_state.context['date_text']:
            details += f"\n📅 Дата: {dialog_state.context['date_text']}"
        details += f"\n🔢 Номер брони: {dialog_state.context['booking_number']}"
        
        response += details + "\n\n"
        response += get_promo_response()
        
        # Сохраняем бронирование в БД
        if user_id:
            DatabaseManager.save_booking({
                'user_id': user_id,
                'destination': dialog_state.context['destination'],
                'travel_date': dialog_state.context['date_text'],
                'booking_number': dialog_state.context['booking_number']
            })
            
            # Сохраняем выбранные услуги в БД
            if dialog_state.context['selected_products']:
                services_to_save = []
                for product_id in dialog_state.context['selected_products']:
                    product = next((p for p in BOT_CONFIG['products'] if p['id'] == product_id), None)
                    if product:
                        service_price = random.randint(500, 2000)
                        services_to_save.append({
                            'id': product_id,
                            'name': product['name'],
                            'price': service_price
                        })
                
                DatabaseManager.save_selected_services(
                    user_id, 
                    dialog_state.context['booking_number'], 
                    services_to_save
                )
        
        dialog_state.add_to_history(user_input, response)
        return response
    
    # Оформление выбранной услуги
    if intent == 'positive_response' and dialog_state.context['awaiting_promo_selection']:
        if dialog_state.context['current_promo_id']:
            promo = next((p for p in BOT_CONFIG['promotions'] if p['id'] == dialog_state.context['current_promo_id']), None)
            if promo:
                response = f"✅ Отлично! Оформляю выбранную услугу!\n\n"
                response += f"🎊 **{promo['short']}**\n\n"
                response += f"📋 Услуга добавлена к вашему заказу {dialog_state.context['booking_number']}!\n\n"
                response += "💎 Хотите посмотреть другие предложения или завершить? (другие/завершить)"
                
                # Логируем использование промо-акции
                if user_id:
                    DatabaseManager.log_promo_usage(user_id, promo['id'])
                
                # Добавляем в список использованных промо-акций
                if promo['id'] not in dialog_state.context['used_promos']:
                    dialog_state.context['used_promos'].append(promo['id'])
                
                dialog_state.add_to_history(user_input, response)
                return response
    
    # Базовые ответы из конфига
    if intent in BOT_CONFIG['intents']:
        base_response = random.choice(BOT_CONFIG['intents'][intent]['responses'])
    else:
        base_response = random.choice(BOT_CONFIG['failure_phrases'])
    
    # Специальная обработка дат
    if intent.startswith('date_'):
        date_responses = {
            'date_tomorrow': "Отлично! На завтра есть отличные варианты!",
            'date_weekend': "Прекрасно! На выходные подберу лучшие предложения!",
            'date_specific': "Замечательно! На указанную дату есть хорошие варианты!"
        }
        base_response = date_responses.get(intent, base_response)
    
    # Добавление следующего вопроса
    next_question = dialog_state.get_next_question()
    if next_question:
        response = base_response
        if not response.endswith(('!', '.', '?')):
            response += "!"
        response += " " + next_question
    else:
        response = base_response
    
    dialog_state.add_to_history(user_input, response)
    return response

def enhanced_aiml_response(replica):
    """Улучшенная обработка AIML с контекстуальными ответами"""
    if not kernel:
        return None
    
    try:
        # Предварительная обработка реплики для AIML
        processed_replica = replica.upper().strip()
        
        # Получаем ответ от AIML
        aiml_response = kernel.respond(processed_replica)
        
        # Проверяем, является ли ответ осмысленным
        if aiml_response and aiml_response.strip() and not aiml_response.startswith('#'):
            logger.info(f"AIML ответ: '{aiml_response}'")
            return aiml_response
        
    except Exception as e:
        logger.error(f"Ошибка AIML: {e}")
    
    return None

def get_products_by_category(category):
    """Возвращает товары по категории"""
    return [p for p in BOT_CONFIG['products'] if p['category'] == category]

def get_scenario_description(scenario_id):
    """Возвращает описание сценария"""
    scenario = BOT_CONFIG['scenarios'].get(scenario_id, {})
    products = [p['name'] for p in BOT_CONFIG['products'] if p['id'] in scenario.get('products', [])]
    
    description = f"**{scenario.get('name', '')}**\n\n"
    description += f"{scenario.get('description', '')}\n\n"
    description += f"📦 **Включает:**\n" + "\n".join(f"• {product}" for product in products)
    description += f"\n\n💰 **Скидка:** {scenario.get('discount', 0)}%"
    description += f"\n🎁 **Особенности:**\n" + "\n".join(f"• {feature}" for feature in scenario.get('features', []))
    
    return description

def get_scenarios_list():
    """Возвращает список всех сценариев"""
    scenarios_text = "🎯 **ДОСТУПНЫЕ СЦЕНАРИИ ПУТЕШЕСТВИЙ:**\n\n"
    
    for i, (scenario_id, scenario) in enumerate(BOT_CONFIG['scenarios'].items(), 1):
        scenarios_text += f"{i}. **{scenario['name']}**\n"
        scenarios_text += f"   {scenario['description']}\n"
        scenarios_text += f"   💰 Скидка: {scenario['discount']}%\n\n"
    
    scenarios_text += "Выберите номер сценария для подробной информации (1-5):"
    return scenarios_text

def get_cart_summary():
    """Возвращает сводку корзины"""
    if not dialog_state.context['selected_products']:
        return "🛒 Ваша корзина пуста."
    
    summary = "🛒 **ВАША КОРЗИНА:**\n\n"
    total_price = 0
    
    for product_id in dialog_state.context['selected_products']:
        product = next((p for p in BOT_CONFIG['products'] if p['id'] == product_id), None)
        if product:
            price = random.randint(500, 2000)
            total_price += price
            summary += f"• {product['name']} - {price} руб.\n"
    
    # Применяем скидку сценария
    if dialog_state.context['current_scenario']:
        scenario = BOT_CONFIG['scenarios'][dialog_state.context['current_scenario']]
        discount = scenario['discount']
        discount_amount = total_price * discount / 100
        final_price = total_price - discount_amount
        
        summary += f"\n💎 **Скидка по сценарию '{scenario['name']}':** -{discount}% (-{discount_amount:.0f} руб.)"
        summary += f"\n💰 **Итоговая стоимость:** {final_price:.0f} руб."
    else:
        summary += f"\n💰 **Общая стоимость:** {total_price} руб."
    
    return summary

def advanced_bot(replica, user_id=None, user_data=None):
    """Усовершенствованная версия бота с полной интеграцией AIML"""
    
    # Сохраняем пользователя в БД
    if user_id and user_data:
        DatabaseManager.save_user({
            'user_id': user_id,
            'username': user_data.get('username'),
            'first_name': user_data.get('first_name'),
            'last_name': user_data.get('last_name')
        })
    
    logger.info(f"Пользователь {user_id}: '{replica}'")
    
    # Специальные команды
    if replica.lower() in ['сброс', 'reset', 'начать заново']:
        dialog_state.reset()
        return "🔄 Диалог сброшен. Давайте начнем сначала! Как ваше настроение сегодня? 🚂"
    
    if replica.lower() in ['история', 'history']:
        history_text = "📜 Последние реплики:\n"
        for msg in dialog_state.conversation_history[-5:]:
            history_text += f"👤 Вы: {msg['user']}\n"
            history_text += f"🤖 Бот: {msg['bot'][:50]}...\n\n"
        return history_text + f"📍 Текущее состояние: {dialog_state.current_state}"
    
    if replica.lower() in ['помощь', 'help']:
        return """🆘 **КОМАНДЫ ПОМОЩИ:**
• 'сброс' - начать новый диалог
• 'история' - показать историю диалога  
• 'билет' - показать электронный билет
• 'сценарии' - показать готовые пакеты путешествий
• 'корзина' - показать выбранные товары
• 'помощь' - показать эту справку"""

    # Обработка сценариев
    if replica.lower() in ['сценарии', 'scenarios', 'пакеты', 'packages']:
        dialog_state.context['awaiting_scenario_selection'] = True
        return get_scenarios_list()
    
    # Обработка выбора сценария
    if dialog_state.context['awaiting_scenario_selection'] and replica in ['1', '2', '3', '4', '5']:
        scenario_ids = list(BOT_CONFIG['scenarios'].keys())
        try:
            scenario_index = int(replica) - 1
            if 0 <= scenario_index < len(scenario_ids):
                scenario_id = scenario_ids[scenario_index]
                if dialog_state.apply_scenario(scenario_id):
                    # Логируем использование сценария
                    if user_id:
                        DatabaseManager.log_scenario_usage(user_id, scenario_id)
                    
                    response = "✅ **СЦЕНАРИЙ ВЫБРАН!**\n\n"
                    response += get_scenario_description(scenario_id)
                    response += f"\n\n{get_cart_summary()}"
                    response += "\n\nХотите продолжить с этим сценарием? (да/нет)"
                    dialog_state.context['awaiting_scenario_selection'] = False
                    return response
        except ValueError:
            pass
    
    # Обработка корзины товаров
    if replica.lower() in ['корзина', 'cart', 'мои товары']:
        return get_cart_summary()

    # Пробуем AIML в первую очередь для естественного диалога
    aiml_response = enhanced_aiml_response(replica)
    if aiml_response:
        dialog_state.add_to_history(replica, aiml_response)
        return aiml_response

    # Если AIML не сработал, используем классическую логику
    intent = simple_classify_intent(replica)
    
    logger.info(f"Выбран интент: '{intent}' (состояние: {dialog_state.current_state})")
    
    if intent:
        response = get_contextual_response(intent, replica, user_id)
        return response
    
    # Ответ по умолчанию с использованием AIML
    default_aiml = enhanced_aiml_response("что сказать")
    if default_aiml:
        response = default_aiml
    else:
        context_aware_failures = {
            "start": "Расскажите, как ваше настроение? 😊",
            "mood_known": "Хотите отправиться в путешествие? 🚆", 
            "interested_in_travel": "Выберите направление: Москва, Санкт-Петербург или Сочи?",
            "destination_selected": "На когда планируете поездку?",
            "ready_for_booking": "Готовы к бронированию?",
            "showing_promotions": "Выберите номер акции для подробностей (1-6)",
            "showing_promo_details": "Хотите оформить эту услугу, посмотреть другие предложения или завершить? (оформить/другие/завершить)"
        }
        
        response = context_aware_failures.get(
            dialog_state.current_state, 
            random.choice(BOT_CONFIG['failure_phrases'])
        )
    
    logger.info(f"Не распознано, ответ по умолчанию: '{response}'")
    dialog_state.add_to_history(replica, response)
    return response

# Глобальный объект состояния диалога
dialog_state = DialogState()

if __name__ == "__main__":
    print("🚂 Усовершенствованный бот-помощник по путешествиям запущен!")
    print("💡 Новые команды: 'сценарии', 'корзина', 'товары'")
    print("🎯 Доступно сценариев:", len(BOT_CONFIG['scenarios']))
    print("🛍️ Доступно товаров:", len(BOT_CONFIG['products']))
    print("🧠 AIML активирован с расширенными паттернами")
    print("💾 База данных инициализирована")
    print("=" * 50)
    
    while True:
        try:
            user_input = input("👤 Вы: ").strip()
            if not user_input:
                continue
                
            if user_input.lower() in ['стоп', 'выход', 'exit', 'quit']:
                print("🤖 Бот: До свидания! Хорошего дня! 👋")
                break
                
            response = advanced_bot(user_input)
            print(f"🤖 Бот: {response}")
            print("-" * 50)
            
        except KeyboardInterrupt:
            print("\n🤖 Бот: Работа завершена. До свидания! 👋")
            break
        except Exception as e:
            print(f"🤖 Бот: Произошла ошибка: {e}")
            logger.error(f"Ошибка в основном цикле: {e}")