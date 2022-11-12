import logging
import os
import time

import requests
import telegram
from dotenv import load_dotenv

from exceptions import (
    SendingMessageError,
    TokensMissing,
    NotCorrectAPIAnswer,
    HomeworkStatusException,
    ServerError
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

logging.basicConfig(
    level=logging.INFO,
    filename='program.log',
    filemode='w',
    format='%(asctime)s, %(levelname)s, %(message)s, %(name)s'
)
logger = logging.getLogger(__name__)
logger.addHandler(
    logging.StreamHandler()
)


def send_message(bot, message):
    """Отправляем сообщение в чат."""
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        logger.info('Сообщение успешно отправлено в чат')
    except Exception:
        raise SendingMessageError(
            'Сбой при отправке сообщения в Telegram')


def get_api_answer(current_timestamp):
    """Запрос к API Яндекс практикума."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    homework_statuses = requests.get(
        ENDPOINT,
        headers=HEADERS,
        params=params
    )
    if homework_statuses.status_code != 200:
        logger.error('Сервер недоступен')
        raise ServerError('Функция get_api_answer вернула не 200')
    hw = homework_statuses.json()
    if isinstance(hw, list):
        hw_dict = hw[0]
        return hw_dict
    return hw


def check_response(response):
    """Проверка ответа API Яндекс практикума."""
    if not isinstance(response, dict):
        raise NotCorrectAPIAnswer('Функция get_api_answer вернула не словарь')
    homework_lst = response.get('homeworks')
    if not isinstance(homework_lst, list):
        raise NotCorrectAPIAnswer('Под ключом `homeworks` не список')
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
        logger.error(e)
        raise e
    if homework_status not in HOMEWORK_STATUSES:
        logger.error("Получен неизвестный статус домашней работы")
        raise HomeworkStatusException
    verdict = HOMEWORK_STATUSES[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверяем доступность переменных окружения."""
    tokens_bool = True
    if not PRACTICUM_TOKEN:
        tokens_bool = False
        logger.critical(
            'Отсутствует PRACTICUM_TOKEN')
    if not TELEGRAM_TOKEN:
        tokens_bool = False
        logger.critical('Отсутствует TELEGRAM_TOKEN')
    if not TELEGRAM_CHAT_ID:
        tokens_bool = False
        logger.critical('Отсутствует TELEGRAM_CHAT_ID')
    return tokens_bool


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        logging.critical('Отсутствует один из токенов')
        raise TokensMissing
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    while True:
        try:
            response = get_api_answer(current_timestamp)
            homeworks = check_response(response)
            for hw in homeworks:
                message = parse_status(hw)
                send_message(bot, message)
            current_timestamp = int(response['current_date'])
        except Exception as error:
            error_message = f' Сбой в работе программы: {error}'
            logger.error(error_message)
            send_message(bot, error_message)
        finally:
            logger.info(f'Следующая проверка через {RETRY_TIME/60} минут')
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
