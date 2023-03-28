import os
import sys

from datetime import datetime
from datetime import timedelta

CDIR = os.path.dirname(os.path.abspath(__file__))

sys.path.append(CDIR)
from logger import logger
from time_utils import TimeUtil
from specific_time import SpecificTime


class StartAndEndTime():
    '''
    datetime_pair = StartAndEndTime()
    datetime_pair.bgn_and_end_of_today()
    datetime_pair.hours_before_and_end_of_today(hours)
    datetime_pair.hours_before_and_now(hours)
    datetime_pair.hours_before_and_now(hours)
    '''

    def __init__(self, now=None, **args):
        self._now = datetime.utcnow() if now is None else now
        self._timeformat = args.get('timeformat', '%Y-%m-%d %H:%M:%S')
        self._st = SpecificTime(self._now)

    def _datetime_to_timestr(self, dt1, dt2):
        tu = TimeUtil(timeformat=self._timeformat)
        ts1 = tu.dt2ts(dt1)
        ts2 = tu.dt2ts(dt2)
        return ts1, ts2

    def bgn_and_end_of_today(self):
        '''
        Returns date time strings of start and end of today

        Returns
        bgn_date: str, '%Y-%m-%d %H:%M:%S', start of today
        end_date: str, '%Y-%m-%d %H:%M:%S', end of today
        '''
        bod = self._st.start_of_the_day()
        eod = self._st.end_of_the_day()
        bgn_date, end_date = self._datetime_to_timestr(bod, eod)

        return bgn_date, end_date

    def hours_before_and_end_of_today(self, hours):
        '''
        Returns date time strings of
        hours before the end of today and end of today

        Args
        hours: int, hours before the end of today

        Returns
        bgn_date: str, '%Y-%m-%d %H:%M:%S', hours before the end of today
        end_date: str, '%Y-%m-%d %H:%M:%S', end of today
        '''
        eod = self._st.end_of_the_day()
        bod = eod - timedelta(hours=hours)
        bgn_date, end_date = self._datetime_to_timestr(bod, eod)
        return bgn_date, end_date

    def hours_before_and_end_of_last_month(self, hours):
        '''
        Returns date time strings of
        hours before the end of last month and end of last month

        Args
        hours: int, hours before the end of today

        Returns
        bgn_date: str, '%Y-%m-%d %H:%M:%S', hours before the end of last month
        end_date: str, '%Y-%m-%d %H:%M:%S', end of last mounth
        '''
        eod = self._st.end_of_last_month()
        bod = eod - timedelta(hours=hours)
        bgn_date, end_date = self._datetime_to_timestr(bod, eod)
        return bgn_date, end_date

    def hours_before_and_now(self, hours):
        '''
        Returns hours before now and now

        Args
        hours: int, hours before now

        Returns
        bgn_date: str, '%Y-%m-%d %H:%M:%S', hours before now
        end_date: str, '%Y-%m-%d %H:%M:%S', now
        '''
        eod = self._st.now()
        bod = eod - timedelta(hours=hours)
        bgn_date, end_date = self._datetime_to_timestr(bod, eod)
        return bgn_date, end_date

    def hours_before_and_start_of_today(self, hours):
        '''
        Returns hours before start of today and start of today

        Args
        hours: int, hours before now

        Returns
        bgn_date: str, '%Y-%m-%d %H:%M:%S', hours before now
        end_date: str, '%Y-%m-%d %H:%M:%S', now
        '''
        eod = self._st.start_of_the_day()
        bod = eod - timedelta(hours=hours)
        bgn_date, end_date = self._datetime_to_timestr(bod, eod)
        return bgn_date, end_date


def main():

    from inspect import getargspec

    def _result_dic():
        dst = {}
        method_names = [x for x in saet.__dir__() if not x.startswith("_")]
        for method_name in method_names:
            method = getattr(saet, method_name)
            argspec = getargspec(method)
            n_args = len(argspec[0])
            if n_args == 1:
                ret = method()
            elif n_args == 2:
                ret = method(hours)
            else:
                raise NotImplementedError('%s not supported' % method_name)
            dst[method_name] = ret
        return dst

    def _print_res(res):
        for k, v in res.items():
            v0 = '\'%s\'' % v[0]
            v1 = '\'%s\'' % v[1]
            k = '\'%s\'' % k
            print('%40s: (%s, %s,),' % (k, v0, v1))

    hours = 7
    saet = StartAndEndTime()
    res = _result_dic()
    _print_res(res)

    dt = datetime(2022, 2, 2, 22, 22, 22)
    saet = StartAndEndTime(dt)
    res = _result_dic()
    _print_res(res)


if __name__ == '__main__':
    main()
