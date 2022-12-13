from datetime import datetime


class Timer:
    """Отладочный таймер. Если время между вызовами метода click больше treshold - выводит сообщение"""
    def __init__(self, treshold=0):
        self.treshold = treshold
        self.time = datetime.now()

    def click(self, message=''):
        now = datetime.now()
        delta = now - self.time
        if delta.seconds > self.treshold:
            print(f">>>> {delta.seconds} > {message}")
        self.time = now
