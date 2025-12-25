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
        super().__init__(int, nullable=nullable)
        
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