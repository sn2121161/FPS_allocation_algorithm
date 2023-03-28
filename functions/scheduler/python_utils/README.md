# python_utils
Python utility modules

## add git repository as a submodule
In your repository, run these commands.
### Add submodule
- Relative path
```
$ git submodule add ../python_utils.git
```
- SSH
```
$ git submodule add git@github.com:Flexible-Power-Systems/python_utils.git
```
- HTTPS
```
$ git submodule add https://github.com/Flexible-Power-Systems/python_utils.git
```
###  Update
```
$ git submodule update --init --recursive
```
Then, in your python script,

```
CDIR = os.path.abspath(os.path.dirname(__file__))
UTIL_DIR = os.path.join(CDIR, RELATIVE_PATH_TO_THE_SUBMODULE)
sys.path.append(UTIL_DIR)
from utils.logger import logger
```
`RELATIVE_PATH_TO_THE_SUBMODULE` may be `../../python_utils`.

## installer
To install modules into your local environment, run setup.py.

If you need to use a virtual environment, prepare the environment before running setup.py

### install by setup.py
```
# --- install modules
$ python setup.py install
```
`python setup.py --help` for more details.

Alternatively, 
```
# --- pip install directly from github
pip install git+https://github.com/Flexible-Power-Systems/python_utils.git
```

#### reference
- [custom python pacage](https://towardsdatascience.com/create-your-custom-python-package-that-you-can-pip-install-from-your-git-repository-f90465867893)
- [install in conda environment](https://stackoverflow.com/questions/19042389/conda-installing-upgrading-directly-from-github)

### virtual environment
#### Linux (WSL, ubuntu)
```
# --- Create virtual environment
$ python -m venv .venv
$ source .venv/bin/activate
# --- Check
$ which python
```

#### Windows

