# Simple ORM

A lightweight, async Python ORM built on top of SQLite with `aiosqlite`. Simple ORM provides an intuitive, SQLAlchemy-inspired API for defining models, managing relationships, and querying databases without the overhead of larger frameworks.

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Features

- **Async/Await Support** - Built on `aiosqlite` for non-blocking database operations
- **SQLAlchemy-Style Query API** - Familiar filtering, ordering, and query building
- **Automatic Schema Management** - Auto-generate tables from entity definitions
- **Foreign Key Relationships** - One-to-many and many-to-one relationships with lazy loading
- **Type Safety** - Full type hints and Python type mapping to SQLite
- **Code Generation** - Auto-generate DTOs and DbContext classes from entities
- **Change Detection** - Smart regeneration that preserves manual edits

## Table of Contents

- [Installation](#installation)
- [Quick Start](#quick-start)
- [Defining Entities](#defining-entities)
- [Database Context](#database-context)
- [CRUD Operations](#crud-operations)
- [Querying](#querying)
- [Relationships](#relationships)
- [Code Generation](#code-generation)
- [API Reference](#api-reference)
- [License](#license)

## Installation

```bash
pip install simple-orm
```

### Requirements

- Python 3.10+
- aiosqlite
- inflection (for code generation)

## Quick Start

```python
import asyncio
from datetime import datetime
from simple_orm import Entity, db_context, Field, table

@table(name="users")
class User(Entity):
    id = Field(int, primary_key=True)
    name = Field(str, nullable=False)
    email = Field(str, nullable=False)
    created_at = Field(datetime, nullable=False)

class AppContext(db_context):
    users: User = User
    
    async def seed_data(self):
        """Optional: seed initial data"""
        pass

async def main():
    # Initialize database context
    context = AppContext('./data/app.db', sync_schema=True)
    await context.initialize()
    
    # Create a new user
    user = User(
        name="John Doe",
        email="john@example.com",
        created_at=datetime.now()
    )
    await user.insert()
    
    # Query users
    users = await User.query().filter(User.name.like("%John%")).all()
    print(f"Found {len(users)} users")

asyncio.run(main())
```

## Defining Entities

Entities are defined by subclassing `Entity` and using the `Field` class for columns:

```python
from simple_orm import Entity, Field, table
from datetime import datetime

@table(name="products")
class Product(Entity):
    id = Field(int, primary_key=True)
    name = Field(str, nullable=False)
    price = Field(float, nullable=False)
    description = Field(str, nullable=True)
    in_stock = Field(bool, default=True)
    created_at = Field(datetime, nullable=False)
```

### Field Types

Simple ORM maps Python types to SQLite types automatically:

| Python Type | SQLite Type |
|-------------|-------------|
| `int` | INTEGER |
| `float` | REAL |
| `str` | TEXT |
| `bool` | INTEGER (0/1) |
| `datetime` | TEXT (ISO format) |
| `Decimal` | REAL |

### Field Options

- `primary_key=True` - Mark as primary key (auto-increment)
- `nullable=False` - Require a value
- `default=value` - Set default value

## Database Context

The `db_context` class manages your database connection and entity registration:

```python
from simple_orm import db_context

class AppContext(db_context):
    # Register entities as class variables
    products: Product = Product
    orders: Order = Order
    
    async def seed_data(self):
        """Called after schema sync - use for initial data"""
        admin = User(name="Admin", email="admin@example.com")
        await admin.insert()

# Initialize with auto-schema sync
context = AppContext('./data/app.db', sync_schema=True)
await context.initialize()
```

## CRUD Operations

### Create (Insert)

```python
# Single insert
user = User(name="Alice", email="alice@example.com", created_at=datetime.now())
await user.insert()
print(f"Created user with ID: {user.id}")

# Bulk insert
users = [
    User(name="Bob", email="bob@example.com", created_at=datetime.now()),
    User(name="Charlie", email="charlie@example.com", created_at=datetime.now()),
]
await context.insert_many(users)
```

### Read (Query)

```python
# Get by ID
user = await User.get_by_id(1)

# Get all
users = await User.get_all()

# Query with filters
active_users = await User.query().filter(User.is_active == True).all()
```

### Update

```python
user = await User.get_by_id(1)
user.email = "newemail@example.com"
await user.update()

# Or use save() which auto-detects insert vs update
await user.save()

# Bulk update
users = await User.query().filter(User.is_active == False).all()
for user in users:
    user.is_active = True
await context.update_many(users)
```

### Delete

```python
user = await User.get_by_id(1)
await user.delete()
```

## Querying

Simple ORM provides a fluent query API similar to SQLAlchemy:

### Basic Filtering

```python
# Equality
users = await User.query().filter(User.name == "Alice").all()

# Comparison operators
expensive = await Product.query().filter(Product.price > 100).all()
cheap = await Product.query().filter(Product.price <= 20).all()

# Multiple conditions (AND)
results = await User.query().filter(
    User.is_active == True,
    User.created_at > datetime(2024, 1, 1)
).all()
```

### Advanced Filtering

```python
# LIKE pattern matching
users = await User.query().filter(User.email.like("%@gmail.com")).all()

# IN clause
users = await User.query().filter(User.id.in_([1, 2, 3, 4])).all()

# NULL checks
users = await User.query().filter(User.phone.is_null()).all()
users = await User.query().filter(User.email.is_not_null()).all()
```

### Ordering and Limiting

```python
# Order by
users = await User.query().order_by(User.created_at.desc()).all()
users = await User.query().order_by(User.name.asc(), User.email.desc()).all()

# Limit results
recent = await User.query().order_by(User.created_at.desc()).limit(10).all()

# Get first result
user = await User.query().filter(User.email == "alice@example.com").first()
```

### Counting

```python
count = await User.query().filter(User.is_active == True).count()
print(f"Active users: {count}")
```

### Filter By (Simple Equality)

```python
# Shorthand for equality filters
user = await User.query().filter_by(email="alice@example.com").first()
users = await User.query().filter_by(is_active=True, role="admin").all()
```

## Relationships

Simple ORM supports foreign key relationships with automatic relationship setup:

### One-to-Many Relationships

```python
from simple_orm import ForeignKey

@table(name="clients")
class Client(Entity):
    id = Field(int, primary_key=True)
    name = Field(str, nullable=False)
    
    # One-to-many: will be auto-populated
    addresses: list[Address]

@table(name="addresses")
class Address(Entity):
    id = Field(int, primary_key=True)
    street = Field(str, nullable=False)
    client_id = ForeignKey("Client", back_populates="addresses")
    
    # Many-to-one: will be auto-populated
    client: Client

# Query relationships
client = await Client.get_by_id(1)

# Get all addresses for this client (returns Query)
addresses = await client.addresses.all()

# Filter related records
active_addresses = await client.addresses.filter(Address.is_active == True).all()

# Access parent from child
address = await Address.get_by_id(1)
client = await address.client  # Fetches the related Client
```

### Foreign Key Options

```python
class Order(Entity):
    id = Field(int, primary_key=True)
    
    # Nullable foreign key
    user_id = ForeignKey("User", nullable=True, back_populates="orders")
    
    # Custom target column (default is "id")
    product_id = ForeignKey("Product", target_column="id", back_populates="orders")
```

## Code Generation

Simple ORM includes code generators to automatically create DTOs and DbContext classes from your entities.

### Generate DTOs

Create Data Transfer Objects from your entities:

```bash
python -m simple_orm.generate_dto \
    --entities data_layer.entities \
    --output data_layer/dtos.py
```

This generates:

```python
# data_layer/dtos.py
from __future__ import annotations
from typing import List
from api_dto import api_dto

@api_dto
class Client:
    id: int
    name: str
    created_at: datetime
    addresses: List[Address]

@api_dto
class Address:
    id: int
    street: str
    client_id: int
```

### Generate DbContext

Auto-generate your database context class:

```bash
python -m simple_orm.generate_dbcontext \
    --entities data_layer/entities \
    --output data_layer/db_context.py
```

This generates:

```python
# data_layer/db_context.py
from data_layer.entities import *
from simple_orm import db_context

class DbContext(db_context):
    clients: Client = Client
    addresses: Address = Address
    
    async def seed_data(self):
        pass  # Add your seed data here
```

### Force Regeneration

By default, code generators preserve manual edits. Use `--force` to overwrite:

```bash
python -m simple_orm.generate_dto --entities data_layer.entities --output data_layer/dtos.py --force
```

### Change Detection

Simple ORM uses SHA256 hashing to detect manual changes to generated files. Metadata is stored in `.simple_orm/` to track file state. If you manually edit a generated file, regeneration will be skipped unless you use `--force`.

## API Reference

### Entity Class

**Methods:**
- `query()` - Create a new query builder
- `get_by_id(id)` - Get entity by primary key
- `get_all()` - Get all entities
- `insert()` - Insert entity into database
- `update()` - Update existing entity
- `save()` - Insert or update (auto-detects)
- `delete()` - Delete entity from database
- `sync_schema()` - Create/update table schema

### Query Class

**Methods:**
- `filter(*conditions)` - Add filter conditions
- `filter_by(**kwargs)` - Simple equality filters
- `order_by(*fields)` - Order results
- `limit(n)` - Limit number of results
- `all()` - Execute and return all results
- `first()` - Get first result or None
- `count()` - Count matching records

### Field Class

**Constructor:**
```python
Field(py_type, primary_key=False, nullable=True, default=None)
```

### ForeignKey Class

**Constructor:**
```python
ForeignKey(target, back_populates=None, target_column="id", nullable=True)
```

### db_context Class

**Constructor:**
```python
db_context(db_path, sync_schema=False)
```

**Methods:**
- `initialize()` - Initialize database (call after construction)
- `sync_schema()` - Sync all entity schemas
- `seed_data()` - Override to provide seed data
- `get_connection()` - Get async database connection
- `insert_many(entities)` - Bulk insert
- `update_many(entities)` - Bulk update

## Advanced Examples

### Complex Queries

```python
# Multiple filters with ordering
results = await Product.query() \
    .filter(
        Product.price > 50,
        Product.in_stock == True
    ) \
    .order_by(Product.price.asc(), Product.name.asc()) \
    .limit(20) \
    .all()

# Pattern matching
gmail_users = await User.query() \
    .filter(User.email.like("%@gmail.com")) \
    .order_by(User.created_at.desc()) \
    .all()

# IN queries
admin_users = await User.query() \
    .filter(User.role.in_(["admin", "superadmin"])) \
    .all()
```

### Transactions

```python
async with context.get_connection() as conn:
    try:
        # Multiple operations in transaction
        user = User(name="Test", email="test@example.com")
        await user.insert()
        
        order = Order(user_id=user.id, total=100.0)
        await order.insert()
        
        await conn.commit()
    except Exception as e:
        await conn.rollback()
        raise
```

### Working with Relationships

```python
# Create related entities
client = Client(name="Acme Corp", created_at=datetime.now())
await client.insert()

addresses = [
    Address(street="123 Main St", client_id=client.id),
    Address(street="456 Oak Ave", client_id=client.id),
]
await context.insert_many(addresses)

# Query relationships
client = await Client.get_by_id(1)
all_addresses = await client.addresses.all()
active_addresses = await client.addresses.filter(Address.is_active == True).all()

# Access parent
address = await Address.get_by_id(1)
client = await address.client  # Automatically fetches related Client
```

## Best Practices

1. **Always use `async/await`** - All database operations are asynchronous
2. **Initialize context once** - Create your DbContext at application startup
3. **Use `sync_schema=True` in development** - Auto-updates schema during development
4. **Use bulk operations** - Use `insert_many()` and `update_many()` for better performance
5. **Leverage relationships** - Define relationships for cleaner code
6. **Use code generation** - Auto-generate DTOs and contexts to reduce boilerplate
7. **Don't edit generated files manually** - Use `--force` flag or modify source entities instead

## Troubleshooting

### RuntimeWarning on module execution
If you see warnings about module imports, ensure your generator scripts aren't imported in `__init__.py`.

### Foreign key errors
Make sure target entities are defined before referencing them in ForeignKey definitions.

### Schema not syncing
Ensure `sync_schema=True` is set when creating DbContext and that you call `await context.initialize()`.

## License

MIT License - see LICENSE file for details.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Support

For issues, questions, or contributions, please visit the GitHub repository.