# q2lsp

q2lsp helps users write QIIME 2 shell workflows by understanding QIIME commands well enough to provide completion, diagnostics, hover text, and editor actions.

## Language

**QIIME command catalog**:
The set of QIIME command facts q2lsp uses for completion, diagnostics, hover text, and editor actions. It includes roots, QIIME commands, actions, action signatures, option labels, requiredness, and help text.
_Avoid_: metadata

**QIIME command**:
The command name immediately under the `qiime` root command. A QIIME command may be a builtin command such as `info` or `tools`, or a plugin such as `diversity` or `feature-table`.
_Avoid_: plugin when the value may also be a builtin, subcommand

**QIIME action**:
A runnable item under a QIIME command. For plugin commands this corresponds to q2cli plugin actions; for builtin command groups, q2lsp also treats builtin subcommands as actions for catalog and editor behavior.
_Avoid_: operation

**command hierarchy**:
The raw tree of QIIME command information obtained from QIIME 2 command discovery. It is input to the QIIME command catalog, not the canonical language for feature behavior.
_Avoid_: catalog data, raw metadata

**action signature**:
The parameters and options accepted by a QIIME action, including their labels, kinds, requiredness, and descriptions.
_Avoid_: option metadata, parameter metadata

**QIIME command fact**:
A fact about QIIME command structure, action signatures, option labels, requiredness, or help text that is independent of how an editor displays it.
_Avoid_: feature result, editor output

**editor feature**:
A user-facing editor capability backed by QIIME command facts, such as completion, diagnostics, hover text, or CodeLens.
_Avoid_: feature

**Setup Wizard**:
A guided q2lsp onboarding flow that helps users either use an existing QIIME 2 environment or create a new QIIME 2 environment before configuring q2lsp to use it.
_Avoid_: diagnose command, generic setup flow

**QIIME 2 environment**:
A Python environment that contains QIIME 2 and may also contain q2lsp. The Setup Wizard treats this as the user-facing setup target, while the Python interpreter is the executable path saved for q2lsp.
_Avoid_: interpreter when referring to the environment as a whole, install

**QIIME 2 environment target**:
The version, distribution, platform, and environment file combination selected for creating a new QIIME 2 environment. After the Setup Wizard sends a creation command to the terminal, that target becomes the validation target until the user explicitly changes it.
_Avoid_: version selection, metadata

**Environment Diagnosis**:
A lightweight readiness check for the QIIME 2 environment q2lsp would use. It tells users whether the environment is ready and can route them to the Setup Wizard when guided repair or creation is needed.
_Avoid_: setup wizard, onboarding flow

## Example dialogue

Dev: “Should diagnostics read the command hierarchy directly?”
Domain expert: “No. Diagnostics should ask the QIIME command catalog whether a command path and option label are valid.”

Dev: “Where does the command hierarchy fit?”
Domain expert: “It is discovery input. Once loaded, editor feature behavior should speak in terms of the QIIME command catalog and action signatures.”

Dev: “Should the QIIME command catalog return diagnostic issues?”
Domain expert: “No. It should return QIIME command facts. Diagnostics turns those facts into editor-facing diagnostic results.”
