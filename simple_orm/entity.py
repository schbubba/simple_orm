from .entity_meta import EntityMeta
from .field import Field
from .foreign_key import ForeignKey
from .query import Query
from .key_words import get_column_name

class Entity(metaclass=EntityMeta):
    id = Field(int, primary_key=True, nullable=False)
    _context = None

    def __init__(self, **kwargs):
        for f in self._fields.values():
            setattr(self, f.name, kwargs.get(f.name, f.default))

    @classmethod
    def query(cls):
        """Create a new query for this entity.
        
        Example:
            sessions = await Session.query().filter(Session.is_active == True).all()
        """
        return Query(cls)

    @classmethod
    async def get_by_id(cls, id):
        """Get entity by primary key."""
        return await cls.query().filter_by(id=id).first()

    @classmethod
    async def get_all(cls):
        """Get all entities."""
        return await cls.query().all()

    @classmethod
    def _from_row(cls, row, description):
        """Convert database row to entity instance."""
        obj = cls()
        for idx, col in enumerate(description):
            col_name = col[0]
            if col_name in cls._fields:
                field = cls._fields[col_name]
                value = field.sql_to_python(row[idx])
                setattr(obj, col_name, value)
        return obj

    @classmethod
    async def sync_schema(cls):
        """Create or update the table for this entity."""
        fields_sql = []
        fks_sql = []

        for f in cls._fields.values():
            name = get_column_name(f.name)
            col = f"{name} {f.sql_type()}"
            if f.primary_key:
                col += " PRIMARY KEY AUTOINCREMENT"
            if not f.nullable:
                col += " NOT NULL"
            fields_sql.append(col)

            if f.default != None:
                if isinstance(f.default, bool):
                    value = 1 if f.default else 0
                    col += f" DEFAULT {value}"

            if isinstance(f, ForeignKey):
                table, colname = f.foreign_key
                fks_sql.append(f"FOREIGN KEY ({f.name}) REFERENCES {table}({colname})")

        sql = f"""
        CREATE TABLE IF NOT EXISTS {cls._table_name} (
            {', '.join(fields_sql + fks_sql)}
        )
        """

        async with cls._context.get_connection() as conn:
            await conn.execute(sql)
            await conn.commit()

    async def insert(self):
        """Insert this entity into the database."""
        table = self._table_name
        fields = []
        values = []
        placeholders = []
        
        for f in self._fields.values():
            if f.primary_key:
                continue
            name = get_column_name(f.name)
            fields.append(name)
            val = getattr(self, f.name)
            values.append(f.python_to_sql(val))
            placeholders.append("?")
        
        sql = f"INSERT INTO {table} ({', '.join(fields)}) VALUES ({', '.join(placeholders)})"
        
        async with self._context.get_connection() as conn:
            cur = await conn.execute(sql, values)
            self.id = cur.lastrowid
            await conn.commit()

    async def update(self):
        """Update this entity in the database."""
        if not self.id:
            raise ValueError("Cannot update entity without an id. Use insert() for new entities.")
        
        table = self._table_name
        fields = []
        values = []
        
        for f in self._fields.values():
            if f.primary_key:
                continue
            name = get_column_name(f.name)
            fields.append(f"{name} = ?")
            val = getattr(self, f.name)
            values.append(f.python_to_sql(val))
        
        values.append(self.id)
        sql = f"UPDATE {table} SET {', '.join(fields)} WHERE id = ?"
        
        async with self._context.get_connection() as conn:
            await conn.execute(sql, values)
            await conn.commit()

    async def save(self):
        """Insert or update based on whether entity has an id."""
        if self.id:
            await self.update()
        else:
            await self.insert()

    async def delete(self):
        """Delete this entity from the database."""
        if not self.id:
            raise ValueError("Cannot delete entity without an id.")
        
        sql = f"DELETE FROM {self._table_name} WHERE id = ?"
        
        async with self._context.get_connection() as conn:
            await conn.execute(sql, (self.id,))
            await conn.commit()
        
        self.id = None