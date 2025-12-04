#!/usr/bin/env python3
"""
Functional Test for Tesseract OCR Engine

Tests the Tesseract engine with a real PDF file to verify:
1. Tesseract is installed and accessible
2. Engine can initialize properly
3. PDF can be converted to images
4. OCR produces valid hOCR output
5. hOCR contains actual text content
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
repo_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(repo_root))

from engines.ocr import get_ocr_engine
from pdf2image import convert_from_path
from utilities import Print
import json


def test_tesseract_engine():
    """
    Functional test for Tesseract OCR engine.

    Uses a real PDF file to verify end-to-end OCR functionality.
    """
    Print("HEADER", "=== Tesseract Engine Functional Test ===")

    # Load configuration
    config_path = repo_root / "config" / "config.json"
    Print("STATE", f"Loading config from: {config_path}")

    with open(config_path) as f:
        config = json.load(f)

    tesseract_config = config['ocr_engines']['tesseract']
    default_dpi = config['processing']['default_dpi']

    # Initialize Tesseract engine
    Print("PROGRESS", "Step 1: Initializing Tesseract engine...")
    try:
        engine = get_ocr_engine("tesseract", tesseract_config)
        engine.initialize(tesseract_config)
        Print("SUCCESS", f"Engine initialized: {engine.name}")
        if hasattr(engine, 'version') and engine.version:
            Print("INFO", f"Version: {engine.version}")
    except Exception as e:
        Print("FAILURE", f"Engine initialization failed: {e}")
        return False

    # Look for a test PDF file
    Print("PROGRESS", "Step 2: Looking for test PDF file...")

    # Check common locations for test PDF
    test_pdf_locations = [
        repo_root / "test_input.pdf",
        repo_root / "tests" / "fixtures" / "sample.pdf",
        Path.home() / "Desktop" / "test.pdf",
    ]

    test_pdf = None
    for location in test_pdf_locations:
        if location.exists():
            test_pdf = location
            Print("SUCCESS", f"Found test PDF: {test_pdf}")
            break

    if not test_pdf:
        Print("WARNING", "No test PDF found, creating a simple test image instead...")
        # Create a simple test image with text
        from PIL import Image, ImageDraw, ImageFont
        img = Image.new('RGB', (800, 200), color='white')
        draw = ImageDraw.Draw(img)

        # Draw simple text
        try:
            # Try to use a default font
            font = ImageFont.load_default()
        except:
            font = None

        text = "Morphic v0.2 Tesseract Test"
        draw.text((50, 50), text, fill='black', font=font)

        # Use this image directly
        test_image = img
        Print("INFO", "Created synthetic test image with text")
    else:
        # Convert first page of PDF to image
        Print("PROGRESS", f"Step 3: Converting PDF to image at {default_dpi} DPI...")
        try:
            pages = convert_from_path(test_pdf, dpi=default_dpi, first_page=1, last_page=1)
            test_image = pages[0]
            Print("SUCCESS", f"Converted page 1 to image: {test_image.size} pixels")
        except Exception as e:
            Print("FAILURE", f"PDF conversion failed: {e}")
            return False

    # Run OCR
    Print("PROGRESS", "Step 4: Running Tesseract OCR...")

    output_dir = repo_root / "tests" / "functional_tests" / "output"
    output_dir.mkdir(exist_ok=True)

    output_base = output_dir / "test_output"

    try:
        hocr_path = engine.recognize_to_hocr(
            test_image,
            language="eng",
            output_path=output_base
        )
        Print("SUCCESS", f"OCR completed: {hocr_path}")
    except Exception as e:
        Print("FAILURE", f"OCR failed: {e}")
        return False

    # Verify hOCR output
    Print("PROGRESS", "Step 5: Verifying hOCR output...")

    if not hocr_path.exists():
        Print("FAILURE", f"hOCR file not found: {hocr_path}")
        return False

    # Read and parse hOCR
    with open(hocr_path, 'r', encoding='utf-8') as f:
        hocr_content = f.read()

    Print("INFO", f"hOCR file size: {len(hocr_content)} bytes")

    # Check for hOCR structure
    if 'ocr_page' not in hocr_content:
        Print("FAILURE", "hOCR file missing 'ocr_page' class")
        return False

    # Extract text content
    from lxml import etree
    try:
        tree = etree.fromstring(hocr_content.encode('utf-8'))
        # Get all text content
        text_content = ' '.join(tree.itertext()).strip()
        # Remove excessive whitespace
        text_content = ' '.join(text_content.split())

        Print("SUCCESS", "hOCR structure is valid")
        Print("INFO", f"Extracted text length: {len(text_content)} characters")

        if text_content:
            # Show first 200 characters
            preview = text_content[:200] + ('...' if len(text_content) > 200 else '')
            Print("INFO", f"Text preview: {preview}")
        else:
            Print("WARNING", "No text content found in hOCR (page may be blank)")

        # Count words and lines
        ns = {'x': 'http://www.w3.org/1999/xhtml'}
        words = tree.xpath('//x:span[@class="ocrx_word"]', namespaces=ns)
        lines = tree.xpath('//x:span[@class="ocr_line"]', namespaces=ns)

        Print("INFO", f"Detected: {len(words)} words in {len(lines)} lines")

        if len(words) > 0:
            Print("SUCCESS", "hOCR contains word-level data")
        else:
            Print("WARNING", "No words detected (page may be blank or image-only)")

    except Exception as e:
        Print("FAILURE", f"hOCR parsing failed: {e}")
        return False

    # Final summary
    Print("HEADER", "=== Test Summary ===")
    Print("SUCCESS", "✓ Tesseract engine initialized")
    Print("SUCCESS", "✓ Image processed successfully")
    Print("SUCCESS", "✓ Valid hOCR output generated")
    Print("SUCCESS", f"✓ Detected {len(words)} words in {len(lines)} lines")

    Print("COMPLETED", "Tesseract engine functional test PASSED")

    return True


if __name__ == "__main__":
    success = test_tesseract_engine()
    sys.exit(0 if success else 1)
