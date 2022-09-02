import json
import globals


def write_globals_to_disk():
    settings = {'VERBOSE': globals.VERBOSE, 'PROHIBITIONS': globals.PROHIBITIONS, 'CESSION': globals.CESSION,
                'TYPE_1_ONLY': globals.TYPE_1_ONLY, 'TYPE_2_ONLY': globals.TYPE_2_ONLY}
    with open('user_settings.json', 'w') as file:
        json.dump(settings, file)


def get_globals_from_disk():
    try:
        with open('user_settings.json', 'r') as file:
            setttings = json.load(file)
        globals.VERBOSE = setttings['VERBOSE']
        globals.PROHIBITIONS = setttings['PROHIBITIONS']
        globals.CESSION = setttings['CESSION']
        globals.TYPE_1_ONLY = setttings['TYPE_1_ONLY']
        globals.TYPE_2_ONLY = setttings['TYPE_2_ONLY']
    except (FileNotFoundError, KeyError):
        print('Ошибка чтения пользовательских настроек')
