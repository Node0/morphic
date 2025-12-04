"""
Image Compressor Protocol for Morphic v0.2

Defines the contract that all image compression strategies must implement.
"""

from typing import Protocol, Optional
from PIL import Image


class ImageCompressor(Protocol):
    """
    Protocol for image compression strategies.

    Compressors are responsible for:
    - Encoding PIL images to compressed byte streams
    - Providing PDF filter names for embedding
    - Managing compression quality parameters
    """

    def compress(self, image: Image.Image, quality: Optional[int] = None) -> bytes:
        """
        Compress image to bytes.

        Args:
            image: PIL Image to compress
            quality: Optional quality override (meaning varies by format)
                    - JPEG2000: compression ratio (10-60+)
                    - JPEG: quality (0-100)
                    - PNG: ignored (lossless)

        Returns:
            Compressed image as bytes

        Raises:
            RuntimeError: If compression fails
        """
        ...

    @property
    def filter_name(self) -> str:
        """
        PDF filter name for this compression format.

        Returns:
            PDF filter identifier (e.g., '/JPXDecode', '/DCTDecode', '/FlateDecode')

        Common filters:
            - JPEG2000: '/JPXDecode'
            - JPEG: '/DCTDecode'
            - PNG: '/FlateDecode'
        """
        ...

    @property
    def name(self) -> str:
        """
        Compressor identifier for logging and debugging.

        Returns:
            Unique name of this compressor (e.g., 'jpeg2000', 'jpeg', 'png')
        """
        ...
