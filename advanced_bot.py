"""
Основная логика бота путешествий
"""

import random
import re
import sqlite3
from datetime import datetime, timedelta
import logging
from typing import Dict, List, Any, Optional
from config import BOT_CONFIG, DATABASE_NAME, LOG_FILE, LOG_LEVEL

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

# Инициализация базы данных
def init_database():
    """Инициализация SQLite базы данных для хранения данных"""
    conn = sqlite3.connect(DATABASE_NAME)
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
            total_price REAL,
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
            booking_number TEXT,
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
            booking_number TEXT,
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
            price REAL,
            category TEXT,
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
        """Сохраняет пользователя в базу данных"""
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT OR REPLACE INTO users (user_id, username, first_name, last_name)
                VALUES (?, ?, ?, ?)
            ''', (
                user_data['user_id'], 
                user_data.get('username'), 
                user_data.get('first_name'), 
                user_data.get('last_name')
            ))
            conn.commit()
        except Exception as e:
            logger.error(f"Ошибка сохранения пользователя: {e}")
        finally:
            conn.close()
    
    @staticmethod
    def save_booking(booking_data: Dict):
        """Сохраняет бронирование в базу данных"""
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO bookings 
                (user_id, destination, travel_date, booking_number, total_price)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                booking_data['user_id'], 
                booking_data['destination'],
                booking_data['travel_date'], 
                booking_data['booking_number'],
                booking_data.get('total_price', 0)
            ))
            conn.commit()
        except Exception as e:
            logger.error(f"Ошибка сохранения бронирования: {e}")
        finally:
            conn.close()
    
    @staticmethod
    def save_selected_services(user_id: int, booking_number: str, services: List[Dict]):
        """Сохраняет выбранные услуги в базу данных"""
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()
        try:
            for service in services:
                cursor.execute('''
                    INSERT INTO selected_services 
                    (user_id, booking_number, service_id, service_name, price, category)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    user_id, booking_number, 
                    service['id'], service['name'], 
                    service['price'], service.get('category', 'other')
                ))
            conn.commit()
        except Exception as e:
            logger.error(f"Ошибка сохранения услуг: {e}")
        finally:
            conn.close()
    
    @staticmethod
    def save_scenario_usage(user_id: int, scenario_id: str, booking_number: str):
        """Сохраняет использование сценария"""
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO scenario_usage (user_id, scenario_id, booking_number)
                VALUES (?, ?, ?)
            ''', (user_id, scenario_id, booking_number))
            conn.commit()
        except Exception as e:
            logger.error(f"Ошибка сохранения использования сценария: {e}")
        finally:
            conn.close()
    
    @staticmethod
    def save_promo_usage(user_id: int, promo_id: int, booking_number: str):
        """Сохраняет использование промо-акции"""
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO promo_usage (user_id, promo_id, booking_number)
                VALUES (?, ?, ?)
            ''', (user_id, promo_id, booking_number))
            conn.commit()
        except Exception as e:
            logger.error(f"Ошибка сохранения использования промо-акции: {e}")
        finally:
            conn.close()


class IntentClassifier:
    """Классификатор намерений на основе ключевых слов"""
    
    def __init__(self, config):
        self.config = config
        self.intent_keywords = self._build_intent_keywords()
    
    def _build_intent_keywords(self):
        """Строит словарь ключевых слов для каждого намерения"""
        intent_keywords = {}
        for intent, data in self.config['intents'].items():
            keywords = []
            for example in data.get('examples', []):
                keywords.extend(example.lower().split())
            intent_keywords[intent] = list(set(keywords))
        return intent_keywords
    
    def get_intent(self, text: str) -> Optional[str]:
        """Определяет намерение на основе ключевых слов"""
        text_lower = text.lower()
        
        # Проверяем специальные команды
        for intent, data in self.config['intents'].items():
            for example in data.get('examples', []):
                if example.lower() in text_lower:
                    return intent
        
        # Если не нашли точное совпадение, ищем по ключевым словам
        best_match = None
        best_score = 0
        
        for intent, keywords in self.intent_keywords.items():
            score = sum(1 for keyword in keywords if keyword in text_lower)
            if score > best_score:
                best_score = score
                best_match = intent
        
        return best_match if best_score > 0 else None


class DialogState:
    """Класс для управления состоянием диалога"""
    
    def __init__(self, user_id=None):
        self.user_id = user_id
        self.reset()
    
    def reset(self, clear_cart=False):
        """Сброс состояния диалога"""
        self.current_state = "start"
        
        # Сохраняем корзину если не очищаем
        cart_items = []
        if not clear_cart and hasattr(self, 'context'):
            cart_items = self.context.get('cart_items', [])
        
        self.context = {
            'destination': None,
            'date': None,
            'date_text': None,
            'booking_confirmed': False,
            'awaiting_promo_selection': False,
            'awaiting_scenario_selection': False,
            'awaiting_date_selection': False,
            'awaiting_destination_selection': False,
            'awaiting_confirmation': False,
            'awaiting_order_confirmation': False,
            'booking_number': None,
            'passenger_name': 'Миша Лукин',
            'passenger_email': 'misha@example.com',
            'selected_products': [],  # ID продуктов
            'selected_promos': [],    # ID промо-акций
            'current_scenario': None,
            'total_price': 0,
            'cart_items': cart_items,
            'ticket_details': None,
            'order_summary': None
        }
        self.conversation_history = []
    
    def add_to_history(self, user_input: str, bot_response: str):
        """Добавляет сообщение в историю диалога"""
        self.conversation_history.append({
            'user': user_input,
            'bot': bot_response,
            'timestamp': datetime.now()
        })
    
    def generate_booking_number(self) -> str:
        """Генерирует уникальный номер бронирования"""
        if not self.context['booking_number']:
            letters = ''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ', k=3))
            numbers = ''.join(random.choices('0123456789', k=6))
            self.context['booking_number'] = f"{letters}-{numbers}"
        return self.context['booking_number']
    
    def add_to_cart(self, item_type: str, item_id: Any, item_data=None) -> bool:
        """Добавляет товар в корзину"""
        cart_item = {
            'type': item_type,  # 'product', 'promo', 'ticket'
            'id': item_id,
            'added_at': datetime.now(),
            'data': item_data or {}
        }
        
        # Проверяем, нет ли уже такого товара
        for item in self.context['cart_items']:
            if item['type'] == item_type and item['id'] == item_id:
                return False
        
        self.context['cart_items'].append(cart_item)
        self.update_total_price()
        return True
    
    def remove_from_cart(self, item_type: str, item_id: Any) -> bool:
        """Удаляет товар из корзины"""
        for i, item in enumerate(self.context['cart_items']):
            if item['type'] == item_type and item['id'] == item_id:
                del self.context['cart_items'][i]
                self.update_total_price()
                return True
        return False
    
    def clear_cart(self) -> bool:
        """Очищает корзину"""
        self.context['cart_items'] = []
        self.context['total_price'] = 0
        self.context['current_scenario'] = None
        return True
    
    def update_total_price(self) -> float:
        """Пересчитывает общую стоимость корзины"""
        total = 0
        
        for item in self.context['cart_items']:
            if item['type'] == 'product':
                product = next((p for p in BOT_CONFIG['products'] if p['id'] == item['id']), None)
                if product:
                    total += product.get('base_price', 0)
            elif item['type'] == 'ticket' and 'price' in item['data']:
                total += item['data']['price']
        
        # Применяем скидку сценария
        if self.context['current_scenario']:
            scenario = BOT_CONFIG['scenarios'][self.context['current_scenario']]
            discount = scenario['discount']
            total = total * (1 - discount / 100)
        
        self.context['total_price'] = round(total, 2)
        return self.context['total_price']
    
    def get_cart_summary(self) -> Dict:
        """Получает сводку по корзине"""
        products = []
        promos = []
        tickets = []
        
        for item in self.context['cart_items']:
            if item['type'] == 'product':
                product = next((p for p in BOT_CONFIG['products'] if p['id'] == item['id']), None)
                if product:
                    products.append(product)
            elif item['type'] == 'promo':
                promo = next((p for p in BOT_CONFIG['promotions'] if p['id'] == item['id']), None)
                if promo:
                    promos.append(promo)
            elif item['type'] == 'ticket':
                tickets.append(item['data'])
        
        return {
            'products': products,
            'promos': promos,
            'tickets': tickets,
            'total_price': self.context['total_price'],
            'item_count': len(self.context['cart_items'])
        }
    
    def apply_scenario(self, scenario_id: str) -> bool:
        """Применяет сценарий"""
        if scenario_id in BOT_CONFIG['scenarios']:
            self.context['current_scenario'] = scenario_id
            scenario = BOT_CONFIG['scenarios'][scenario_id]
            
            # Очищаем продукты и добавляем продукты сценария
            self.context['cart_items'] = [item for item in self.context['cart_items'] 
                                         if item['type'] != 'product']
            
            for product_id in scenario['products']:
                self.add_to_cart('product', product_id)
            
            # Добавляем билет
            ticket_data = self.generate_ticket_data()
            if ticket_data:
                # Удаляем старый билет если есть
                self.context['cart_items'] = [item for item in self.context['cart_items'] 
                                            if item['type'] != 'ticket']
                self.add_to_cart('ticket', f"ticket_{self.generate_booking_number()}", ticket_data)
            
            self.update_total_price()
            return True
        return False
    
    def generate_ticket_data(self) -> Optional[Dict]:
        """Генерирует данные билета"""
        if not self.context['destination'] or not self.context['date_text']:
            return None
        
        booking_number = self.generate_booking_number()
        ticket_price = random.randint(1500, 4500)
        
        departure_times = {
            'Москва': ['08:30', '12:45', '16:20', '20:15'],
            'Санкт-Петербург': ['09:15', '13:30', '17:45', '21:00'],
            'Сочи': ['07:00', '14:20', '19:10']
        }
        
        arrival_times = {
            'Москва': ['14:25', '18:40', '22:15', '02:00+1'],
            'Санкт-Петербург': ['15:45', '20:00', '00:15+1', '03:30+1'],
            'Сочи': ['23:40', '07:00+1', '11:50+1']
        }
        
        train_numbers = {
            'Москва': ['001А', '034С', '078Ф', '105В'],
            'Санкт-Петербург': ['012Д', '045М', '089Р', '112Т'],
            'Сочи': ['023К', '067Н', '098П']
        }
        
        dest = self.context['destination']
        idx = random.randint(0, min(
            len(departure_times.get(dest, ['08:00'])) - 1,
            len(arrival_times.get(dest, ['14:00'])) - 1,
            len(train_numbers.get(dest, ['000'])) - 1
        ))
        
        ticket_data = {
            'booking_number': booking_number,
            'destination': dest,
            'date': self.context['date_text'],
            'passenger': self.context['passenger_name'],
            'train_number': train_numbers[dest][idx],
            'departure_time': departure_times[dest][idx],
            'arrival_time': arrival_times[dest][idx],
            'wagon': random.randint(1, 15),
            'seat': random.randint(1, 36),
            'price': ticket_price,
            'created_at': datetime.now().strftime("%d.%m.%Y %H:%M")
        }
        
        return ticket_data


class TravelBot:
    """Основной класс бота путешествий"""
    
    def __init__(self):
        self.config = BOT_CONFIG
        self.classifier = IntentClassifier(self.config)
        self.states = {}
        logger.info("Бот путешествий инициализирован")
    
    def get_state(self, user_id: int) -> DialogState:
        """Получение состояния диалога для пользователя"""
        if user_id not in self.states:
            self.states[user_id] = DialogState(user_id)
        return self.states[user_id]
    
    def process_message(self, user_input: str, user_data: Dict = None) -> str:
        """Обработка сообщения пользователя"""
        if not user_input or not user_input.strip():
            return "Пожалуйста, напишите что-нибудь! ✍️"
        
        user_input = user_input.strip()
        
        # Сохранение данных пользователя
        if user_data:
            DatabaseManager.save_user(user_data)
            user_id = user_data['user_id']
        else:
            user_id = 1  # Значение по умолчанию для тестирования
        
        state = self.get_state(user_id)
        state.add_to_history(user_input, "")
        
        # Проверка на специальные команды
        special_response = self._handle_special_commands(user_input, state)
        if special_response:
            return special_response
        
        # Проверка на ожидание подтверждения заказа
        if state.context.get('awaiting_order_confirmation'):
            return self._handle_order_confirmation(user_input, state, user_id)
        
        # Проверка на ожидание подтверждения бронирования
        if state.context.get('awaiting_confirmation'):
            return self._handle_booking_confirmation(user_input, state, user_id)
        
        # Проверка на выбор сценария
        if state.context['awaiting_scenario_selection']:
            return self._handle_scenario_selection(user_input, state, user_id)
        
        # Проверка на выбор промо-акции
        if state.context['awaiting_promo_selection']:
            return self._handle_promo_selection(user_input, state, user_id)
        
        # Проверка на выбор даты
        if state.context['awaiting_date_selection']:
            return self._handle_date_selection(user_input, state)
        
        # Проверка на выбор направления
        if state.context['awaiting_destination_selection']:
            return self._handle_destination_selection(user_input, state)
        
        # Определение намерения
        intent = self.classifier.get_intent(user_input)
        
        # Обработка намерения
        response = self._generate_response(intent, user_input, state, user_id)
        
        return response
    
    def _handle_special_commands(self, user_input: str, state: DialogState) -> Optional[str]:
        """Обработка специальных команд"""
        user_input_lower = user_input.lower()
        
        if user_input_lower == 'сброс':
            state.reset(clear_cart=True)
            return "Состояние диалога сброшено. Начнем заново! 🔄"
        
        elif user_input_lower in ['корзина', 'моя корзина', 'посмотреть корзину']:
            return self.show_cart(state)
        
        elif user_input_lower == 'оформить заказ':
            return self.process_order(state)
        
        elif user_input_lower == 'очистить корзину':
            state.clear_cart()
            return "🛒 Корзина очищена! Теперь вы можете добавить новые товары."
        
        elif user_input_lower in ['сценарии', 'типы поездок']:
            if state.context['destination'] and state.context['date_text']:
                state.context['awaiting_scenario_selection'] = True
                return self._show_scenarios(state, short=True)
            else:
                return "Сначала выберите направление и дату, чтобы увидеть подходящие сценарии! 🗺️"
        
        elif user_input_lower == 'акции':
            state.context['awaiting_promo_selection'] = True
            return self._show_promotions(state)
        
        elif user_input_lower == 'мой билет':
            cart_summary = state.get_cart_summary()
            if cart_summary['tickets']:
                return self.show_ticket(state)
            else:
                return "В корзине нет билета. Сначала выберите сценарий путешествия! 🎫"
        
        elif user_input_lower == 'продолжить бронирование':
            cart_summary = state.get_cart_summary()
            if cart_summary['item_count'] > 0:
                return self.show_cart(state)
            else:
                return "Корзина пуста. Начните новое бронирование! 🚂"
        
        return None
    
    def _handle_scenario_selection(self, user_input: str, state: DialogState, user_id: int) -> str:
        """Обработка выбора сценария"""
        scenarios = self.config['scenarios']
        user_input_lower = user_input.lower().strip()
        
        # Пробуем распознать номер сценария (1-5)
        try:
            scenario_num = int(user_input_lower)
            if 1 <= scenario_num <= len(scenarios):
                scenario_keys = list(scenarios.keys())
                scenario_id = scenario_keys[scenario_num - 1]
                
                state.apply_scenario(scenario_id)
                state.context['awaiting_scenario_selection'] = False
                
                scenario_data = scenarios[scenario_id]
                response = f"✅ **Выбран сценарий: {scenario_data['name']}**\n\n"
                response += f"📝 {scenario_data['description']}\n\n"
                response += f"💰 **Скидка по сценарию: {scenario_data['discount']}%**\n\n"
                response += "🛍️ **В корзину добавлены:**\n"
                
                cart_summary = state.get_cart_summary()
                for product in cart_summary['products']:
                    response += f"• {product['name']} - {product.get('base_price', 0)} руб.\n"
                
                if cart_summary['tickets']:
                    for ticket in cart_summary['tickets']:
                        response += f"• Билет {ticket['destination']} - {ticket['price']} руб.\n"
                
                response += f"\n💵 **Общая стоимость: {cart_summary['total_price']:.2f} руб.**\n\n"
                response += "✅ Добавить в корзину и продолжить?"
                
                state.context['awaiting_confirmation'] = True
                return response
        except ValueError:
            pass
        
        # Если не число, ищем по названию
        for scenario_id, scenario_data in scenarios.items():
            if scenario_data['name'].lower() in user_input_lower:
                state.apply_scenario(scenario_id)
                state.context['awaiting_scenario_selection'] = False
                
                response = f"✅ **Выбран сценарий: {scenario_data['name']}**\n\n"
                response += f"📝 {scenario_data['description']}\n\n"
                response += f"💰 **Скидка по сценарию: {scenario_data['discount']}%**\n\n"
                response += "🛍️ **В корзину добавлены:**\n"
                
                cart_summary = state.get_cart_summary()
                for product in cart_summary['products']:
                    response += f"• {product['name']} - {product.get('base_price', 0)} руб.\n"
                
                if cart_summary['tickets']:
                    for ticket in cart_summary['tickets']:
                        response += f"• Билет {ticket['destination']} - {ticket['price']} руб.\n"
                
                response += f"\n💵 **Общая стоимость: {cart_summary['total_price']:.2f} руб.**\n\n"
                response += "✅ Добавить в корзину и продолжить?"
                
                state.context['awaiting_confirmation'] = True
                return response
        
        return "Пожалуйста, выберите сценарий из предложенных. Введите номер (1-5) или название."
    
    def _handle_promo_selection(self, user_input: str, state: DialogState, user_id: int) -> str:
        """Обработка выбора промо-акции"""
        try:
            promo_num = int(user_input.strip())
            if 1 <= promo_num <= len(self.config['promotions']):
                promo = self.config['promotions'][promo_num - 1]
                
                # Добавляем промо-акцию в корзину
                state.add_to_cart('promo', promo['id'], promo)
                state.context['awaiting_promo_selection'] = False
                
                response = f"✅ **Добавлена акция: {promo['short']}**\n\n"
                response += f"{promo['full']}\n\n"
                
                cart_summary = state.get_cart_summary()
                if cart_summary['item_count'] > 0:
                    response += f"🛒 В корзине: {cart_summary['item_count']} товаров\n"
                    response += f"💵 Общая стоимость: {cart_summary['total_price']:.2f} руб.\n\n"
                
                response += "Хотите добавить еще акции? (да/нет)"
                state.context['awaiting_confirmation'] = True
                return response
        except ValueError:
            pass
        
        return "Пожалуйста, введите номер акции от 1 до 6."
    
    def _handle_date_selection(self, user_input: str, state: DialogState) -> str:
        """Обработка выбора даты"""
        state.context['date_text'] = user_input
        state.context['awaiting_date_selection'] = False
        
        if state.context['destination']:
            state.context['awaiting_scenario_selection'] = True
            response = f"📅 **Дата поездки: {user_input}**\n"
            response += f"📍 **Направление: {state.context['destination']}**\n\n"
            response += "Теперь выберите тип путешествия:\n\n"
            response += self._show_scenarios(state, short=True)
        else:
            state.context['awaiting_destination_selection'] = True
            response = "📅 Отлично! Теперь выберите направление:\n"
            response += "1. Москва 🏙️\n2. Санкт-Петербург 🏛️\n3. Сочи 🌴\n\n"
            response += "Или напишите свой вариант!"
        
        return response
    
    def _handle_destination_selection(self, user_input: str, state: DialogState) -> str:
        """Обработка выбора направления"""
        user_input_lower = user_input.lower()
        
        destinations = {
            'москва': 'Москва',
            'мск': 'Москва',
            'питер': 'Санкт-Петербург',
            'спб': 'Санкт-Петербург',
            'санкт-петербург': 'Санкт-Петербург',
            'петербург': 'Санкт-Петербург',
            'сочи': 'Сочи'
        }
        
        for key, value in destinations.items():
            if key in user_input_lower:
                state.context['destination'] = value
                break
        
        if not state.context['destination']:
            state.context['destination'] = user_input
        
        state.context['awaiting_destination_selection'] = False
        
        if state.context['date_text']:
            state.context['awaiting_scenario_selection'] = True
            response = f"📍 **Направление: {state.context['destination']}**\n"
            response += f"📅 **Дата: {state.context['date_text']}**\n\n"
            response += "Теперь выберите тип путешествия:\n\n"
            response += self._show_scenarios(state, short=True)
        else:
            response = f"📍 **Направление: {state.context['destination']}**\n\n"
            response += "📅 Теперь введите дату поездки (например: 'завтра', '20 декабря', 'на выходные'):"
            state.context['awaiting_date_selection'] = True
        
        return response
    
    def _handle_booking_confirmation(self, user_input: str, state: DialogState, user_id: int) -> str:
        """Обработка подтверждения бронирования"""
        user_input_lower = user_input.lower()
        
        if user_input_lower in ['да', 'yes', 'ок', 'подтверждаю', 'согласен', 'согласна', 'добавить']:
            response = "✅ **Товары добавлены в корзину!**\n\n"
            
            cart_summary = state.get_cart_summary()
            if cart_summary['item_count'] > 0:
                response += f"🛒 В корзине: {cart_summary['item_count']} товаров\n"
                response += f"💵 Общая стоимость: {cart_summary['total_price']:.2f} руб.\n\n"
            
            response += "Что дальше?\n"
            response += "• 🛒 Посмотреть корзину\n"
            response += "• 🎁 Добавить акции\n"
            response += "• ✅ Оформить заказ\n"
            response += "• 🔄 Продолжить выбор"
            
            state.context['awaiting_confirmation'] = False
            state.current_state = "cart_ready"
            return response
        elif user_input_lower in ['нет', 'no', 'не', 'отмена']:
            state.context['awaiting_confirmation'] = False
            return "Хорошо, отменяем. Хотите выбрать другой сценарий?"
        else:
            return "Пожалуйста, подтвердите добавление в корзину (да/нет)"
    
    def _handle_order_confirmation(self, user_input: str, state: DialogState, user_id: int) -> str:
        """Обработка подтверждения заказа"""
        user_input_lower = user_input.lower()
        
        if user_input_lower in ['да', 'yes', 'ок', 'подтверждаю', 'согласен', 'согласна']:
            # Сохраняем бронирование в БД
            booking_data = {
                'user_id': user_id,
                'destination': state.context['destination'],
                'travel_date': state.context['date_text'],
                'booking_number': state.generate_booking_number(),
                'total_price': state.context['total_price']
            }
            
            try:
                DatabaseManager.save_booking(booking_data)
                
                # Сохраняем сценарий если есть
                if state.context['current_scenario']:
                    DatabaseManager.save_scenario_usage(
                        user_id, 
                        state.context['current_scenario'], 
                        booking_data['booking_number']
                    )
                
                # Сохраняем промо-акции если есть
                for item in state.context['cart_items']:
                    if item['type'] == 'promo':
                        DatabaseManager.save_promo_usage(
                            user_id, 
                            item['id'], 
                            booking_data['booking_number']
                        )
                
                # Сохраняем услуги
                cart_summary = state.get_cart_summary()
                if cart_summary['products']:
                    DatabaseManager.save_selected_services(
                        user_id,
                        booking_data['booking_number'],
                        cart_summary['products']
                    )
                
                response = f"""
✅ **БРОНИРОВАНИЕ ПОДТВЕРЖДЕНО!** ✅

📋 **Детали заказа:**
📍 Направление: {state.context['destination']}
📅 Дата: {state.context['date_text']}
🎫 Номер брони: {booking_data['booking_number']}
👤 Пассажир: {state.context['passenger_name']}
💵 Итоговая сумма: {state.context['total_price']:.2f} руб.

📧 Информация отправлена на email: {state.context['passenger_email']}

Спасибо за бронирование! Хорошей поездки! 🚂✨
"""
                
                # Создаем чек
                receipt = self._generate_receipt(state, booking_data['booking_number'])
                state.context['order_summary'] = receipt
                
                state.context['awaiting_order_confirmation'] = False
                state.context['booking_confirmed'] = True
                
                return response + "\n\n" + receipt
                
            except Exception as e:
                logger.error(f"Ошибка сохранения бронирования: {e}")
                return "❌ Произошла ошибка при оформлении заказа. Пожалуйста, попробуйте позже."
        
        elif user_input_lower in ['нет', 'no', 'не', 'отмена']:
            state.context['awaiting_order_confirmation'] = False
            return "Оформление заказа отменено. Хотите что-то изменить в корзине?"
        else:
            return "Пожалуйста, подтвердите оформление заказа (да/нет)"
    
    def _generate_response(self, intent: Optional[str], user_input: str, 
                          state: DialogState, user_id: int) -> str:
        """Генерация ответа на основе намерения и состояния"""
        
        # Если намерение не распознано
        if not intent:
            if state.current_state == "start":
                cart_summary = state.get_cart_summary()
                if cart_summary['item_count'] > 0:
                    return f"🛒 В вашей корзине: {cart_summary['item_count']} товаров\n💵 Сумма: {cart_summary['total_price']:.2f} руб.\n\nЧем могу помочь?"
                else:
                    return random.choice([
                        "Здравствуйте! Я помогу вам организовать путешествие! 🚂",
                        "Привет! Куда хотите отправиться? 🌍"
                    ])
            elif state.current_state == "destination_selected":
                return "Отлично! Теперь выберите дату поездки. Например: 'завтра', 'на выходные', '25 декабря'"
            elif state.current_state == "date_selected":
                return "Теперь выберите направление: Москва, Санкт-Петербург или Сочи?"
            elif state.current_state == "cart_ready":
                return "Готовы оформить бронирование или хотите узнать о дополнительных услугах?"
            else:
                return random.choice(self.config['failure_phrases'])
        
        # Обработка распознанных намерений
        if intent in self.config['intents']:
            responses = self.config['intents'][intent]['responses']
            base_response = random.choice(responses)
            
            # Дополнительная логика для конкретных намерений
            if intent == 'greeting':
                state.reset(clear_cart=False)
                return base_response
            
            elif intent == 'destination':
                state.context['awaiting_destination_selection'] = True
                return "Куда хотите отправиться? (Москва, Санкт-Петербург, Сочи или другой город)"
            
            elif intent == 'date':
                state.context['awaiting_date_selection'] = True
                return "Когда планируете поездку? (например: 'завтра', 'на выходные', '25 декабря')"
            
            elif intent == 'destination_moscow':
                state.context['destination'] = 'Москва'
                state.context['awaiting_date_selection'] = True
                return f"{base_response}\n\n📅 Когда планируете поездку? (например: 'завтра', 'на выходные')"
            
            elif intent == 'destination_spb':
                state.context['destination'] = 'Санкт-Петербург'
                state.context['awaiting_date_selection'] = True
                return f"{base_response}\n\n📅 Когда планируете поездку? (например: 'завтра', 'на выходные')"
            
            elif intent == 'destination_sochi':
                state.context['destination'] = 'Сочи'
                state.context['awaiting_date_selection'] = True
                return f"{base_response}\n\n📅 Когда планируете поездку? (например: 'завтра', 'на выходные')"
            
            elif intent == 'date_tomorrow':
                tomorrow = (datetime.now() + timedelta(days=1)).strftime("%d.%m.%Y")
                state.context['date_text'] = f"завтра ({tomorrow})"
                if state.context['destination']:
                    state.context['awaiting_scenario_selection'] = True
                    return f"{base_response}\n📍 Направление: {state.context['destination']}\n📅 Дата: завтра\n\n" + self._show_scenarios(state, short=True)
                else:
                    state.context['awaiting_destination_selection'] = True
                    return f"{base_response}\n\nКуда хотите отправиться? (Москва, Санкт-Петербург, Сочи)"
            
            elif intent == 'date_weekend':
                # Находим ближайшую пятницу
                today = datetime.now()
                days_until_friday = (4 - today.weekday()) % 7
                if days_until_friday == 0:  # Если сегодня пятница
                    days_until_friday = 7
                friday = today + timedelta(days=days_until_friday)
                weekend_date = friday.strftime("%d.%m.%Y")
                state.context['date_text'] = f"на выходные ({weekend_date})"
                if state.context['destination']:
                    state.context['awaiting_scenario_selection'] = True
                    return f"{base_response}\n📍 Направление: {state.context['destination']}\n📅 Дата: на выходные\n\n" + self._show_scenarios(state, short=True)
                else:
                    state.context['awaiting_destination_selection'] = True
                    return f"{base_response}\n\nКуда хотите отправиться? (Москва, Санкт-Петербург, Сочи)"
            
            elif intent == 'promo_interest':
                state.context['awaiting_promo_selection'] = True
                return self._show_promotions(state)
            
            elif intent == 'view_cart':
                return self.show_cart(state)
            
            elif intent == 'confirm_booking':
                cart_summary = state.get_cart_summary()
                if cart_summary['item_count'] == 0:
                    return "Корзина пуста! Сначала добавьте товары. 🛒"
                else:
                    return self.process_order(state)
            
            elif intent == 'help':
                help_text = """
🤖 **ПОМОЩЬ ПО КОМАНДАМ:**

🛒 **Работа с корзиной:**
• "Корзина" - просмотр корзины
• "Очистить корзину" - очистить корзину
• "Оформить заказ" - завершить покупку

🎫 **Бронирование:**
• "Москва"/"СПб"/"Сочи" - выбрать направление
• "Завтра"/"На выходные" - выбрать дату
• "Сценарии" - показать типы поездок
• "Акции" - показать текущие акции
• "Мой билет" - показать электронный билет

🔄 **Прочее:**
• "Сброс" - начать заново
• "Продолжить бронирование" - вернуться к корзине

💡 Просто напишите, куда и когда хотите поехать, и я помогу с выбором!
"""
                return help_text
            
            else:
                return base_response
        
        return random.choice(self.config['failure_phrases'])
    
    def show_ticket(self, state: DialogState) -> str:
        """Показывает электронный билет"""
        cart_summary = state.get_cart_summary()
        
        for ticket in cart_summary['tickets']:
            ticket_display = f"""
╔══════════════════════════════════════╗
║      ЭЛЕКТРОННЫЙ БИЛЕТ НА ПОЕЗД      ║
╠══════════════════════════════════════╣
║ 📍 Направление: {ticket['destination']:<20} ║
║ 🎫 Номер брони: {ticket['booking_number']:<18} ║
║ 👤 Пассажир: {ticket['passenger']:<24} ║
║ 📅 Дата: {ticket['date']:<26} ║
║ 🚂 Поезд: №{ticket['train_number']:<25} ║
║ 🕗 Отправление: {ticket['departure_time']:<19} ║
║ 🕓 Прибытие: {ticket['arrival_time']:<21} ║
║ 💺 Вагон: {ticket['wagon']:<2} Место: {ticket['seat']:<2}        ║
║ 💰 Стоимость: {ticket['price']:<6} руб.      ║
╠══════════════════════════════════════╣
║  Предъявите этот билет при посадке!  ║
╚══════════════════════════════════════╝
"""
            return ticket_display
        
        return "Билет не найден в корзине. 🎫"
    
    def show_cart(self, state: DialogState) -> str:
        """Показывает содержимое корзины"""
        cart_summary = state.get_cart_summary()
        
        if cart_summary['item_count'] == 0:
            return "🛒 **Ваша корзина пуста!**\n\nДобавьте товары, выбрав сценарий путешествия или акции."
        
        response = "🛒 **ВАША КОРЗИНА**\n\n"
        
        # Показываем билеты
        tickets = cart_summary['tickets']
        if tickets:
            response += "🎫 **БИЛЕТЫ:**\n"
            for ticket in tickets:
                response += f"• Билет {ticket['destination']} - {ticket['date']}\n"
                response += f"  Номер: {ticket['booking_number']}\n"
                response += f"  Цена: {ticket['price']} руб.\n\n"
        
        # Показываем продукты
        products = cart_summary['products']
        if products:
            response += "🛍️ **УСЛУГИ:**\n"
            for product in products:
                response += f"• {product['name']}\n"
                response += f"  Цена: {product.get('base_price', 0)} руб.\n"
                if product.get('description'):
                    response += f"  Описание: {product['description']}\n"
                response += "\n"
        
        # Показываем промо-акции
        promos = cart_summary['promos']
        if promos:
            response += "🎁 **АКЦИИ:**\n"
            for promo in promos:
                response += f"• {promo['short']}\n"
                response += f"  {promo['full']}\n\n"
        
        # Показываем скидку сценария
        if state.context['current_scenario']:
            scenario = self.config['scenarios'][state.context['current_scenario']]
            response += f"💰 **Скидка по сценарию '{scenario['name']}': {scenario['discount']}%**\n\n"
        
        response += f"💵 **ИТОГО: {cart_summary['total_price']:.2f} руб.**\n\n"
        
        response += "🔸 **Доступные действия:**\n"
        response += "• ✅ Оформить заказ\n"
        response += "• 🎁 Добавить акции\n"
        response += "• 🗑️ Удалить товар (укажите номер)\n"
        response += "• 🔄 Продолжить выбор\n"
        response += "• 🚫 Очистить корзину"
        
        return response
    
    def process_order(self, state: DialogState) -> str:
        """Обработка оформления заказа"""
        cart_summary = state.get_cart_summary()
        
        if cart_summary['item_count'] == 0:
            return "Корзина пуста! Сначала добавьте товары. 🛒"
        
        # Проверяем, есть ли билет
        if not cart_summary['tickets']:
            return "Для оформления заказа нужен билет! Выберите сценарий путешествия. 🎫"
        
        response = "✅ **ПОДТВЕРЖДЕНИЕ ЗАКАЗА**\n\n"
        
        # Показываем детали заказа
        response += "📋 **Детали заказа:**\n"
        
        for ticket in cart_summary['tickets']:
            response += f"📍 Направление: {ticket['destination']}\n"
            response += f"📅 Дата: {ticket['date']}\n"
            response += f"👤 Пассажир: {state.context['passenger_name']}\n"
            response += f"📧 Email: {state.context['passenger_email']}\n\n"
        
        if cart_summary['products']:
            response += "🛍️ **Дополнительные услуги:**\n"
            for product in cart_summary['products']:
                response += f"• {product['name']} - {product.get('base_price', 0)} руб.\n"
            response += "\n"
        
        if cart_summary['promos']:
            response += "🎁 **Акции:**\n"
            for promo in cart_summary['promos']:
                response += f"• {promo['short']}\n"
            response += "\n"
        
        response += f"💵 **Общая стоимость: {cart_summary['total_price']:.2f} руб.**\n\n"
        
        response += "✅ **Подтвердить заказ?** (да/нет)\n"
        response += "После подтверждения вы получите электронный билет и чек."
        
        state.context['awaiting_order_confirmation'] = True
        
        return response
    
    def _show_scenarios(self, state: DialogState, short: bool = False) -> str:
        """Показывает доступные сценарии"""
        scenarios = self.config['scenarios']
        
        if short:
            response = "🎯 **Выберите тип путешествия:**\n\n"
            for i, (scenario_id, scenario) in enumerate(scenarios.items(), 1):
                response += f"{i}. **{scenario['name']}**\n"
                response += f"   Скидка: {scenario['discount']}%\n"
                response += f"   {scenario['description']}\n\n"
            response += "📝 Введите номер (1-5) или название сценария:"
        else:
            response = "🎯 **ДОСТУПНЫЕ СЦЕНАРИИ ПУТЕШЕСТВИЙ**\n\n"
            for i, (scenario_id, scenario) in enumerate(scenarios.items(), 1):
                response += f"**{i}. {scenario['name']}**\n"
                response += f"📝 {scenario['description']}\n"
                response += f"💰 **Скидка: {scenario['discount']}%**\n"
                
                # Показываем продукты сценария
                response += "🛍️ **Включает услуги:**\n"
                for product_id in scenario['products']:
                    product = next((p for p in self.config['products'] if p['id'] == product_id), None)
                    if product:
                        response += f"• {product['name']}"
                        if product.get('base_price'):
                            response += f" - {product['base_price']} руб."
                        response += "\n"
                
                response += f"\n🏷️ **Примерная стоимость: {self._calculate_scenario_price(scenario_id, state)} руб.**\n\n"
                response += "─" * 40 + "\n\n"
        
        return response
    
    def _show_promotions(self, state: DialogState) -> str:
        """Показывает доступные промо-акции"""
        promotions = self.config['promotions']
        
        response = "🎁 **ТЕКУЩИЕ АКЦИИ И ПРЕДЛОЖЕНИЯ**\n\n"
        
        for i, promo in enumerate(promotions, 1):
            response += f"**{i}. {promo['short']}**\n"
            response += f"{promo['full']}\n\n"
        
        response += "📝 Чтобы добавить акцию, введите её номер (1-6):"
        
        return response
    
    def _calculate_scenario_price(self, scenario_id: str, state: DialogState) -> float:
        """Рассчитывает примерную стоимость сценария"""
        if scenario_id not in self.config['scenarios']:
            return 0
        
        scenario = self.config['scenarios'][scenario_id]
        total = 0
        
        # Добавляем стоимость продуктов
        for product_id in scenario['products']:
            product = next((p for p in self.config['products'] if p['id'] == product_id), None)
            if product and 'base_price' in product:
                total += product['base_price']
        
        # Добавляем примерную стоимость билета
        ticket_price = random.randint(1500, 4500)
        total += ticket_price
        
        # Применяем скидку
        total = total * (1 - scenario['discount'] / 100)
        
        return round(total, 2)
    
    def _generate_receipt(self, state: DialogState, booking_number: str) -> str:
        """Генерирует чек покупки"""
        cart_summary = state.get_cart_summary()
        
        receipt = f"""
🧾 **ЧЕК ПОКУПКИ** 🧾

Номер брони: {booking_number}
Дата: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}
Пассажир: {state.context['passenger_name']}
Email: {state.context['passenger_email']}
────────────────────────────────
"""
        
        # Билет
        for ticket in cart_summary['tickets']:
            receipt += f"🎫 БИЛЕТ\n"
            receipt += f"Направление: {ticket['destination']}\n"
            receipt += f"Дата: {ticket['date']}\n"
            receipt += f"Поезд №{ticket['train_number']}\n"
            receipt += f"Стоимость: {ticket['price']} руб.\n"
            receipt += "────────────────────────────────\n"
        
        # Услуги
        if cart_summary['products']:
            receipt += "🛍️ УСЛУГИ\n"
            for product in cart_summary['products']:
                receipt += f"• {product['name']}: {product.get('base_price', 0)} руб.\n"
            receipt += "────────────────────────────────\n"
        
        # Скидка
        if state.context['current_scenario']:
            scenario = self.config['scenarios'][state.context['current_scenario']]
            receipt += f"💰 СКИДКА\n"
            receipt += f"Сценарий: {scenario['name']}\n"
            receipt += f"Размер скидки: {scenario['discount']}%\n"
            receipt += "────────────────────────────────\n"
        
        receipt += f"ИТОГО К ОПЛАТЕ: {cart_summary['total_price']:.2f} руб.\n"
        receipt += "────────────────────────────────\n"
        receipt += "Спасибо за покупку! Хорошей поездки! 🚂"
        
        return receipt