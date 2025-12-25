"""
Schema metadata management for bidirectional code generation.
Tracks entity definitions in the database for reverse engineering.
"""

import json
from datetime import datetime
from typing import Any

class SchemaMetadata:
    """Manages the _simple_orm_table_mappings metadata table."""
    
    METADATA_TABLE = "_simple_orm_table_mappings"
    VERSION_TABLE = "_simple_orm_schema_version"
    
    @classmethod
    async def ensure_metadata_tables(cls, connection):
        """Create metadata tables if they don't exist."""
        
        # Table mappings - stores column-level metadata
        await connection.execute(f"""
            CREATE TABLE IF NOT EXISTS {cls.METADATA_TABLE} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                table_name TEXT NOT NULL,
                column_name TEXT NOT NULL,
                python_type TEXT NOT NULL,
                sql_type TEXT NOT NULL,
                is_primary_key INTEGER NOT NULL DEFAULT 0,
                is_foreign_key INTEGER NOT NULL DEFAULT 0,
                is_nullable INTEGER NOT NULL DEFAULT 1,
                foreign_table TEXT,
                foreign_column TEXT,
                default_value TEXT,
                back_populates TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(table_name, column_name)
            )
        """)
        
        # Schema version tracking
        await connection.execute(f"""
            CREATE TABLE IF NOT EXISTS {cls.VERSION_TABLE} (
                version INTEGER PRIMARY KEY AUTOINCREMENT,
                entities_hash TEXT NOT NULL,
                applied_at TEXT NOT NULL,
                entity_count INTEGER NOT NULL
            )
        """)
        
        await connection.commit()
    
    @classmethod
    async def record_entity_metadata(cls, connection, entity_cls):
        """Record metadata for a single entity class."""
        from .foreign_key import ForeignKey
        
        table_name = entity_cls._table_name
        timestamp = datetime.now().isoformat()
        
        # Delete existing metadata for this table
        await connection.execute(
            f"DELETE FROM {cls.METADATA_TABLE} WHERE table_name = ?",
            (table_name,)
        )
        
        # Record each field
        for field_name, field in entity_cls._fields.items():
            python_type = field.py_type.__name__
            sql_type = field.sql_type()
            is_primary_key = 1 if field.primary_key else 0
            is_foreign_key = 1 if isinstance(field, ForeignKey) else 0
            is_nullable = 1 if field.nullable else 0
            
            # Handle foreign key metadata
            foreign_table = None
            foreign_column = None
            back_populates = None
            
            if isinstance(field, ForeignKey):
                if field.foreign_key:
                    foreign_table, foreign_column = field.foreign_key
                back_populates = field.back_populates
            
            # Serialize default value
            default_value = None
            if field.default is not None:
                try:
                    default_value = json.dumps(field.default)
                except (TypeError, ValueError):
                    default_value = str(field.default)
            
            await connection.execute(f"""
                INSERT INTO {cls.METADATA_TABLE} 
                (table_name, column_name, python_type, sql_type, is_primary_key, 
                 is_foreign_key, is_nullable, foreign_table, foreign_column, 
                 default_value, back_populates, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                table_name, field_name, python_type, sql_type, is_primary_key,
                is_foreign_key, is_nullable, foreign_table, foreign_column,
                default_value, back_populates, timestamp, timestamp
            ))
        
        await connection.commit()
    
    @classmethod
    async def record_schema_version(cls, connection, entities_hash: str, entity_count: int):
        """Record a new schema version."""
        timestamp = datetime.now().isoformat()
        
        await connection.execute(f"""
            INSERT INTO {cls.VERSION_TABLE} (entities_hash, applied_at, entity_count)
            VALUES (?, ?, ?)
        """, (entities_hash, timestamp, entity_count))
        
        await connection.commit()
    
    @classmethod
    async def get_all_table_metadata(cls, connection) -> dict:
        """Retrieve all table metadata as a dictionary."""
        cursor = await connection.execute(f"""
            SELECT table_name, column_name, python_type, sql_type, 
                   is_primary_key, is_foreign_key, is_nullable,
                   foreign_table, foreign_column, default_value, back_populates
            FROM {cls.METADATA_TABLE}
            ORDER BY table_name, id
        """)
        
        rows = await cursor.fetchall()
        
        # Group by table
        tables = {}
        for row in rows:
            table_name = row[0]
            if table_name not in tables:
                tables[table_name] = []
            
            column_meta = {
                'column_name': row[1],
                'python_type': row[2],
                'sql_type': row[3],
                'is_primary_key': bool(row[4]),
                'is_foreign_key': bool(row[5]),
                'is_nullable': bool(row[6]),
                'foreign_table': row[7],
                'foreign_column': row[8],
                'default_value': row[9],
                'back_populates': row[10]
            }
            tables[table_name].append(column_meta)
        
        return tables
    
    @classmethod
    async def get_schema_versions(cls, connection, limit: int = 10):
        """Get recent schema versions."""
        cursor = await connection.execute(f"""
            SELECT version, entities_hash, applied_at, entity_count
            FROM {cls.VERSION_TABLE}
            ORDER BY version DESC
            LIMIT ?
        """, (limit,))
        
        return await cursor.fetchall()
    
    @classmethod
    async def table_exists(cls, connection, table_name: str) -> bool:
        """Check if metadata exists for a table."""
        cursor = await connection.execute(f"""
            SELECT COUNT(*) FROM {cls.METADATA_TABLE}
            WHERE table_name = ?
        """, (table_name,))
        
        result = await cursor.fetchone()
        return result[0] > 0