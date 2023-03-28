from datetime import time
from datetime import datetime
from datetime import timedelta


class SpecificTime():
    '''
    st = SpecificTime()
    st.now()
    st.start_of_the_day()
    st.end_of_the_day()

    st = SpecificTime(datetime)
    '''

    def __init__(self, now: datetime = None):
        '''
        now: datetime, defaule None (obtained by datetime.utcnow())
        '''
        self._now = datetime.utcnow() if now is None else now
        self._now = self._now.replace(microsecond=0)

    def now(self):
        '''
        return now
        '''
        dst = self._now
        return dst

    def start_of_the_day(self):
        '''
        return start of the day
        '''
        now = self.now()
        dst = now.replace(hour=0, minute=0, second=0, microsecond=0)
        return dst

    def end_of_the_day(self):
        '''
        return end of the day
        '''
        now = self.now()
        eotd = datetime.combine(now, time.max)
        # dst = eotd.replace(microsecond=0) + timedelta(seconds=1)
        dst = eotd.replace(microsecond=0)
        return dst

    def start_of_last_day(self):
        '''
        return start of last day
        '''
        dst = self.start_of_the_day() - timedelta(days=1)
        return dst

    def end_of_last_day(self):
        '''
        return end of last day
        '''
        dst = self.end_of_the_day() - timedelta(days=1)
        return dst

    def start_of_next_day(self):
        '''
        return start of next day
        '''
        dst = self.start_of_the_day() + timedelta(days=1)
        return dst

    def end_of_next_day(self):
        '''
        return end of next day
        '''
        dst = self.end_of_the_day() + timedelta(days=1)
        return dst

    def start_of_the_week(self):
        '''
        return start of the week
        '''
        sotd = self.start_of_the_day()
        dst = sotd - timedelta(days=sotd.weekday())
        return dst

    def end_of_the_week(self):
        '''
        return end of the week
        '''
        eotd = self.end_of_the_day()
        dst = eotd + timedelta(days=(6 - eotd.weekday()))
        return dst

    def start_of_last_week(self):
        '''
        return start of the last week
        '''
        sotw = self.start_of_the_week()
        dst = sotw - timedelta(days=7)
        return dst

    def end_of_last_week(self):
        '''
        return end of the last week
        '''
        sotw = self.start_of_the_week()
        dst = sotw - timedelta(seconds=1)
        return dst

    def start_of_next_week(self):
        '''
        return start of the next week
        '''
        eotw = self.end_of_the_week()
        dst = eotw + timedelta(seconds=1)
        return dst

    def end_of_next_week(self):
        '''
        return end of the next week
        '''
        sotw = self.end_of_the_week()
        dst = sotw + timedelta(days=7)
        return dst

    def start_of_the_month(self):
        '''
        return start of the month
        '''
        sotd = self.start_of_the_day()
        dst = sotd.replace(day=1)
        return dst

    def end_of_the_month(self):
        '''
        return end of the month
        '''
        eotd = self.end_of_the_day()
        tmp = eotd.replace(day=28) + timedelta(days=4)
        dst = tmp - timedelta(days=tmp.day)
        return dst

        return dst

    def start_of_last_month(self):
        '''
        return end of last month
        '''
        solm = self.end_of_last_month()
        dst = solm.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return dst

    def end_of_last_month(self):
        '''
        return end of last month
        '''
        sotm = self.start_of_the_month()
        dst = sotm - timedelta(seconds=1)
        return dst

    def start_of_next_month(self):
        '''
        return end of next month
        '''
        sotm = self.end_of_the_month()
        dst = sotm + timedelta(seconds=1)
        return dst

    def end_of_next_month(self):
        '''
        return end of next month
        '''
        eotm = self.end_of_the_month() + timedelta(days=1)
        tmp = eotm.replace(day=28) + timedelta(days=4)
        dst = tmp - timedelta(days=tmp.day)
        return dst


def main():
    from inspect import getargspec

    def print_result():
        print('-' * 100)
        method_names = [x for x in st.__dir__() if not x.startswith("_")]
        for method_name in method_names:
            method = getattr(st, method_name)
            argspec = getargspec(method)
            n_args = len(argspec[0])
            if n_args == 1:
                print('%20s: %s' % (method_name, method()))
            else:
                print('%20s: num args is %d' % (method_name, n_args))

    st = SpecificTime()
    print_result()

    dt = datetime(2022, 2, 2, 22, 22, 22)
    st = SpecificTime(dt)
    print_result()


if __name__ == '__main__':
    main()
