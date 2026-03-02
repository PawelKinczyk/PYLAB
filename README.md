# PYLAB

PYLAB is a pyRevit extension that adds custom productivity tools for Revit.

## Compatibility
- Revit 2022-2026
- pyRevit

## Repository Structure
- `PYLAB.extension/` main pyRevit extension package
- `PYLAB.extension/PYLAB.tab/` production tools
- `PYLAB.extension/lib/pylab/` shared Python helpers
- `docs/` install, migration, update, and authoring docs

## Quick Install
```powershell
pyrevit extend ui PYLAB https://github.com/PawelKinczyk/PYLAB.git
```

Then run:
```powershell
pyrevit reload
```

## Update to Latest
```powershell
pyrevit extensions update
pyrevit reload
```

For local clones tracking the official source:
```powershell
git checkout main
git pull --ff-only
pyrevit reload
```

## Documentation
- [Install](docs/install.md)
- [Migration](docs/migration.md)
- [Update](docs/update.md)
- [Add-on Authoring](docs/addon-authoring.md)

## Notes
Some commands rely on English Revit category names.
