"""
Улучшенная логика бота путешествий с полным циклом оформления заказа
"""

import json
import os
import random
import sqlite3
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from config import BOT_CONFIG, DATABASE_NAME, LOG_FILE, LOG_LEVEL
import logging

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
    """Инициализация SQLite базы данных"""
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
    
    # Таблица заказов
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            order_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            ticket_number TEXT UNIQUE,
            destination TEXT,
            travel_date TEXT,
            scenario_name TEXT,
            total_price REAL,
            status TEXT DEFAULT 'confirmed',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
    ''')
    
    # Таблица товаров в заказе
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS order_items (
            item_id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER,
            item_type TEXT,
            item_name TEXT,
            price REAL,
            quantity INTEGER DEFAULT 1,
            FOREIGN KEY (order_id) REFERENCES orders (order_id)
        )
    ''')
    
    conn.commit()
    conn.close()
    logger.info("База данных инициализирована")

# Инициализация базы данных при импорте
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
            logger.info(f"Пользователь {user_data['user_id']} сохранен в БД")
        except Exception as e:
            logger.error(f"Ошибка сохранения пользователя: {e}")
        finally:
            conn.close()
    
    @staticmethod
    def save_order(order_data: Dict):
        """Сохраняет заказ в базу данных"""
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO orders 
                (user_id, ticket_number, destination, travel_date, scenario_name, total_price)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                order_data['user_id'], 
                order_data['ticket_number'],
                order_data.get('destination'), 
                order_data.get('travel_date'),
                order_data.get('scenario_name'),
                order_data.get('total_price', 0)
            ))
            order_id = cursor.lastrowid
            
            # Сохраняем товары заказа
            for item in order_data.get('items', []):
                cursor.execute('''
                    INSERT INTO order_items (order_id, item_type, item_name, price, quantity)
                    VALUES (?, ?, ?, ?, ?)
                ''', (
                    order_id,
                    item.get('type', 'product'),
                    item.get('name'),
                    item.get('price', 0),
                    item.get('quantity', 1)
                ))
            
            conn.commit()
            logger.info(f"Заказ {order_data['ticket_number']} сохранен в БД")
            return order_id
        except Exception as e:
            logger.error(f"Ошибка сохранения заказа: {e}")
            return None
        finally:
            conn.close()
    
    @staticmethod
    def get_user_orders(user_id: int) -> List[Dict]:
        """Получает заказы пользователя"""
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()
        try:
            cursor.execute('''
                SELECT o.*, 
                       GROUP_CONCAT(oi.item_name, ', ') as items_list
                FROM orders o
                LEFT JOIN order_items oi ON o.order_id = oi.order_id
                WHERE o.user_id = ?
                GROUP BY o.order_id
                ORDER BY o.created_at DESC
                LIMIT 10
            ''', (user_id,))
            
            orders = []
            columns = [description[0] for description in cursor.description]
            for row in cursor.fetchall():
                order_dict = dict(zip(columns, row))
                orders.append(order_dict)
            
            return orders
        except Exception as e:
            logger.error(f"Ошибка получения заказов: {e}")
            return []
        finally:
            conn.close()


class UserState:
    """Класс для хранения состояния пользователя"""
    
    def __init__(self, user_id: int):
        self.user_id = user_id
        self.context = {
            'awaiting_confirmation': False,
            'awaiting_order_confirmation': False,
            'awaiting_scenario_selection': False,
            'awaiting_promo_selection': False,
            'awaiting_date': False,
            'awaiting_destination': False,
            'destination': None,
            'date_text': None,
            'scenario_id': None,
            'scenario_name': None,
            'booking_number': None,
            'passenger_name': 'Путешественник',
            'passenger_email': None,
            'selected_promos': []
        }
        self.user_data = {}
        self.cart = {
            'products': [],
            'tickets': [],
            'promotions': []
        }
    
    def reset(self, clear_cart: bool = False):
        """Сброс состояния"""
        self.context = {
            'awaiting_confirmation': False,
            'awaiting_order_confirmation': False,
            'awaiting_scenario_selection': False,
            'awaiting_promo_selection': False,
            'awaiting_date': False,
            'awaiting_destination': False,
            'destination': None,
            'date_text': None,
            'scenario_id': None,
            'scenario_name': None,
            'booking_number': None,
            'passenger_name': 'Путешественник',
            'passenger_email': None,
            'selected_promos': []
        }
        if clear_cart:
            self.clear_cart()
        else:
            # Оставляем только промо-акции
            self.cart = {
                'products': [],
                'tickets': [],
                'promotions': self.cart['promotions']
            }
    
    def clear_cart(self):
        """Очистка корзины"""
        self.cart = {
            'products': [],
            'tickets': [],
            'promotions': []
        }
    
    def add_to_cart(self, item_type: str, item_id: Any, item_data: Dict = None):
        """Добавление товара в корзину"""
        cart_item = {
            'type': item_type,
            'id': item_id,
            'data': item_data or {},
            'added_at': datetime.now()
        }
        
        # Проверяем дубликаты для продуктов и билетов
        if item_type in ['product', 'ticket']:
            for item in self.cart[item_type + 's']:
                if item.get('id') == item_id:
                    return False
        
        self.cart[item_type + 's'].append(cart_item)
        return True
    
    def remove_from_cart(self, item_type: str, item_id: Any):
        """Удаление товара из корзины"""
        items_key = item_type + 's'
        if items_key in self.cart:
            for i, item in enumerate(self.cart[items_key]):
                if item.get('id') == item_id:
                    del self.cart[items_key][i]
                    return True
        return False
    
    def get_cart_summary(self) -> Dict:
        """Получение сводки корзины"""
        total_price = 0
        items = []
        
        # Билеты
        for ticket in self.cart['tickets']:
            price = ticket['data'].get('price', 0)
            total_price += price
            items.append({
                'type': 'ticket',
                'name': f"Билет {ticket['data'].get('destination', '')}",
                'price': price
            })
        
        # Продукты
        for product in self.cart['products']:
            price = product['data'].get('price', 0)
            total_price += price
            items.append({
                'type': 'product',
                'name': product['data'].get('name', 'Услуга'),
                'price': price
            })
        
        # Применяем скидку сценария
        if self.context.get('scenario_id') and self.context['scenario_id'] in BOT_CONFIG['scenarios']:
            scenario = BOT_CONFIG['scenarios'][self.context['scenario_id']]
            discount = scenario['discount']
            discount_amount = total_price * discount / 100
            total_price -= discount_amount
        
        # Применяем промо-акции
        for promo in self.cart['promotions']:
            if promo['data'].get('discount_type') == 'percentage':
                discount_value = promo['data'].get('discount_value', 0)
                discount_amount = total_price * discount_value / 100
                total_price -= discount_amount
        
        return {
            'item_count': len(self.cart['tickets']) + len(self.cart['products']),
            'total_price': round(total_price, 2),
            'items': items,
            'products': self.cart['products'],
            'tickets': self.cart['tickets'],
            'promotions': self.cart['promotions']
        }
    
    def apply_scenario(self, scenario_id: str) -> bool:
        """Применение сценария"""
        if scenario_id in BOT_CONFIG['scenarios']:
            scenario = BOT_CONFIG['scenarios'][scenario_id]
            self.context['scenario_id'] = scenario_id
            self.context['scenario_name'] = scenario['name']
            
            # Очищаем продукты (но оставляем промо-акции)
            self.cart['products'] = []
            self.cart['tickets'] = []
            
            # Добавляем билет
            if self.context['destination']:
                ticket_price = BOT_CONFIG['prices'].get(self.context['destination'], 1000)
                ticket_data = {
                    'name': f'Билет {self.context["destination"]}',
                    'price': ticket_price,
                    'destination': self.context['destination'],
                    'date': self.context.get('date_text', 'Не указана')
                }
                self.add_to_cart('ticket', f"ticket_{scenario_id}", ticket_data)
            
            # Добавляем рекомендуемые услуги
            for service_name in scenario.get('recommended_services', []):
                if service_name in BOT_CONFIG['additional_services']:
                    service_data = {
                        'name': service_name,
                        'price': BOT_CONFIG['additional_services'][service_name]
                    }
                    self.add_to_cart('product', f"product_{service_name}", service_data)
            
            return True
        return False
    
    def generate_ticket_number(self):
        """Генерация уникального номера билета"""
        if not self.context['booking_number']:
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            random_part = ''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789', k=6))
            self.context['booking_number'] = f"TK{timestamp[-6:]}{random_part}"
        return self.context['booking_number']
    
    def create_order_data(self, ticket_number: str) -> Dict:
        """Создание данных заказа"""
        cart_summary = self.get_cart_summary()
        
        items = []
        # Билеты
        for ticket in self.cart['tickets']:
            items.append({
                'type': 'ticket',
                'name': ticket['data'].get('name', 'Билет'),
                'price': ticket['data'].get('price', 0)
            })
        
        # Продукты
        for product in self.cart['products']:
            items.append({
                'type': 'product',
                'name': product['data'].get('name', 'Услуга'),
                'price': product['data'].get('price', 0)
            })
        
        # Промо-акции
        for promo in self.cart['promotions']:
            items.append({
                'type': 'promo',
                'name': promo['data'].get('short', 'Акция'),
                'price': 0  # Промо-акции не влияют на стоимость
            })
        
        return {
            'user_id': self.user_id,
            'ticket_number': ticket_number,
            'destination': self.context.get('destination'),
            'travel_date': self.context.get('date_text'),
            'scenario_name': self.context.get('scenario_name'),
            'total_price': cart_summary['total_price'],
            'items': items,
            'created_at': datetime.now().isoformat()
        }


class TravelBot:
    """Основной класс бота"""
    
    def __init__(self):
        self.user_states = {}
        logger.info("TravelBot инициализирован")
    
    def get_state(self, user_id: int) -> UserState:
        """Получение состояния пользователя"""
        if user_id not in self.user_states:
            self.user_states[user_id] = UserState(user_id)
        return self.user_states[user_id]
    
    def process_message(self, text: str, user_data: Dict) -> str:
        """Обработка входящего сообщения"""
        state = self.get_state(user_data['user_id'])
        text_lower = text.lower().strip()
        
        # Обработка специальных команд
        special_response = self._handle_special_commands(text, state)
        if special_response:
            return special_response
        
        # Обработка состояний ожидания
        if state.context['awaiting_order_confirmation']:
            return self._handle_order_confirmation(text, state, user_data)
        
        if state.context['awaiting_confirmation']:
            return self._handle_scenario_confirmation(text, state)
        
        if state.context['awaiting_scenario_selection']:
            return self._handle_scenario_selection(text, state)
        
        if state.context['awaiting_promo_selection']:
            return self._handle_promo_selection(text, state)
        
        if state.context['awaiting_date']:
            return self._handle_date_selection(text, state)
        
        if state.context['awaiting_destination']:
            return self._handle_destination_selection(text, state)
        
        # Обработка основных команд
        if text_lower in ['москва', 'санкт-петербург', 'сочи', 'спб', 'питер']:
            destination_map = {
                'москва': 'Москва',
                'санкт-петербург': 'Санкт-Петербург',
                'сочи': 'Сочи',
                'спб': 'Санкт-Петербург',
                'питер': 'Санкт-Петербург'
            }
            state.context['destination'] = destination_map.get(text_lower, text)
            
            if not state.context.get('date_text'):
                return f"📍 Выбрано направление: {state.context['destination']}\n\n📅 Теперь выберите дату поездки (например: 'завтра', 'на выходные'):"
            else:
                state.context['awaiting_scenario_selection'] = True
                return f"📍 Направление: {state.context['destination']}\n📅 Дата: {state.context['date_text']}\n\nТеперь выберите тип путешествия!"
        
        # Обработка выбора даты
        if text_lower in ['завтра', 'на выходные']:
            state.context['date_text'] = text.capitalize()
            
            if not state.context.get('destination'):
                return f"📅 Дата выбрана: {state.context['date_text']}\n\n📍 Теперь выберите направление (Москва, СПб, Сочи):"
            else:
                state.context['awaiting_scenario_selection'] = True
                return f"📍 Направление: {state.context['destination']}\n📅 Дата: {state.context['date_text']}\n\nТеперь выберите тип путешествия!"
        
        # Обработка выбора сценария по номеру
        if text in ['1', '2', '3', '4', '5']:
            if state.context.get('destination') and state.context.get('date_text'):
                if state.apply_scenario(text):
                    return self._show_scenario_summary(state)
                else:
                    return "❌ Ошибка выбора сценария. Попробуйте еще раз."
            else:
                return "⚠️ Сначала выберите направление и дату!"
        
        # Ответ по умолчанию
        return self._get_default_response(state)
    
    def _handle_special_commands(self, text: str, state: UserState) -> Optional[str]:
        """Обработка специальных команд"""
        text_lower = text.lower().strip()
        
        if text_lower in ['корзина', 'cart', 'заказ']:
            return self.show_cart(state)
        
        elif text_lower == 'очистить корзину':
            state.clear_cart()
            return "🛒 Корзина очищена! Теперь вы можете добавить новые товары."
        
        elif text_lower == 'сброс':
            state.reset(clear_cart=True)
            return "✅ Состояние сброшено. Начнем заново! 🔄"
        
        elif text_lower == 'помощь':
            return self._show_help()
        
        elif text_lower == 'сценарии':
            if state.context.get('destination') and state.context.get('date_text'):
                state.context['awaiting_scenario_selection'] = True
                return self._show_scenarios(state)
            else:
                return "Сначала выберите направление и дату, чтобы увидеть подходящие сценарии! 🗺️"
        
        elif text_lower == 'акции':
            state.context['awaiting_promo_selection'] = True
            return self._show_promotions(state)
        
        elif text_lower == 'оформить':
            cart_summary = state.get_cart_summary()
            if cart_summary['item_count'] == 0:
                return "Корзина пуста! Сначала добавьте товары. 🛒"
            return self.process_order(state)
        
        elif text_lower == 'продолжить':
            cart_summary = state.get_cart_summary()
            if cart_summary['item_count'] > 0:
                return self.show_cart(state)
            else:
                return "Корзина пуста. Начните новое бронирование! 🚂"
        
        return None
    
    def _handle_order_confirmation(self, text: str, state: UserState, user_data: Dict) -> str:
        """Обработка подтверждения заказа"""
        text_lower = text.lower().strip()
        
        if text_lower in ['да', 'yes', 'ок', 'подтверждаю', 'согласен', 'согласна', '✅ да, подтверждаю']:
            # Генерируем номер билета
            ticket_number = state.generate_ticket_number()
            
            # Создаем данные заказа
            order_data = state.create_order_data(ticket_number)
            
            # Сохраняем в БД
            DatabaseManager.save_order(order_data)
            
            # Сохраняем пользователя
            DatabaseManager.save_user(user_data)
            
            # Очищаем корзину
            state.clear_cart()
            
            # Сбрасываем состояния
            state.context['awaiting_order_confirmation'] = False
            
            # Формируем финальное сообщение
            response = f"""
🎉 **БРОНИРОВАНИЕ ПОДТВЕРЖДЕНО!** 🎫

✅ **Ваш заказ успешно оформлен!**

📋 **Детали заказа:**
• Номер билета: `{ticket_number}`
• Направление: {state.context.get('destination', 'Не указано')}
• Дата: {state.context.get('date_text', 'Не указана')}
• Сценарий: {state.context.get('scenario_name', 'Не выбран')}

💰 **Итоговая стоимость:** {order_data['total_price']:.2f} руб.

📧 **Информация отправлена:** {state.context.get('passenger_email', 'не указан')}

🚂 **Приятного путешествия!** 🌍
Спасибо, что выбрали наш сервис!

📱 Ваш билет сохранен в истории заказов.
Чтобы посмотреть его, нажмите '🎫 Мой билет'
"""
            
            logger.info(f"Заказ подтвержден: {ticket_number} для пользователя {user_data['user_id']}")
            return response
        
        elif text_lower in ['нет', 'no', 'не', 'отменить', '❌ нет, отменить']:
            state.context['awaiting_order_confirmation'] = False
            return "❌ Заказ отменен. Вы можете изменить состав корзины и попробовать снова."
        
        return "Пожалуйста, подтвердите оформление заказа кнопкой '✅ Да, подтверждаю' или отмените кнопкой '❌ Нет, отменить'"
    
    def _handle_scenario_confirmation(self, text: str, state: UserState) -> str:
        """Обработка подтверждения сценария"""
        text_lower = text.lower().strip()
        
        if text_lower in ['да', 'yes', 'ок', 'подтверждаю', 'согласен', 'согласна', '✅ да, подтверждаю']:
            state.context['awaiting_confirmation'] = False
            
            cart_summary = state.get_cart_summary()
            response = "✅ **Товары добавлены в корзину!**\n\n"
            response += f"🛒 В корзине: {cart_summary['item_count']} товаров\n"
            response += f"💵 Общая стоимость: {cart_summary['total_price']:.2f} руб.\n\n"
            response += "Что дальше?\n"
            response += "• 🛒 Посмотреть корзину\n"
            response += "• 🎁 Добавить акции\n"
            response += "• ✅ Оформить заказ\n"
            response += "• 🔄 Продолжить выбор"
            
            return response
        
        elif text_lower in ['нет', 'no', 'не', 'отменить', '❌ нет, отменить']:
            state.context['awaiting_confirmation'] = False
            state.clear_cart()
            return "Хорошо, отменяем. Хотите выбрать другой сценарий?"
        
        return "Пожалуйста, подтвердите добавление в корзину (да/нет)"
    
    def _handle_scenario_selection(self, text: str, state: UserState) -> str:
        """Обработка выбора сценария"""
        if text in ['1', '2', '3', '4', '5']:
            if state.apply_scenario(text):
                return self._show_scenario_summary(state)
        
        # Проверка по названию
        scenarios = BOT_CONFIG['scenarios']
        for scenario_id, scenario_data in scenarios.items():
            if scenario_data['name'].lower() in text.lower():
                if state.apply_scenario(scenario_id):
                    return self._show_scenario_summary(state)
        
        return "Пожалуйста, выберите сценарий из предложенных. Введите номер (1-5) или название."
    
    def _handle_promo_selection(self, text: str, state: UserState) -> str:
        """Обработка выбора промо-акции"""
        try:
            promo_num = int(text.strip())
            if 1 <= promo_num <= len(BOT_CONFIG['promotions']):
                promo = BOT_CONFIG['promotions'][promo_num - 1]
                
                # Добавляем промо-акцию в корзину
                if state.add_to_cart('promo', promo['id'], promo):
                    state.context['awaiting_promo_selection'] = False
                    
                    response = f"✅ **Добавлена акция: {promo['short']}**\n\n"
                    response += f"{promo['full']}\n\n"
                    
                    cart_summary = state.get_cart_summary()
                    if cart_summary['item_count'] > 0:
                        response += f"🛒 В корзине: {cart_summary['item_count']} товаров\n"
                        response += f"💵 Общая стоимость: {cart_summary['total_price']:.2f} руб.\n\n"
                    
                    return response
        except ValueError:
            pass
        
        return "Пожалуйста, введите номер акции от 1 до 6."
    
    def _handle_date_selection(self, text: str, state: UserState) -> str:
        """Обработка выбора даты"""
        state.context['date_text'] = text
        state.context['awaiting_date'] = False
        
        if state.context['destination']:
            state.context['awaiting_scenario_selection'] = True
            response = f"📅 **Дата поездки: {text}**\n"
            response += f"📍 **Направление: {state.context['destination']}**\n\n"
            response += "Теперь выберите тип путешествия:\n\n"
            response += self._show_scenarios(state)
        else:
            state.context['awaiting_destination'] = True
            response = "📅 Отлично! Теперь выберите направление:\n"
            response += "• Москва 🏙️\n• Санкт-Петербург 🏛️\n• Сочи 🌴\n\n"
            response += "Или напишите свой вариант!"
        
        return response
    
    def _handle_destination_selection(self, text: str, state: UserState) -> str:
        """Обработка выбора направления"""
        destination_map = {
            'москва': 'Москва',
            'мск': 'Москва',
            'питер': 'Санкт-Петербург',
            'спб': 'Санкт-Петербург',
            'санкт-петербург': 'Санкт-Петербург',
            'петербург': 'Санкт-Петербург',
            'сочи': 'Сочи'
        }
        
        text_lower = text.lower()
        for key, value in destination_map.items():
            if key in text_lower:
                state.context['destination'] = value
                break
        
        if not state.context['destination']:
            state.context['destination'] = text
        
        state.context['awaiting_destination'] = False
        
        if state.context['date_text']:
            state.context['awaiting_scenario_selection'] = True
            response = f"📍 **Направление: {state.context['destination']}**\n"
            response += f"📅 **Дата: {state.context['date_text']}**\n\n"
            response += "Теперь выберите тип путешествия:\n\n"
            response += self._show_scenarios(state)
        else:
            state.context['awaiting_date'] = True
            response = f"📍 **Направление: {state.context['destination']}**\n\n"
            response += "📅 Теперь введите дату поездки (например: 'завтра', '20 декабря', 'на выходные'):"
        
        return response
    
    def _show_scenario_summary(self, state: UserState) -> str:
        """Показать сводку по сценарию"""
        if not state.context.get('scenario_id'):
            return "Сценарий не выбран."
        
        scenario_id = state.context['scenario_id']
        scenario = BOT_CONFIG['scenarios'][scenario_id]
        
        summary = f"✅ **Выбран сценарий: {scenario['name']}**\n\n"
        summary += f"{random.choice(scenario.get('dialogue', ['Отличный выбор!']))}\n\n"
        summary += f"📝 {scenario['description']}\n\n"
        summary += f"💰 **Скидка по сценарию: {scenario['discount']}%**\n\n"
        summary += "🛍️ **В корзину добавлены:**\n"
        
        cart_summary = state.get_cart_summary()
        for item in cart_summary['items']:
            summary += f"• {item['name']} - {item['price']} руб.\n"
        
        summary += f"\n💵 **Общая стоимость: {cart_summary['total_price']:.2f} руб.**\n\n"
        summary += "✅ Добавить в корзину и продолжить?"
        
        state.context['awaiting_confirmation'] = True
        
        return summary
    
    def _show_scenarios(self, state: UserState) -> str:
        """Показать доступные сценарии"""
        scenarios = BOT_CONFIG['scenarios']
        
        response = "🎯 **Выберите тип путешествия:**\n\n"
        for i, (scenario_id, scenario) in enumerate(scenarios.items(), 1):
            response += f"{i}. **{scenario['name']}**\n"
            response += f"   Скидка: {scenario['discount']}%\n"
            response += f"   {scenario['description']}\n\n"
        response += "📝 Введите номер (1-5) или название сценария:"
        
        return response
    
    def _show_promotions(self, state: UserState) -> str:
        """Показать доступные промо-акции"""
        promotions = BOT_CONFIG['promotions']
        
        response = "🎁 **ТЕКУЩИЕ АКЦИИ И ПРЕДЛОЖЕНИЯ**\n\n"
        for i, promo in enumerate(promotions, 1):
            response += f"{i}. **{promo['short']}**\n"
            response += f"   {promo['full']}\n\n"
        response += "📝 Чтобы добавить акцию, введите её номер (1-6):"
        
        return response
    
    def _show_help(self) -> str:
        """Показать справку"""
        return """
🤖 **ПОМОЩЬ ПО КОМАНДАМ БОТА**

📋 **Основные команды:**
• Москва/СПб/Сочи - выбрать направление
• Завтра/На выходные - выбрать дату
• Сценарии - показать типы поездок
• Акции - показать текущие акции
• Корзина - просмотр корзины
• Оформить - завершить покупку
• Сброс - начать заново
• Помощь - показать это сообщение

🛒 **Работа с корзиной:**
• Добавляйте товары через выбор сценария
• Применяйте акции для скидок
• Очищайте корзину если нужно

🎫 **Процесс бронирования:**
1. Выберите направление
2. Укажите дату поездки
3. Выберите сценарий
4. Добавьте акции (опционально)
5. Подтвердите оформление заказа
6. Получите номер билета

🚂 **Приятного путешествия!**
"""
    
    def _get_default_response(self, state: UserState) -> str:
        """Получить ответ по умолчанию"""
        cart_summary = state.get_cart_summary()
        if cart_summary['item_count'] > 0:
            return f"🛒 В вашей корзине: {cart_summary['item_count']} товаров\n💵 Сумма: {cart_summary['total_price']:.2f} руб.\n\nЧем могу помочь?"
        else:
            return "Здравствуйте! Я помогу вам организовать путешествие! 🚂\n\nКуда хотите отправиться? (Москва, СПб, Сочи)"
    
    def show_cart(self, state: UserState) -> str:
        """Показать содержимое корзины"""
        cart_summary = state.get_cart_summary()
        
        if cart_summary['item_count'] == 0:
            return "🛒 **Ваша корзина пуста!**\n\nДобавьте товары, выбрав сценарий путешествия или акции."
        
        response = "🛒 **ВАША КОРЗИНА**\n\n"
        
        # Билеты
        for ticket in cart_summary['tickets']:
            ticket_data = ticket['data']
            response += f"🎫 **{ticket_data.get('name', 'Билет')}**\n"
            response += f"📍 Направление: {ticket_data.get('destination', 'Не указано')}\n"
            response += f"📅 Дата: {ticket_data.get('date', 'Не указана')}\n"
            response += f"💰 Стоимость: {ticket_data.get('price', 0)} руб.\n\n"
        
        # Продукты
        for product in cart_summary['products']:
            product_data = product['data']
            response += f"🛍️ **{product_data.get('name', 'Услуга')}**\n"
            response += f"💰 Стоимость: {product_data.get('price', 0)} руб.\n\n"
        
        # Промо-акции
        if cart_summary['promotions']:
            response += "🎁 **АКТИВНЫЕ АКЦИИ:**\n"
            for promo in cart_summary['promotions']:
                promo_data = promo['data']
                response += f"• {promo_data.get('short', 'Акция')}\n"
            response += "\n"
        
        # Скидка сценария
        if state.context.get('scenario_name'):
            response += f"💰 **Скидка по сценарию '{state.context['scenario_name']}': {BOT_CONFIG['scenarios'][state.context['scenario_id']]['discount']}%**\n\n"
        
        response += f"💵 **ИТОГО: {cart_summary['total_price']:.2f} руб.**\n\n"
        
        response += "🔸 **Доступные действия:**\n"
        response += "• ✅ Оформить заказ\n"
        response += "• 🎁 Добавить акции\n"
        response += "• 🔄 Продолжить выбор\n"
        response += "• 🗑️ Очистить корзину\n"
        response += "• 🆘 Помощь"
        
        return response
    
    def process_order(self, state: UserState) -> str:
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
        
        # Направление и дата
        if state.context.get('destination'):
            response += f"📍 Направление: {state.context['destination']}\n"
        if state.context.get('date_text'):
            response += f"📅 Дата: {state.context['date_text']}\n"
        
        # Пассажир
        response += f"👤 Пассажир: {state.context.get('passenger_name', 'Не указан')}\n"
        
        # Билеты
        response += "\n🎫 **Билеты:**\n"
        for ticket in cart_summary['tickets']:
            ticket_data = ticket['data']
            response += f"• {ticket_data.get('name', 'Билет')} - {ticket_data.get('price', 0)} руб.\n"
        
        # Услуги
        if cart_summary['products']:
            response += "\n🛍️ **Дополнительные услуги:**\n"
            for product in cart_summary['products']:
                product_data = product['data']
                response += f"• {product_data.get('name', 'Услуга')} - {product_data.get('price', 0)} руб.\n"
        
        # Акции
        if cart_summary['promotions']:
            response += "\n🎁 **Акции:**\n"
            for promo in cart_summary['promotions']:
                promo_data = promo['data']
                response += f"• {promo_data.get('short', 'Акция')}\n"
        
        # Скидка сценария
        if state.context.get('scenario_name'):
            scenario = BOT_CONFIG['scenarios'][state.context['scenario_id']]
            response += f"\n💰 **Скидка по сценарию '{scenario['name']}': {scenario['discount']}%**\n"
        
        response += f"\n💵 **Общая стоимость: {cart_summary['total_price']:.2f} руб.**\n\n"
        
        response += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        response += "✅ **Подтвердить оформление заказа?**\n\n"
        response += "После подтверждения:\n"
        response += "• Вы получите номер электронного билета\n"
        response += "• Билет будет сохранен в вашей истории\n"
        response += "• Сможете просмотреть его в любое время\n\n"
        
        response += "Нажмите '✅ Да, подтверждаю' чтобы завершить оформление\n"
        response += "или '❌ Нет, отменить' для отмены"
        
        # Устанавливаем состояние ожидания подтверждения заказа
        state.context['awaiting_order_confirmation'] = True
        
        return response
    
    def show_ticket(self, state: UserState) -> str:
        """Показать электронный билет"""
        # Проверяем, есть ли подтвержденный заказ
        if not state.context.get('booking_number'):
            return "У вас нет активных билетов. Сначала оформите заказ! 🎫"
        
        # Получаем заказы пользователя из БД
        orders = DatabaseManager.get_user_orders(state.user_id)
        if not orders:
            return "Билеты не найдены. Возможно, они были отменены."
        
        # Берем последний заказ
        latest_order = orders[0]
        
        # Формируем билет
        ticket_response = f"""
🎫 **ВАШ ЭЛЕКТРОННЫЙ БИЛЕТ**

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 **ДЕТАЛИ БИЛЕТА:**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• Номер билета: `{latest_order['ticket_number']}`
• Направление: {latest_order.get('destination', 'Не указано')}
• Дата поездки: {latest_order.get('travel_date', 'Не указана')}
• Тип путешествия: {latest_order.get('scenario_name', 'Не выбран')}
• Статус: ✅ Подтвержден
• Дата бронирования: {datetime.fromisoformat(latest_order['created_at']).strftime('%d.%m.%Y %H:%M') if 'created_at' in latest_order else 'Неизвестно'}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💰 **ОПЛАТА:**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• Итоговая стоимость: {latest_order.get('total_price', 0):.2f} руб.
• Способ оплаты: Карта онлайн

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📱 **ИНСТРУКЦИИ:**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. Сохраните номер билета: `{latest_order['ticket_number']}`
2. При посадке покажите этот билет или номер
3. Имейте при себе документ, удостоверяющий личность
4. Приходите на посадку за 30 минут до отправления

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🚂 **ПРИЯТНОЙ ПОЕЗДКИ!**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⚠️ **Важно:** Электронный билет является официальным документом.
"""
        
        return ticket_response
    
    def _generate_receipt(self, state: UserState, ticket_number: str) -> str:
        """Генерация чека покупки"""
        cart_summary = state.get_cart_summary()
        
        receipt = f"""
🧾 **ЧЕК ПОКУПКИ**

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 **ДЕТАЛИ ЗАКАЗА:**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Номер билета: {ticket_number}
Дата: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}
Пассажир: {state.context.get('passenger_name', 'Не указан')}
Email: {state.context.get('passenger_email', 'Не указан')}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
        
        # Билет
        for ticket in cart_summary['tickets']:
            ticket_data = ticket['data']
            receipt += f"🎫 БИЛЕТ\n"
            receipt += f"Направление: {ticket_data.get('destination', 'Не указано')}\n"
            receipt += f"Дата: {ticket_data.get('date', 'Не указана')}\n"
            receipt += f"Стоимость: {ticket_data.get('price', 0)} руб.\n"
            receipt += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        
        # Услуги
        if cart_summary['products']:
            receipt += "🛍️ УСЛУГИ\n"
            for product in cart_summary['products']:
                product_data = product['data']
                receipt += f"• {product_data.get('name', 'Услуга')}: {product_data.get('price', 0)} руб.\n"
            receipt += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        
        # Скидка
        if state.context.get('scenario_name'):
            scenario = BOT_CONFIG['scenarios'][state.context['scenario_id']]
            receipt += f"💰 СКИДКА\n"
            receipt += f"Сценарий: {scenario['name']}\n"
            receipt += f"Размер скидки: {scenario['discount']}%\n"
            receipt += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        
        # Акции
        if cart_summary['promotions']:
            receipt += "🎁 АКЦИИ\n"
            for promo in cart_summary['promotions']:
                promo_data = promo['data']
                receipt += f"• {promo_data.get('short', 'Акция')}\n"
            receipt += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        
        receipt += f"ИТОГО К ОПЛАТЕ: {cart_summary['total_price']:.2f} руб.\n"
        receipt += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        receipt += "Спасибо за покупку! Хорошей поездки! 🚂"
        
        return receipt
    
    def show_user_tickets(self, user_id: int) -> str:
        """Показать все билеты пользователя"""
        orders = DatabaseManager.get_user_orders(user_id)
        
        if not orders:
            return "🎫 У вас нет активных билетов. Начните новое бронирование!"
        
        response = "🎫 **ВАШИ БИЛЕТЫ**\n\n"
        
        for i, order in enumerate(orders, 1):
            response += f"**{i}. Билет №{order['ticket_number']}**\n"
            response += f"📍 Направление: {order.get('destination', 'Не указано')}\n"
            response += f"📅 Дата: {order.get('travel_date', 'Не указана')}\n"
            response += f"💰 Стоимость: {order.get('total_price', 0):.2f} руб.\n"
            response += f"📋 Статус: {order.get('status', 'Неизвестно')}\n"
            
            created_date = None
            if 'created_at' in order:
                try:
                    created_date = datetime.fromisoformat(order['created_at']).strftime('%d.%m.%Y %H:%M')
                except (ValueError, TypeError):
                    created_date = order['created_at']
            
            if created_date:
                response += f"🕒 Забронирован: {created_date}\n"
            
            response += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        
        response += f"📊 **Всего билетов: {len(orders)}**\n\n"
        response += "Чтобы посмотреть детали конкретного билета, нажмите '🎫 Мой билет'"
        
        return response