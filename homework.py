"""Проект бота-ассистента по отправке статусов домашней работы в Telegram."""
import logging
import os
from urllib.error import HTTPError

import requests
import sys
import time
import telegram

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.DEBUG,
    filename='main.log',
    filemode='w',
    format='%(asctime)s, %(levelname)s, %(message)s'
)

logger = logging.getLogger(__name__)
handler = logging.StreamHandler(stream=sys.stdout)
logger.addHandler(handler)


class MissingEnv(Exception):
    """Отсутствует одна или несколько переменных окружения."""

    pass


class MissingKey(Exception):
    """Отсутствует необходимый ключ в словаре."""

    pass


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.info('Успешная отправка сообщения в Telegram')
    except Exception:
        logger.error('Сбой при отправке сообщения в Telegram')


def get_api_answer(current_timestamp):
    """Делает запрос к единственному эндпоинту API-сервиса."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    response = requests.get(ENDPOINT, headers=HEADERS, params=params)
    if response.status_code != 200:
        msg = f'Недоступен endpoint {ENDPOINT}, ошибка {response.status_code}'
        logger.error(msg)
        raise HTTPError(msg)
    response = response.json()
    return response


def check_response(response):
    """Проверяет ответ API на корректность."""
    if not isinstance(response, dict):
        msg = ('Недокументированный статус домашней работы, '
               'обнаруженный в ответе API')
        logger.error(msg)
        raise TypeError(msg)
    if not isinstance(response['homeworks'], list):
        msg = ('Недокументированный статус домашней работы, '
               'обнаруженный в ответе API')
        logger.error(msg)
        raise TypeError(msg)
    return response['homeworks']


def parse_status(homework):
    """Извлекает из информации о конкретной домашней работе статус работы."""
    try:
        homework_name = homework.get('homework_name')
        homework_status = homework.get('status')
        if homework_name is None or homework_status is None:
            raise MissingKey('отсутствие ожидаемых ключей homework_name '
                             'и status в ответе API')
    except MissingKey:
        logger.error('отсутствие ожидаемых ключей homework_name '
                     'и status в ответе API')
    verdict = HOMEWORK_STATUSES[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверяет доступность переменных окружения."""
    return all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID])


def main():
    """Основная логика работы бота."""
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    message_error = ''
    if check_tokens():
        logger.debug('Все переменные окружения на месте')
        msg = 'Все переменные окружения на месте'
    else:
        msg = ('Отсутствует одна или несколько переменных окружения')
        logger.critical(msg)
        raise MissingEnv(msg)
    while True:
        try:
            response = get_api_answer(current_timestamp)
            homework = check_response(response)
            try:
                message = parse_status(homework[0])
                send_message(bot, message)
            except IndexError:
                logger.debug('Отсутствие в ответе новых статусов домашки')
            current_timestamp = response.get('current_date', current_timestamp)
        except Exception as error:
            new_message_error = f'Сбой в работе программы: {error}'
            if message_error != new_message_error:
                bot.send_message(TELEGRAM_CHAT_ID, new_message_error)
            message_error = new_message_error
            current_timestamp = int(time.time())
        finally:
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
