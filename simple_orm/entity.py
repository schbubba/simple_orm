from .entity_meta import EntityMeta
from .field import Field
from .foreign_key import ForeignKey
from .query import Query
from .key_words import get_column_name
import uuid

class Entity(metaclass=EntityMeta):
    id = Field(int, primary_key=True, nullable=False)
    _context = None

    def __init__(self, **kwargs):
        # Storage for pending relationship children before insert
        self._pending_relationships = {}
        
        for f in self._fields.values():
            setattr(self, f.name, kwargs.get(f.name, f.default))

    @classmethod
    def query(cls):
        """Create a new query for this entity.
        
        Example:
            sessions = await Session.query().filter(Session.is_active == True).all()
        """
        return Query(cls)
    
    def add_child(self, relationship_name, child):
        """Add a child entity to a relationship for cascade insert.
        
        Args:
            relationship_name: Name of the relationship attribute (e.g., 'channel_episodes')
            child: Child entity to add
            
        Example:
            channel = Channel(name="My Channel")
            episode = ChannelEpisode(name="Episode 1")
            channel.add_child('channel_episodes', episode)
            await channel.insert()  # Inserts both channel and episode
        """
        if relationship_name not in self._pending_relationships:
            self._pending_relationships[relationship_name] = []
        self._pending_relationships[relationship_name].append(child)

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
                col += " PRIMARY KEY"
                # Only add AUTOINCREMENT for integer primary keys
                if f.py_type == int:
                    col += " AUTOINCREMENT"
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

    async def insert(self, cascade=True):
        """Insert this entity into the database.
        
        Args:
            cascade: If True, also insert related entities that have been added via add_child()
        """
        table = self._table_name
        fields = []
        values = []
        placeholders = []
        
        # Find the primary key field
        pk_field = None
        for f in self._fields.values():
            if f.primary_key:
                pk_field = f
                break
        
        for f in self._fields.values():
            if f.primary_key:
                # For int primary keys, skip (let AUTOINCREMENT handle it)
                if f.py_type == int:
                    continue
                    
                # For string primary keys, auto-generate UUID if not provided
                if f.py_type == str:
                    current_value = getattr(self, f.name)
                    if current_value is None:
                        # Auto-generate UUID
                        setattr(self, f.name, str(uuid.uuid4()))
                    
                    name = get_column_name(f.name)
                    fields.append(name)
                    val = getattr(self, f.name)
                    values.append(f.python_to_sql(val))
                    placeholders.append("?")
                    continue
            
            name = get_column_name(f.name)
            fields.append(name)
            val = getattr(self, f.name)
            values.append(f.python_to_sql(val))
            placeholders.append("?")
        
        sql = f"INSERT INTO {table} ({', '.join(fields)}) VALUES ({', '.join(placeholders)})"
        
        async with self._context.get_connection() as conn:
            cur = await conn.execute(sql, values)
            # Only set id from lastrowid for integer primary keys
            if pk_field and pk_field.py_type == int:
                self.id = cur.lastrowid
            await conn.commit()
        
        # Handle cascade inserts for relationships
        if cascade and self._pending_relationships:
            from .relationship import Relationship
            
            for relationship_name, children in self._pending_relationships.items():
                # Get the Relationship descriptor from the class
                relationship = getattr(type(self), relationship_name, None)
                
                if not isinstance(relationship, Relationship):
                    raise ValueError(f"'{relationship_name}' is not a valid relationship on {type(self).__name__}")
                
                # Set the foreign key on each child and insert
                for child in children:
                    setattr(child, relationship.foreign_key_attr_name, self.id)
                    await child.insert(cascade=cascade)

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
        # Check if primary key has a value (works for both int and str)
        pk_value = getattr(self, 'id', None)
        
        # For integer PKs: None or 0 means new entity
        # For string PKs: None means new entity
        pk_field = None
        for f in self._fields.values():
            if f.primary_key:
                pk_field = f
                break
        
        if pk_field:
            if pk_field.py_type == int:
                is_new = (pk_value is None or pk_value == 0)
            else:  # string or other types
                is_new = (pk_value is None)
        else:
            is_new = True
        
        if is_new:
            await self.insert()
        else:
            await self.update()

    async def delete(self):
        """Delete this entity from the database."""
        if not self.id:
            raise ValueError("Cannot delete entity without an id.")
        
        sql = f"DELETE FROM {self._table_name} WHERE id = ?"
        
        async with self._context.get_connection() as conn:
            await conn.execute(sql, (self.id,))
            await conn.commit()
        
        self.id = None