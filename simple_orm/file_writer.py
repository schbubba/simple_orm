import os
import pathlib
import re
import json
import hashlib
from typing import Literal
from .class_writer import ClassWriter

MarkerName = Literal["header", "import", "class", "decorator", "property", "method", "start", "stop"]


class FileWriter:
    """Generates Python files with metadata tracking stored in cache folder."""
    
    # Constants for markers (only used during generation, stripped from final output)
    SEPARATOR = "🧩"
    MARKERS = {
        "header": "🌲",
        "import": "📙",
        "class": "📖",
        "decorator": "📘",
        "property": "🔒",
        "method": "📕",
        "start": "🟩",
        "stop": "🛑"
    }
    
    CACHE_DIR = ".simple_orm"
    
    def __init__(self, name: str, output_path: str):
        self.name = name
        self._classes: list[ClassWriter] = []
        self.header_comments: list[str] = []
        self.imports: list[str] = []
        self.separator = self.SEPARATOR
        self.markers = self.MARKERS
        self.output_path = output_path

    def add_header_comment(self, line: str):
        """Add a comment to the file header."""
        self.header_comments.append(line)
    
    def add_import(self, line: str):
        """Add an import statement to the file."""
        self.imports.append(line)

    def add_class(self, name: str, base: str = None, indent: int = 4, property_boundaries: bool = False) -> ClassWriter:
        """Add a class to the file and return the ClassWriter for further configuration."""
        cw = ClassWriter(self.separator, name, indent, property_boundaries)
        if base:
            cw.class_inherits = base
        self._classes.append(cw)
        return cw
    
    def _add_markers_to_section(self, items: list[str], marker_type: str) -> list[str]:
        """Add start/stop markers to a section of lines."""
        if not items:
            return []
        
        marked = []
        for i, item in enumerate(items):
            if i == 0:
                marked.append(f"{item}{self.separator}#{{{marker_type}}}{{start}}")
            elif i == len(items) - 1:
                marked.append(f"{item}{self.separator}#{{{marker_type}}}{{stop}}")
            else:
                marked.append(f"{item}{self.separator}#{{{marker_type}}}")
        return marked
    
    def _build_lines(self) -> list[str]:
        """Build all lines for the file with metadata markers (temporarily)."""
        lines = []

        # Add header comments
        if self.header_comments:
            lines.extend(self._add_markers_to_section(self.header_comments, "header"))
            lines.append("")

        # Add imports
        if self.imports:
            lines.extend(self._add_markers_to_section(self.imports, "import"))
            lines.append("")

        # Add classes
        for cw in self._classes:
            lines.extend(cw._build_lines())
            lines.append("")

        # Apply marker formatting and padding
        max_length = len(max(lines, key=len)) + 4 if lines else 0
        formatted_lines = []
        
        for line in lines:
            if self.separator in line:
                parts = line.split(self.separator)
                code_part = parts[0]
                marker_part = parts[1].format(**self.markers)
                formatted_lines.append(code_part.ljust(max_length) + marker_part)
            else:
                formatted_lines.append(line.ljust(max_length))

        return formatted_lines
    
    def _clean_lines(self, lines: list[str]) -> list[str]:
        """Remove padding and markers from lines to get clean Python code."""
        return [line[:-4].rstrip() for line in lines]

    def _build_meta_data(self, lines: list[str]) -> dict:
        """Build metadata structure from marked lines."""
        file_meta = {}

        # Extract headers
        headers_found = self._get_boundaries(lines, "header")
        if headers_found:
            file_meta["headers"] = headers_found

        # Extract imports
        imports_found = self._get_boundaries(lines, "import")
        if imports_found:
            file_meta["imports"] = imports_found

        # Extract classes and their contents
        classes_found = self._get_boundaries(lines, "class")
        classes = []
        
        for start, end, class_name in classes_found:
            cls = {"class": [start, end, class_name]}
            class_lines = lines[start:end + 1]

            # Extract properties within class
            properties_found = self._get_boundaries(class_lines, "property", offset=start)
            if properties_found:
                cls["properties"] = properties_found

            # Extract methods within class
            methods_found = self._get_boundaries(class_lines, "method", offset=start)
            if methods_found:
                cls["methods"] = methods_found

            classes.append(cls)

        file_meta["classes"] = classes
        
        return file_meta

    def _get_boundaries(self, lines: list[str], marker_name: MarkerName, offset: int = 0) -> list[tuple[int, int, str]]:
        """
        Extract (start_index, end_index, name) for each marked block.
        
        For classes, extracts the class name. For other markers, uses the marker type as the name.
        """
        blocks = []
        start_tag = self.markers[marker_name] + self.markers["start"]
        stop_tag = self.markers[marker_name] + self.markers["stop"]
        
        # Pattern to extract class names
        class_pattern = re.compile(r"class ([A-Za-z0-9_]+)[\(:]")
        
        start_index = None
        block_name = None

        for i, line in enumerate(lines):
            # Detect start of block
            if line.rstrip().endswith(start_tag):
                start_index = i
                
                # Try to extract class name if this is a class block
                if marker_name == "class":
                    match = class_pattern.search(line)
                    block_name = match.group(1) if match else marker_name
                else:
                    block_name = marker_name
                continue

            # Detect end of block
            if start_index is not None and line.rstrip().endswith(stop_tag):
                blocks.append((start_index + offset, i + offset, block_name))
                start_index = None
                block_name = None

        return blocks

    def _calculate_content_hash(self, content: str) -> str:
        """Calculate SHA256 hash of file content."""
        return hashlib.sha256(content.encode('utf-8')).hexdigest()

    def _get_metadata_path(self) -> pathlib.Path:
        """Get the path to the metadata file for this output file."""
        # Use the output file path to create a unique metadata filename
        # Replace path separators and special chars to create valid filename
        safe_name = str(self.output_path).replace('/', '_').replace('\\', '_').replace(':', '_')
        return pathlib.Path(self.CACHE_DIR) / f"{safe_name}.meta.json"

    def _save_metadata(self, file_meta: dict, content_hash: str):
        """Save metadata to cache folder."""
        metadata = {
            "version": 1,
            "path": self.output_path,
            "sha256": content_hash,
            "meta": file_meta
        }
        
        # Ensure cache directory exists
        os.makedirs(self.CACHE_DIR, exist_ok=True)
        
        # Write metadata file
        meta_path = self._get_metadata_path()
        with open(meta_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=4)

    def _load_metadata(self) -> dict | None:
        """Load metadata from cache folder if it exists."""
        meta_path = self._get_metadata_path()
        
        if not meta_path.exists():
            return None
        
        try:
            with open(meta_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f'Warning: Could not load metadata: {e}')
            return None

    def generate_file(self) -> str:
        """Generate the complete file content as a string."""
        # Build lines with markers
        marked_lines = self._build_lines()
        
        # Clean lines (remove markers)
        clean_lines = self._clean_lines(marked_lines)
        
        # Return final content
        return "\n".join(clean_lines) + "\n"

    def _has_user_modifications(self, file_path: pathlib.Path) -> bool:
        """
        Check if the file has been modified by comparing SHA256 hashes.
        Returns True if user has made changes, False otherwise.
        """
        # Load stored metadata
        metadata = self._load_metadata()
        
        if not metadata:
            # No metadata means this is a new file or metadata was deleted
            return False
        
        stored_hash = metadata.get('sha256')
        if not stored_hash:
            return False
        
        # Read current file content
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                current_content = f.read()
        except FileNotFoundError:
            # File doesn't exist, no modifications
            return False
        
        # Calculate current hash
        current_hash = self._calculate_content_hash(current_content)
        
        # Compare hashes
        return current_hash != stored_hash

    def write_file(self, force: bool = False):
        """
        Write the generated file to disk.
        
        Args:
            force: If True, overwrite even if user modifications detected
        """
        output_path = pathlib.Path(self.output_path)
        
        # Check if file exists and has been modified by user
        if output_path.exists() and not force:
            if self._has_user_modifications(output_path):
                print(f'Warning: {self.name} at {output_path} has been modified by user.')
                print('Skipping regeneration to preserve changes. Use force=True to overwrite.')
                return
        
        # Generate content
        content = self.generate_file()
        
        # Write the file
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        # Calculate hash and save metadata
        content_hash = self._calculate_content_hash(content)
        
        # Build metadata from marked lines (need to regenerate marked lines for metadata)
        marked_lines = self._build_lines()
        file_meta = self._build_meta_data(marked_lines)
        
        # Save metadata to cache
        self._save_metadata(file_meta, content_hash)

        print(f'{self.name} generated and saved to {output_path}')