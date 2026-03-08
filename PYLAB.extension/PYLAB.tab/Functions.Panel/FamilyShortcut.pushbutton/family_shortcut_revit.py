"""Revit API helpers for FamilyShortcut."""

import clr

clr.AddReference("PresentationFramework")

from Autodesk.Revit import DB
from Autodesk.Revit.DB import (
    BuiltInCategory,
    BuiltInParameter,
    CategoryType,
    FamilySymbol,
    FilteredElementCollector,
    Transaction,
)
from Autodesk.Revit.UI import ExternalEvent, IExternalEventHandler

from pyrevit import forms
from pyrevit import revit


EXCLUDED_CATEGORY_ENUM_NAMES = [
    "OST_GenericAnnotation",
    "OST_DetailComponents",
    "OST_TitleBlocks",
    "OST_Views",
    "OST_Viewports",
    "OST_RevisionClouds",
    "OST_SectionHeads",
    "OST_ElevationMarks",
    "OST_GridHeads",
    "OST_LevelHeads",
    "OST_DoorTags",
    "OST_WindowTags",
    "OST_RoomTags",
    "OST_AreaTags",
    "OST_SpaceTags",
    "OST_MultiCategoryTags",
    "OST_MaterialTags",
    "OST_StructuralFramingTags",
    "OST_StructuralColumnTags",
    "OST_PipeTags",
    "OST_DuctTags",
    "OST_GenericModelTags",
    "OST_CaseworkTags",
    "OST_FurnitureTags",
    "OST_LightingFixtureTags",
    "OST_PlumbingFixtureTags",
    "OST_SpecialityEquipmentTags",
]


def _build_excluded_category_ids():
    excluded_ids = set()
    for enum_name in EXCLUDED_CATEGORY_ENUM_NAMES:
        enum_value = getattr(BuiltInCategory, enum_name, None)
        if enum_value is not None:
            excluded_ids.add(int(enum_value))
    return excluded_ids


EXCLUDED_CATEGORY_IDS = _build_excluded_category_ids()


def get_symbol_name(symbol):
    try:
        name = symbol.Name
        if name:
            return name
    except Exception:
        pass

    for parameter_id in [
        BuiltInParameter.SYMBOL_NAME_PARAM,
        BuiltInParameter.ALL_MODEL_TYPE_NAME,
    ]:
        try:
            parameter = symbol.get_Parameter(parameter_id)
            if parameter is None:
                continue
            value = parameter.AsString() or parameter.AsValueString()
            if value:
                return value
        except Exception:
            continue

    try:
        return DB.Element.Name.GetValue(symbol)
    except Exception:
        return ""


def get_family_name(symbol):
    try:
        return symbol.Family.Name
    except Exception:
        return ""


def get_category_name(symbol):
    try:
        category = symbol.Category
        if category is None:
            return ""
        return category.Name or ""
    except Exception:
        return ""


def is_same_document(document_a, document_b):
    if document_a is None or document_b is None:
        return False

    try:
        if document_a.Equals(document_b):
            return True
    except Exception:
        pass

    try:
        if document_a.GetHashCode() == document_b.GetHashCode():
            return True
    except Exception:
        pass

    try:
        if document_a.Title == document_b.Title and document_a.PathName == document_b.PathName:
            return True
    except Exception:
        pass

    return False


def is_placeable_symbol(symbol):
    if not isinstance(symbol, FamilySymbol):
        return False

    try:
        family = symbol.Family
        if family is None or getattr(family, "IsInPlace", False):
            return False
    except Exception:
        return False

    try:
        category = symbol.Category
        if category is None:
            return False
        if category.CategoryType != CategoryType.Model:
            return False
        if category.Id.IntegerValue in EXCLUDED_CATEGORY_IDS:
            return False
    except Exception:
        return False

    return True


def collect_placeable_symbols(document=None):
    current_doc = document or revit.doc
    collector = (
        FilteredElementCollector(current_doc)
        .OfClass(FamilySymbol)
        .WhereElementIsElementType()
    )

    symbols = []
    for symbol in collector:
        if is_placeable_symbol(symbol):
            symbols.append(symbol)

    symbols.sort(
        key=lambda item: (
            get_category_name(item),
            get_family_name(item),
            get_symbol_name(item),
        )
    )
    return symbols


def resolve_symbol(document, assignment):
    family_name = assignment.family_name
    type_name = assignment.type_name
    category_name = assignment.category_name

    all_matches = []
    category_matches = []
    for symbol in collect_placeable_symbols(document):
        if get_family_name(symbol) != family_name:
            continue
        if get_symbol_name(symbol) != type_name:
            continue

        all_matches.append(symbol)
        if category_name and get_category_name(symbol) == category_name:
            category_matches.append(symbol)

    if category_name:
        if len(category_matches) == 1:
            return category_matches[0], None
        if len(category_matches) > 1:
            return None, (
                "Multiple family types match [{} : {}] in category [{}].".format(
                    family_name, type_name, category_name
                )
            )

    if len(all_matches) == 1:
        return all_matches[0], None

    if len(all_matches) > 1:
        return None, (
            "Multiple family types match [{} : {}] in the active model. "
            "Add category metadata in the shortcut manager to disambiguate.".format(
                family_name, type_name
            )
        )

    return None, "Family type [{} : {}] is not loaded in this model.".format(
        family_name, type_name
    )


def start_native_placement(symbol):
    active_uidoc = revit.uidoc
    active_doc = revit.doc

    if active_uidoc is None or active_doc is None:
        raise Exception("No active Revit document is available.")

    if symbol is None:
        raise Exception("No family type was provided for placement.")

    if not is_same_document(symbol.Document, active_doc):
        raise Exception("The active document changed before placement started.")

    if not symbol.IsActive:
        tx = Transaction(active_doc, "Activate FamilyShortcut type")
        try:
            tx.Start()
            symbol.Activate()
            active_doc.Regenerate()
            tx.Commit()
        except Exception as ex:
            if tx.HasStarted():
                tx.RollBack()
            raise Exception("Could not activate family type: {}".format(ex))

    try:
        active_uidoc.PostRequestForElementTypePlacement(symbol)
    except Exception as ex:
        raise Exception("Could not start native placement: {}".format(ex))


class PlacementRequest(object):
    def __init__(self):
        self.symbol = None
        self.success = False
        self.error_message = ""

    def set_symbol(self, symbol):
        self.symbol = symbol
        self.success = False
        self.error_message = ""

    def reset(self):
        self.symbol = None
        self.success = False
        self.error_message = ""


class PlacementExternalEventHandler(IExternalEventHandler):
    def __init__(self, request):
        self.request = request

    def Execute(self, uiapp):
        self.request.success = False
        self.request.error_message = ""

        try:
            start_native_placement(self.request.symbol)
            self.request.success = True
        except Exception as ex:
            self.request.error_message = str(ex)

    def GetName(self):
        return "FamilyShortcut Placement Handler"


def create_placement_external_event():
    request = PlacementRequest()
    handler = PlacementExternalEventHandler(request)
    external_event = ExternalEvent.Create(handler)
    return request, handler, external_event


def request_native_placement(symbol, request, external_event):
    request.set_symbol(symbol)
    external_event.Raise()


def build_symbol_picker_rows(document=None):
    rows = []
    for symbol in collect_placeable_symbols(document):
        rows.append(
            {
                "shortcut": "",
                "family_name": get_family_name(symbol),
                "type_name": get_symbol_name(symbol),
                "category_name": get_category_name(symbol),
            }
        )
    return rows


def show_revit_warning(message):
    forms.alert(
        message,
        title="FamilyShortcut",
        warn_icon=True,
        exitscript=False,
    )
