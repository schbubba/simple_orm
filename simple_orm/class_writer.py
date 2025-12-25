class ClassWriter:
    """Builds Python class definitions with properties and methods."""
    
    def __init__(self, separator: str, name: str, indent: int = 4, property_boundaries: bool = False):
        self.decorator = None
        self.separator = separator
        self.name = name
        self.indent = " " * indent
        self.property_boundaries = property_boundaries
        self.properties: list[str] = []
        self.methods: list[str] = []
        self.header_comments: list[str] = []
        self.class_inherits: str | None = None

    def set_decorator(self, line: str):
        """Add a decorator to the class (e.g., @dataclass)."""
        self.decorator = f"{line}{self.separator}#{{decorator}}{{start}}{{stop}}"

    def add_property(self, line: str):
        """Add a class property or attribute."""
        self.properties.append(f"{self.indent}{line}{self.separator}#{{property}}")

    def add_method(self, line: str, indent_level: int = 1):
        """Add a method to the class."""
        self.methods.append(f"{self.indent * indent_level}{line}{self.separator}#{{method}}")

    def _mark_boundaries(self):
        """Mark start and stop boundaries for properties and methods."""
        if self.properties:
            self.properties[0] += "{start}"
            self.properties[-1] += "{stop}"

        if self.methods:
            self.methods[0] += "{start}"
            self.methods[-1] += "{stop}"

    def _build_lines(self) -> list[str]:
        """Build the complete class definition as a list of lines."""
        self._mark_boundaries()

        lines = []

        # Add decorator if present
        if self.decorator:
            lines.append(self.decorator)

        # Add class header
        if self.class_inherits:
            lines.append(f"class {self.name}({self.class_inherits}):{self.separator}#{{class}}{{start}}")
        else:
            lines.append(f"class {self.name}:{self.separator}#{{class}}{{start}}")

        # Add properties
        if self.properties:
            lines.extend(self.properties)
            lines.append("")
        
        # Add methods
        if self.methods:
            lines.extend(self.methods)

        # Handle empty class
        if not self.properties and not self.methods:
            lines.append(f"{self.indent}pass")

        # Mark class end
        last_line = lines[-1]
        if self.separator in last_line:
            last_line += "{class}{stop}"
        else:
            last_line += f"{self.separator}#{{class}}{{stop}}"
        lines[-1] = last_line

        return lines

    def generate_class(self) -> str:
        """Generate the complete class definition as a string."""
        return "\n".join(self._build_lines())