"""Shared parameter binding utilities.

Used by B8 (parameter category manager), B9 (Excel import), and G3 (project setup).

Handles cross-version CategorySet creation (Revit 2023 vs 2024+) with the same
try/except fallback pattern used in Bypass.pushbutton for SpecTypeId/UnitType.
"""

import clr
import System

from Autodesk.Revit.DB import (
    BindingMap,
    BuiltInCategory,
    CategorySet,
    Definition,
    ElementBinding,
    ExternalDefinition,
    InstanceBinding,
    TypeBinding,
)
from pyrevit import revit

doc = revit.doc
app = revit.app


def create_category_set():
    """Create an empty CategorySet, compatible with Revit 2023 and 2024+.

    Revit 2023: requires app.Create.NewCategorySet()
    Revit 2024+: supports CategorySet() constructor

    Returns a CategorySet instance.
    """
    try:
        cs = CategorySet()
        cs.Insert(None)  # won't actually insert None, just validates it's usable
        return CategorySet()
    except Exception:
        return app.Create.NewCategorySet()


def list_shared_parameters():
    """Return all shared parameter definitions from the shared parameter file.

    Returns list of dicts: {name, guid, group_name, definition (ExternalDefinition)}
    Returns empty list if no shared parameter file is configured.
    """
    results = []
    try:
        spf = app.OpenSharedParameterFile()
        if spf is None:
            return results

        for group in spf.Groups:
            group_name = group.Name
            for definition in group.Definitions:
                if definition is not None:
                    try:
                        results.append({
                            "name": definition.Name,
                            "guid": definition.GUID.ToString(),
                            "group_name": group_name,
                            "definition": definition,
                        })
                    except Exception:
                        pass
    except Exception:
        pass

    sorted_results = sorted(results, key=lambda d: (d["group_name"], d["name"]))
    return sorted_results


def get_bound_categories(definition):
    """Return set of BuiltInCategory values currently bound to this definition.

    Args:
        definition: ExternalDefinition from the shared parameter file.

    Returns:
        set of BuiltInCategory values (or empty set).
    """
    bound = set()
    try:
        bindings = doc.ParameterBindings

        # BindingMap supports indexer access by Definition
        binding = bindings.get_Item(definition)
        if binding is not None:
            for cat in binding.Categories:
                try:
                    builtin_cat = cat.BuiltInCategory
                    bound.Add(builtin_cat)
                except Exception:
                    pass
    except Exception:
        pass

    return bound


def set_bound_categories(definition, categories):
    """Set (replace) category bindings for a shared parameter.

    Args:
        definition: ExternalDefinition
        categories: list of BuiltInCategory values to bind to

    Cannot mutate existing Binding's CategorySet — builds a new Binding
    and calls BindingMap.ReInsert().

    Uses instance binding by default.
    """
    if not categories:
        return

    cs = create_category_set()
    for cat in categories:
        try:
            category_obj = doc.Settings.Categories.get_Item(cat)
            if category_obj is not None:
                cs.Insert(category_obj)
        except Exception:
            pass

    # Determine binding type — default to InstanceBinding
    try:
        new_binding = InstanceBinding(cs)
    except Exception:
        try:
            new_binding = app.Create.NewInstanceBinding(cs)
        except Exception:
            new_binding = app.Create.NewTypeBinding(cs)

    try:
        doc.ParameterBindings.ReInsert(definition, new_binding)
        doc.Regenerate()
    except Exception:
        # ReInsert fails on some versions — try Insert if definition is new
        doc.ParameterBindings.Insert(definition, new_binding)
        doc.Regenerate()


def remove_binding(definition):
    """Remove all category bindings for a shared parameter."""
    try:
        doc.ParameterBindings.Remove(definition)
        doc.Regenerate()
    except Exception:
        pass


def get_project_categories():
    """Return list of (BuiltInCategory, category_name) for categories that exist in the document.

    Filters to model categories (not annotation/internal).
    """
    results = []
    # All BuiltInCategory values
    builtin_cats = System.Enum.GetValues(
        clr.GetClrType(BuiltInCategory)
    )
    for cat in builtin_cats:
        try:
            cat_obj = doc.Settings.Categories.get_Item(cat)
            if cat_obj is not None and cat_obj.CategoryType.ToString() == "Model":
                results.append((cat, cat_obj.Name))
        except Exception:
            pass

    return sorted(results, key=lambda x: x[1].lower())
