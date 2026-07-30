# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

PYLAB is a pyRevit extension (not a standalone app) — collection of IronPython/CPython3 scripts that add a **PYLAB** ribbon tab to Autodesk Revit. There is no build system, package manager, test suite, or CI. "Running" the code means loading it into Revit via pyRevit.

## Commands

There is no build/lint/test tooling in this repo. The only real "commands" are pyRevit CLI operations, run from PowerShell:

```powershell
# Register a local clone as an extension (dev loop)
pyrevit extend ui PYLAB "C:\path\to\PYLAB\PYLAB.extension"

# Reload after editing a script (Revit must be running)
pyrevit reload

# Update a GitHub-registered install
pyrevit extensions update
```

There is no automated way to execute Revit API code outside Revit — verifying a change means reloading pyRevit and clicking the button inside a running Revit session. Always sanity-check IronPython 2.7 syntax constraints (no f-strings in older scripts, `except Exception as e:` style) since some scripts run under pyRevit's IronPython engine.

## Architecture: panel-per-addon layout

Everything lives under `PYLAB.extension/PYLAB.tab/`, following pyRevit's bundle conventions. Full authoring guide: `docs/addon-authoring.md`.

```
PYLAB.extension/PYLAB.tab/bundle.yaml          <- tab-level layout (panel order)
PYLAB.extension/PYLAB.tab/<Name>.Panel/bundle.yaml   <- panel-level layout (button order)
PYLAB.extension/PYLAB.tab/<Name>.Panel/<Cmd>.pushbutton/
    bundle.yaml       <- title, tooltip, author
    script.py         <- entrypoint, must exist
    icon.dark.png / icon.light.png   <- theme-aware icons (some legacy buttons use single icon.png)
    <helper>.py       <- optional extra modules (only for larger tools, see FamilyShortcut)
```

Panels currently in layout order: **Info** (urlbuttons only — author/bug/feature links), **Functions** (general-purpose model tools), **MEPHelp** (pipe/duct/insulation/air-terminal workflows), **AECVisionIntegration** (CSV → wall import). `AirTerminalCalculator.pulldown` is a pulldown button group nesting three sibling pushbuttons.

To add a new tool: create a `.pushbutton` folder with `bundle.yaml` + `script.py`, then add its name to the parent panel's `bundle.yaml` `layout:` list. To add a whole new panel, create `<Name>.Panel/bundle.yaml` and add it to the tab-level `bundle.yaml`.

## Script conventions

- Entrypoint is always `script.py`. Multi-file tools (e.g. `FamilyShortcut.pushbutton/`) split into `<name>_manager.py` (UI/dialog), `<name>_revit.py` (Revit API calls), `<name>_runtime.py` (runtime/placement flow), `<name>_store.py` (persistence) — `script.py` stays a thin dispatcher that appends its own dir to `sys.path` and imports the helpers.
- Standard header pattern:
  ```python
  from pyrevit import revit
  from pyrevit import forms
  doc = revit.doc
  uidoc = revit.uidoc
  ```
  A few older scripts (`ActiveWorkset`) instead import `from rpw import revit` — prefer the `pyrevit.revit` style for new/edited code, don't mix the two in one file.
- Revit API mutations go through `Transaction`/`TransactionGroup` (see `Bypass.pushbutton/script.py` for a per-element sub-transaction pattern that rolls back individual failures without aborting the whole batch).
- Shift-click alternate behavior is detected via the pyRevit-injected `__shiftclick__` global (wrap in try/except — see `FamilyShortcut`, `Element3DFocus`, `PipeDuctOffset`). Used for opening settings/management dialogs instead of running the default action.
- Custom WinForms UI (bigger tools like `Bypass`, `PlaceInRoomsSpaces`) uses `clr.AddReference("System.Windows.Forms")` + `System.Windows.Forms` controls directly rather than pyRevit's `forms` helpers, since it needs richer layout than `forms.WPFWindow`/`forms.SelectFromList` provide.
- Persistent user settings/state are stored as JSON under `%APPDATA%\pyRevit\PYLAB\<ToolName>\...` (e.g. `FamilyShortcut\shortcuts.json`, `Bypass\last_run_debug.json`), not in the repo.
- Output/reporting uses pyRevit's `script.get_output()` / `output.get_output()` window rather than custom result dialogs.
- Some commands assume **English Revit category/parameter names** — this is a known limitation, not a bug to silently "fix" without checking `docs/button-guide.md` first.

## Docs to check before changing behavior

- `docs/button-guide.md` — authoritative per-button description of purpose, usage steps, internals, and settings. Update this when a tool's behavior, settings, or shift-click actions change.
- `docs/roadmap.md` — planned features (A-G categories), agreed architecture per item, branch names, and phase ordering/dependencies. Check this before starting new-feature work to see what's already scoped and which branch/foundation it depends on.
- `docs/addon-authoring.md` — the panel/button scaffolding rules (naming, bundle.yaml shape).
- `docs/install.md`, `docs/update.md`, `docs/migration.md` — end-user install/upgrade flows; only relevant if changing extension registration structure or requirements.
