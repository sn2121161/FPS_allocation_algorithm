import os
import sys

from datetime import datetime
from datetime import time
from datetime import timedelta

CDIR = os.path.dirname(os.path.abspath(__file__))

sys.path.append(CDIR)
from logger import logger
from time_utils import TimeUtil
from IPython import embed


class DateTimePairs():
    '''
    '''

    def __init__(self, **args):
        '''
        timeformat: default '%Y-%m-%d %H:%M:%S'
        '''
        timeformat = args.get('timeformat', '%Y-%m-%d %H:%M:%S')
        self._tu = TimeUtil(timeformat=timeformat)

    def _to_datetime(self, bgn_date, end_date):
        bgn_dt = self._tu.anytype2datetime(bgn_date)
        end_dt = self._tu.anytype2datetime(end_date)
        return bgn_dt, end_dt

    def _to_src_dtype(self, src, dtype):
        if dtype is None or isinstance(src, dtype):
            dst = src
        elif dtype == int or dtype == float:
            dst = self._tu.anytype2unixtime(src)
            if dtype == int:
                dst = int(dst)
        elif dtype == datetime:
            dst = self._tu.anytype2datetime(src)
        elif dtype == str:
            dst = self._tu.anytype2timestr(src)
        else:
            msg = '%s -> %s not supported' % (type(src), dtype)
            raise NotImplementedError(msg)
        return dst

    def _end_of_the_day(self, src_dt):
        '''
        Args
        src_dt: datetime

        Returns
        dst_dt: datetime
        '''
        dst_dt = datetime.combine(src_dt, time.max)
        dst_dt = dst_dt.replace(tzinfo=src_dt.tzinfo)
        dst_dt = dst_dt.replace(microsecond=0)
        return dst_dt

    def _begin_of_the_day(self, src_dt):
        '''
        Args
        src_dt: datetime

        Returns
        dst_dt: datetime
        '''
        dst_dt = src_dt.replace(hour=0, minute=0, second=0, microsecond=0)
        return dst_dt

    def _iter_daily_dt(self, bgn_date_dt, end_date_dt):
        bgn_eod = self._end_of_the_day(bgn_date_dt)
        end_dt = bgn_eod
        bgn_dt = bgn_date_dt
        while bgn_dt <= end_date_dt:
            yield bgn_dt, end_dt
            if end_dt >= end_date_dt:
                break
            end_dt += timedelta(days=1)
            if end_dt > end_date_dt:
                end_dt = end_date_dt
            bgn_dt = self._begin_of_the_day(end_dt)

    def iter_daily(self, bgn_date, end_date, dst_dtype=datetime):
        '''
        Returns pairs of beginning and end of the day between
        bgn_date and end_date.
        Args
        bgn_date: str, datetime or int(unixtime)
        end_date: str, datetime or int(unixtime)
        dst_dtype: destination data type, str, datetime, float, or int.
                   default datetime

        Returns
        pair_bgn: dst_dtype
        pair_end: dst_dtype
        '''
        b_date_dt, e_date_dt = self._to_datetime(bgn_date, end_date)
        for pair in self._iter_daily_dt(b_date_dt, e_date_dt):
            pair = (self._to_src_dtype(pair[0], dst_dtype),
                    self._to_src_dtype(pair[1], dst_dtype))
            yield pair


def main():
    bgn_date = '2022-03-20 08:00:00'
    end_date = '2022-03-29 12:00:00'
    dtp = DatetimePairs()
    for bt, et in dtp.iter_daily(bgn_date, end_date, int):
        print(bt, et)


if __name__ == '__main__':
    main()
