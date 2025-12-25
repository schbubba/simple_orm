# generate_dto.py

from __future__ import annotations

import importlib
import inspect
import pkgutil
import pathlib
from typing import (
    get_origin, get_args, List, TYPE_CHECKING, ForwardRef
)

from simple_orm.entity import Entity
from simple_orm import Field
from api_dto import is_sensitive_field, SensitiveFields
from simple_orm.file_writer import FileWriter
from simple_orm.class_writer import ClassWriter

SensitiveFields().initialize(fields=["id"])

# ---------------------------------------------------------
# Import all entity modules so subclass lookup works
# ---------------------------------------------------------
def import_entities_from_path(module_path: str):
    pkg = importlib.import_module(module_path)

    for _, mod_name, _ in pkgutil.walk_packages(pkg.__path__, pkg.__name__ + "."):
        importlib.import_module(mod_name)


# ---------------------------------------------------------
# Convert a Python or typing type to a clean annotation string
# ---------------------------------------------------------
def type_to_str(t) -> str:
    # Handle ForwardRef("ClassName")
    if isinstance(t, ForwardRef):
        return t.__forward_arg__

    origin = get_origin(t)

    # List[X]
    if origin in (list, List):
        args = get_args(t)
        inner = args[0] if args else "Any"
        return f"List[{type_to_str(inner)}]"

    # Entity → reference to another DTO
    if inspect.isclass(t) and issubclass(t, Entity):
        return t.__name__

    # datetime, date, etc.
    try:
        return t.__name__
    except Exception:
        return str(t).replace("typing.", "")


# ---------------------------------------------------------
# Detect referenced entities (nested relations)
# ---------------------------------------------------------
def extract_referenced_entities(annotations: dict) -> set[type]:
    refs = set()

    for t in annotations.values():

        # ForwardRef("ClassName") — resolve later
        if isinstance(t, ForwardRef):
            continue

        origin = get_origin(t)
        args = get_args(t)

        # List[Entity]
        if origin in (list, List) and args:
            inner = args[0]
            if isinstance(inner, ForwardRef):
                continue
            if inspect.isclass(inner) and issubclass(inner, Entity):
                refs.add(inner)

        # Direct reference
        elif inspect.isclass(t) and issubclass(t, Entity):
            refs.add(t)

    return refs


# ---------------------------------------------------------
# Determine if datetime import is needed
# ---------------------------------------------------------
datetime_needed_types = {"datetime", "date", "time", "timedelta"}

def needs_datetime_import(all_annotations, subclasses):
    for cls in subclasses:
        # Field types
        for name, value in vars(cls).items():
            if isinstance(value, Field):
                if value.py_type.__name__ in datetime_needed_types:
                    return True

        # Annotation types
        for name, t in all_annotations.get(cls, {}).items():
            type_str = type_to_str(t)
            if any(dt in type_str for dt in datetime_needed_types):
                return True
    return False


# ---------------------------------------------------------
# Main DTO Generator
# ---------------------------------------------------------
def generate_dtos(entities_module: str, output_path: str, force: bool = False):
    import_entities_from_path(entities_module)

    fw = FileWriter('DTOs', output_path)

    subclasses = Entity.__subclasses__()
    all_annotations = {cls: getattr(cls, "__annotations__", {}) for cls in subclasses}

    # ---------------------------------------------------------
    # FILE HEADER + IMPORTS
    # ---------------------------------------------------------
    lines = []
    fw.add_header_comment("# ---------------------------------------------------------")
    fw.add_header_comment("# AUTO-GENERATED FILE — DO NOT EDIT.")
    fw.add_header_comment("# DTOs generated from Entity classes via simple_orm.")
    fw.add_header_comment("# ---------------------------------------------------------")
    
    fw.add_import("from __future__ import annotations")
    fw.add_import("from typing import List, TYPE_CHECKING")

    if needs_datetime_import(all_annotations, subclasses):
        fw.add_import("from datetime import datetime")

    fw.add_import("from api_dto import api_dto")

    # TYPE_CHECKING imports
    global_referenced = set()
    for cls, ann in all_annotations.items():
        global_referenced.update(extract_referenced_entities(ann))

    if global_referenced:
        fw.add_import("if TYPE_CHECKING:")
        for ref in sorted(global_referenced, key=lambda c: c.__name__):
            fw.add_import(f"    from {ref.__module__} import {ref.__name__}")

    # ---------------------------------------------------------
    # GENERATE DTO CLASSES
    # ---------------------------------------------------------
    for cls in subclasses:
        cw = fw.add_class(cls.__name__)

        # Class decorator
        cw.set_decorator("@api_dto")

        # Field() entries
        for name, value in vars(cls).items():
            if isinstance(value, Field) and not is_sensitive_field(name):
                cw.add_property(f"{name}: {value.py_type.__name__}")

        # Annotated entries
        for name, t in all_annotations[cls].items():
            if is_sensitive_field(name):
                continue
            if hasattr(cls, name) and isinstance(getattr(cls, name), Field):
                continue
            cw.add_property(f"{name}: {type_to_str(t)}")

    

    # ---------------------------------------------------------
    # WRITE FILE
    # ---------------------------------------------------------
    fw.write_file(force)
    



# ---------------------------------------------------------
# CLI
# ---------------------------------------------------------
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Generate DTOs from simple_orm Entity classes.")
    parser.add_argument("--entities", required=True, help="Path to entities module")
    parser.add_argument("--output", required=True, help="Output path for generated DTOs")
    parser.add_argument("--force", action="store_true", help="Force overwrite even if user modifications detected")

    args = parser.parse_args()
    generate_dtos(args.entities, args.output, force=args.force)
