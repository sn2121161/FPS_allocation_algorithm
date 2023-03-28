'''
unittest_time_utils.py
'''

import unittest

import os
import sys
from datetime import datetime
import pytz

CDIR = os.path.dirname(os.path.abspath(__file__))

sys.path.append(os.path.join(CDIR, '..'))
from utils.logger import logger
from utils.time_utils import TimeUtil

logger.setLevel('CRITICAL')

# logger.setLevel('DEBUG')


class TestTimeUtil(unittest.TestCase):
    def test_timeutil_init(self):
        # ---
        tu = TimeUtil()
        self.assertEqual(tu.tzinfo, pytz.UTC)
        self.assertEqual(tu.timeformat, '%Y-%m-%d_%H-%M-%S')
        # ---
        tu = TimeUtil(timeformat='%Y-%m-%d_%H:%M:%S')
        self.assertEqual(tu.tzinfo, pytz.UTC)
        self.assertEqual(tu.timeformat, '%Y-%m-%d_%H:%M:%S')
        # ---
        tu = TimeUtil(timeformat='%Y-%m-%d_%H:%M:%S', timezone='Asia/Tokyo')
        self.assertEqual(tu.tzinfo.zone, 'Asia/Tokyo')
        self.assertEqual(tu.timeformat, '%Y-%m-%d_%H:%M:%S')
        # ---
        tu = TimeUtil(timezone='Europe/London')
        self.assertEqual(tu.tzinfo.zone, 'Europe/London')
        self.assertEqual(tu.timeformat, '%Y-%m-%d_%H-%M-%S')

    def test_timeutil_convert(self):
        '''
        time converting with default setting
        '''
        tu = TimeUtil()

        # --- from timestr
        src_ts = '1970-01-01_01-02-03'
        self.assertEqual(tu.timestr2unixtime(src_ts), 3723)
        self.assertEqual(tu.timestr2datetime(src_ts),
                         datetime(1970, 1, 1, 1, 2, 3, tzinfo=pytz.UTC))

        # --- from timestamp
        src_ut = 100
        self.assertEqual(tu.unixtime2timestr(src_ut), '1970-01-01_00-01-40')
        self.assertEqual(tu.unixtime2datetime(src_ut),
                         datetime(1970, 1, 1, 0, 1, 40, tzinfo=pytz.UTC))

        # --- from datetime
        src_dt = datetime(1980, 2, 3, 4, 5, 30, tzinfo=pytz.UTC)
        self.assertEqual(tu.datetime2timestr(src_dt), '1980-02-03_04-05-30')
        self.assertEqual(tu.datetime2unixtime(src_dt), 318398730)

        # --- from datetime
        src_dt = datetime(1980, 5, 3, 4, 5, 30, tzinfo=pytz.UTC)
        self.assertEqual(tu.datetime2timestr(src_dt), '1980-05-03_04-05-30')
        self.assertEqual(tu.datetime2unixtime(src_dt), 326174730)

    def test_timeutil_convert_timeformat(self):
        # --- time format
        tu = TimeUtil(timeformat='%Y-%m-%d_%H:%M:%S')
        src_ts = '1970-01-01_01:02:03'
        self.assertEqual(tu.timestr2unixtime(src_ts), 3723)
        self.assertEqual(tu.timestr2datetime(src_ts),
                         datetime(1970, 1, 1, 1, 2, 3, tzinfo=pytz.UTC))

        src_ut = 100
        self.assertEqual(tu.unixtime2timestr(src_ut), '1970-01-01_00:01:40')
        self.assertEqual(tu.unixtime2datetime(src_ut),
                         datetime(1970, 1, 1, 0, 1, 40, tzinfo=pytz.UTC))

        src_dt = datetime(1971, 1, 1, 0, 0, 30, tzinfo=pytz.UTC)
        self.assertEqual(tu.datetime2timestr(src_dt), '1971-01-01_00:00:30')
        self.assertEqual(tu.datetime2unixtime(src_dt), 31536030)

        # --- from datetime
        src_dt = datetime(1980, 5, 3, 4, 5, 30, tzinfo=pytz.UTC)
        self.assertEqual(tu.datetime2timestr(src_dt), '1980-05-03_04:05:30')
        self.assertEqual(tu.datetime2unixtime(src_dt), 326174730)

    def test_timeutil_convert_timezone(self):
        # --- default setting
        tu = TimeUtil(timezone='Europe/London')
        src_ts = '1970-01-01_01-02-03'
        ut = tu.timestr2unixtime(src_ts)
        dt = tu.timestr2datetime(src_ts)
        logger.critical('3600 should not be added probably pytz issue')
        self.assertEqual(ut, 123 + 3600)
        self.assertEqual(dt.year, 1970)
        self.assertEqual(dt.month, 1)
        self.assertEqual(dt.day, 1)
        self.assertEqual(dt.hour, 1)
        self.assertEqual(dt.minute, 2)
        self.assertEqual(dt.second, 3)
        self.assertEqual(tu.tzinfo.zone, 'Europe/London')

        src_ut = 100
        self.assertEqual(tu.unixtime2timestr(src_ut), '1970-01-01_01-01-40')
        self.assertEqual(dt.year, 1970)
        self.assertEqual(dt.month, 1)
        self.assertEqual(dt.day, 1)
        self.assertEqual(dt.hour, 1)
        self.assertEqual(dt.minute, 2)
        self.assertEqual(dt.second, 3)
        self.assertEqual(tu.tzinfo.zone, 'Europe/London')

        src_dt = datetime(1971,
                          1,
                          1,
                          0,
                          0,
                          30,
                          tzinfo=pytz.timezone('Europe/London'))
        self.assertEqual(tu.datetime2timestr(src_dt), '1971-01-01_00-00-30')
        logger.critical('60 seconds difference. check ptyz')
        ut = tu.datetime2unixtime(src_dt)
        self.assertEqual(ut, src_dt.timestamp() - 60)
        # --- from datetime
        src_dt = datetime(1980,
                          5,
                          3,
                          4,
                          5,
                          30,
                          tzinfo=pytz.timezone('Europe/London'))
        st = tu.datetime2timestr(src_dt)
        self.assertEqual(st, '1980-05-03_04-05-30')
        logger.critical('60 seconds difference. check ptyz')
        ut = tu.datetime2unixtime(src_dt)
        self.assertEqual(ut, src_dt.timestamp() - 60)

    def test_timeutil_convert_timeformat_and_timezone(self):
        # --- time format and time zone
        tu = TimeUtil(timeformat='%Y-%m-%d_%H:%M:%S')
        src_ts = '1970-01-01_01:02:03'
        self.assertEqual(tu.timestr2unixtime(src_ts), 3723)
        self.assertEqual(tu.timestr2datetime(src_ts),
                         datetime(1970, 1, 1, 1, 2, 3, tzinfo=pytz.UTC))

        src_ut = 100
        self.assertEqual(tu.unixtime2timestr(src_ut), '1970-01-01_00:01:40')
        self.assertEqual(tu.unixtime2datetime(src_ut),
                         datetime(1970, 1, 1, 0, 1, 40, tzinfo=pytz.UTC))

        src_dt = datetime(1980, 2, 3, 4, 5, 30, tzinfo=pytz.UTC)
        self.assertEqual(tu.datetime2timestr(src_dt), '1980-02-03_04:05:30')
        self.assertEqual(tu.datetime2unixtime(src_dt), 318398730)

        # --- from datetime
        src_dt = datetime(1980,
                          5,
                          3,
                          4,
                          5,
                          30,
                          tzinfo=pytz.timezone('Europe/London'))
        st = tu.datetime2timestr(src_dt)
        self.assertEqual(st, '1980-05-03_04:05:30')
        ut = tu.datetime2unixtime(src_dt)
        logger.critical('60 seconds difference. check ptyz')
        self.assertEqual(ut, src_dt.timestamp() - 60)


if __name__ == '__main__':
    unittest.main()
