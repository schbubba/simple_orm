"""
Generate Entity classes from database metadata.
Reverse engineers entities from _simple_orm_table_mappings.
"""

import asyncio
import aiosqlite
import json
import inflection
from pathlib import Path

from simple_orm.schema_metadata import SchemaMetadata
from simple_orm.file_writer import FileWriter


async def generate_entities_from_db(db_path: str, output_path: str, force: bool = False):
    """
    Generate Entity classes from database metadata.
    
    Args:
        db_path: Path to SQLite database
        output_path: Output path for generated entities file
        force: Force overwrite even if user modifications detected
    """
    
    # Connect to database and read metadata
    conn = await aiosqlite.connect(db_path)
    
    try:
        # Check if metadata tables exist
        cursor = await conn.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name=?
        """, (SchemaMetadata.METADATA_TABLE,))
        
        if not await cursor.fetchone():
            print(f"Error: No metadata found in {db_path}")
            print(f"Run sync_schema() first to generate metadata.")
            return
        
        # Get all table metadata
        tables_meta = await SchemaMetadata.get_all_table_metadata(conn)
        
        if not tables_meta:
            print("No entity metadata found in database.")
            return
        
        # Generate the file
        fw = FileWriter('Entities', output_path)
        
        # Add header
        fw.add_header_comment("# ---------------------------------------------------------")
        fw.add_header_comment("# AUTO-GENERATED FROM DATABASE METADATA")
        fw.add_header_comment("# Entities reverse-engineered from database schema.")
        fw.add_header_comment("# ---------------------------------------------------------")
        
        # Add imports
        fw.add_import("from simple_orm import Entity, Field, ForeignKey, table")
        fw.add_import("from datetime import datetime")
        fw.add_import("from typing import TYPE_CHECKING")
        
        # Collect forward references for TYPE_CHECKING
        forward_refs = set()
        for table_name, columns in tables_meta.items():
            for col in columns:
                if col['is_foreign_key'] and col['foreign_table']:
                    # Convert table name to class name
                    class_name = _table_to_class_name(col['foreign_table'])
                    forward_refs.add(class_name)
        
        # Add TYPE_CHECKING block for forward references
        if forward_refs:
            fw.add_import("")
            fw.add_import("if TYPE_CHECKING:")
            for ref in sorted(forward_refs):
                fw.add_import(f"    from __future__ import annotations")
                break
        
        # Generate each entity class
        for table_name, columns in sorted(tables_meta.items()):
            # Skip metadata tables
            if table_name.startswith('_simple_orm_'):
                continue
            
            class_name = _table_to_class_name(table_name)
            
            cw = fw.add_class(class_name, base="Entity")
            
            # Add table decorator
            cw.set_decorator(f'@table(name="{table_name}")')
            
            # Add fields
            for col in columns:
                field_def = _generate_field_definition(col, tables_meta)
                cw.add_property(field_def)
            
            # Add relationship annotations
            for col in columns:
                if col['is_foreign_key'] and col['back_populates']:
                    # Add the reverse relationship annotation
                    target_class = _table_to_class_name(col['foreign_table'])
                    # This is a forward reference (many-to-one)
                    # The actual relationship will be on the other side
            
            # Add back_populates relationships (one-to-many)
            for col in columns:
                if col['is_foreign_key'] and col['back_populates']:
                    target_class = _table_to_class_name(col['foreign_table'])
                    # The target class should have a list annotation
                    # This will be handled when we process that table
            
            # Check if this table is referenced by others (one-to-many relationships)
            for other_table, other_cols in tables_meta.items():
                if other_table == table_name:
                    continue
                    
                for other_col in other_cols:
                    if other_col['is_foreign_key'] and other_col['foreign_table'] == table_name:
                        if other_col['back_populates']:
                            # Add the list annotation for one-to-many
                            related_class = _table_to_class_name(other_table)
                            relationship_name = other_col['back_populates']
                            cw.add_property(f"{relationship_name}: list[{related_class}]")
        
        # Write the file
        fw.write_file(force)
        print(f"Generated {len(tables_meta)} entities to {output_path}")
        
    finally:
        await conn.close()


def _table_to_class_name(table_name: str) -> str:
    """Convert table name to class name (e.g., 'user_profiles' -> 'UserProfile')."""
    # Remove plural, convert to PascalCase
    singular = inflection.singularize(table_name)
    return inflection.camelize(singular)


def _generate_field_definition(col: dict, all_tables: dict) -> str:
    """Generate Field() or ForeignKey() definition from column metadata."""
    
    col_name = col['column_name']
    py_type = col['python_type']
    
    # Handle foreign keys
    if col['is_foreign_key']:
        target_table = col['foreign_table']
        target_class = _table_to_class_name(target_table)
        
        parts = [f'"{target_class}"']
        
        if col['back_populates']:
            parts.append(f'back_populates="{col["back_populates"]}"')
        
        if col['foreign_column'] and col['foreign_column'] != 'id':
            parts.append(f'target_column="{col["foreign_column"]}"')
        
        if not col['is_nullable']:
            parts.append('nullable=False')
        
        return f'{col_name} = ForeignKey({", ".join(parts)})'
    
    # Handle regular fields
    parts = [py_type]
    
    if col['is_primary_key']:
        parts.append('primary_key=True')
    
    if not col['is_nullable']:
        parts.append('nullable=False')
    
    # Handle default values
    if col['default_value']:
        try:
            default = json.loads(col['default_value'])
            if isinstance(default, str):
                parts.append(f'default="{default}"')
            elif isinstance(default, bool):
                parts.append(f'default={default}')
            elif isinstance(default, (int, float)):
                parts.append(f'default={default}')
        except (json.JSONDecodeError, ValueError):
            pass
    
    return f'{col_name} = Field({", ".join(parts)})'


def main():
    """CLI entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Generate Entity classes from database metadata."
    )
    parser.add_argument(
        "--db",
        required=True,
        help="Path to SQLite database with metadata"
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Output path for generated entities file"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force overwrite even if user modifications detected"
    )
    
    args = parser.parse_args()
    
    asyncio.run(generate_entities_from_db(args.db, args.output, args.force))


if __name__ == "__main__":
    main()