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
from markups import button_names, get_kbd
from xml_parcing import check_cession
from user_settings_handler import get_globals_from_disk, write_globals_to_disk
from config import TG_KEY, TASKS_ROOT, WHITELIST
import globals

telegram_bot = Bot(token=TG_KEY)
dp = Dispatcher(telegram_bot, storage=MemoryStorage())


def extract_cad_nums(text: str) -> list:
    """Возвращает все найденные в тексте кадастровые номера"""
    found_cad_nums = re.findall(r"\d{2}:\d{2}:\d{7}:\d{1,5}", text)
    return sorted(set(found_cad_nums))


def extract_cad_raion(text: str) -> list:
    """Возвращает все найденые в тексте кадастровые районы (район должен быть прописан отдельно, не в составе номера)"""
    found_cad_raions = re.findall(r"\d{2}:\d{2}:", text.strip())
    return sorted(set(found_cad_raions))


def get_type2_files_set() -> set:
    """Возвращает полные имена файлов для всех выписок 2го типа в индексе"""
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
    write_globals_to_disk()
    text = button_names['verbose_on'][2:] + (' ВКЛ' if globals.VERBOSE else ' ВЫКЛ')
    await telegram_bot.send_message(message.from_user.id, text, reply_markup=get_kbd(), parse_mode="HTML")


@dp.message_handler(Text(endswith=button_names['prohibitions_on'][2:]))
@check_whitelist
async def toggle_prohibitons(message: types.Message, *args, **kwargs):
    globals.PROHIBITIONS = not globals.PROHIBITIONS
    if globals.PROHIBITIONS and globals.CESSION:
        globals.CESSION = False
    write_globals_to_disk()
    text = button_names['prohibitions_on'][2:] + (' ВКЛ' if globals.PROHIBITIONS else ' ВЫКЛ')
    await telegram_bot.send_message(message.from_user.id, text, reply_markup=get_kbd(), parse_mode="HTML")


@dp.message_handler(Text(endswith=button_names['cession_on'][2:]))
@check_whitelist
async def toggle_cession(message: types.Message, *args, **kwargs):
    globals.CESSION = not globals.CESSION
    if globals.CESSION and globals.PROHIBITIONS:
        globals.PROHIBITIONS = False
    write_globals_to_disk()
    text = button_names['cession_on'][2:] + (' ВКЛ' if globals.CESSION else ' ВЫКЛ')
    await telegram_bot.send_message(message.from_user.id, text, reply_markup=get_kbd(), parse_mode="HTML")


@dp.message_handler(Text(endswith=button_names['type_1_only_on'][2:]))
@check_whitelist
async def toggle_type1_only(message: types.Message, *args, **kwargs):
    globals.TYPE_1_ONLY = not globals.TYPE_1_ONLY
    if globals.TYPE_1_ONLY:
        globals.TYPE_2_ONLY = False
    write_globals_to_disk()
    text = button_names['type_1_only_on'][2:] + (' ВКЛ' if globals.TYPE_1_ONLY else ' ВЫКЛ')
    await telegram_bot.send_message(message.from_user.id, text, reply_markup=get_kbd(), parse_mode="HTML")


@dp.message_handler(Text(endswith=button_names['type_2_only_on'][2:]))
@check_whitelist
async def toggle_type2_only(message: types.Message, *args, **kwargs):
    globals.TYPE_2_ONLY = not globals.TYPE_2_ONLY
    if globals.TYPE_2_ONLY:
        globals.TYPE_1_ONLY = False
    write_globals_to_disk()
    text = button_names['type_2_only_on'][2:] + (' ВКЛ' if globals.TYPE_2_ONLY else ' ВЫКЛ')
    await telegram_bot.send_message(message.from_user.id, text, reply_markup=get_kbd(), parse_mode="HTML")


@dp.message_handler(Text(endswith=button_names['date_dirs_on'][2:]))
@check_whitelist
async def toggle_date_dirs(message: types.Message, *args, **kwargs):
    globals.DATE_DIRS = not globals.DATE_DIRS
    write_globals_to_disk()
    if globals.DATE_DIRS:
        text = 'В заданиях будут создавться каталоги для каждой отдельной даты'
    else:
        text = 'В заданиях будут создаваться каталоги по годам'
    await telegram_bot.send_message(message.from_user.id, text, reply_markup=get_kbd(), parse_mode="HTML")


@dp.message_handler(Text(equals=button_names['create_task']))
@check_whitelist
async def create_task(message: types.Message, *args, **kwargs):
    """Создание простого задания, стадия 1: Предлагаем ввести имя каталога"""
    text = f"ЗАДАНИЕ{' (Запреты и аресты)' if globals.PROHIBITIONS else ''}{' (Передача собственности)' if globals.CESSION else ''}: Введите название каталога"
    await TaskCreation.task_naming.set()
    await telegram_bot.send_message(message.from_user.id, text, reply_markup=get_kbd(), parse_mode="HTML")


@dp.message_handler(state=TaskCreation.task_naming)
@check_whitelist
async def input_task_name(message: types.Message, state: FSMContext,  *args, **kwargs):
    """Создание простого задания, стадия 2: Проверяем валидность имени и предлагаем ввести кадастровые номера"""
    dirname = message.text.strip()

    # проверяем что в имени папки нет недопустимых символов
    forbidden_chars = '/\:*?«<>|'
    if any([ch in dirname for ch in forbidden_chars]):
        chars = [ch for ch in forbidden_chars if ch in dirname]
        text = f"Данные символы нельзя использовать в имени каталога:\n{' '.join(chars)}\nЗадание отменено."
        await state.finish()
    else:
        await state.update_data(dirname=dirname)
        await TaskCreation.input_cad_nums.set()
        text = f"ЗАДАНИЕ{' (Запреты и аресты)' if globals.PROHIBITIONS else ''}{' (Передача собственности)' if globals.CESSION else ''}: Введите кадастровые номера"
    await telegram_bot.send_message(message.from_user.id, text, reply_markup=get_kbd(), parse_mode="HTML")


@dp.message_handler(state=TaskCreation.input_cad_nums)
@check_whitelist
async def input_cad_nums(message: types.Message, state: FSMContext,  *args, **kwargs):
    """Создание простого задания, стадия 3: Для каждого из найденных номеров копируем файлы в созданную папку и отправляем отчет"""
    found_cad_nums = extract_cad_nums(message.text)
    # если кадастровых номеров не найдено - ищем кадастровые районы
    use_cadaster_kvartals = False
    if not found_cad_nums:
        use_cadaster_kvartals = True
        found_cad_nums = extract_cad_raion(message.text)
    try:
        if found_cad_nums:
            found, years_count = {}, {}
            not_found, n_copied, cn_dates_and_sizes = [], 0, []
            text = 'ЗАПРЕТЫ И АРЕСТЫ\n' if globals.PROHIBITIONS else ''
            if globals.CESSION:
                text += 'ПЕРЕДАЧА СОБСТВЕННОСТИ\n'
            type2_files = get_type2_files_set()  # получаем множество полных имен файлов для всех выписок 2го типа в индексе
            for cad_num in found_cad_nums:
                results = docfetcher_search(f'"{cad_num}"')
                if results:
                    found[cad_num] = [r for r in results if r.getType() == 'xml']
                    """Если поставлены флаги Только 1го типа, Только 2го типа или Передача собственности -
                    оставляем в найденных только нужные файлы"""
                    if globals.TYPE_1_ONLY:
                        found[cad_num] = [r for r in found[cad_num] if r.getPathStr() not in type2_files]
                    if globals.TYPE_2_ONLY:
                        found[cad_num] = [r for r in found[cad_num] if r.getPathStr() in type2_files]
                    if globals.CESSION:
                        found[cad_num] = [r for r in found[cad_num] if check_cession(r.getPathStr())]
                else:
                    not_found.append(cad_num)

            if not_found:  # tесли есть кадастровые номера(районы), по которым результаты поиска нулевые
                text += 'Не найдены в базе:\n<code>'
                for cad_num in not_found:
                    text += f'{cad_num}\n'
                text += '</code>\n'
            else:
                if not globals.PROHIBITIONS:  # в режиме Запеты и аресты данная информация излишня
                    text += 'Все номера найдены в базe\n'

            if globals.CESSION:
                found = {k: v for k, v in found.items() if v}
                if not found:
                    text += 'Повторяющихся дат регистрации не обнаружено\n'

            if found:
                prohibitions = {f.getPathStr() for f in docfetcher_search(f'запрет арест')} if globals.PROHIBITIONS else {}
                state_data = await state.get_data()
                task_path = os.path.join(TASKS_ROOT, state_data['dirname'])
                if not os.path.exists(task_path):
                    os.makedirs(task_path)
                    text += f'Создан каталог:\n<code>{task_path}</code>\n'
                else:
                    text += f'Каталог уже существует:\n<code>{task_path}</code>\n'

                for cad_num in found:
                    DEBUGTEXT = f">>>> DEBUG <<<<\n{cad_num}---Найдено файлов: {len(found[cad_num])}\n"
                    print(f"{cad_num} Найдено файлов: {len(found[cad_num])}"+"-"*50)
                    for file in found[cad_num]:
                        DEBUGTEXT += f"__{file.getPathStr()}\n"
                        if globals.PROHIBITIONS and file.getPathStr() not in prohibitions:  # если включен режим "Запреты и аресты", то пропускаем все файлы, где нет запретов/арестов
                            continue
                        print('  -Файл', file.getPathStr())
                        try:
                            ext_date = get_date(file.getPathStr())
                            if not globals.DATE_DIRS:  # если пользователь не выбрал опцию Каталоги по Датам, то дата сокращаестся до года (и, соответственно выписки кладутся в подпапки по годам, а не по отдельным датам)
                                ext_date = ext_date[:4]
                            file_size = os.path.getsize(file.getPathStr())
                            ext_type = 2 if file.getPathStr() in type2_files else 1
                            if (cad_num, ext_date, file_size) not in cn_dates_and_sizes:  # обрабатываем файл только если файлов с тем же номером, датой и размером за эту сессию не обрабатывалось.
                                if not use_cadaster_kvartals or not globals.DATE_DIRS:  # если ищем не уникальные кадастровые номера, а кадастровые кварталы - проверку на уникльность выписок пропускаем
                                    cn_dates_and_sizes.append((cad_num, ext_date, file_size))
                                # каталог с датой/годом для выписки
                                ext_dir_path = os.path.join(task_path, ext_date)
                                if not os.path.exists(ext_dir_path):
                                    os.makedirs(ext_dir_path)
                                # конечное расположение файла выписки
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
                                    DEBUGTEXT += f"____имя: {target_filename}\n"
                            else:
                                print('\tОбработка пропущена, файл с таким содерижмым уже существует')
                                DEBUGTEXT += f"____содержимое: {cad_num}, {ext_date}, {file_size}\n"

                        except FileNotFoundError as ex:
                            print('\tФайл не доступен:', ex)
                        await telegram_bot.send_message(message.from_user.id, text=DEBUGTEXT)
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


@dp.message_handler()
@check_whitelist
async def default_input(message: types.Message, **kwargs):
    """Стандартный обработчик сообщений - ищет в сообщении кадастровые номера и сообщает есть ли в индексе файлы с таким номером в теле"""
    found_cad_nums = extract_cad_nums(message.text)
    # found_cad_nums = found_cad_nums if found_cad_nums else extract_cad_raion(message.text)
    text = ''
    try:
        if found_cad_nums:
            type2_files = get_type2_files_set()
            found, not_found, files_excluded = [], [], 0
            for cad_num in found_cad_nums:
                results_dataset = docfetcher_search(f'"{cad_num}"')
                if not results_dataset:
                    not_found.append(cad_num)
                else:
                    result_files = [r.getPathStr() for r in results_dataset if r.getType() == 'xml']
                    initial_len = len(result_files)

                    if globals.TYPE_1_ONLY:
                        result_files = [r for r in result_files if r not in type2_files]
                    elif globals.TYPE_2_ONLY:
                        result_files = [r for r in result_files if r in type2_files]
                    if len(result_files) != initial_len:
                        files_excluded += (initial_len-len(result_files))

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
            if files_excluded:
                text += f'Файлов исключено из поиска: {files_excluded}\n'

            if not_found:
                text += 'Не найдены в базе:\n<code>'
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
    get_globals_from_disk()
    executor.start_polling(dp, skip_updates=True)
