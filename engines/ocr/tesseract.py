"""
Tesseract OCR engine for Morphic v0.2

Implementation adapted from OCRmyPDF (MIT/MPL-2.0):
https://github.com/ocrmypdf/OCRmyPDF/blob/main/src/ocrmypdf/_exec/tesseract.py

Key adaptations:
- Removed plugin system integration
- Simplified error handling (standard Python exceptions)
- Removed subprocess wrapper dependency
- Single-language focus for v0.2

Original authors: James R. Barlow and contributors
License: MIT/MPL-2.0
"""

from typing import Optional
from PIL import Image
import subprocess
from pathlib import Path
import tempfile
from . import register_ocr_engine
from utilities import Print


@register_ocr_engine("tesseract")
class TesseractEngineFactory:
    """Factory for creating Tesseract engine instances."""

    @staticmethod
    def create(config: dict):
        """
        Create a Tesseract engine instance.

        Args:
            config: Configuration dictionary with:
                - binary_path: Path to tesseract binary (default: 'tesseract')
                - oem: OCR Engine Mode (default: 3 for LSTM)
                - psm: Page Segmentation Mode (default: 3 for auto)
                - language: Language code (default: 'eng')

        Returns:
            Initialized TesseractEngine instance
        """
        return TesseractEngine(config)


class TesseractEngine:
    """
    Tesseract OCR implementation using direct hOCR output.

    Why Tesseract over EasyOCR?
    - Tesseract produces hOCR with 99% text alignment quality
    - EasyOCR has ~70% alignment (bounding boxes don't match perfectly)
    - Native hOCR output (no conversion needed)
    - Industry standard for searchable PDFs
    """

    def __init__(self, config: dict):
        """
        Initialize Tesseract engine.

        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.tesseract_path = config.get('binary_path', 'tesseract')
        self.oem = config.get('oem', 3)  # LSTM neural nets
        self.psm = config.get('psm', 3)  # Fully automatic page segmentation
        self.language = config.get('language', 'eng')
        self._version = None

    def initialize(self, config: dict) -> None:
        """
        Verify Tesseract installation.

        Adapted from ocrmypdf/_exec/tesseract.py:version()

        Args:
            config: Additional configuration (currently unused)

        Raises:
            RuntimeError: If Tesseract is not found or version is incompatible
        """
        try:
            result = subprocess.run(
                [self.tesseract_path, '--version'],
                capture_output=True,
                text=True,
                check=True,
                timeout=5
            )
            version_line = result.stdout.split('\n')[0]
            self._version = version_line
            Print("SUCCESS", f"Found {version_line}")

            # Verify minimum version (4.0+)
            if 'tesseract' in version_line.lower():
                version_parts = version_line.split()
                if len(version_parts) >= 2:
                    version_str = version_parts[1]
                    # Parse major version
                    try:
                        major = int(version_str.split('.')[0])
                        if major < 4:
                            Print("WARNING", "Tesseract 4.0+ recommended for best results")
                    except (ValueError, IndexError):
                        Print("WARNING", f"Could not parse Tesseract version: {version_str}")

            # Verify language is available
            self._verify_language(self.language)

        except FileNotFoundError:
            raise RuntimeError(
                f"Tesseract not found at '{self.tesseract_path}'. "
                f"Install: brew install tesseract (macOS) or apt-get install tesseract-ocr (Linux)"
            )
        except subprocess.TimeoutExpired:
            raise RuntimeError(
                f"Tesseract command timed out. Check installation at: {self.tesseract_path}"
            )
        except Exception as e:
            raise RuntimeError(f"Tesseract initialization failed: {e}")

    def _verify_language(self, language: str) -> None:
        """
        Verify that the specified language is available.

        Adapted from ocrmypdf/_exec/tesseract.py:get_languages()

        Args:
            language: Language code to verify (e.g., 'eng')

        Raises:
            RuntimeError: If language is not available
        """
        try:
            result = subprocess.run(
                [self.tesseract_path, '--list-langs'],
                capture_output=True,
                text=True,
                check=True,
                timeout=5
            )

            # Parse available languages from output
            # Format is:
            # List of available languages (X):
            # eng
            # fra
            # ...
            available_langs = []
            for line in result.stdout.split('\n'):
                line = line.strip()
                if line and not line.startswith('List of'):
                    available_langs.append(line)

            if language not in available_langs:
                raise RuntimeError(
                    f"Tesseract language '{language}' not available. "
                    f"Available: {', '.join(available_langs)}. "
                    f"Install: brew install tesseract-lang (macOS)"
                )

            Print("DEBUG", f"Language '{language}' verified")

        except subprocess.TimeoutExpired:
            Print("WARNING", "Could not verify language (timeout), proceeding anyway")
        except subprocess.CalledProcessError as e:
            Print("WARNING", f"Could not verify language: {e.stderr}")

    def recognize_to_hocr(
        self,
        image: Image.Image,
        language: str = "eng",
        output_path: Optional[Path] = None
    ) -> Path:
        """
        Run Tesseract and return path to hOCR file.

        Adapted from ocrmypdf/_exec/tesseract.py:generate_hocr()
        Key change: Simplified to not use ocrmypdf's subprocess wrapper.

        Args:
            image: PIL Image to OCR
            language: Tesseract language code (default: 'eng')
            output_path: Base path for output (will append .hocr)

        Returns:
            Path to generated hOCR file

        Raises:
            RuntimeError: If OCR fails
        """
        # Use provided language or fall back to configured default
        lang = language if language else self.language

        # Determine output paths
        if output_path:
            temp_img = output_path.parent / f"{output_path.stem}_img.png"
            hocr_base = output_path.parent / output_path.stem
        else:
            # Use temp directory - /var/tmp is more reliable on macOS than /tmp
            # (which is symlinked to /private/tmp and can cause Tesseract access issues)
            temp_dir = Path("/var/tmp/morphic")
            temp_dir.mkdir(exist_ok=True, parents=True)
            temp_img = temp_dir / "morphic_temp.png"
            hocr_base = temp_dir / "morphic_temp"

        # Save image temporarily
        # Convert to RGB if needed (Tesseract prefers RGB)
        if image.mode in ('RGBA', 'LA', 'P'):
            Print("DEBUG", f"Converting image from {image.mode} to RGB")
            background = Image.new('RGB', image.size, (255, 255, 255))
            if image.mode == 'P':
                image = image.convert('RGBA')
            if 'A' in image.mode:
                background.paste(image, mask=image.split()[-1])
            else:
                background.paste(image)
            image = background

        image.save(temp_img, format='PNG')
        Print("DEBUG", f"Saved temp image to {temp_img}")

        # Build Tesseract command
        # Pattern from ocrmypdf/_exec/tesseract.py:generate_hocr() line ~220
        cmd = [
            self.tesseract_path,
            str(temp_img),
            str(hocr_base),
            '-l', lang,
            '--oem', str(self.oem),
            '--psm', str(self.psm),
            'hocr'  # Output format
        ]

        Print("DEBUG", f"Running: {' '.join(cmd)}")

        try:
            # Use bytes mode to avoid encoding issues with Tesseract output
            # Note: Do NOT use check=True - Tesseract may return non-zero even on success
            # (e.g., warnings about image format that don't prevent OCR)
            result = subprocess.run(
                cmd,
                capture_output=True,
                timeout=120  # 2 minute timeout for OCR
            )

            # Log Tesseract output if present (decode with error handling)
            # Note: Tesseract writes progress/warnings to stderr even on success
            if result.stdout:
                stdout_text = result.stdout.decode('utf-8', errors='replace').strip()
                if stdout_text:
                    Print("DEBUG", f"Tesseract stdout: {stdout_text}")
            if result.stderr:
                stderr_text = result.stderr.decode('utf-8', errors='replace').strip()
                # Filter out common informational messages and Leptonica noise
                for line in stderr_text.split('\n'):
                    # Skip version info and Leptonica errors (often spurious)
                    if line and not line.startswith('Tesseract Open Source'):
                        if 'Leptonica Error' not in line and 'fopenReadStream' not in line:
                            Print("DEBUG", f"Tesseract: {line}")

        except subprocess.TimeoutExpired:
            Print("FAILURE", "Tesseract timed out after 120 seconds")

            # Cleanup temp image on timeout
            if temp_img.exists():
                temp_img.unlink()

            raise RuntimeError("OCR timed out - image may be too large or complex")

        # Verify hOCR output was created
        hocr_path = hocr_base.with_suffix('.hocr')

        if not hocr_path.exists():
            # Cleanup temp image
            if temp_img.exists():
                temp_img.unlink()

            raise RuntimeError(
                f"Tesseract did not produce expected output: {hocr_path}"
            )

        # Verify hOCR has content
        if hocr_path.stat().st_size == 0:
            Print("WARNING", "Tesseract produced empty hOCR file")
        else:
            Print("DEBUG", f"Generated hOCR: {hocr_path} ({hocr_path.stat().st_size} bytes)")

        # Cleanup temp image
        if temp_img.exists():
            temp_img.unlink()

        return hocr_path

    @property
    def name(self) -> str:
        """Engine identifier."""
        return "tesseract"

    @property
    def version(self) -> Optional[str]:
        """Tesseract version string."""
        return self._version
