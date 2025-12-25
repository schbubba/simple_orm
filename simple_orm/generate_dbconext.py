

import inspect
import pathlib
import inflection

from.file_writer import FileWriter
from .class_writer import ClassWriter

# Discover all entity classes dynamically
def discover_entities(entities_path):
    entities = {}
    for py_file in pathlib.Path(entities_path).glob('*.py'):
        if py_file.name == '__init__.py':
            continue
        module_name = f'data_layer.entities.{py_file.stem}'
        module = __import__(module_name, fromlist=['*'])
        for name, obj in inspect.getmembers(module, inspect.isclass):
            if obj.__module__ == module_name:
                entities[name] = name
    return entities


def generate_dbcontext(entities_path: str, output_path: str, force: bool = False):
    entities = discover_entities(entities_path)
    fw = FileWriter('DbContext', output_path)

    fw.add_header_comment("# ---------------------------------------------------------")
    fw.add_header_comment("# AUTO-GENERATED FILE  DO NOT EDIT ANYTHING BUT SEED_DATA.")
    fw.add_header_comment("# DbContext generated from Entity classes via simple_orm.")
    fw.add_header_comment("# ---------------------------------------------------------")
    fw.add_import("from data_layer.entities import *")
    fw.add_import("from simple_orm import db_context")

    cw = fw.add_class("DbContext", property_boundaries=True)
    cw.class_inherits = "db_context"

    for entity_name in entities:
        prop_name = inflection.underscore(inflection.pluralize(entity_name))
        cw.add_property(f"{prop_name}: {entity_name} = {entity_name}")

    cw.add_method("async def seed_data(self):")
    cw.add_method("pass", indent_level=2)

    fw.write_file(force)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Generate DbContext from simple_orm Entity classes.")
    parser.add_argument("--entities", required=True, help="Path to entities module")
    parser.add_argument("--output", required=True, help="Output path for generated DbContext")
    parser.add_argument("--force", action="store_true", help="Force overwrite even if user modifications detected")

    args = parser.parse_args()
    generate_dbcontext(args.entities, args.output, force=args.force)

