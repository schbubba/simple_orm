from abc import abstractmethod
import os
import aiosqlite
from contextlib import asynccontextmanager

from .entity_meta import EntityMeta
from .foreign_key import ForeignKey


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
        conn = await aiosqlite.connect(self._db_path)
        try:
            yield conn
        except:
            await conn.rollback()
            raise
        finally:
            await conn.close()

    async def sync_schema(self):
        for cls in EntityMeta.registry.values():
            print(f"SYNCING: {cls.__name__}")
            await cls.sync_schema()
        await self.seed_data()

    @abstractmethod
    async def seed_data(self):
        raise NotImplementedError()


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