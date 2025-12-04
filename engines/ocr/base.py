"""
OCR Engine Protocol for Morphic v0.2

Defines the contract that all OCR engines must implement.
Uses Python's Protocol for structural subtyping (duck typing with type safety).
"""

from typing import Protocol, Optional
from pathlib import Path
from PIL import Image


class OCREngine(Protocol):
    """
    Protocol for OCR engines.

    All OCR engines must implement these methods to be compatible
    with the Morphic pipeline.
    """

    def initialize(self, config: dict) -> None:
        """
        Initialize the engine with configuration.

        This method should:
        - Verify the OCR binary/library is available
        - Check version compatibility
        - Validate configuration parameters
        - Raise RuntimeError if initialization fails

        Args:
            config: Engine-specific configuration dictionary

        Raises:
            RuntimeError: If engine cannot be initialized
        """
        ...

    def recognize_to_hocr(
        self,
        image: Image.Image,
        language: str = "eng",
        output_path: Optional[Path] = None
    ) -> Path:
        """
        Run OCR and return path to hOCR file.

        hOCR format provides:
        - Text content
        - Bounding box coordinates (bbox x1 y1 x2 y2)
        - Confidence scores
        - Word/line/paragraph hierarchy

        Args:
            image: PIL Image to perform OCR on
            language: ISO 639-2 language code (e.g., 'eng', 'fra')
            output_path: Optional base path for output (will append .hocr)

        Returns:
            Path to generated hOCR file

        Raises:
            RuntimeError: If OCR fails
        """
        ...

    @property
    def name(self) -> str:
        """
        Engine identifier for logging and debugging.

        Returns:
            Unique name of this engine (e.g., 'tesseract', 'easyocr')
        """
        ...
