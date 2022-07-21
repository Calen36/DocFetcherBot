import re
import os
import shutil

from py4j.java_gateway import JavaGateway, GatewayParameters
from py4j.java_gateway import java_import
from py4j.protocol import Py4JNetworkError

from aiogram import Bot, types
from aiogram.dispatcher import Dispatcher
from aiogram.utils import executor
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher.filters import Text
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.dispatcher import FSMContext

from unpack import get_date
from config import TG_KEY, TASKS_ROOT, WHITELIST

telegram_bot = Bot(token=TG_KEY)
dp = Dispatcher(telegram_bot, storage=MemoryStorage())

button_names = {'create_task': 'Создать задание',}
kbd = types.ReplyKeyboardMarkup(resize_keyboard=True)
kbd.row(button_names['create_task'],)


def extract_cad_nums(text):
    found_cad_nums = re.findall(r"\d{2}:\d{2}:\d{7}:\d{1,5}", text)
    return sorted(set(found_cad_nums))


def check_whitelist(func):
    async def wrapper(*args, **kwargs):
        for arg in args:
            if isinstance(arg, types.Message) and arg.from_user.id in WHITELIST:
                await func(*args, **kwargs)
    return wrapper


class TaskCreation(StatesGroup):
    task_naming = State()
    input_cad_nums = State()


@dp.message_handler(Text(equals=button_names['create_task']))
@check_whitelist
async def create_task(message: types.Message, *args, **kwargs):
    text = 'Введите название каталога'
    await TaskCreation.task_naming.set()
    await telegram_bot.send_message(message.from_user.id, text, reply_markup=kbd, parse_mode="HTML")


@dp.message_handler(state=TaskCreation.task_naming)
@check_whitelist
async def input_task_name(message: types.Message, state: FSMContext,  *args, **kwargs):
    dirname = message.text.strip()
    forbidden_chars = '/\:*?«<>|'
    if any([ch in dirname for ch in forbidden_chars]):
        chars = [ch for ch in forbidden_chars if ch in dirname]
        text = f"Данные символы нельзя использовать в имени каталога:\n{' '.join(chars)}\nЗадание отменено."
        await state.finish()
    else:
        await state.update_data(dirname=dirname)
        await TaskCreation.input_cad_nums.set()
        text = f"Введите кадастровые номера"
    await telegram_bot.send_message(message.from_user.id, text, reply_markup=kbd, parse_mode="HTML")


@dp.message_handler(state=TaskCreation.input_cad_nums)
@check_whitelist
async def input_cad_nums(message: types.Message, state: FSMContext,  *args, **kwargs):
    found_cad_nums = extract_cad_nums(message.text)
    try:
        if found_cad_nums:
            found, years_count = {}, {}
            not_found, text, n_copied, dates_and_sizes = [], '', 0, []
            for cad_num in found_cad_nums:
                results = docfetcher_search(f'"{cad_num}"')
                if results:
                    found[cad_num] = [r for r in results if r.getType() == 'xml']
                else:
                    not_found.append(cad_num)
            if not_found:
                text += 'Не найдены в базе:\n<code>'
                for cad_num in not_found:
                    text += f'{cad_num}\n'
                text += '</code>\n'
            else:
                text = 'Все номера найдены в базe\n'
            if found:
                state_data = await state.get_data()
                task_path = os.path.join(TASKS_ROOT, state_data['dirname'])
                if not os.path.exists(task_path):
                    os.makedirs(task_path)

                for cad_num in found:
                    for file in found[cad_num]:
                        print('Обрабатывается файл', file.getPathStr())
                        ext_date = get_date(file.getPathStr())
                        file_size = os.path.getsize(file.getPathStr())
                        if (ext_date, file_size) not in dates_and_sizes:
                            dates_and_sizes.append((ext_date, file_size))
                            n_copied += 1
                            year = ext_date[:4]

                            if year in years_count:
                                years_count[year] += 1
                            else:
                                years_count[year] = 1
                            ext_dir_path = os.path.join(task_path, ext_date)
                            if not os.path.exists(ext_dir_path):
                                os.makedirs(ext_dir_path)
                            target_filename = os.path.join(ext_dir_path, file.getFilename())
                            if not os.path.exists(target_filename):
                                shutil.copy(file.getPathStr(), ext_dir_path)
                                print('\tСкопировано. Новое расположение:', ext_dir_path)
                            else:
                                print('\tКопирование пропущено, файл уже существует:', target_filename)
                        else:
                            print('\tОбработка пропущена, файл с таким содерижмым уже существует')

                text += f'Создан каталог:\n<code>{task_path}</code>\n'
                text += f'Скопирован{"ы" if n_copied > 1 else ""} {n_copied} файл{"а" if n_copied%10 in (2,3,4) else ""}{"ов" if n_copied%10 in (5,6,7,8,9,0) else ""}\n'
                text += f'По годам:<code>\n'
                for year in sorted(years_count):
                    text += f'{year}: {years_count[year]}\n'
                text += '</code>\n'
        else:
            text = "Кадастровых номеров не найдено. Задание отменено."
    except Py4JNetworkError:
        text = 'DocFetcher не запущен'
    await telegram_bot.send_message(message.from_user.id, text, parse_mode="HTML", reply_markup=kbd,)
    await state.finish()


@dp.message_handler()
@check_whitelist
async def parce_cad_nums(message: types.Message, **kwargs):
    """добавляет в очередь кадастровые номера, найденные в сообщении"""
    found_cad_nums = extract_cad_nums(message.text)

    try:
        if found_cad_nums:
            not_found = []
            for cad_num in found_cad_nums:
                results = docfetcher_search(f'"{cad_num}"')
                if not results:
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
    await telegram_bot.send_message(message.from_user.id, text, reply_markup=kbd, parse_mode="HTML")


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
