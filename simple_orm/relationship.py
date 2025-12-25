from .entity_meta import EntityMeta

class Relationship:
    def __init__(self, target_entity_name, foreign_key_attr_name):
        self.target_entity_name = target_entity_name
        self.foreign_key_attr_name = foreign_key_attr_name
        self.name = None
        self._validated = False
    
    def _validate(self):
        """Validate that names exist - called on first access."""
        if not self._validated:
            if self.target_entity_name not in EntityMeta.registry:
                available = ', '.join(EntityMeta.registry.keys())
                raise ValueError(
                    f"Unknown entity '{self.target_entity_name}'. "
                    f"Available: {available}"
                )
            
            target = EntityMeta.registry[self.target_entity_name]
            if self.foreign_key_attr_name not in target._fields:
                available = ', '.join(target._fields.keys())
                raise ValueError(
                    f"Unknown field '{self.foreign_key_attr_name}' on {self.target_entity_name}. "
                    f"Available: {available}"
                )
            self._validated = True
    
    def __get__(self, obj, owner):
        """Return a query builder instead of executing the query."""
        if obj is None:
            return self
        
        self._validate()  # Fails fast with helpful error
        
        if not obj.id:
            # Return an already-filtered query that will return empty results
            target = EntityMeta.registry[self.target_entity_name]
            return target.query().filter_by(id=-1)  # Will never match
        
        target = EntityMeta.registry[self.target_entity_name]
        fk_column = getattr(target, self.foreign_key_attr_name)
        
        # Return the query, not the results
        return target.query().filter(fk_column == obj.id)