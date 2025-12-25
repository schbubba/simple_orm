# ORM/single_relationship.py
from .entity_meta import EntityMeta

class SingleRelationship:
    """Represents a many-to-one relationship (returns single entity)."""
    
    def __init__(self, target_entity_name, foreign_key_field_name):
        self.target_entity_name = target_entity_name
        self.foreign_key_field_name = foreign_key_field_name
        self.name = None
    
    def __set_name__(self, owner, name):
        self.name = name
    
    def __get__(self, obj, owner):
        """Returns a coroutine that fetches the related entity."""
        if obj is None:
            return self
        
        # Get the foreign key value
        fk_value = getattr(obj, self.foreign_key_field_name)
        
        if fk_value is None:
            # Return a coroutine that resolves to None
            async def _get_none():
                return None
            return _get_none()
        
        # Get the target entity and return the coroutine
        target = EntityMeta.registry[self.target_entity_name]
        return target.get_by_id(fk_value)
    
    def __set__(self, obj, value):
        """Allow setting the relationship by entity instance."""
        if value is None:
            setattr(obj, self.foreign_key_field_name, None)
        else:
            setattr(obj, self.foreign_key_field_name, value.id)