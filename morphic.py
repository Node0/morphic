#!/usr/bin/env python3
"""
Morphic v0.2: AI-first PDF preprocessor with OCR and dehyphenation.

This is the main orchestrator that wires together all Morphic components
to convert scanned/image PDFs into searchable PDFs optimized for RAG systems.

Architecture:
- Factory pattern for extensibility (inspired by Crystallizer)
- Protocol-based contracts for type safety
- Clean separation of concerns

Key patterns learned from OCRmyPDF:
- Tesseract hOCR generation (99% alignment quality)
- Rendering mode 3 for invisible text layer
- Text-under-image layering for visual fidelity

Unique Morphic features:
- JPEG2000 compression (50:1 ratio at 600 DPI)
- Dictionary-validated dehyphenation for RAG
- TJ operator text grouping for proper extraction

Usage:
    from morphic import MorphicPipeline

    pipeline = MorphicPipeline()
    pipeline.initialize()
    pipeline.process_pdf(Path("input.pdf"), Path("output.pdf"))

Or from command line:
    python morphic.py input.pdf output.pdf --dpi 300
"""

import json
import shutil
import tempfile
from pathlib import Path
from typing import List, Optional
from datetime import datetime

from pdf2image import convert_from_path
from PIL import Image

from engines.ocr import get_ocr_engine
from engines.pdf import get_pdf_engine
from engines.compression import get_compressor
from processors.dehyphenation import Dehyphenator
from utilities import Print


class MorphicPipeline:
    """
    Main orchestrator for Morphic PDF processing.

    Pipeline stages:
    1. PDF → Images (pdf2image with poppler)
    2. Images → hOCR (Tesseract OCR)
    3. hOCR → Dehyphenated hOCR (Dehyphenator)
    4. Image + hOCR → Searchable PDF page (pikepdf + JPEG2000)
    5. Merge pages → Final PDF

    Attributes:
        config: Loaded configuration dictionary
        ocr_engine: Initialized OCR engine instance
        pdf_engine: Initialized PDF engine instance
        compressor: Initialized image compressor instance
        dehyphenator: Initialized dehyphenation processor
        temp_dir: Path to temporary working directory
    """

    def __init__(self, config_path: Optional[Path] = None):
        """
        Initialize pipeline with configuration.

        Args:
            config_path: Path to config.json. If None, uses default location.
        """
        self.config = self._load_config(config_path)
        self.ocr_engine = None
        self.pdf_engine = None
        self.compressor = None
        self.dehyphenator = None
        self.temp_dir = None
        self._initialized = False

    def _load_config(self, config_path: Optional[Path]) -> dict:
        """Load configuration from JSON file."""
        if config_path is None:
            # Default: look for config relative to this file
            config_path = Path(__file__).parent / "config" / "config.json"

        if not config_path.exists():
            raise FileNotFoundError(
                f"Configuration file not found: {config_path}\n"
                f"Create config/config.json or specify path with config_path parameter."
            )

        with open(config_path) as f:
            config = json.load(f)

        Print("DEBUG", f"Loaded configuration v{config.get('version', 'unknown')}")
        return config

    def initialize(
        self,
        ocr_engine_name: str = "tesseract",
        pdf_engine_name: str = "pikepdf",
        compression: str = "jpeg2000"
    ) -> None:
        """
        Initialize all processing engines.

        This must be called before process_pdf().

        Args:
            ocr_engine_name: Name of OCR engine to use (default: tesseract)
            pdf_engine_name: Name of PDF engine to use (default: pikepdf)
            compression: Name of compression strategy (default: jpeg2000)

        Raises:
            ValueError: If specified engine is not registered
            RuntimeError: If engine initialization fails
        """
        Print("STARTING", f"Initializing Morphic v{self.config.get('version', '0.2.0')} pipeline")

        # Initialize OCR engine
        ocr_config = self.config['ocr_engines'].get(ocr_engine_name, {})
        self.ocr_engine = get_ocr_engine(ocr_engine_name, ocr_config)
        self.ocr_engine.initialize(ocr_config)
        Print("SUCCESS", f"OCR engine: {self.ocr_engine.name}")

        # Initialize PDF engine
        pdf_config = self.config['pdf_engines'].get(pdf_engine_name, {})
        self.pdf_engine = get_pdf_engine(pdf_engine_name, pdf_config)
        Print("SUCCESS", f"PDF engine: {self.pdf_engine.name}")

        # Initialize compressor
        comp_config = self.config['compression'].get(compression, {})
        self.compressor = get_compressor(compression, comp_config)
        Print("SUCCESS", f"Compressor: {self.compressor.name}")

        # Initialize dehyphenator
        dehyp_config = self.config['processing'].get('dehyphenation', {'enabled': True})
        self.dehyphenator = Dehyphenator(dehyp_config)
        if dehyp_config.get('enabled', True):
            Print("SUCCESS", f"Dehyphenation: enabled (dictionary: {dehyp_config.get('dictionary', 'en_US')})")
        else:
            Print("INFO", "Dehyphenation: disabled")

        # Create temp directory
        temp_base = self.config['processing'].get('temp_dir', '/tmp/morphic')
        self.temp_dir = Path(temp_base) / f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        Print("DEBUG", f"Temp directory: {self.temp_dir}")

        self._initialized = True
        Print("SUCCESS", "Pipeline initialized")

    def process_pdf(
        self,
        input_pdf: Path,
        output_pdf: Path,
        dpi: Optional[int] = None,
        first_page: Optional[int] = None,
        last_page: Optional[int] = None,
        keep_temp: bool = False
    ) -> dict:
        """
        Process a PDF through the complete pipeline.

        Args:
            input_pdf: Path to input PDF file
            output_pdf: Path for output searchable PDF
            dpi: Resolution for rendering (default: from config, typically 600)
            first_page: First page to process (1-indexed, default: 1)
            last_page: Last page to process (default: all pages)
            keep_temp: Keep temporary files for debugging (default: False)

        Returns:
            dict with processing statistics:
                - pages: Number of pages processed
                - input_size: Input file size in bytes
                - output_size: Output file size in bytes
                - compression_ratio: Size reduction ratio
                - words_dehyphenated: Total words merged
                - processing_time: Time in seconds

        Raises:
            RuntimeError: If pipeline not initialized or processing fails
            FileNotFoundError: If input PDF doesn't exist
        """
        if not self._initialized:
            raise RuntimeError("Pipeline not initialized. Call initialize() first.")

        input_pdf = Path(input_pdf)
        output_pdf = Path(output_pdf)

        if not input_pdf.exists():
            raise FileNotFoundError(f"Input PDF not found: {input_pdf}")

        # Use configured DPI if not specified
        if dpi is None:
            dpi = self.config['processing'].get('default_dpi', 600)

        start_time = datetime.now()
        input_size = input_pdf.stat().st_size

        Print("STATE", f"Processing: {input_pdf.name}")
        Print("INFO", f"Input size: {input_size / (1024*1024):.2f} MB")
        Print("INFO", f"Resolution: {dpi} DPI")

        # =====================================================================
        # Stage 1: Extract pages as images
        # =====================================================================
        Print("PROGRESS", "Stage 1/5: Extracting pages from PDF...")

        pages = convert_from_path(
            input_pdf,
            dpi=dpi,
            first_page=first_page,
            last_page=last_page
        )

        total_pages = len(pages)
        Print("INFO", f"Extracted {total_pages} page{'s' if total_pages != 1 else ''}")

        # =====================================================================
        # Stage 2-4: Process each page
        # =====================================================================
        pdf_pages = []
        total_dehyphenated = 0

        for page_num, img in enumerate(pages, 1):
            Print("PROGRESS", f"Processing page {page_num}/{total_pages}")

            # Create temp paths for this page
            page_base = self.temp_dir / f"page_{page_num}"
            img_path = page_base.with_suffix('.png')

            # Save image temporarily
            img.save(img_path, format='PNG')
            Print("DEBUG", f"  Saved image: {img.size[0]}x{img.size[1]} px")

            # Stage 2: OCR → hOCR
            Print("DEBUG", f"  Running OCR...")
            hocr_path = self.ocr_engine.recognize_to_hocr(
                img,
                output_path=page_base
            )

            # Stage 3: Dehyphenate hOCR
            if self.config['processing']['dehyphenation'].get('enabled', True):
                merged = self.dehyphenator.process_file(hocr_path)
                total_dehyphenated += merged
                if merged > 0:
                    Print("DEBUG", f"  Dehyphenated: {merged} word pairs")

            # Stage 4: Create searchable PDF page
            Print("DEBUG", f"  Creating PDF page...")
            page_pdf = self.pdf_engine.create_searchable_page(
                image_path=img_path,
                hocr_path=hocr_path,
                dpi=dpi,
                compressor=self.compressor
            )
            pdf_pages.append(page_pdf)

            # Cleanup temp files for this page (unless debugging)
            if not keep_temp:
                img_path.unlink(missing_ok=True)
                hocr_path.unlink(missing_ok=True)

        # =====================================================================
        # Stage 5: Merge pages into final PDF
        # =====================================================================
        Print("PROGRESS", "Stage 5/5: Merging pages...")

        final_pdf = self.pdf_engine.merge_pages(pdf_pages)

        # Ensure output directory exists
        output_pdf.parent.mkdir(parents=True, exist_ok=True)

        # Save final PDF
        final_pdf.save(str(output_pdf))

        # =====================================================================
        # Cleanup and statistics
        # =====================================================================
        if not keep_temp and self.temp_dir.exists():
            try:
                shutil.rmtree(self.temp_dir)
                Print("DEBUG", "Cleaned up temp directory")
            except Exception as e:
                Print("WARNING", f"Could not clean temp directory: {e}")

        # Calculate statistics
        end_time = datetime.now()
        output_size = output_pdf.stat().st_size
        processing_time = (end_time - start_time).total_seconds()

        # Compression ratio (input / output)
        compression_ratio = input_size / output_size if output_size > 0 else 0

        stats = {
            'pages': total_pages,
            'input_size': input_size,
            'output_size': output_size,
            'compression_ratio': compression_ratio,
            'words_dehyphenated': total_dehyphenated,
            'processing_time': processing_time
        }

        # Final summary
        Print("COMPLETED", f"Saved: {output_pdf}")
        Print("INFO", f"Output size: {output_size / (1024*1024):.2f} MB")
        Print("INFO", f"Compression: {compression_ratio:.1f}x reduction")
        if total_dehyphenated > 0:
            Print("INFO", f"Dehyphenated: {total_dehyphenated} word pairs")
        Print("INFO", f"Time: {processing_time:.1f} seconds ({processing_time/total_pages:.1f}s per page)")

        return stats

    def process_images(
        self,
        image_paths: List[Path],
        output_pdf: Path,
        dpi: int = 300,
        keep_temp: bool = False
    ) -> dict:
        """
        Process a list of images into a searchable PDF.

        Useful for processing images directly without an input PDF.

        Args:
            image_paths: List of paths to image files
            output_pdf: Path for output searchable PDF
            dpi: Resolution of input images (default: 300)
            keep_temp: Keep temporary files for debugging

        Returns:
            dict with processing statistics (same as process_pdf)
        """
        if not self._initialized:
            raise RuntimeError("Pipeline not initialized. Call initialize() first.")

        if not image_paths:
            raise ValueError("No image paths provided")

        start_time = datetime.now()
        total_input_size = sum(Path(p).stat().st_size for p in image_paths)

        Print("STATE", f"Processing {len(image_paths)} images")
        Print("INFO", f"Resolution: {dpi} DPI")

        pdf_pages = []
        total_dehyphenated = 0

        for page_num, img_path in enumerate(image_paths, 1):
            img_path = Path(img_path)
            Print("PROGRESS", f"Processing image {page_num}/{len(image_paths)}: {img_path.name}")

            # Load image
            img = Image.open(img_path)

            # Create temp path for hOCR
            page_base = self.temp_dir / f"page_{page_num}"

            # OCR
            hocr_path = self.ocr_engine.recognize_to_hocr(
                img,
                output_path=page_base
            )

            # Dehyphenate
            if self.config['processing']['dehyphenation'].get('enabled', True):
                merged = self.dehyphenator.process_file(hocr_path)
                total_dehyphenated += merged

            # Create PDF page
            page_pdf = self.pdf_engine.create_searchable_page(
                image_path=img_path,
                hocr_path=hocr_path,
                dpi=dpi,
                compressor=self.compressor
            )
            pdf_pages.append(page_pdf)

            # Cleanup
            if not keep_temp:
                hocr_path.unlink(missing_ok=True)

        # Merge and save
        Print("PROGRESS", "Merging pages...")
        final_pdf = self.pdf_engine.merge_pages(pdf_pages)
        output_pdf.parent.mkdir(parents=True, exist_ok=True)
        final_pdf.save(str(output_pdf))

        # Cleanup
        if not keep_temp and self.temp_dir.exists():
            shutil.rmtree(self.temp_dir, ignore_errors=True)

        # Statistics
        end_time = datetime.now()
        output_size = output_pdf.stat().st_size
        processing_time = (end_time - start_time).total_seconds()

        stats = {
            'pages': len(image_paths),
            'input_size': total_input_size,
            'output_size': output_size,
            'compression_ratio': total_input_size / output_size if output_size > 0 else 0,
            'words_dehyphenated': total_dehyphenated,
            'processing_time': processing_time
        }

        Print("COMPLETED", f"Saved: {output_pdf}")
        Print("INFO", f"Output size: {output_size / (1024*1024):.2f} MB")

        return stats


def main():
    """Command-line entry point for quick testing."""
    import argparse

    parser = argparse.ArgumentParser(
        description='Morphic v0.2: AI-first PDF preprocessor with OCR and dehyphenation',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python morphic.py input.pdf output.pdf
  python morphic.py input.pdf output.pdf --dpi 300
  python morphic.py input.pdf output.pdf --pages 1-10
        """
    )

    parser.add_argument('input', type=Path, help='Input PDF file')
    parser.add_argument('output', type=Path, help='Output PDF file')
    parser.add_argument('--dpi', type=int, default=None, help='Resolution (default: from config)')
    parser.add_argument('--first-page', type=int, default=None, help='First page to process')
    parser.add_argument('--last-page', type=int, default=None, help='Last page to process')
    parser.add_argument('--keep-temp', action='store_true', help='Keep temporary files')
    parser.add_argument('--config', type=Path, default=None, help='Path to config.json')

    args = parser.parse_args()

    try:
        pipeline = MorphicPipeline(config_path=args.config)
        pipeline.initialize()

        stats = pipeline.process_pdf(
            input_pdf=args.input,
            output_pdf=args.output,
            dpi=args.dpi,
            first_page=args.first_page,
            last_page=args.last_page,
            keep_temp=args.keep_temp
        )

        return 0

    except FileNotFoundError as e:
        Print("FAILURE", str(e))
        return 1
    except RuntimeError as e:
        Print("FAILURE", str(e))
        return 2
    except KeyboardInterrupt:
        Print("WARNING", "Interrupted by user")
        return 130
    except Exception as e:
        Print("FAILURE", f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
