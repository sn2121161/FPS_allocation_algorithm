# import psycopg2
# from python_utils.utils.logger import logger
import alloc_functions.cleanup as cleaner
# import alloc_functions.mixed as mixed
import alloc_functions.daily as daily
import alloc_functions.allocation_scenario as scenario
import alloc_functions.controller as controller
from python_utils.utils.logger import logger

RUNS = [215]
# ALLOCATIONS = [658, 639]


def main(runs):
    for r in runs:
        allocations = controller.main(r)
        # allocations = ALLOCATIONS
        for alloc in allocations:
            try:
                scenario.main(alloc)
                daily.main(alloc)
                cleaner.main(alloc)
                # mixed.main(alloc)

            except Exception as e:
                logger.error(e)
    return


if __name__ == '__main__':
    main(RUNS)
    # daily.run_unallocated(257)
