"""Persistent storage helpers for FamilyShortcut."""

import json
import os
import re
import tempfile
from datetime import datetime

import clr

clr.AddReference("mscorlib")

from System.IO import File


SCHEMA_VERSION = 1
SHORTCUT_PATTERN = re.compile(r"^[A-Z]{2}$")


class StorageError(Exception):
    pass


class ValidationError(Exception):
    pass


class ShortcutAssignment(object):
    def __init__(
        self,
        shortcut="",
        family_name="",
        type_name="",
        category_name="",
        enabled=True,
        created_utc=None,
        updated_utc=None,
        notes="",
    ):
        self.shortcut = normalize_shortcut(shortcut)
        self.family_name = normalize_name(family_name)
        self.type_name = normalize_name(type_name)
        self.category_name = normalize_name(category_name)
        self.enabled = bool(enabled)
        self.created_utc = created_utc or utc_now_text()
        self.updated_utc = updated_utc or self.created_utc
        self.notes = (notes or "").strip()

    def clone(self):
        return ShortcutAssignment(
            shortcut=self.shortcut,
            family_name=self.family_name,
            type_name=self.type_name,
            category_name=self.category_name,
            enabled=self.enabled,
            created_utc=self.created_utc,
            updated_utc=self.updated_utc,
            notes=self.notes,
        )

    def display_name(self):
        return "{} : {}".format(self.family_name, self.type_name)

    def to_dict(self):
        return {
            "shortcut": self.shortcut,
            "family_name": self.family_name,
            "type_name": self.type_name,
            "category_name": self.category_name,
            "enabled": self.enabled,
            "created_utc": self.created_utc,
            "updated_utc": self.updated_utc,
            "notes": self.notes,
        }

    @staticmethod
    def from_dict(data):
        if not isinstance(data, dict):
            raise ValidationError("Assignment entry must be an object.")
        return ShortcutAssignment(
            shortcut=data.get("shortcut", ""),
            family_name=data.get("family_name", ""),
            type_name=data.get("type_name", ""),
            category_name=data.get("category_name", ""),
            enabled=data.get("enabled", True),
            created_utc=data.get("created_utc"),
            updated_utc=data.get("updated_utc"),
            notes=data.get("notes", ""),
        )


class ShortcutStore(object):
    def __init__(self, file_path=None):
        self.file_path = file_path or get_storage_file_path()

    def load(self):
        return load_assignments(self.file_path)

    def save(self, assignments):
        return save_assignments(assignments, self.file_path)


def utc_now_text():
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


def normalize_name(text):
    return (text or "").strip()


def normalize_shortcut(text):
    value = (text or "").strip().upper()
    if not value:
        return ""

    filtered = []
    for char in value:
        if "A" <= char <= "Z":
            filtered.append(char)
    return "".join(filtered)[:2]


def is_valid_shortcut(shortcut):
    return bool(SHORTCUT_PATTERN.match(shortcut or ""))


def get_storage_folder_path():
    appdata_path = os.environ.get("APPDATA")
    if not appdata_path:
        raise StorageError("APPDATA environment variable is not available.")
    return os.path.join(appdata_path, "pyRevit", "PYLAB", "FamilyShortcut")


def get_storage_file_path():
    return os.path.join(get_storage_folder_path(), "shortcuts.json")


def ensure_storage_folder(file_path):
    folder_path = os.path.dirname(file_path)
    if not os.path.isdir(folder_path):
        os.makedirs(folder_path)


def build_payload(assignments):
    return {
        "schema_version": SCHEMA_VERSION,
        "assignments": [assignment.to_dict() for assignment in assignments],
    }


def validate_assignments(assignments):
    errors = []
    seen_shortcuts = {}

    for index, assignment in enumerate(assignments):
        row_label = "Row {}".format(index + 1)

        if not is_valid_shortcut(assignment.shortcut):
            errors.append("{}: shortcut must contain exactly 2 letters.".format(row_label))

        if not assignment.family_name:
            errors.append("{}: family name is required.".format(row_label))

        if not assignment.type_name:
            errors.append("{}: type name is required.".format(row_label))

        if assignment.enabled:
            existing_index = seen_shortcuts.get(assignment.shortcut)
            if existing_index is not None:
                errors.append(
                    "{}: shortcut '{}' conflicts with row {}.".format(
                        row_label, assignment.shortcut, existing_index + 1
                    )
                )
            else:
                seen_shortcuts[assignment.shortcut] = index

    return errors


def load_assignments(file_path=None):
    target_path = file_path or get_storage_file_path()
    if not os.path.exists(target_path):
        return []

    try:
        with open(target_path, "r") as stream:
            payload = json.load(stream)
    except ValueError:
        raise StorageError(
            "Shortcut storage file is not valid JSON:\n{}".format(target_path)
        )
    except Exception as ex:
        raise StorageError(
            "Could not read shortcut storage file:\n{}\n\n{}".format(target_path, ex)
        )

    if not isinstance(payload, dict):
        raise StorageError("Shortcut storage file root must be a JSON object.")

    assignments_data = payload.get("assignments", [])
    if not isinstance(assignments_data, list):
        raise StorageError("Shortcut storage 'assignments' must be a JSON array.")

    assignments = []
    for item in assignments_data:
        assignments.append(ShortcutAssignment.from_dict(item))
    return assignments


def replace_file_safely(source_path, target_path):
    if hasattr(os, "replace"):
        os.replace(source_path, target_path)
        return

    if File.Exists(target_path):
        backup_path = target_path + ".bak"
        if File.Exists(backup_path):
            File.Delete(backup_path)
        File.Replace(source_path, target_path, backup_path)
        if File.Exists(backup_path):
            File.Delete(backup_path)
        return

    File.Move(source_path, target_path)


def save_assignments(assignments, file_path=None):
    target_path = file_path or get_storage_file_path()
    validation_errors = validate_assignments(assignments)
    if validation_errors:
        raise ValidationError("\n".join(validation_errors))

    ensure_storage_folder(target_path)
    payload = build_payload(assignments)

    temp_fd, temp_path = tempfile.mkstemp(prefix="familyshortcut_", suffix=".json")
    try:
        with os.fdopen(temp_fd, "w") as stream:
            json.dump(payload, stream, indent=2, sort_keys=False)
        replace_file_safely(temp_path, target_path)
    except Exception as ex:
        try:
            if os.path.exists(temp_path):
                os.remove(temp_path)
        except Exception:
            pass
        raise StorageError(
            "Could not save shortcut storage file:\n{}\n\n{}".format(target_path, ex)
        )

    return target_path
