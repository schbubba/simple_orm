KEY_WORDS = ["order"]

def get_column_name(name: str) -> str:
    """Return the column name, escaping it if it's a SQL keyword."""
    if name.lower() in KEY_WORDS:
        return f"[{name}]"
    return name

def reverse_column_name(escaped_name: str) -> str:
    """Return the original column name from an escaped name."""
    if escaped_name.startswith("[") and escaped_name.endswith("]"):
        return escaped_name[1:-1]
    return escaped_name