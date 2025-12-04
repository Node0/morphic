#!/usr/bin/env python3.11
# end of phase-2 implementation tests for OCR engine integration


from pathlib import Path
from PIL import Image
import sys

# Add repo root to path for imports
repo_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(repo_root))

from engines.ocr import get_ocr_engine

# Setup paths relative to repo root
sample_input_dir = repo_root / "ocr_sample_input_files"
sample_output_dir = repo_root / "ocr_sample_output_files"

# Ensure output directory exists
sample_output_dir.mkdir(parents=True, exist_ok=True)

# Use the 5-page sample PDF
sample_pdf = sample_input_dir / "sample_5_page_source.pdf"

if not sample_pdf.exists():
    print(f"ERROR: Sample input file not found at {sample_pdf}")
    sys.exit(1)

# Initialize the OCR engine
engine = get_ocr_engine("tesseract", {"binary_path": "tesseract"})
engine.initialize({})

# Process the 5-page sample
# Note: This test processes the PDF by converting pages to images first
# In the full pipeline, this will be handled by pdf2image
from pdf2image import convert_from_path

print(f"Processing {sample_pdf.name}...")
pages = convert_from_path(str(sample_pdf), dpi=300)  # Use 300 DPI for faster testing

for page_num, page_img in enumerate(pages, 1):
    print(f"  OCR on page {page_num}/{len(pages)}")
    
    # Save page image for debugging
    page_img_path = sample_output_dir / f"page_{page_num}.png"
    page_img.save(page_img_path)
    
    # Run OCR
    hocr_output_base = sample_output_dir / f"page_{page_num}"
    hocr_path = engine.recognize_to_hocr(page_img, output_path=hocr_output_base)
    
    print(f"  Generated hOCR: {hocr_path}")
    
    # Verify hOCR file exists and has content
    if hocr_path.exists():
        hocr_size = hocr_path.stat().st_size
        print(f"  hOCR file size: {hocr_size} bytes")
        
        # Quick sanity check: does it contain expected hOCR structure?
        with open(hocr_path, 'r', encoding='utf-8') as f:
            content = f.read()
            if 'ocr_page' in content and 'ocrx_word' in content:
                print(f"  ✓ Valid hOCR structure detected")
            else:
                print(f"  ⚠ Warning: hOCR structure may be incomplete")
    else:
        print(f"  ✗ ERROR: hOCR file not created")

print(f"\nTest complete! Output files in: {sample_output_dir}")
print(f"  - Page images: page_*.png")
print(f"  - hOCR files: page_*.hocr")