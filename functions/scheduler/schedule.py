from scheduling_functions import controller
from scheduling_functions import schedule_scenario
# import numpy as np

scenarios = []

if __name__ == '__main__':
    if scenarios == []:
        scenarios = controller.main()
    for scen in scenarios:
        schedule_scenario.main(scen)
