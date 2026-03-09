# PYLAB - pyRevit Extension

PYLAB is a collection of productivity tools for Autodesk Revit built with pyRevit. It adds a dedicated **PYLAB** tab to the Revit ribbon with grouped tools for model management, MEP workflows, coordination tasks, and project-specific utilities.

## Features
- **General** panel tools for copying filters and parameters, switching active worksets, finding linked element IDs, focusing elements in 3D, resetting section boxes, measuring model elements, placing families in rooms or spaces, and launching family shortcuts.
- **MEP** panel tools for pipe and duct offset workflows, parallel pipe connection, bypass creation, insulation placement, batch pipe type changes, and air terminal calculator commands for supply and return layouts.
- **AECVision integration** tools for creating Revit walls from AECVision-generated CSV data.
- **Information** panel links for author details, bug reporting, and feature requests.
- Installation, update, migration, and add-on authoring docs in the repository `docs/` folder.
- Practical command groupings that map directly to the ribbon layout used inside Revit.

## Installation
Install directly from GitHub:

```powershell
pyrevit extend ui PYLAB https://github.com/PawelKinczyk/PYLAB.git
```

Or register a local clone:

```powershell
pyrevit extend ui PYLAB "C:\path\to\PYLAB\PYLAB.extension"
```

Reload pyRevit:

```powershell
pyrevit reload
```

## Requirements
- Autodesk Revit 2022-2026
- pyRevit installed and working
- Some commands rely on English Revit category names

## Usage
After installation, the **PYLAB** tab appears in the Revit ribbon with these panels:

- **Information**: author link, bug report shortcut, and feature idea shortcut.
- **General**: day-to-day model utilities such as copying data between views and parameters, locating elements, section-box management, family placement helpers, and quantity-style measurements.
- **MEP**: pipe, duct, insulation, bypass, and air terminal workflows intended for faster MEP production work.
- **AECVision integration**: import-oriented workflow for generating walls from AECVision CSV exports.

Some tools support extra behavior on **Shift-click**, including settings and management dialogs. Current examples include `Family Shortcut`, `Element 3D Focus`, and commands with dedicated calculator settings in the MEP panel.

Additional documentation:

- [Install](docs/install.md)
- [Update](docs/update.md)
- [Migration](docs/migration.md)
- [Add-on Authoring](docs/addon-authoring.md)
- [Button Guide](docs/button-guide.md)

## Update
If PYLAB was installed through pyRevit extension registration:

```powershell
pyrevit extensions update
pyrevit reload
```

If you use a local git clone:

```powershell
git checkout main
git pull --ff-only
pyrevit reload
```

## License
GPL-3.0
