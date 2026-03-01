# Install PYLAB Extension

## Requirements
- Autodesk Revit 2022-2026
- pyRevit installed and working

## Install from GitHub (recommended)
1. Open Command Prompt.
2. Run:

```powershell
pyrevit extend ui PYLAB https://github.com/PawelKinczyk/PYLAB.git
```

3. Restart Revit (or run `pyrevit reload`).
4. Verify new tabs are available:
- `PYLAB` (production tools)
- `PYLABDev` (developer/test tools)

## Install from local clone
1. Clone the repository locally.
2. Register local path:

```powershell
pyrevit extend ui PYLAB "C:\path\to\PYLAB\PYLAB.extension"
```

3. Restart Revit or run `pyrevit reload`.
