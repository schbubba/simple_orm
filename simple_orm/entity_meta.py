from .field import Field

class EntityMeta(type):
    registry = {}

    def __new__(meta, name, bases, attrs):
        fields = {}

        for key, val in list(attrs.items()):
            if isinstance(val, Field):
                val.name = key
                fields[key] = val

        attrs["_fields"] = fields

        cls = super().__new__(meta, name, bases, attrs)

        if name != "Entity":
            EntityMeta.registry[name] = cls

        cls._table_name = attrs.get("_table_name")

        return cls
    

