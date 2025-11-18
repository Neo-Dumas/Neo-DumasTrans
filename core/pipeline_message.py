from pathlib import Path
from typing import Optional

class PipelineMessage:
    def __init__(self, chunk_path: Path):
        self.chunk_path = chunk_path
        self.chunk_stem = chunk_path.stem
        self.pdf_type: Optional[str] = None
        self.mineru_output: Optional[dict] = None
        self.leaf_block_path: Optional[Path] = None
        self.translated_path: Optional[Path] = None
        self.html_path: Optional[Path] = None
        self.pdf_path: Optional[Path] = None
        self.censored_pdf_path: Optional[Path] = None
        self.error: Optional[str] = None