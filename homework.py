import logging
import os
import sys
import time
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv

from exceptions import (
    SendingMessageError,
    HomeworkStatusException,
    ServerError,
    ConnectionServerError
)

load_dotenv()


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

logger = logging.getLogger(__name__)
handler = logging.StreamHandler()
logger.addHandler(handler)


def send_message(bot, message):
    """Отправляем сообщение в чат."""
    try:
        logger.info('Отправление сообщения')
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        logger.info('Сообщение успешно отправлено в чат')
    except Exception:
        raise SendingMessageError(
            'Сбой при отправке сообщения в Telegram')


def get_api_answer(current_timestamp):
    """Запрос к API Яндекс практикума."""
    logger.info('Получаем ответ от API Практикума.')
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    try:
        homework_statuses = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params=params
        )
    except requests.exceptions.ConnectionError:
        raise ConnectionServerError('Урл может быть недоступен')
    if homework_statuses.status_code != HTTPStatus.OK:
        raise ServerError('Функция get_api_answer вернула не 200')
    homework = homework_statuses.json()
    if isinstance(homework, list):
        hw_dict = homework[0]
        return hw_dict
    return homework


def check_response(response):
    """Проверка ответа API Яндекс практикума."""
    if not isinstance(response, dict):
        raise TypeError('Функция get_api_answer вернула не словарь')
    homework_lst = response.get('homeworks')
    if not isinstance(homework_lst, list):
        raise TypeError('Под ключом `homeworks` не список')
    if not len(homework_lst):
        logger.debug('Под ключом `homeworks` список пуст')
    return homework_lst


def parse_status(homework):
    """Извлекает из информации о домашней работе статус этой работы."""
    if isinstance(homework, list):
        homework = homework[0]
    try:
        homework_name = homework['homework_name']
        homework_status = homework['status']
    except KeyError as e:
        raise e
    if homework_status not in HOMEWORK_STATUSES:
        raise HomeworkStatusException
    verdict = HOMEWORK_STATUSES[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверяем доступность переменных окружения."""
    return all((PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID))


def main():
    """Основная логика работы бота."""
    logger.debug("Бот запущен")
    if not check_tokens():
        logger.critical("Не хватает токенов")
        sys.exit("Не хватает токенов")
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    while True:
        try:
            response = get_api_answer(current_timestamp)
            homeworks = check_response(response)
            if homeworks:
                message = parse_status(homeworks)
                send_message(bot, message)
            logging.debug('отсутствие в ответе новых статусов')
            current_timestamp = int(response['current_date'])
        except Exception as error:
            error_message = f' Сбой в работе программы: {error}'
            logger.error(error_message)
            send_message(bot, error_message)
        finally:
            logger.info(f'Следующая проверка через {RETRY_TIME/60} минут')
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG,
        filename=__file__ + '.log',
        filemode='w',
        format='%(asctime)s, %(levelname)s, %(message)s, %(name)s, %(lineno)d'
    )
    main()
