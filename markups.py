from aiogram import types
import globals


button_names = {'create_task': 'Создать задание',
                'verbose_off': '⬜ Подробный вывод',
                'verbose_on': '☑ Подробный вывод',
                'prohibitions_off': '⬜ Запреты и аресты',
                'prohibitions_on': '☑ Запреты и аресты',
                'cession_off': '⬜ Передача собственности',
                'cession_on': '☑ Передача собственности',
                'type_1_only_on': '☑ Только 1го типа',
                'type_1_only_off': '⬜ Только 1го типа',
                'type_2_only_on': '☑ Только 2го типа',
                'type_2_only_off': '⬜ Только 2го типа',
                }


def get_kbd():
    kbd = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kbd.row(button_names['create_task'])
    kbd.row(button_names['verbose_on'] if globals.VERBOSE else button_names['verbose_off'],
            button_names['prohibitions_on'] if globals.PROHIBITIONS else button_names['prohibitions_off'],
            button_names['cession_on'] if globals.CESSION else button_names['cession_off'])
    kbd.row(button_names['type_1_only_on'] if globals.TYPE_1_ONLY else button_names['type_1_only_off'],
            button_names['type_2_only_on'] if globals.TYPE_2_ONLY else button_names['type_2_only_off'])
    return kbd
