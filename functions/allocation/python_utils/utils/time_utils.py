# -*- coding: utf-8 -*-
'''
time_util.py
'''
import os
import sys

from datetime import datetime
from datetime import timedelta
import pytz

from numpy import cos
from numpy import sin
from numpy import pi as n_pi
from numpy import atleast_1d
from numpy import roll
from numpy import array as arr
from numpy import ndarray as ndarr

CDIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(CDIR)
from logger import logger


class TimeConverter(object):
    def __init__(self, **args):
        self.timeformat = args.get('timeformat', '%Y-%m-%d_%H-%M-%S')
        self.tzinfo = pytz.timezone(args.get('timezone', 'UTC'))

    def __del__(self):
        '''
        Destructor
        '''
        pass

    def set_timezone(self, timezonestr):
        '''
        set time zone
        @argv
        timezonestr: string to explain a timezone
                     'Asia/Tokyo' (default)
                     'GMT'
                     'UTC'
                     'Europe/London'
                     see more details with pytz.common_timezones
        '''
        self.tzinfo = pytz.timezone(timezonestr)
        logger.info('timezone set as: %s', self.tzinfo.zone)

    def set_timestring_format(self, timeformat):
        '''
        default  timeformat is '%Y-%m-%d_%H-%M-%S'.
        ### day
        %d: Day of the month (zero-padded decimal number) 01, 02, ..., 31
        %j: Day of the year (zero-padded decimal number) 001, 002, ..., 366
        ### Month
        %b: locale’s abbreviated name. Jan, Feb, ..
        %B: locale’s full name. January, February, ..
        %m: zero-padded decimal number. 01, 02,...
        ### year
        %y: without century as a zero-padded decimal number. 00, 01,...
        %Y: with century as a decimal number. 0001, 0002, ..., 2013, 2014
        ### hour
        %H: 24-hour clock as a zero-padded decimal number. 00, 01, ..., 23
        %I: 12-hour clock as a zero-padded decimal number. 01, 02, ..., 12
        %p: Locale’s equivalent of either. AM o PM
        ### minute
        %M  a zero-padded decimal number.: 00, 01, ..., 59
        ### second
        %S: a zero-padded decimal number.: 00, 01, ..., 59
        ### microsecond
        %f: a decimal number, zero-padded on the left.: 000000, 000001, ...
        ### timezone
        %z: UTC offset in the form +HHMM or -HHMM
        %Z: Time zone name
        ### Week
        %a: Weekday as locale’s abbreviated name.
            Sun, Mon, …, Sat (en_US);
            So, Mo, …, Sa (de_DE)
        %A: Weekday as locale’s full name.
            Sunday, Monday, …, Saturday (en_US);
            Sonntag, Montag, …, Samstag (de_DE)
        %w: Weekday as a decimal number
            where 0 is Sunday and 6 is Saturday.0, 1, …, 6
        %U: Sunday as the first day of the week as a zero padded decimal num.
        %W: Monday as the first day of the week as a decimal number
        ### date format
        %c: Locale’s appropriate date and time representaton.
            Tue Aug 16 21:30:00 1988
        %x: Locale’s appropriate date representation. 08/16/
        %X: Locale’s appropriate time representation. 21:30:
        ###
        %%: A literal '%' character.
        '''
        self.timeformat = timeformat

    def __datetime_naive2aware(self, d):
        if d.tzinfo is None:
            d = self.tzinfo.localize(d)
        return d

    def now(self, format='timestr'):
        dt = datetime.now()
        dt_now = self.__datetime_naive2aware(dt)
        if format == 'timestr':
            return self.datetime2timestr(dt_now)
        elif format == 'unixtime':
            return self.datetime2unixtime(dt_now)
        else:
            return dt_now

    def now_dt(self):
        return self.now(format='datetime')

    def now_ut(self):
        return self.now(format='unixtime')

    def now_ts(self):
        return self.now(format='timestr')

    def dt2ts(self, dt):
        ts = self.datetime2timestr(dt)
        return ts

    def datetime2timestr(self, d):
        '''
        datetime to unixtime
        @argv
        d: datetime object
        @return
        timestamp: string
        '''
        d = self.__datetime_naive2aware(d)
        timestr = d.strftime(self.timeformat)
        return timestr

    def dt2ut(self, dt):
        '''
        datetime to unixtime
        @argv
        dt: datetime object
        @return
        timestamp: int
        '''
        timestamp = self.datetime2unixtime(dt)
        return timestamp

    def datetime2unixtime(self, dt):
        '''
        datetime to unixtime
        @argv
        d: datetime object
        @return
        timestamp: int
        '''
        d = self.__datetime_naive2aware(dt)
        timestamp = d.replace(tzinfo=pytz.utc).timestamp()
        # timestamp = calendar.timegm(d.astimezone(pytz.utc).timetuple())
        # timestamp = calendar.timegm(d.utctimetuple())
        return timestamp

    def ts2ut(self, timestr):
        '''
        @argv
        timestr: string
        @return
        timestamp: unixtime, int
        '''
        d = self.timestr2unixtime(timestr)
        return d

    def timestr2unixtime(self, timestr):
        '''
        @argv
        timestr: string
        @return
        timestamp: unixtime, int
        '''
        try:
            d = self.timestr2datetime(timestr)
        except ValueError as e:
            raise e
        timestamp = self.datetime2unixtime(d)
        return timestamp

    def ut2dt(self, timestamp):
        '''
        @argv
        timestamp: time stamp. int or float
        @return
        d: datetime object
        '''
        d = self.unixtime2datetime(timestamp)
        return d

    def unixtime2datetime(self, timestamp):
        '''
        @argv
        timestamp: time stamp. int or float
        @return
        d: datetime object
        '''
        d = datetime.fromtimestamp(timestamp, self.tzinfo)
        return d

    def ts2dt(self, timestr):
        '''
        transfer time string to datetime.
        @argv
        timestr: string
        @return
        d: datetime object
        '''
        d = self.timestr2datetime(timestr)
        return d

    def timestr2datetime(self, timestr):
        '''
        transfer time string to datetime.
        @argv
        timestr: string
        @return
        d: datetime object
        '''
        d = datetime.strptime(timestr, self.timeformat)
        d = self.__datetime_naive2aware(d)

        return d

    def ut2ts(self, timestamp):
        '''
        @argv
        timestamp: int or float
        @return
        timestr: string
        '''
        d = self.unixtime2timestr(timestamp)
        return d

    def unixtime2timestr(self, timestamp):
        '''
        @argv
        timestamp: int or float
        @return
        timestr: string
        '''
        d = datetime.fromtimestamp(timestamp, self.tzinfo)
        timestr = d.strftime(self.timeformat)
        return timestr

    def any2ut(self, src):
        '''
        @argv
        src: string, datetime object, int or float.
        @return
        dst unixtime
        '''
        dst = self.anytype2unixtime(src)
        return dst

    def anytype2unixtime(self, src):
        '''
        @argv
        src: string, datetime object, int or float.
        @return
        dst unixtime
        '''
        if isinstance(src, str):
            dst = self.timestr2unixtime(src)
        elif isinstance(src, datetime):
            dst = self.datetime2unixtime(src)
        elif isinstance(src, int):
            dst = src
        elif isinstance(src, float):
            dst = src
        else:
            logger.error('input data type is not supported.', type(src))
            dst = src

        return dst

    def any2ts(self, src):
        '''
        @argv
        src: string, datetime object, int or float.
        @return
        dst: time string
        '''
        ts = self.anytype2timestr(src)
        return ts

    def anytype2timestr(self, src):
        '''
        @argv
        src: string, datetime object, int or float.
        @return
        dst: time string
        '''
        if isinstance(src, str):
            dst = src
        elif isinstance(src, datetime):
            dst = self.datetime2timestr(src)
        elif isinstance(src, int):
            dst = self.unixtime2timestr(src)
        elif isinstance(src, float):
            dst = self.unixtime2timestr(src)
        else:
            logger.error('the format is not supported.', type(src))
            dst = dst

        return dst

    def any2dt(self, src):
        '''
        @argv
        src: string, datetime object, int or float.
        @return
        dst: datetime
        '''
        dst = self.anytype2datetime(src)
        return dst

    def anytype2datetime(self, src):
        '''
        @argv
        src: string, datetime object, int or float.
        @return
        dst: datetime
        '''
        if isinstance(src, str):
            dst = self.timestr2datetime(src)
        elif isinstance(src, datetime):
            dst = src
        elif isinstance(src, int):
            dst = self.unixtime2datetime(src)
        elif isinstance(src, float):
            dst = self.unixtime2datetime(src)
        else:
            logger.error('input data type is not supported.', type(src))
            dst = src

        return dst


class TimeUtil(TimeConverter):
    '''
    tu = TimeUtil()
    tu = TimeUtil(timeformat='%Y-%m-%d_%H-%M-%S')
    tu = TimeUtil(timezone='Asia/Tokyo')
    tu = TimeUtil(timeformat='%Y-%m-%d_%H-%M-%S', timezone='Asia/Tokyo')
    __init__(self)
    timeformat='%Y-%m-%d_%H-%M-%S'
    timezone='Asia/Tokyo'
    __del__(self)
    set_timezone(timezonestr)
    set_timestring_format(timeformat)
    datetime2timestr(d)
    datetime2unixtime(d)
    timestr2unixtime(timestr)
    unixtime2datetime(timestamp)
    timestr2datetime(timestr)
    unixtime2timestr(timestamp)
    anytype2unixtime(src)
    __datetime_naive2aware(d)
    '''
    def __init__(self, **args):
        '''
        timeformat: string, see docs in set_timestring_format()
        timezone: string, one of the list "pytz.all_timezones"
        '''
        TimeConverter.__init__(self, **args)
        # self.timeformat = args.get('timeformat', '%Y-%m-%d_%H-%M-%S')
        # self.tzinfo = pytz.timezone(args.get('timezone', 'UTC'))

    def __del__(self):
        '''
        Destructor
        '''
        pass

    def convert_style(self, src, style='timestr'):
        '''
        time_style: timestr, datetime, or unixtime
        '''
        if style == 'timestr':
            dst = self.anytype2timestr(src)
        elif style == 'datetime':
            dst = self.anytype2unixtime(src)
        elif style == 'unixtime':
            dst = self.anytype2datetime(src)
        else:
            logger.error('%s does not supported' % style)
            raise NotImplementedError
        return dst

    def time_diff_seconds(self, t1, t2):
        if t1 < t2:
            df = self.anytype2datetime(t2) - self.anytype2datetime(t1)
        else:
            df = self.anytype2datetime(t1) - self.anytype2datetime(t2)
        return df.seconds

    def get_datetime(self, year, month, day, hour, minute, second):
        d = datetime(year, month, day, hour, minute, second)
        d = self.__datetime_naive2aware(d)
        return d

    def get_timedelta(self, d, **keys):
        delta_seconds = keys.get('seconds', 0)
        delta_minutes = keys.get('minutes', 0)
        delta_hours = keys.get('hours', 0)
        if delta_seconds == 0:
            if delta_minutes != 0:
                delta_seconds = delta_minutes * 60
            else:
                delta_seconds = delta_hours * 3600
        return d + timedelta(seconds=delta_seconds)

    def floor_time_by_hour(self, src):
        dt = self.anytype2datetime(src)
        dt = dt.replace(minute=0, second=0)
        if isinstance(src, int):
            dst = self.datetime2unixtime(dt)
        elif isinstance(src, str):
            dst = self.datetime2timestr(dt)
        elif isinstance(src, datetime):
            dst = dt
        return dst

    def ceil_time_by_hour(self, src):
        dt = self.anytype2datetime(src) + timedelta(hours=1)
        dt = dt.replace(minute=0, second=0)
        if isinstance(src, int):
            dst = self.datetime2unixtime(dt)
        elif isinstance(src, str):
            dst = self.datetime2timestr(dt)
        elif isinstance(src, datetime):
            dst = dt
        return dst

    def get_begin_of_the_day(self, src):
        src_dt = self.anytype2datetime(src)
        dst_dt = src_dt.replace(hour=0, minute=0, second=0)
        if isinstance(src, int):
            dst = self.datetime2unixtime(dst_dt)
        elif isinstance(src, str):
            dst = self.datetime2timestr(dst_dt)
        elif isinstance(src, datetime):
            dst = dst_dt
        return dst

    def get_begin_of_the_week(self, src):
        src_dt = self.anytype2datetime(src)
        dst_dt = src_dt - timedelta(days=src_dt.weekday())
        dst_dt = self.get_begin_of_the_day(dst_dt)
        if isinstance(src, int):
            dst = self.datetime2unixtime(dst_dt)
        elif isinstance(src, str):
            dst = self.datetime2timestr(dst_dt)
        elif isinstance(src, datetime):
            dst = dst_dt
        return dst

    def get_time_of_day_cat_hour(self, src, hour_range=1, hour_shift=0):
        '''
        @arguments
        src: np.array(data_len), or list(data_len), or int
        house_range: range to categolise the time of the day
        hour_shift: beginning of the day
        @output
        dst: np.array or int, (depends on the src)
        '''
        if not isinstance(src, list) and not isinstance(src, ndarr):
            src_list = [src]
        else:
            src_list = src
        num_hours_in_a_day = 24
        hours = range(num_hours_in_a_day)
        h_cat = [int(t / float(hour_range)) for t in roll(hours, hour_shift)]
        hour2cat = dict(zip(hours, h_cat))
        dst = arr([hour2cat[self.anytype2datetime(t).hour] for t in src_list])
        if len(dst) == 1:
            dst = dst[0]
        return dst

    def get_day_of_week_cat_day(self, src, day_range=1, day_shift=0):
        '''
        @arguments
        src: np.array(data_len), or list(data_len), or int
        house_range: range to categolise the time of the day
        hour_shift: beginning of the day
        @output
        dst: np.array or int, (depends on the src)
        '''
        if not isinstance(src, list) and not isinstance(src, ndarr):
            src_list = [src]
        else:
            src_list = src
        num_days_in_a_week = 7
        days = range(num_days_in_a_week)
        d_cat = [int(t / float(day_range)) for t in roll(days, day_shift)]
        day2cat = dict(zip(days, d_cat))
        dst = arr([day2cat[self.any2dt(t).weekday()] for t in src_list])
        if len(dst) == 1:
            dst = dst[0]
        return dst

    def get_time_of_day_sin_cos(self, src):
        len_day = 60 * 60 * 24
        src_ut = self.anytype2unixtime(src)
        bod = self.get_begin_of_the_day(src_ut)
        rel_ut = src_ut - bod
        dst = atleast_1d([
            sin(2 * n_pi * rel_ut / float(len_day)),
            cos(2 * n_pi * rel_ut / float(len_day))
        ])
        return dst

    def get_day_of_week_sin_cos(self, src):
        len_week = 60 * 60 * 24 * 7
        src_ut = self.anytype2unixtime(src)
        bow = self.get_begin_of_the_week(src_ut)
        rel_ut = src_ut - bow
        dst = atleast_1d([
            sin(2 * n_pi * rel_ut / float(len_week)),
            cos(2 * n_pi * rel_ut / float(len_week))
        ])
        return dst

    def is_in_period(self, src, period_bgn, period_end):
        s = self.anytype2unixtime(src)
        pb = self.anytype2unixtime(period_bgn)
        pe = self.anytype2unixtime(period_end)
        if pb <= s and s < pe:
            return True
        else:
            return False


# -----------------------------------------------------------------------------
def get_time_range_pairs(time_bgn, time_end, dur_sec, **args):
    '''
    @argv
    time_bgn: string, datetime or int(unixtime)
    time_end: string, datetime or int(unixtime)
    apply_hour_bgn: specific starting hour
    apply_hour_end: specific ending hour
    @output
    time_range_pairs: list of datetime pairs
    '''
    timeformat = args.get('timeformat', None)
    apply_hour_bgn = args.get('apply_hour_bgn', None)
    apply_hour_end = args.get('apply_hour_end', None)
    if isinstance(timeformat, str):
        tu = TimeUtil(timeformat=timeformat)
    else:
        tu = TimeUtil()
    dbgn = tu.anytype2datetime(time_bgn)
    dend = tu.anytype2datetime(time_end)
    time_range_pairs = []
    tb = dbgn
    while tb < dend:
        te = tb + timedelta(seconds=dur_sec)
        if apply_hour_bgn is not None or apply_hour_end is not None:
            ahb = datetime(tb.year,
                           tb.month,
                           tb.day,
                           apply_hour_bgn,
                           tzinfo=tu.tzinfo)
            ahe = datetime(tb.year,
                           tb.month,
                           tb.day,
                           apply_hour_end,
                           tzinfo=tu.tzinfo)
            if apply_hour_bgn > apply_hour_end:
                if tb.hour - apply_hour_bgn < 0:
                    ahb -= timedelta(hours=24)
                if ahe < ahb:
                    ahe += timedelta(days=1)
        else:
            ahb = tb
            ahe = te
        if ahb <= tb and te <= ahe:
            time_range_pairs.append([tb, te])
        tb = te
    return time_range_pairs


# -----------------------------------------------------------------------------
def main2():
    dbgn = '2015-06-30_19-00-00'
    dend = '2015-07-03_03-00-00'
    dur = 3600
    adbgn = 2
    adend = 5
    tmp = get_time_range_pairs(dbgn,
                               dend,
                               dur,
                               apply_hour_bgn=adbgn,
                               apply_hour_end=adend)
    print(dbgn, dend, dur, adbgn, adend)
    for t1, t2 in tmp:
        print(t1)
        print(t2)
        print('')


# -----------------------------------------------------------------------------
def main():
    tu = TimeUtil()

    print('time zone:', tu.tzinfo)

    orgts = '2014-09-01_12-40-00'

    print('--------------------------------------------------------')
    print('%25s' % 'input timestring:', orgts)
    org2ut = tu.timestr2unixtime(orgts)
    org2dt = tu.timestr2datetime(orgts)
    print('%25s' % 'timestring to datetime:', org2dt)
    print('%25s' % 'timestring to unixtime:', org2ut)

    timestamp = org2ut
    print('--------------------------------------------------------')
    print('%25s' % 'input unixtime:', timestamp)
    ut2str = tu.unixtime2timestr(timestamp)
    ut2dt = tu.unixtime2datetime(timestamp)
    print('%25s' % 'unixtime to string:', ut2str)
    print('%25s' % 'unixtime to datetime:', ut2dt)

    print('--------------------------------------------------------')
    print('%25s' % 'input datetime:', ut2dt)
    dt2str = tu.datetime2timestr(ut2dt)
    dt2ut = tu.datetime2unixtime(ut2dt)
    print('%25s' % 'datetime to timestring:', dt2str)
    print('%25s' % 'datetime to unixtime:', dt2ut)

    print('--------------------------------------------------------')
    now_ts = tu.now_ts()
    now_ts_2_ut = tu.timestr2unixtime(now_ts)
    now_ts_2_dt = tu.timestr2datetime(now_ts)
    print('%25s' % 'timestring to datetime:', now_ts_2_ut)
    print('%25s' % 'timestring to unixtime:', now_ts_2_dt)


if __name__ == '__main__':
    main()
    main2()
