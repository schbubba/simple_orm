from abc import abstractmethod
import os
import hashlib
import aiosqlite
from contextlib import asynccontextmanager

from .entity_meta import EntityMeta
from .foreign_key import ForeignKey
from .schema_metadata import SchemaMetadata

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from simple_orm import get_column_name, reverse_column_name

class db_context:
    
    def __init__(self, db_path, sync_schema=False):
        self._db_path = db_path
        self._sync_schema = sync_schema

        for cls in EntityMeta.registry.values():
            cls._context = self

        for cls in EntityMeta.registry.values():
            for f in cls._fields.values():
                if isinstance(f, ForeignKey):
                    f.resolve(EntityMeta.registry)

        dir = os.path.dirname(self._db_path)
        if not os.path.exists(dir):
            os.makedirs(dir)

    async def initialize(self):
        if self._sync_schema:
            await self.sync_schema()

    @asynccontextmanager
    async def get_connection(self):
        conn = await aiosqlite.connect(self._db_path, timeout=30.0)
        try:
            # Enable WAL mode for better concurrency
            await conn.execute("PRAGMA journal_mode=WAL")
            # Set busy timeout to 30 seconds
            await conn.execute("PRAGMA busy_timeout=30000")
            yield conn
        except:
            await conn.rollback()
            raise
        finally:
            await conn.close()

    async def sync_schema(self):
        """Sync schema for all entities and record metadata."""
        async with self.get_connection() as conn:
            # Ensure metadata tables exist first
            await SchemaMetadata.ensure_metadata_tables(conn)
            
            # Sync each entity
            for cls in EntityMeta.registry.values():
                print(f"SYNCING: {cls.__name__}")
                await cls.sync_schema()
                
                # Record metadata for this entity
                await SchemaMetadata.record_entity_metadata(conn, cls)
            
            # Calculate and record schema version
            entities_hash = self._calculate_entities_hash()
            entity_count = len(EntityMeta.registry)
            await SchemaMetadata.record_schema_version(conn, entities_hash, entity_count)
            
            print(f"Schema synced: {entity_count} entities")
        
        await self.seed_data()
    
    def _calculate_entities_hash(self) -> str:
        """Calculate SHA256 hash of all entity definitions."""
        entity_signatures = []
        
        for cls_name in sorted(EntityMeta.registry.keys()):
            cls = EntityMeta.registry[cls_name]
            fields = []
            
            for field_name in sorted(cls._fields.keys()):
                field = cls._fields[field_name]
                field_sig = f"{field_name}:{field.py_type.__name__}:{field.primary_key}:{field.nullable}"
                fields.append(field_sig)
            
            entity_sig = f"{cls_name}:{cls._table_name}:{'|'.join(fields)}"
            entity_signatures.append(entity_sig)
        
        combined = "\n".join(entity_signatures)
        return hashlib.sha256(combined.encode('utf-8')).hexdigest()

    @abstractmethod
    async def seed_data(self):
        raise NotImplementedError()

    async def get_schema_metadata(self) -> dict:
        """Get all table metadata from the database."""
        async with self.get_connection() as conn:
            return await SchemaMetadata.get_all_table_metadata(conn)
    
    async def get_schema_versions(self, limit: int = 10):
        """Get recent schema versions."""
        async with self.get_connection() as conn:
            return await SchemaMetadata.get_schema_versions(conn, limit)

    async def insert_many(self, entities):
        if not entities:
            return
        
        grouped = {}
        for e in entities:
            grouped.setdefault(type(e), []).append(e)

        async with self.get_connection() as conn:
            for cls, items in grouped.items():
                fields = [get_column_name(f.name) for f in cls._fields.values() if not f.primary_key]

                placeholders = ", ".join("?" for _ in fields)
                sql = f"INSERT INTO {cls._table_name} ({', '.join(fields)}) VALUES ({placeholders})"

                rows = []
                for obj in items:
                    vals = [
                        obj._fields[reverse_column_name(f)].python_to_sql(getattr(obj, reverse_column_name(f)))
                        for f in fields
                    ]
                    rows.append(vals)

                await conn.executemany(sql, rows)
            await conn.commit()

    async def update_many(self, entities):
        if not entities:
            return
        
        # Check all entities have IDs
        for e in entities:
            if not e.id:
                raise ValueError(f"Cannot update entity without an id: {e}")
        
        grouped = {}
        for e in entities:
            grouped.setdefault(type(e), []).append(e)
        
        async with self.get_connection() as conn:
            for cls, items in grouped.items():
                fields = [f.name for f in cls._fields.values() if not f.primary_key]
                set_clause = ", ".join(f"{f} = ?" for f in fields)
                sql = f"UPDATE {cls._table_name} SET {set_clause} WHERE id = ?"
                
                rows = []
                for obj in items:
                    vals = [
                        obj._fields[f].python_to_sql(getattr(obj, f))
                        for f in fields
                    ]
                    vals.append(obj.id)  # Add id for WHERE clause
                    rows.append(vals)
                
                await conn.executemany(sql, rows)
            await conn.commit()