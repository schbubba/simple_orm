import datetime
from decimal import Decimal

class Field:
    def __init__(self, py_type, primary_key=False, nullable=True, default=None):
        self.py_type = py_type
        self.primary_key = primary_key
        self.nullable = nullable
        self.default = default
        self.name = None
        self.entity_cls = None

    def __get__(self, obj, owner):
        """Descriptor to return Column for class access, value for instance access."""
        if obj is None:
            # Accessing from class (e.g., Session.is_active)
            # Return Column for query building
            from .query import Column
            return Column(self.name)
        # Accessing from instance (e.g., session.is_active)
        # Return actual value
        return obj.__dict__.get(self.name, self.default)
    
    def __set__(self, obj, value):
        """Set value on instance."""
        obj.__dict__[self.name] = value

    def sql_type(self):
        """Map Python type -> SQLite type."""
        type_map = {
            int: "INTEGER",
            float: "REAL",
            str: "TEXT",
            bool: "INTEGER",
            datetime.datetime: "TEXT",
            Decimal: "REAL"
        }
        return type_map.get(self.py_type, "TEXT")
    
    def python_to_sql(self, value):
        """Convert Python value to SQL-safe value."""
        if value is None:
            return None
        if isinstance(value, datetime.datetime):
            return value.isoformat()
        if isinstance(value, Decimal):
            return float(value)
        if isinstance(value, bool):
            return int(value)
        return value
    
    def sql_to_python(self, value):
        """Convert SQL value back to Python type."""
        if value is None:
            return None
        if self.py_type == datetime.datetime and isinstance(value, str):
            return datetime.datetime.fromisoformat(value)
        if self.py_type == bool and isinstance(value, int):
            return bool(value)
        if self.py_type == Decimal and isinstance(value, (int, float)):
            return Decimal(str(value))
        return value