import os
import sys

CDIR = os.path.abspath(os.path.dirname(__file__))

UTIL_DIR = os.path.join(CDIR, '..')

sys.path.append(CDIR)
from example_logger_main_func import main
from example_logger_main_func import main2

sys.path.append(UTIL_DIR)
from utils.logger import Logger

logger = Logger()

if __name__ == '__main__':
    main()
    logfilepath = os.path.join(CDIR, 'log_%s.txt' % os.path.basename(__file__))
    logger.init_file_handler(logfilepath)
    main()
    main2()
