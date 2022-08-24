import json
import globals


def write_globals_to_disk():
    settings = {'VERBOSE': globals.VERBOSE, 'PROHIBITIONS': globals.PROHIBITIONS, 'CESSION': globals.CESSION}
    with open('user_settings.json', 'w') as file:
        json.dump(settings, file)


def get_globals_from_disk():
    try:
        with open('user_settings.json', 'r') as file:
            setttings = json.load(file)
        globals.VERBOSE = setttings['VERBOSE']
        globals.PROHIBITIONS = setttings['PROHIBITIONS']
        globals.CESSION = setttings['CESSION']
    except (FileNotFoundError, KeyError):
        print('Ошибка чтения пользовательских настроек')
