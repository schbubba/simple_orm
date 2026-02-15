# ORM/foreign_key.py
from .field import Field

class ForeignKey(Field):
    def __init__(self, target, back_populates=None, target_column="id", nullable=True):
        """
        Args:
            target: Target entity class or string name
            back_populates: Name of the attribute on the target class for reverse relationship
            target_column: Column on target (usually "id")
            nullable: Whether FK can be NULL
        """
        # Don't call super().__init__ yet - we need to determine the type first
        # Store parameters for later
        self._py_type = None  # Will be set in resolve()
        self.nullable = nullable
        self.primary_key = False
        self.default = None
        
        self._target = target
        self.target_column = target_column
        self.foreign_key = None
        self.back_populates = back_populates
        self.owner_class = None
    
    def __set_name__(self, owner, name):
        """Called when the field is assigned to a class."""
        self.name = name
        self.owner_class = owner
    
    def resolve(self, registry):
        """Convert target -> (table_name, column) and set up relationships."""
        if isinstance(self._target, str):
            cls = registry[self._target]
        elif isinstance(self._target, type):
            cls = self._target
        elif callable(self._target):
            cls = self._target()
        else:
            raise TypeError("Invalid foreign key target")
        
        # Find the target column's field to get its type
        target_field = cls._fields.get(self.target_column)
        if not target_field:
            raise ValueError(f"Target column '{self.target_column}' not found in {cls.__name__}")
        
        # Set the FK type to match the target field's type
        self.py_type = target_field.py_type
        
        self.foreign_key = (cls._table_name, self.target_column)
        
        # Set up reverse relationship on target class (one-to-many)
        if self.back_populates:
            from .relationship import Relationship
            setattr(cls, self.back_populates, Relationship(self.owner_class.__name__, self.name))
        
        # Set up forward relationship on owner class (many-to-one)
        # Remove '_id' suffix to get the relationship name (e.g., 'client_id' -> 'client')
        if self.name.endswith('_id'):
            relationship_name = self.name[:-3]  # Remove '_id'
            from .single_relationship import SingleRelationship
            setattr(self.owner_class, relationship_name, SingleRelationship(cls.__name__, self.name))