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
import globals

telegram_bot = Bot(token=TG_KEY)
dp = Dispatcher(telegram_bot, storage=MemoryStorage())

button_names = {'create_task': 'Создать задание',
                'verbose_off': '⬜ Подробный вывод',
                'verbose_on': '☑ Подробный вывод',
                'prohibitions': 'Запреты и аресты'
                }


kbd1 = types.ReplyKeyboardMarkup(resize_keyboard=True)
kbd1.row(button_names['create_task'], button_names['verbose_off'], button_names['prohibitions'])
kbd2 = types.ReplyKeyboardMarkup(resize_keyboard=True)
kbd2.row(button_names['create_task'], button_names['verbose_on'], button_names['prohibitions'])


def get_kbd():
    if globals.VERBOSE:
        return kbd2
    return kbd1


def extract_cad_nums(text):
    found_cad_nums = re.findall(r"\d{2}:\d{2}:\d{7}:\d{1,5}", text)
    return sorted(set(found_cad_nums))


def get_type2_files_set():
    type2_dataset = docfetcher_search(
        f'"Выписка из Единого государственного реестра недвижимости о переходе прав на объект недвижимости"')
    result = {r.getPathStr() for r in type2_dataset if r.getType() == 'xml'}
    return result


def check_whitelist(func):
    async def wrapper(*args, **kwargs):
        for arg in args:
            if isinstance(arg, types.Message) and arg.from_user.id in WHITELIST:
                await func(*args, **kwargs)
    return wrapper


class TaskCreation(StatesGroup):
    task_naming = State()
    input_cad_nums = State()


async def send_multipart_msg(user_id, text):
    parts = []
    current_part = []
    for line in text.splitlines():
        if len('\n'.join(current_part) + line) < 4000:
            current_part.append(line)
        else:
            parts.append(current_part)
            current_part = [line]
    if current_part:
        parts.append(current_part)
    parts = ['\n'.join(p) for p in parts]
    for i, part in enumerate(parts):
        if part.count('<code>') > part.count('</code>'):
            parts[i] = part + '</code>'
        if part.count('<code>') < part.count('</code>'):
            parts[i] = '<code>' + part
    for part in parts:
        await telegram_bot.send_message(user_id, part, reply_markup=get_kbd(), parse_mode="HTML")


@dp.message_handler(Text(endswith=button_names['verbose_on'][2:]))
@check_whitelist
async def toggle_verbose(message: types.Message, *args, **kwargs):
    globals.VERBOSE = not globals.VERBOSE
    text = button_names['verbose_on'][2:] + (' ВКЛ' if globals.VERBOSE else ' ВЫКЛ')
    await telegram_bot.send_message(message.from_user.id, text, reply_markup=get_kbd(), parse_mode="HTML")


@dp.message_handler(Text(equals=button_names['create_task']))
@check_whitelist
async def create_task(message: types.Message, *args, **kwargs):
    text = 'Введите название каталога'
    await TaskCreation.task_naming.set()
    await telegram_bot.send_message(message.from_user.id, text, reply_markup=get_kbd(), parse_mode="HTML")


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
    await telegram_bot.send_message(message.from_user.id, text, reply_markup=get_kbd(), parse_mode="HTML")


@dp.message_handler(state=TaskCreation.input_cad_nums)
@check_whitelist
async def input_cad_nums(message: types.Message, state: FSMContext,  *args, **kwargs):
    found_cad_nums = extract_cad_nums(message.text)
    try:
        if found_cad_nums:
            found, years_count = {}, {}
            not_found, text, n_copied, cn_dates_and_sizes = [], '', 0, []
            type2_files = get_type2_files_set()
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
                    text += f'Создан каталог:\n<code>{task_path}</code>\n'
                else:
                    text += f'Каталог уже существует:\n<code>{task_path}</code>\n'

                for cad_num in found:
                    for file in found[cad_num]:
                        print('Обрабатывается файл', file.getPathStr())
                        try:
                            ext_date = get_date(file.getPathStr())
                            file_size = os.path.getsize(file.getPathStr())
                            ext_type = 2 if file.getPathStr() in type2_files else 1
                            if (cad_num, ext_date, file_size) not in cn_dates_and_sizes:
                                cn_dates_and_sizes.append((cad_num, ext_date, file_size))
                                ext_dir_path = os.path.join(task_path, ext_date)
                                if not os.path.exists(ext_dir_path):
                                    os.makedirs(ext_dir_path)
                                target_filename = os.path.join(ext_dir_path, file.getFilename())
                                if not os.path.exists(target_filename):
                                    shutil.copy(file.getPathStr(), ext_dir_path)
                                    print('\tСкопировано. Новое расположение:', ext_dir_path)
                                    n_copied += 1
                                    year = ext_date[:4]
                                    if year in years_count:
                                        years_count[year].append((cad_num, ext_type))
                                    else:
                                        years_count[year] = [(cad_num, ext_type)]
                                else:
                                    print('\tКопирование пропущено, файл c таким именем уже существует:', target_filename)
                            else:
                                print('\tОбработка пропущена, файл с таким содерижмым уже существует')
                        except FileNotFoundError as ex:
                            print('\tФайл не доступен:', ex)

                text += f'Скопирован{"ы" if n_copied != 1 else ""} {n_copied} файл{"а" if n_copied%10 in (2,3,4) else ""}{"ов" if n_copied%10 in (5,6,7,8,9,0) else ""}\n'
                if years_count:
                    text += f'По годам:<code>\n'
                    for year in sorted(years_count):
                        text += f'{"⯈ " if globals.VERBOSE else ""}{year}: {len(years_count[year])}\n'
                        if globals.VERBOSE:
                            for cn, et in years_count[year]:
                                text += f"{cn}{' ❷' if et == 2 else ''}\n"
                    text += '</code>\n'
        else:
            text = "Кадастровых номеров не найдено. Задание отменено."
    except Py4JNetworkError:
        text = 'DocFetcher не запущен'
    await send_multipart_msg(message.from_user.id, text)
    # await telegram_bot.send_message(message.from_user.id, text, parse_mode="HTML", reply_markup=get_kbd(),)
    await state.finish()


@dp.message_handler(Text(equals=button_names['prohibitions']))
@check_whitelist
async def show_prohibitons(message: types.Message, *args, **kwargs):
    try:
        results_java_obj = docfetcher_search(f'запрет арест')
        results = [r.getTitle() for r in results_java_obj]
        text = '\n'.join(results)
    except Py4JNetworkError:
        text = 'DocFetcher не запущен'

    await send_multipart_msg(message.from_user.id, text)


@dp.message_handler()
@check_whitelist
async def parce_cad_nums(message: types.Message, **kwargs):
    found_cad_nums = extract_cad_nums(message.text)
    text = ''
    try:
        if found_cad_nums:
            type2_files = get_type2_files_set()
            found, not_found = [], []
            for cad_num in found_cad_nums:
                results_dataset = docfetcher_search(f'"{cad_num}"')
                if not results_dataset:
                    not_found.append(cad_num)
                else:
                    result_files = [r.getPathStr() for r in results_dataset if r.getType() == 'xml']
                    types_count = {1: 0, 2: 0}
                    for r_file in result_files:
                        if r_file in type2_files:
                            types_count[2] += 1
                        else:
                            types_count[1] += 1
                    if types_count[1]:
                        found.append((cad_num, 1, types_count[1]))
                    if types_count[2]:
                        found.append((cad_num, 2, types_count[2]))

            if not_found:
                text = 'Не найдены в базе:\n<code>'
                for x in not_found:
                    text += f'{x}\n'
                text += '</code>'
            if found:
                if text:
                    text += '\n'
                text += 'Найдены:\n<code>'
                for x in found:
                    text += f"{x[0]} {'❷ ' if x[1] == 2 else ''}{str(x[2]) + 'шт.' if x[2]>1 else ''}\n"
                text += '</code>'
        else:
            text = "Введите один или несколько кадастровых номеров."
    except Py4JNetworkError:
        text = 'DocFetcher не запущен'
    await send_multipart_msg(message.from_user.id, text)
    # await telegram_bot.send_message(message.from_user.id, text, reply_markup=get_kbd(), parse_mode="HTML")


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
