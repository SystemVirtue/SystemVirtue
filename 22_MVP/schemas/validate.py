"""Minimal JSON Schema validator (stdlib only).

Supports the subset used by the SystemVirtue MVP schemas:
type (string or list, incl. "null"), enum, pattern, properties,
required, additionalProperties (bool), items (single schema),
minimum, maximum, minLength, maxLength, minItems, maxItems.

Per JSON Schema semantics, pattern/length checks apply only to strings
and numeric bounds only to numbers.
"""

import re


class SchemaError(ValueError):
    pass


_TYPE_CHECKS = {
    "object": lambda v: isinstance(v, dict),
    "array": lambda v: isinstance(v, list),
    "string": lambda v: isinstance(v, str),
    "boolean": lambda v: isinstance(v, bool),
    "null": lambda v: v is None,
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
}


def _type_ok(value, type_spec):
    types = type_spec if isinstance(type_spec, list) else [type_spec]
    for t in types:
        check = _TYPE_CHECKS.get(t)
        if check is None:
            raise SchemaError("unsupported schema type: %r" % t)
        if check(value):
            return True
    return False


def validate(instance, schema, path="$"):
    """Return a list of error strings; empty list means the instance is valid."""
    errors = []
    if not isinstance(schema, dict):
        raise SchemaError("schema must be an object")

    if "type" in schema and not _type_ok(instance, schema["type"]):
        errors.append("%s: expected type %r, got %s" % (path, schema["type"], type(instance).__name__))
        return errors  # further keyword checks are meaningless

    if "enum" in schema and instance not in schema["enum"]:
        errors.append("%s: value %r not in enum %r" % (path, instance, schema["enum"]))

    if isinstance(instance, str):
        if "pattern" in schema and not re.search(schema["pattern"], instance):
            errors.append("%s: %r does not match pattern %r" % (path, instance, schema["pattern"]))
        if "minLength" in schema and len(instance) < schema["minLength"]:
            errors.append("%s: %r shorter than minLength %d" % (path, instance, schema["minLength"]))
        if "maxLength" in schema and len(instance) > schema["maxLength"]:
            errors.append("%s: longer than maxLength %d" % (path, schema["maxLength"]))

    if isinstance(instance, (int, float)) and not isinstance(instance, bool):
        if "minimum" in schema and instance < schema["minimum"]:
            errors.append("%s: %r below minimum %r" % (path, instance, schema["minimum"]))
        if "maximum" in schema and instance > schema["maximum"]:
            errors.append("%s: %r above maximum %r" % (path, instance, schema["maximum"]))

    if isinstance(instance, list):
        if "minItems" in schema and len(instance) < schema["minItems"]:
            errors.append("%s: %d items, below minItems %d" % (path, len(instance), schema["minItems"]))
        if "maxItems" in schema and len(instance) > schema["maxItems"]:
            errors.append("%s: %d items, above maxItems %d" % (path, len(instance), schema["maxItems"]))
        if "items" in schema:
            for i, item in enumerate(instance):
                errors.extend(validate(item, schema["items"], "%s[%d]" % (path, i)))

    if isinstance(instance, dict):
        for key in schema.get("required", []):
            if key not in instance:
                errors.append("%s: missing required property %r" % (path, key))
        props = schema.get("properties", {})
        for key, value in instance.items():
            if key in props:
                errors.extend(validate(value, props[key], "%s.%s" % (path, key)))
            elif schema.get("additionalProperties") is False:
                errors.append("%s: unexpected property %r" % (path, key))

    return errors


def assert_valid(instance, schema, name="instance"):
    errors = validate(instance, schema)
    if errors:
        raise SchemaError("%s failed validation:\n  %s" % (name, "\n  ".join(errors)))
