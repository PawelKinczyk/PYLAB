"""Naming standard validation engine — pure Python, no Revit API.

Used by D4 (naming check) and D8 (BIM standard compliance umbrella).

Config format (naming_standards.json):

    {
      "views": {
        "delimiter": "_",
        "segments": [
          {"name": "dyscyplina", "type": "closed", "variants": ["ARC","MEP","STR"]},
          {"name": "poziom", "type": "freetext", "min_len": 1, "max_len": 3},
          {"name": "typ", "type": "closed", "variants": ["RZUT","PRZEKROJ","3D"]},
          {"name": "opis", "type": "freetext", "max_len": 20}
        ]
      },
      "sheets": { ... },
      "families": { ... },
      "filters": { ... },
      "schedules": { ... }
    }

Each target key maps to a ruleset with a delimiter and an ordered list of
segment definitions. Segments are checked in order.
"""


class NamingViolation(object):
    """One naming rule violation."""

    def __init__(self, segment_index, segment_name, expected, actual):
        self.segment_index = segment_index
        self.segment_name = segment_name
        self.expected = expected
        self.actual = actual

    def __str__(self):
        return "segment {} ({}) — expected {}, got '{}'".format(
            self.segment_index,
            self.segment_name,
            self.expected,
            self.actual,
        )


def validate_name(name, ruleset):
    """Validate a single name against a ruleset.

    Args:
        name: the string to validate (e.g. "MEP_01_RZUT_parter")
        ruleset: dict with 'delimiter' and 'segments' keys

    Returns:
        list of NamingViolation (empty = valid)
    """
    delimiter = ruleset.get("delimiter", "_")
    segments = ruleset.get("segments", [])
    parts = name.split(delimiter)
    violations = []

    for i, seg_def in enumerate(segments):
        actual = parts[i] if i < len(parts) else ""
        seg_name = seg_def.get("name", "segment_{}".format(i))
        seg_type = seg_def.get("type", "freetext")

        if seg_type == "closed":
            variants = seg_def.get("variants", [])
            if actual not in variants:
                violations.append(
                    NamingViolation(
                        i,
                        seg_name,
                        "one of [{}]".format(", ".join(variants)),
                        actual if actual else "(missing)",
                    )
                )

        elif seg_type == "freetext":
            min_len = seg_def.get("min_len", 0)
            max_len = seg_def.get("max_len", None)

            if min_len and len(actual) < min_len:
                violations.append(
                    NamingViolation(
                        i,
                        seg_name,
                        "at least {} characters".format(min_len),
                        actual if actual else "(missing)",
                    )
                )
            elif max_len is not None and len(actual) > max_len:
                violations.append(
                    NamingViolation(
                        i,
                        seg_name,
                        "at most {} characters".format(max_len),
                        "{} ({} chars)".format(actual, len(actual)),
                    )
                )

    return violations


def validate_names(names, ruleset):
    """Validate a list of names. Returns {name: [violations]} for failed names only."""
    results = {}
    for name in names:
        violations = validate_name(name, ruleset)
        if violations:
            results[name] = violations
    return results
