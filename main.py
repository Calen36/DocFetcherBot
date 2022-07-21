import sys
import re

from py4j.java_gateway import JavaGateway, GatewayParameters
from py4j.java_gateway import java_import
from py4j.protocol import Py4JNetworkError

from aiogram import Bot, types
from aiogram.dispatcher import Dispatcher
from aiogram.utils import executor
from aiogram.contrib.fsm_storage.memory import MemoryStorage


from config import TG_KEY, ADMINLIST, WHITELIST

telegram_bot = Bot(token=TG_KEY)
dp = Dispatcher(telegram_bot, storage=MemoryStorage())

def check_whitelist(func):
    async def wrapper(msg: types.Message):
        if msg.from_user.id in WHITELIST:
            await func(msg)
    return wrapper


def check_admin(func):
    async def wrapper(msg: types.Message):
        if msg.from_user.id in ADMINLIST:
            await func(msg)
    return wrapper


@dp.message_handler()
@check_whitelist
async def parce_cad_nums(message: types.Message):
    """добавляет в очередь кадастровые номера, найденные в сообщении"""
    found_cad_nums = re.findall(r"\d{2}:\d{2}:\d{7}:\d{1,5}", message.text)
    found_cad_nums = sorted(set(found_cad_nums))

    try:
        if found_cad_nums:
            found, not_found = [], []
            for cad_num in found_cad_nums:
                results = docfetcher_search(f'"{cad_num}"')
                if results:
                    found.append(cad_num)
                else:
                    not_found.append(cad_num)
            if not_found:
                text = 'Не найдены в базе:\n<code>'
                for x in not_found:
                    text += f'{x}\n'
                text += '</code>'
            else:
                text = 'Все номера найдены в базе'
        else:
            text = "Введите один или несколько кадастровых номеров."
    except Py4JNetworkError:
        text = 'DocFetcher не запущен'
    await telegram_bot.send_message(message.from_user.id, text, parse_mode="HTML")


def main():
    if len(sys.argv) <= 1:
        print("No query specified.")
        return
    query = " ".join(sys.argv[1:])
    try:
        result_docs = docfetcher_search(query, 28834)
        for doc in result_docs:
            print(doc.getFilename() + "\t" + doc.getPathStr())
    except:
        print("ERROR: " + str(sys.exc_info()[1]))


def my_main():
    query = '"23:26:1103015:111"'
    try:
        result_docs = docfetcher_search(query, 28834)
        for doc in result_docs:
            print(doc.getPathStr())
    except:
        print("ERROR: " + str(sys.exc_info()[1]))


def docfetcher_search(query, port=28834):
    """Sends the given query string to the running DocFetcher instance at the
    given port and returns a list of result objects.

    The result objects provide the following getter methods for accessing their
    attributes:
    - getAuthors
    - getDateStr - e-mail send date
    - getFilename
    - getLastModifiedStr - last-modified date on files
    - getPathStr - file path
    - getScore - result score as int
    - getSender - e-mail sender
    - getSizeInKB - file size as int
    - getTitle
    - getType
    - isEmail - boolean indicating whether result object is e-mail or file

    This method will throw an error if communication with the DocFetcher
    instance fails.
    """
    gateway = JavaGateway(gateway_parameters=GatewayParameters(port=port))
    java_import(gateway.jvm, "net.sourceforge.docfetcher.gui.Application")
    application = gateway.jvm.net.sourceforge.docfetcher.gui.Application

    indexRegistry = application.getIndexRegistry()
    searcher = indexRegistry.getSearcher()
    results = searcher.search(query)
    return results


if __name__ == '__main__':
    # loop = asyncio.get_event_loop()
    executor.start_polling(dp, skip_updates=True)