"""
JPEG2000 compression engine for Morphic v0.2

This is NEW functionality not present in OCRmyPDF.
OCRmyPDF only preserves existing JPEG2000, it does not encode to it.

JPEG2000 is essential for Morphic because:
- 600 DPI images require efficient compression
- Large document corpora (6000+ pages) need minimal file sizes
- Quality at high compression ratios exceeds JPEG

Requirements:
- Pillow with OpenJPEG support (pip install Pillow)
- OpenJPEG library: brew install openjpeg (macOS) or apt-get install libopenjp2-7 (Linux)
"""

import io
from typing import Optional
from PIL import Image

from . import register_compressor

# Import utilities for logging - use relative import from repo root
import sys
from pathlib import Path
repo_root = Path(__file__).resolve().parent.parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))
from utilities import Print


@register_compressor("jpeg2000")
class JPEG2000CompressorFactory:
    """Factory for creating JPEG2000 compressor instances."""

    @staticmethod
    def create(config: dict) -> "JPEG2000Compressor":
        return JPEG2000Compressor(config)


class JPEG2000Compressor:
    """
    JPEG2000 compression for high-resolution document images.

    JPEG2000 provides superior quality at high compression ratios compared
    to JPEG, making it ideal for 600 DPI document scans where file size
    must be minimized without sacrificing OCR accuracy or visual quality.

    Attributes:
        quality_layers: List of quality values for progressive encoding
        quality_mode: Either 'rates' (compression ratio) or 'dB' (PSNR)
        irreversible: If True, use lossy DWT (better compression)
    """

    def __init__(self, config: dict):
        """
        Initialize JPEG2000 compressor with configuration.

        Args:
            config: Configuration dictionary with optional keys:
                - quality_layers: List[int] - Quality values (default: [50])
                - quality_mode: str - 'rates' or 'dB' (default: 'rates')
                - irreversible: bool - Use lossy transform (default: True)
        """
        self.quality_layers = config.get('quality_layers', [50])
        self.quality_mode = config.get('quality_mode', 'rates')
        self.irreversible = config.get('irreversible', True)

        # Verify JPEG2000 support at initialization
        self._verify_jpeg2000_support()

    def _verify_jpeg2000_support(self) -> None:
        """
        Verify that Pillow has JPEG2000 encoding support.

        Raises:
            RuntimeError: If JPEG2000 encoding is not available
        """
        # Check if JPEG2000 is in supported formats
        if 'JPEG2000' not in Image.registered_extensions().values():
            # Try to encode a test image to verify
            test_img = Image.new('RGB', (10, 10), color='white')
            buffer = io.BytesIO()
            try:
                test_img.save(buffer, format='JPEG2000')
            except Exception as e:
                raise RuntimeError(
                    f"JPEG2000 encoding not available: {e}\n"
                    f"Install OpenJPEG library:\n"
                    f"  macOS: brew install openjpeg\n"
                    f"  Linux: apt-get install libopenjp2-7\n"
                    f"Then reinstall Pillow: pip install --force-reinstall Pillow"
                )

        Print("DEBUG", "JPEG2000 encoding verified")

    def compress(self, image: Image.Image, quality: Optional[int] = None) -> bytes:
        """
        Compress image to JPEG2000 format.

        Args:
            image: PIL Image to compress (will be converted to RGB if needed)
            quality: Optional quality override (compression ratio for 'rates' mode)
                    Higher values = more compression = smaller files = lower quality
                    Typical values: 20 (high quality) to 100 (high compression)

        Returns:
            JPEG2000 compressed image as bytes

        Raises:
            RuntimeError: If compression fails
        """
        if quality is None:
            quality = self.quality_layers[0]

        # Ensure RGB mode (JPEG2000 doesn't support RGBA well in PDFs)
        if image.mode == 'RGBA':
            # Composite onto white background
            background = Image.new('RGB', image.size, (255, 255, 255))
            background.paste(image, mask=image.split()[3])  # Use alpha as mask
            image = background
            Print("DEBUG", "Converted RGBA to RGB for JPEG2000")
        elif image.mode == 'LA':
            # Grayscale with alpha
            background = Image.new('L', image.size, 255)
            background.paste(image, mask=image.split()[1])
            image = background.convert('RGB')
            Print("DEBUG", "Converted LA to RGB for JPEG2000")
        elif image.mode == 'P':
            # Palette mode
            image = image.convert('RGB')
            Print("DEBUG", "Converted palette to RGB for JPEG2000")
        elif image.mode == 'L':
            # Grayscale - convert to RGB for consistency
            image = image.convert('RGB')
            Print("DEBUG", "Converted grayscale to RGB for JPEG2000")
        elif image.mode != 'RGB':
            image = image.convert('RGB')
            Print("DEBUG", f"Converted {image.mode} to RGB for JPEG2000")

        buffer = io.BytesIO()

        try:
            # Pillow JPEG2000 encoding parameters
            # See: https://pillow.readthedocs.io/en/stable/handbook/image-file-formats.html#jpeg-2000
            image.save(
                buffer,
                format='JPEG2000',
                quality_mode=self.quality_mode,
                quality_layers=[quality],
                irreversible=self.irreversible
            )

            compressed_bytes = buffer.getvalue()

            # Log compression stats
            original_size = image.width * image.height * 3  # RGB = 3 bytes/pixel
            compressed_size = len(compressed_bytes)
            ratio = original_size / compressed_size if compressed_size > 0 else 0

            Print("DEBUG",
                f"JPEG2000: {image.width}x{image.height} compressed "
                f"{original_size:,} -> {compressed_size:,} bytes "
                f"(ratio: {ratio:.1f}:1)"
            )

            return compressed_bytes

        except Exception as e:
            raise RuntimeError(
                f"JPEG2000 compression failed: {e}\n"
                f"Image: {image.size}, mode: {image.mode}\n"
                f"Quality: {quality}, mode: {self.quality_mode}"
            )

    @property
    def filter_name(self) -> str:
        """
        PDF filter name for JPEG2000.

        Returns:
            '/JPXDecode' - the PDF filter for JPEG2000 streams
        """
        return "JPXDecode"

    @property
    def name(self) -> str:
        """Compressor identifier."""
        return "jpeg2000"
