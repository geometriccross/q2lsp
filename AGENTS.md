# AGENTS.md
This is a documentation file for the various agents available in this repository.

## Project Structure
<Project Root>
├── src
│   └── q2lsp
│       ├── lsp
│       └── qiime
└── tests
    ├── lsp
    └── qiime


## Library information
### pygls
In this repository, pygls is available for lsp implementation.
This is tha pygls documentation link.

https://pygls.readthedocs.io/en/latest/


### qiime2
QIIME 2 is a framework for bioinformatics written in Python.
While QIIME2 is commonly used via the CLI, an API is also provided in Python, allowing native handling of its commands.

qiime2 ref: https://amplicon-docs.qiime2.org/en/stable/

The library used for QIIME 2 as a CLI is called `click`.
QIIME 2 is built upon the foundation of `click`.


## Coding Style
Keep it simple.
Don't use OOP features like inheritance.
You should add types for all.
Code with layered architecture in mind.


## Testing
In python codebase, we use `pytest` for testing.


## Typical traps
### Import
Cannot import/use q2cli RootCommand like this;
```python
import q2cli
q2cli.commands.RootCommand()
```

```bash
Traceback(most recent call last):
    File "/home/geometriccross/projects/q2gui/./main.py", line 14, in <module >
    root = q2cli.commands.RootCommand()
AttributeError: module 'q2cli' has no attribute 'commands'
```

So we need to use this way to import

```python
from q2cli.commands import RootCommand
```


### Get Command Instance
When obtaining an instance of a command defined in qiime2, please do so via `from q2cli.commands import RootCommand`.
You can also obtain an instance from `PluginManager`, but please do not use it in this case as it cannot retrieve builtin commands.


### Q2 Command Execution
qiime2 command are typically VERY HEAVY processes, except for help commands.

