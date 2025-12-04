"""
PDF Engine Protocol for Morphic v0.2

Defines the contract that all PDF manipulation engines must implement.
"""

from typing import Protocol, List
from pathlib import Path
import pikepdf


class PDFEngine(Protocol):
    """
    Protocol for PDF manipulation engines.

    PDF engines are responsible for:
    - Creating searchable PDF pages from images + hOCR
    - Embedding invisible text layers (rendering mode 3)
    - Merging multiple pages into final document
    """

    def create_searchable_page(
        self,
        image_path: Path,
        hocr_path: Path,
        dpi: int,
        compressor
    ) -> pikepdf.Pdf:
        """
        Create a PDF page with invisible text layer.

        The text layer must be:
        - Invisible (rendering mode 3 or equivalent)
        - Positioned exactly under corresponding image pixels
        - Selectable and searchable

        Args:
            image_path: Path to image file for this page
            hocr_path: Path to hOCR file with OCR results
            dpi: DPI of the source image (for coordinate conversion)
            compressor: ImageCompressor instance for image encoding

        Returns:
            Single-page PDF with image and text layer

        Raises:
            RuntimeError: If PDF creation fails
        """
        ...

    def merge_pages(self, pages: List[pikepdf.Pdf]) -> pikepdf.Pdf:
        """
        Merge multiple PDF pages into one document.

        Args:
            pages: List of single-page PDF objects

        Returns:
            Multi-page PDF document

        Raises:
            ValueError: If pages list is empty
        """
        ...

    @property
    def name(self) -> str:
        """
        Engine identifier for logging and debugging.

        Returns:
            Unique name of this engine (e.g., 'pikepdf', 'pypdf')
        """
        ...
