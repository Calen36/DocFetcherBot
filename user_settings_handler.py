import json
import globals


def write_globals_to_disk():
    settings = {'VERBOSE': globals.VERBOSE, 'PROHIBITIONS': globals.PROHIBITIONS}
    with open('user_settings.json', 'w') as file:
        json.dump(settings, file)


def get_globals_from_disk():
    with open('user_settings.json', 'r') as file:
        setttings = json.load(file)
    globals.VERBOSE = setttings['VERBOSE']
    globals.PROHIBITIONS = setttings['PROHIBITIONS']
