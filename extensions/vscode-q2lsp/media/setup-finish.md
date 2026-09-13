# Start writing QIIME 2 commands

Choose **Check and Save** to verify QIIME 2 and q2lsp again, then save the interpreter path.

- **Workspace** uses this environment for the current project.
- **User** uses it as your default across projects.

Open a `.sh` file and type `qiime ` to see command completions. Saving setup does not run a QIIME 2 workflow or activate your terminal.

Before running commands in a terminal, activate your QIIME 2 environment. For Pixi, use `pixi shell` in the project folder; the wizard includes QIIME 2 in `default`. For Conda, use `conda activate <environment-name>`. The wizard logs the exact activation command after creating and checking the environment; find it in [Show q2lsp Server Log](command:q2lsp.showServerLog).

```sh
qiime --help
```

If editor features do not start, use [Setup / Diagnose Environment](command:q2lsp.diagnoseEnvironment) or [Show q2lsp Server Log](command:q2lsp.showServerLog).
