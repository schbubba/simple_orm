class Condition:
    """Represents a SQL condition with parameters."""
    def __init__(self, sql, params):
        self.sql = sql
        self.params = params


class Column:
    """Represents a database column for query building."""
    def __init__(self, name):
        self.name = name
    
    def __eq__(self, other):
        return Condition(f"{self.name} = ?", [other])
    
    def __ne__(self, other):
        return Condition(f"{self.name} != ?", [other])
    
    def __lt__(self, other):
        return Condition(f"{self.name} < ?", [other])
    
    def __le__(self, other):
        return Condition(f"{self.name} <= ?", [other])
    
    def __gt__(self, other):
        return Condition(f"{self.name} > ?", [other])
    
    def __ge__(self, other):
        return Condition(f"{self.name} >= ?", [other])
    
    def like(self, pattern):
        """SQL LIKE operator."""
        return Condition(f"{self.name} LIKE ?", [pattern])
    
    def in_(self, values):
        """SQL IN operator."""
        if not values:
            return Condition("1 = 0", [])  # Always false
        placeholders = ", ".join("?" * len(values))
        return Condition(f"{self.name} IN ({placeholders})", list(values))
    
    def is_null(self):
        """SQL IS NULL."""
        return Condition(f"{self.name} IS NULL", [])
    
    def is_not_null(self):
        """SQL IS NOT NULL."""
        return Condition(f"{self.name} IS NOT NULL", [])
    
    def desc(self):
        """For ORDER BY DESC."""
        return f"{self.name} DESC"
    
    def asc(self):
        """For ORDER BY ASC."""
        return f"{self.name} ASC"
    
    def __str__(self):
        return self.name


class Query:
    """SQLAlchemy-style async query builder."""
    def __init__(self, entity_cls):
        self.entity_cls = entity_cls
        self._filters = []
        self._params = []
        self._order_by = None
        self._limit_val = None
    
    def filter(self, *conditions):
        """Add filter conditions using comparison operators.
        
        Example:
            await Session.query().filter(Session.is_active == True).all()
        """
        for condition in conditions:
            if isinstance(condition, Condition):
                self._filters.append(condition.sql)
                self._params.extend(condition.params)
            else:
                raise TypeError(f"Expected Condition, got {type(condition)}")
        return self
    
    def filter_by(self, **kwargs):
        """Simple equality filters using keyword arguments.
        
        Example:
            await Session.query().filter_by(is_active=True).all()
        """
        for k, v in kwargs.items():
            self._filters.append(f"{k} = ?")
            self._params.append(v)
        return self
    
    def order_by(self, *fields):
        """Order by one or more fields.
        
        Example:
            await Session.query().order_by(Session.timestamp.desc()).all()
        """
        self._order_by = ", ".join(str(f) for f in fields)
        return self
    
    def limit(self, n):
        """Limit number of results."""
        self._limit_val = n
        return self
    
    async def all(self):
        """Execute query and return all results."""
        sql = f"SELECT * FROM {self.entity_cls._table_name}"
        
        if self._filters:
            sql += f" WHERE {' AND '.join(self._filters)}"
        
        if self._order_by:
            sql += f" ORDER BY {self._order_by}"
        
        if self._limit_val is not None:
            sql += f" LIMIT {self._limit_val}"
        
        async with self.entity_cls._context.get_connection() as conn:
            cursor = await conn.execute(sql, self._params)
            rows = await cursor.fetchall()
            return [self.entity_cls._from_row(row, cursor.description) 
                    for row in rows]
    
    async def first(self):
        """Get first result or None."""
        results = await self.limit(1).all()
        return results[0] if results else None
    
    async def count(self):
        """Count matching records."""
        sql = f"SELECT COUNT(*) FROM {self.entity_cls._table_name}"
        
        if self._filters:
            sql += f" WHERE {' AND '.join(self._filters)}"
        
        async with self.entity_cls._context.get_connection() as conn:
            cursor = await conn.execute(sql, self._params)
            result = await cursor.fetchone()
            return result[0]