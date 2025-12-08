#!/usr/bin/env python3.11
"""
Phase 5 Integration Test: Dehyphenation → PDF with Verification

This test PROVES dehyphenation works by:
1. Processing hOCR files with dehyphenation
2. Generating a searchable PDF from dehyphenated hOCR
3. Extracting text from the PDF
4. Verifying dehyphenated words appear in extracted text
5. Verifying hyphenated fragments do NOT appear

Success criteria:
- "retrieving" IN extracted text (was "retriev-" + "ing")
- "psychologist" IN extracted text (was "psycholo-" + "gist")
- "retriev-" NOT IN extracted text
- "psycholo-" NOT IN extracted text

Output:
- ocr_sample_output_files/phase5_dehyphenated_output.pdf

Usage:
    python tests/functional_tests/phase-5_integration_test.py
"""

import sys
import shutil
import subprocess
from pathlib import Path
import tempfile

# Add repo root to path for imports
repo_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(repo_root))

from utilities import Print
from processors.dehyphenation import Dehyphenator
from engines.pdf import get_pdf_engine
from engines.compression import get_compressor


def extract_text_from_pdf(pdf_path: Path) -> str:
    """Extract text from PDF using pdftotext -raw."""
    try:
        result = subprocess.run(
            ["pdftotext", "-raw", str(pdf_path), "-"],
            capture_output=True,
            text=True,
            timeout=60
        )
        if result.returncode == 0:
            return result.stdout
        else:
            Print("WARNING", f"pdftotext failed: {result.stderr}")
            return ""
    except Exception as e:
        Print("WARNING", f"Text extraction failed: {e}")
        return ""


def main():
    Print("HEADER", "Phase 5 Integration Test: Dehyphenation → PDF")
    print("=" * 70)
    print()

    output_dir = repo_root / "ocr_sample_output_files"

    # Verify prerequisites
    hocr_files = sorted(output_dir.glob("page_*.hocr"))
    png_files = sorted(output_dir.glob("page_*.png"))

    if not hocr_files or not png_files:
        Print("FAILURE", "Missing input files. Run phase-2 test first.")
        sys.exit(1)

    Print("INFO", f"Found {len(hocr_files)} hOCR files and {len(png_files)} PNG files")

    # ==========================================================================
    # STEP 1: Create working copies and apply dehyphenation
    # ==========================================================================
    Print("HEADER", "Step 1: Apply Dehyphenation to hOCR Files")

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Copy hOCR and PNG files to temp directory
        for hocr_file in hocr_files:
            shutil.copy(hocr_file, temp_path / hocr_file.name)
        for png_file in png_files:
            shutil.copy(png_file, temp_path / png_file.name)

        Print("INFO", f"Copied files to working directory")

        # Initialize dehyphenator
        dehyp_config = {
            'enabled': True,
            'dictionary': 'en_US',
            'min_word_length': 4
        }
        dehyphenator = Dehyphenator(dehyp_config)

        # Track what we dehyphenated for verification
        expected_merged_words = []
        expected_removed_fragments = []
        total_merged = 0

        # Process each hOCR file
        for hocr_file in sorted(temp_path.glob("page_*.hocr")):
            merged = dehyphenator.process_file(hocr_file)
            total_merged += merged

        Print("SUCCESS", f"Dehyphenation complete: {total_merged} word pairs merged")

        # Known merges from our test data (based on previous test run)
        expected_merged_words = [
            "retrieving",      # from retriev- + ing
            "psychologist",    # from psycholo- + gist
            "intermediate",    # from intermedi- + ate
            "reporting",       # from report- + ing
            "neuroscience",    # from neurosci- + ence
        ]

        expected_removed_fragments = [
            "retriev-",
            "psycholo-",
            "intermedi-",
            "neurosci-",
        ]

        # ==================================================================
        # STEP 2: Generate PDF from dehyphenated hOCR
        # ==================================================================
        Print("HEADER", "Step 2: Generate Searchable PDF")

        # Initialize PDF engine and compressor
        pdf_config = {"rendering_mode": 3, "font_size_ratio": 0.75}
        pdf_engine = get_pdf_engine("pikepdf", pdf_config)

        comp_config = {"quality_layers": [50], "quality_mode": "rates", "irreversible": True}
        compressor = get_compressor("jpeg2000", comp_config)

        dpi = 300  # Matches Phase 2 test

        # Process all pages
        page_pdfs = []
        page_num = 1

        while True:
            png_file = temp_path / f"page_{page_num}.png"
            hocr_file = temp_path / f"page_{page_num}.hocr"

            if not png_file.exists() or not hocr_file.exists():
                break

            Print("PROGRESS", f"Creating PDF page {page_num}...")

            page_pdf = pdf_engine.create_searchable_page(
                image_path=png_file,
                hocr_path=hocr_file,
                dpi=dpi,
                compressor=compressor
            )
            page_pdfs.append(page_pdf)
            page_num += 1

        # Merge pages
        Print("PROGRESS", f"Merging {len(page_pdfs)} pages...")
        final_pdf = pdf_engine.merge_pages(page_pdfs)

        # Save to output directory
        output_pdf = output_dir / "phase5_dehyphenated_output.pdf"
        final_pdf.save(str(output_pdf))

        file_size = output_pdf.stat().st_size
        Print("SUCCESS", f"Created PDF: {output_pdf.name} ({file_size:,} bytes)")

        # ==================================================================
        # STEP 3: Extract text and verify dehyphenation
        # ==================================================================
        Print("HEADER", "Step 3: Verify Dehyphenation in PDF Text")

        extracted_text = extract_text_from_pdf(output_pdf)

        if not extracted_text:
            Print("FAILURE", "Could not extract text from PDF")
            sys.exit(1)

        Print("INFO", f"Extracted {len(extracted_text):,} characters from PDF")

        # Normalize for comparison
        extracted_lower = extracted_text.lower()

        # ==================================================================
        # VERIFICATION: Check merged words ARE present
        # ==================================================================
        Print("HEADER", "Verification: Merged Words Present")

        merged_found = []
        merged_missing = []

        for word in expected_merged_words:
            if word.lower() in extracted_lower:
                merged_found.append(word)
                Print("SUCCESS", f"✓ Found merged word: '{word}'")
            else:
                merged_missing.append(word)
                Print("FAILURE", f"✗ Missing merged word: '{word}'")

        # ==================================================================
        # VERIFICATION: Check hyphenated fragments are NOT present
        # ==================================================================
        Print("HEADER", "Verification: Hyphenated Fragments Removed")

        fragments_found = []
        fragments_removed = []

        for fragment in expected_removed_fragments:
            if fragment.lower() in extracted_lower:
                fragments_found.append(fragment)
                Print("FAILURE", f"✗ Fragment still present: '{fragment}'")
            else:
                fragments_removed.append(fragment)
                Print("SUCCESS", f"✓ Fragment removed: '{fragment}'")

        # ==================================================================
        # FINAL SUMMARY
        # ==================================================================
        print()
        print("=" * 70)
        Print("HEADER", "Phase 5 Integration Test Summary")
        print()

        print(f"  Output PDF: {output_pdf}")
        print(f"  File size: {file_size:,} bytes")
        print(f"  Pages: {len(page_pdfs)}")
        print(f"  Words dehyphenated: {total_merged}")
        print()

        print("  MERGED WORDS VERIFICATION:")
        print(f"    ✓ Found: {len(merged_found)}/{len(expected_merged_words)}")
        for word in merged_found:
            print(f"      - {word}")
        if merged_missing:
            print(f"    ✗ Missing: {len(merged_missing)}")
            for word in merged_missing:
                print(f"      - {word}")
        print()

        print("  FRAGMENT REMOVAL VERIFICATION:")
        print(f"    ✓ Removed: {len(fragments_removed)}/{len(expected_removed_fragments)}")
        for frag in fragments_removed:
            print(f"      - {frag}")
        if fragments_found:
            print(f"    ✗ Still present: {len(fragments_found)}")
            for frag in fragments_found:
                print(f"      - {frag}")
        print()

        # Determine pass/fail
        all_merged_found = len(merged_missing) == 0
        all_fragments_removed = len(fragments_found) == 0

        if all_merged_found and all_fragments_removed:
            Print("COMPLETED", "ALL VERIFICATIONS PASSED")
            print()
            print("  The PDF proves dehyphenation is working:")
            print(f"    • Merged words searchable in PDF: {merged_found}")
            print(f"    • Hyphenated fragments removed: {fragments_removed}")
            print()
            print(f"  To verify manually:")
            print(f"    1. Open: {output_pdf}")
            print(f"    2. Search (Cmd+F) for 'retrieving' - should find it")
            print(f"    3. Search for 'retriev-' - should NOT find it")
            print()
            sys.exit(0)
        else:
            Print("FAILURE", "VERIFICATION FAILED")
            if merged_missing:
                print(f"  Missing merged words: {merged_missing}")
            if fragments_found:
                print(f"  Fragments not removed: {fragments_found}")
            sys.exit(1)


if __name__ == "__main__":
    main()
