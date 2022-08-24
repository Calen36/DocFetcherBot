from aiogram import types
import globals


button_names = {'create_task': 'Создать задание',
                'verbose_off': '⬜ Подробный вывод',
                'verbose_on': '☑ Подробный вывод',
                'prohibitions_off': '⬜ Запреты и аресты',
                'prohibitions_on': '☑ Запреты и аресты',
                'cession_off': '⬜ Передача собственности',
                'cession_on': '☑ Передача собственности',
                }


kbd_voff_poff_coff = types.ReplyKeyboardMarkup(resize_keyboard=True)
kbd_voff_poff_coff.row(button_names['create_task'])
kbd_voff_poff_coff.row(button_names['verbose_off'], button_names['prohibitions_off'], button_names['cession_off'])

kbd_voff_pon_coff = types.ReplyKeyboardMarkup(resize_keyboard=True)
kbd_voff_pon_coff.row(button_names['create_task'])
kbd_voff_pon_coff.row(button_names['verbose_off'], button_names['prohibitions_on'], button_names['cession_off'])

kbd_voff_poff_con = types.ReplyKeyboardMarkup(resize_keyboard=True)
kbd_voff_poff_con.row(button_names['create_task'])
kbd_voff_poff_con.row(button_names['verbose_off'], button_names['prohibitions_off'], button_names['cession_on'])

kbd_von_poff_coff = types.ReplyKeyboardMarkup(resize_keyboard=True)
kbd_von_poff_coff.row(button_names['create_task'])
kbd_von_poff_coff.row(button_names['verbose_on'], button_names['prohibitions_off'], button_names['cession_off'])

kbd_von_pon_coff = types.ReplyKeyboardMarkup(resize_keyboard=True)
kbd_von_pon_coff.row(button_names['create_task'])
kbd_von_pon_coff.row(button_names['verbose_on'], button_names['prohibitions_on'], button_names['cession_off'])

kbd_von_poff_con = types.ReplyKeyboardMarkup(resize_keyboard=True)
kbd_von_poff_con.row(button_names['create_task'])
kbd_von_poff_con.row(button_names['verbose_on'], button_names['prohibitions_off'], button_names['cession_on'])


def get_kbd():
    if globals.VERBOSE and globals.PROHIBITIONS:
        return kbd_von_pon_coff
    elif globals.VERBOSE and globals.CESSION:
        return kbd_von_poff_con
    elif globals.VERBOSE:
        return kbd_von_poff_coff
    elif globals.PROHIBITIONS:
        return kbd_voff_pon_coff
    elif globals.CESSION:
        return kbd_voff_poff_con
    return kbd_voff_poff_coff
