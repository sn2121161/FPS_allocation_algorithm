# Git submodules
A Git submodule is a repository embedded inside another repository. The submodule has its own history; the repository it is embedded in is called a superproject [[gitsubmodules](https://git-scm.com/docs/gitsubmodules)].

# Quick summary
- Adding submodule
In your repository,
```
git submodule add <PATH/TO/A/REPOSITORY/AS/SUBMODULE> [<DIR_NAME>]
git submodule update --init --recursive
```

- Cloning a repository with submodules
```
git clone --recurse-submodules <URL_PATH>
```
or
```
git clone <URL_PATH>
git submodule update --init --recursive
```

- Pulling all changes including submodules
```
git pull --recurse-submodules
```

- Pulling all changes excluding submodules
```
git pull
```

# Basic workflow
## Adding a submodule
A repository can be added to another repository as a submodule by using `git submodule add` command.

### Using relative path
If the repository that you want to add as a submodule is the same organisation, the relative path can be used. 
```
git submodule add <RELATIVE/PATH/TO/A/REPOSITORY> [<DIR_NAME>]
```

For example, if you want to add `python_utils` as a submodule of `vehicle_energy_model_app` and both repositories are under `Flexible-Power-Systems`, 
in the `vehicle_energy_model_app` repository,
```
git submodule add ../python_utils.git
```
Then, a file `.gitsubmodules` and a directory `python_utils` will be created.
At this point the directory may be empty.

This is the content of the `.gitsubmodules`.
```
[submodule "python_utils"]
        path = python_utils
        url = ../python_utils.git
```
This case, ssh/https wouldn't matter.

### Using full path
Alternatively, the full path to the submodule repository can be used. 
```
git submodule add <URL/TO/A/SUBMODULE/REPOSITORY> [<DIR_NAME>]
```
`<DIR_NAME>` is optional. If it is not given, the repository name of `<URL/TO/A/SUBMODULE/REPOSITORY>` is used.

By executing this, a file `.gitsubmodules` and a directory `<DIR_NAME>` will be created. (Also, some config files in `.git` directory)
At this point the directory may be empty.

For example, if you want to add `python_utils` as a submodule of `vehicle_energy_model_app`, in the `vehicle_energy_model_app` repository,
```
git submodule add git@github.com:Flexible-Power-Systems/python_utils.git
```
Then, a file `.gitsubmodules` and a directory `python_utils` will be created.
At this point the directory may be empty.

This is the content of the `.gitsubmodules`.
```
[submodule "python_utils"]
        path = python_utils
        url = git@github.com:Flexible-Power-Systems/python_utils.git
```
As you can see above, "ssh" type git path is written in the file. This means that git clone using https may be failed.

## Updating the submodule
To fill the contents of the directory of the submodule that was added,
```
git submodule update --init --recursive
```


# Cloning a repository with submodules
To clone a repository with submodules,
```
git clone --recurse-submodules <URL/TO/A/REPOSITORY>
```
or
```
git clone <URL_PATH>
git submodule update --init --recursive
```

# Pulling all changes in the repositpry including the changes in the submodules
```
git pull --recurse-submodules
```

# Deleting a submodule
```
git submodule deinit <DIR_NAME>
git rm <DIR_NAME>
git commit-m "Removed submodule "
rm -rf .git/modules/<DIR_NAME>
```

# Alternative way of using git submodules
```
pip install git+https://github.com/Flexible-Power-Systems/python_utils.git
```


# Reference
1. [https://git-scm.com/docs/gitsubmodules](https://git-scm.com/docs/gitsubmodules)
2. [https://git-scm.com/docs/git-submodule](https://git-scm.com/docs/git-submodule)
3. [https://github.blog/2016-02-01-working-with-submodules](https://github.blog/2016-02-01-working-with-submodules)
