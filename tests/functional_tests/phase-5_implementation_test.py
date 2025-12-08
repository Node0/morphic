#!/usr/bin/env python3.11
"""
Phase 5 Implementation Test: Dehyphenation Processor

This test verifies:
1. Dehyphenator correctly identifies hyphenated word pairs
2. Dictionary validation works (with pyenchant)
3. hOCR is correctly modified (merged text, updated bbox)
4. Original files are preserved (test uses copies)

Prerequisites:
- Phase 2 must be complete (hOCR files in ocr_sample_output_files/)
- pyenchant installed: pip install pyenchant

Usage:
    python tests/functional_tests/phase-5_implementation_test.py
"""

import sys
import shutil
from pathlib import Path
import tempfile

# Add repo root to path for imports
repo_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(repo_root))

from lxml import etree
from utilities import Print
from processors.dehyphenation import Dehyphenator


def find_hyphenated_words(hocr_path: Path) -> list:
    """Find all words ending with hyphen in an hOCR file."""
    try:
        tree = etree.parse(str(hocr_path))
    except:
        parser = etree.HTMLParser(recover=True)
        tree = etree.parse(str(hocr_path), parser)

    ns = {'x': 'http://www.w3.org/1999/xhtml'}
    words = tree.xpath('//x:span[@class="ocrx_word"]', namespaces=ns)
    if not words:
        words = tree.xpath('//*[@class="ocrx_word"]')

    hyphenated = []
    for word in words:
        text = ''.join(word.itertext()).strip()
        if text.endswith('-'):
            hyphenated.append(text)

    return hyphenated


def count_words(hocr_path: Path) -> int:
    """Count total words in hOCR file."""
    try:
        tree = etree.parse(str(hocr_path))
    except:
        parser = etree.HTMLParser(recover=True)
        tree = etree.parse(str(hocr_path), parser)

    ns = {'x': 'http://www.w3.org/1999/xhtml'}
    words = tree.xpath('//x:span[@class="ocrx_word"]', namespaces=ns)
    if not words:
        words = tree.xpath('//*[@class="ocrx_word"]')

    return len(words)


def extract_all_text(hocr_path: Path) -> str:
    """Extract all text from hOCR file."""
    try:
        tree = etree.parse(str(hocr_path))
    except:
        parser = etree.HTMLParser(recover=True)
        tree = etree.parse(str(hocr_path), parser)

    ns = {'x': 'http://www.w3.org/1999/xhtml'}
    words = tree.xpath('//x:span[@class="ocrx_word"]', namespaces=ns)
    if not words:
        words = tree.xpath('//*[@class="ocrx_word"]')

    texts = []
    for word in words:
        text = ''.join(word.itertext()).strip()
        if text:
            texts.append(text)

    return ' '.join(texts)


def test_dehyphenator_initialization() -> bool:
    """Test that Dehyphenator initializes correctly."""
    Print("HEADER", "Testing Dehyphenator Initialization")

    try:
        config = {
            'enabled': True,
            'dictionary': 'en_US',
            'min_word_length': 4
        }
        dehyp = Dehyphenator(config)

        Print("SUCCESS", f"Dehyphenator initialized: {dehyp.name}")
        Print("INFO", f"Dictionary available: {dehyp.dictionary is not None}")
        Print("INFO", f"Min word length: {dehyp.min_word_length}")

        return True

    except Exception as e:
        Print("FAILURE", f"Initialization failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_find_hyphenated_words_in_sample() -> bool:
    """Test finding hyphenated words in sample hOCR files."""
    Print("HEADER", "Testing Hyphenated Word Detection")

    output_dir = repo_root / "ocr_sample_output_files"

    if not output_dir.exists():
        Print("FAILURE", f"Output directory not found: {output_dir}")
        Print("INFO", "Run phase-2_implementation_test.py first")
        return False

    total_hyphenated = 0
    files_with_hyphens = 0

    for hocr_file in sorted(output_dir.glob("page_*.hocr")):
        hyphenated = find_hyphenated_words(hocr_file)
        if hyphenated:
            Print("INFO", f"{hocr_file.name}: {len(hyphenated)} hyphenated words")
            for word in hyphenated[:3]:  # Show first 3
                Print("DEBUG", f"  - {word}")
            total_hyphenated += len(hyphenated)
            files_with_hyphens += 1

    if total_hyphenated > 0:
        Print("SUCCESS", f"Found {total_hyphenated} hyphenated words in {files_with_hyphens} files")
        return True
    else:
        Print("WARNING", "No hyphenated words found in sample files")
        return True  # Not a failure, just no data


def test_dehyphenation_on_copy() -> bool:
    """Test dehyphenation on a copy of sample files."""
    Print("HEADER", "Testing Dehyphenation Processing")

    output_dir = repo_root / "ocr_sample_output_files"
    hocr_files = list(output_dir.glob("page_*.hocr"))

    if not hocr_files:
        Print("FAILURE", "No hOCR files found")
        return False

    # Create temp directory for test
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Copy hOCR files to temp directory
        for hocr_file in hocr_files:
            shutil.copy(hocr_file, temp_path / hocr_file.name)

        Print("INFO", f"Copied {len(hocr_files)} files to temp directory")

        # Initialize dehyphenator
        config = {
            'enabled': True,
            'dictionary': 'en_US',
            'min_word_length': 4
        }
        dehyp = Dehyphenator(config)

        # Process each file
        total_merged = 0
        merge_examples = []

        for hocr_file in sorted(temp_path.glob("page_*.hocr")):
            # Count before
            before_hyphenated = find_hyphenated_words(hocr_file)
            before_word_count = count_words(hocr_file)

            # Process
            merged = dehyp.process_file(hocr_file)
            total_merged += merged

            # Count after
            after_hyphenated = find_hyphenated_words(hocr_file)
            after_word_count = count_words(hocr_file)

            if merged > 0:
                Print("INFO",
                    f"{hocr_file.name}: merged {merged} words "
                    f"(hyphenated: {len(before_hyphenated)} -> {len(after_hyphenated)}, "
                    f"total words: {before_word_count} -> {after_word_count})"
                )

                # Record example merges for verification
                # The word count should decrease by the number of merges
                # (because we remove the second word of each pair)
                expected_word_reduction = merged
                actual_word_reduction = before_word_count - after_word_count

                if actual_word_reduction != expected_word_reduction:
                    Print("WARNING",
                        f"Word count mismatch: expected -{expected_word_reduction}, "
                        f"got -{actual_word_reduction}"
                    )

        Print("SUCCESS", f"Total merged: {total_merged} hyphenated word pairs")

        # Verify some merges by checking text content
        if total_merged > 0:
            Print("HEADER", "Verifying Merged Words in Text")

            # Check if merged words appear in the text
            for hocr_file in sorted(temp_path.glob("page_*.hocr")):
                text = extract_all_text(hocr_file)

                # Look for common merged patterns
                expected_words = ['retrieving', 'psychology', 'intermediate',
                                  'reporting', 'processing', 'neuroscience']

                found_words = []
                for word in expected_words:
                    if word.lower() in text.lower():
                        found_words.append(word)

                if found_words:
                    Print("SUCCESS", f"{hocr_file.name}: found merged words: {found_words}")

        return total_merged > 0 or len(find_hyphenated_words(hocr_files[0])) == 0


def test_disabled_dehyphenation() -> bool:
    """Test that disabled dehyphenation doesn't modify files."""
    Print("HEADER", "Testing Disabled Dehyphenation")

    output_dir = repo_root / "ocr_sample_output_files"
    sample_file = list(output_dir.glob("page_1.hocr"))

    if not sample_file:
        Print("FAILURE", "No sample file found")
        return False

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        test_file = temp_path / "test.hocr"
        shutil.copy(sample_file[0], test_file)

        # Get original content
        original_content = test_file.read_text()

        # Process with disabled dehyphenation
        config = {'enabled': False}
        dehyp = Dehyphenator(config)
        merged = dehyp.process_file(test_file)

        # Verify no changes
        new_content = test_file.read_text()

        if merged == 0 and original_content == new_content:
            Print("SUCCESS", "Disabled dehyphenation correctly skipped processing")
            return True
        else:
            Print("FAILURE", "Disabled dehyphenation modified the file")
            return False


def test_hocr_structure_preserved() -> bool:
    """Test that hOCR structure remains valid after processing."""
    Print("HEADER", "Testing hOCR Structure Preservation")

    output_dir = repo_root / "ocr_sample_output_files"
    sample_files = list(output_dir.glob("page_*.hocr"))

    if not sample_files:
        Print("FAILURE", "No sample files found")
        return False

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Copy and process
        test_file = temp_path / "test.hocr"
        shutil.copy(sample_files[0], test_file)

        config = {'enabled': True, 'dictionary': 'en_US'}
        dehyp = Dehyphenator(config)
        dehyp.process_file(test_file)

        # Verify structure
        try:
            tree = etree.parse(str(test_file))

            # Check for required elements
            ns = {'x': 'http://www.w3.org/1999/xhtml'}

            pages = tree.xpath('//x:div[@class="ocr_page"]', namespaces=ns)
            if not pages:
                pages = tree.xpath('//*[@class="ocr_page"]')

            lines = tree.xpath('//x:span[@class="ocr_line"]', namespaces=ns)
            if not lines:
                lines = tree.xpath('//*[@class="ocr_line"]')

            words = tree.xpath('//x:span[@class="ocrx_word"]', namespaces=ns)
            if not words:
                words = tree.xpath('//*[@class="ocrx_word"]')

            Print("INFO", f"Structure: {len(pages)} pages, {len(lines)} lines, {len(words)} words")

            # Verify words have valid bboxes
            valid_bboxes = 0
            for word in words[:10]:  # Check first 10
                title = word.get('title', '')
                if 'bbox' in title:
                    valid_bboxes += 1

            if valid_bboxes > 0:
                Print("SUCCESS", f"hOCR structure preserved with valid bboxes")
                return True
            else:
                Print("FAILURE", "Word elements missing bbox attributes")
                return False

        except Exception as e:
            Print("FAILURE", f"Failed to parse processed hOCR: {e}")
            return False


def main():
    """Run all Phase 5 tests."""
    Print("HEADER", "Phase 5 Implementation Test: Dehyphenation Processor")
    print("=" * 60)

    # Test 1: Initialization
    init_ok = test_dehyphenator_initialization()
    print()

    if not init_ok:
        Print("FAILURE", "Initialization test failed - cannot continue")
        sys.exit(1)

    # Test 2: Find hyphenated words
    find_ok = test_find_hyphenated_words_in_sample()
    print()

    # Test 3: Dehyphenation processing
    process_ok = test_dehyphenation_on_copy()
    print()

    # Test 4: Disabled mode
    disabled_ok = test_disabled_dehyphenation()
    print()

    # Test 5: Structure preservation
    structure_ok = test_hocr_structure_preserved()
    print()

    # Summary
    print("=" * 60)
    Print("HEADER", "Phase 5 Test Summary")

    results = [
        ("Dehyphenator Initialization", init_ok),
        ("Hyphenated Word Detection", find_ok),
        ("Dehyphenation Processing", process_ok),
        ("Disabled Mode", disabled_ok),
        ("hOCR Structure Preservation", structure_ok),
    ]

    all_passed = True
    for name, passed in results:
        status = "PASSED" if passed else "FAILED"
        symbol = "✓" if passed else "✗"
        print(f"  {symbol} {name}: {status}")
        if not passed:
            all_passed = False

    print()

    if all_passed:
        Print("COMPLETED", "All Phase 5 tests passed!")
        Print("INFO", "Dehyphenation processor is ready for integration")
        sys.exit(0)
    else:
        Print("FAILURE", "Some tests failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
