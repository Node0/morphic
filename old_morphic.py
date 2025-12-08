#!/usr/bin/env python3.11

import argparse
import sys
import time
import io
import re
from pathlib import Path
from typing import List, Tuple, Generator
from natsort import natsorted
from pdf2image import convert_from_path
import fitz  # PyMuPDF
from PIL import Image
import numpy as np
import easyocr
from utilities import Print, CPU_and_Mem_usage

# Try to import enchant for dehyphenation, fallback gracefully if not available
try:
    import enchant
    ENCHANT_AVAILABLE = True
except ImportError:
    ENCHANT_AVAILABLE = False

def get_image_files(folder: Path) -> List[Path]:
    """Return naturally sorted list of image files."""
    exts = ('.png', '.jpg', '.jpeg', '.webp', '.tiff', '.bmp', '.jp2', '.jpx')
    files = [f for f in folder.iterdir() if f.suffix.lower() in exts]
    return natsorted(files)

def detect_image_dpi(img: Image.Image, filename: str, default_dpi: int, debug: bool) -> int:
    """
    Attempt to detect DPI from image EXIF metadata.
    Returns detected DPI or default_dpi if not found.
    """
    try:
        # Try to get DPI from EXIF
        if hasattr(img, 'info') and 'dpi' in img.info:
            dpi_tuple = img.info['dpi']
            # DPI can be a tuple (x_dpi, y_dpi)
            detected_dpi = int(dpi_tuple[0]) if isinstance(dpi_tuple, tuple) else int(dpi_tuple)
            if debug:
                Print("DEBUG", f"{filename}: Detected DPI from EXIF: {detected_dpi}")
            return detected_dpi
    except Exception as e:
        if debug:
            Print("DEBUG", f"{filename}: Failed to read DPI from EXIF: {e}")
    
    # No DPI found, use default
    if debug:
        Print("DEBUG", f"{filename}: No DPI in metadata, using default: {default_dpi}")
    return default_dpi

def dehyphenate_lines(results: List[Tuple], debug: bool = False) -> List[Tuple]:
    """
    Merge words split by end-of-line hyphens.
    
    Detects patterns like:
        Line N:   "accom-"
        Line N+1: "modates"
    
    And merges them to:
        Line N:   "accommodates"
        Line N+1: (first word removed)
    
    Args:
        results: List of (bbox, text, conf) tuples from EasyOCR
        debug: Enable debug logging
    
    Returns:
        Modified list with dehyphenated words
    """
    if not ENCHANT_AVAILABLE:
        if debug:
            Print("DEBUG", "enchant library not available, skipping dehyphenation")
        return results
    
    if not results:
        return results
    
    try:
        # Initialize English dictionary
        dict_checker = enchant.Dict("en_US")
    except Exception as e:
        if debug:
            Print("WARNING", f"Failed to initialize enchant dictionary: {e}")
        return results
    
    modified_results = []
    skip_next = False
    dehyphen_count = 0
    
    for i in range(len(results)):
        if skip_next:
            skip_next = False
            continue
            
        bbox, text, conf = results[i]
        
        # Check if this line ends with a hyphen and there's a next line
        if text.rstrip().endswith('-') and i < len(results) - 1:
            # Get the next line
            next_bbox, next_text, next_conf = results[i + 1]
            
            # Extract the word before hyphen
            text_without_hyphen = text.rstrip()[:-1]  # Remove trailing hyphen
            last_word_match = re.search(r'(\S+)$', text_without_hyphen)
            
            if last_word_match:
                word_before_hyphen = last_word_match.group(1)
                
                # Extract first word of next line
                first_word_match = re.search(r'^(\S+)', next_text.lstrip())
                
                if first_word_match:
                    word_after_hyphen = first_word_match.group(1)
                    
                    # Try to merge the words
                    merged_word = word_before_hyphen + word_after_hyphen
                    
                    # Check if merged word is valid
                    is_valid_merged = dict_checker.check(merged_word)
                    
                    # Also check if the hyphenated form is a legitimate compound word
                    hyphenated_form = word_before_hyphen + '-' + word_after_hyphen
                    is_legitimate_compound = dict_checker.check(hyphenated_form)
                    
                    if is_valid_merged and not is_legitimate_compound:
                        # This is a line-break hyphenation, merge it!
                        
                        # Reconstruct the current line text with merged word
                        prefix = text_without_hyphen[:last_word_match.start()]
                        new_current_text = prefix + merged_word
                        
                        # Reconstruct next line with first word removed
                        remaining_next_text = next_text[first_word_match.end():].lstrip()
                        
                        if debug:
                            Print("DEBUG", f"Dehyphenated: '{word_before_hyphen}-' + '{word_after_hyphen}' → '{merged_word}'")
                        
                        # Add modified current line
                        modified_results.append((bbox, new_current_text, conf))
                        
                        # Add modified next line (if it's not empty after removal)
                        if remaining_next_text.strip():
                            modified_results.append((next_bbox, remaining_next_text, next_conf))
                        
                        skip_next = True
                        dehyphen_count += 1
                        continue
        
        # No dehyphenation needed, keep original
        modified_results.append((bbox, text, conf))
    
    if debug and dehyphen_count > 0:
        Print("INFO", f"Dehyphenated {dehyphen_count} word(s) on this page")
    
    return modified_results

def load_images_from_folder(folder: Path, source_dpi: int, queue_depth: int, debug: bool) -> Generator[List[Tuple[str, Image.Image, int]], None, None]:
    """
    Load images in batches for memory control.
    Auto-detects DPI from EXIF when available.
    Returns tuples of (filename, image, detected_dpi).
    """
    image_files = get_image_files(folder)
    total_pages = len(image_files)
    Print("INFO", f"Found {total_pages} images in folder")
    
    batch = []
    for i, f in enumerate(image_files, 1):
        Print("PROGRESS", f"Loading image {i} of {total_pages}: {f.name}")
        try:
            img = Image.open(f)
            # Convert to RGB if needed
            if img.mode in ('RGBA', 'LA', 'P'):
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                background.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
                img = background
            
            # Detect DPI from EXIF
            detected_dpi = detect_image_dpi(img, f.name, source_dpi, debug)
            batch.append((f.name, img, detected_dpi))
        except Exception as e:
            Print("WARNING", f"Failed to load {f.name}: {e}")
            continue
            
        if len(batch) >= queue_depth:
            yield batch
            batch = []
    
    if batch:
        yield batch

def load_images_from_pdf(pdf_path: Path, source_dpi: int, queue_depth: int, debug: bool) -> Generator[List[Tuple[str, Image.Image, int]], None, None]:
    """
    Load PDF pages as images in batches at source DPI.
    Converts pages in chunks to avoid loading entire PDF into memory.
    Returns tuples of (filename, image, dpi) where dpi is source_dpi for all pages.
    """
    try:
        from pdf2image import pdfinfo_from_path
        info = pdfinfo_from_path(str(pdf_path))
        total_pages = info["Pages"]
        Print("INFO", f"PDF has {total_pages} pages")
    except:
        total_pages = None
        Print("WARNING", "Could not determine page count, processing all pages")
    
    # Convert pages in chunks instead of all at once
    Print("STATE", f"Rasterizing PDF in batches of {queue_depth} pages at {source_dpi} DPI")
    
    page_num = 1
    while True:
        # Calculate chunk range
        first_page = page_num
        last_page = page_num + queue_depth - 1
        
        if total_pages and first_page > total_pages:
            break
        
        Print("PROGRESS", f"Converting PDF pages {first_page}-{min(last_page, total_pages or last_page)} to images")
        
        try:
            # Convert only this chunk of pages
            images = convert_from_path(
                str(pdf_path), 
                dpi=source_dpi,
                first_page=first_page,
                last_page=last_page
            )
        except Exception as e:
            if "Unable to get page" in str(e) or page_num > (total_pages or 9999):
                # Reached end of PDF
                break
            else:
                Print("WARNING", f"Failed to convert pages {first_page}-{last_page}: {e}")
                break
        
        if not images:
            break
        
        batch = []
        for idx, img in enumerate(images):
            current_page = first_page + idx
            if debug:
                Print("DEBUG", f"Loaded page {current_page}")
            # For PDFs, all pages have the same DPI (the rendering DPI)
            batch.append((f"page_{current_page}", img, source_dpi))
        
        if batch:
            yield batch
            page_num += len(batch)
        else:
            break

def get_image_format_pil_name(format_str: str) -> str:
    """Convert CLI format string to PIL format name."""
    format_map = {
        'jpeg': 'JPEG',
        'jpg': 'JPEG',
        'png': 'PNG',
        'jp2': 'JPEG2000',
        'jpx': 'JPEG2000'
    }
    return format_map.get(format_str.lower(), 'PNG')

def validate_output_format(format_str: str) -> bool:
    """Check if format is valid for PDF embedding."""
    valid_formats = ['png', 'jpeg', 'jpg', 'jp2', 'jpx']
    if format_str.lower() not in valid_formats:
        Print("FAILURE", f"Invalid output format: {format_str}. Valid options: {', '.join(valid_formats)}")
        return False
    return True

def downsample_image(img: Image.Image, source_dpi: int, target_dpi: int, debug: bool) -> Image.Image:
    """
    Downsample image if target_dpi < source_dpi.
    Returns original image if target_dpi >= source_dpi.
    """
    if target_dpi >= source_dpi:
        if debug:
            Print("DEBUG", f"No downsampling needed: target DPI ({target_dpi}) >= source DPI ({source_dpi})")
        return img
    
    scale_factor = target_dpi / source_dpi
    new_width = int(img.width * scale_factor)
    new_height = int(img.height * scale_factor)
    
    Print("INFO", f"Downsampling from {source_dpi} DPI to {target_dpi} DPI "
                  f"({img.width}x{img.height} → {new_width}x{new_height} pixels)")
    
    # Use LANCZOS for high-quality downsampling
    downsampled = img.resize((new_width, new_height), Image.LANCZOS)
    return downsampled

def ocr_and_render_batch(
    batch: List[Tuple[str, Image.Image, int]],
    reader,
    doc: fitz.Document,
    image_format: str,
    output_dpi: int,
    jpeg2000_ratio: int,
    dehyphenate: bool,
    debug: bool,
    current_page: int,
    total_pages: int
):
    """
    Process a batch of images:
    1. Run OCR on full-resolution images
    2. Apply dehyphenation if enabled
    3. Downsample if output_dpi < detected source DPI
    4. Embed downsampled images in PDF with compression control
    5. Add OCR text overlay with coordinate scaling
    
    Each batch item is (name, image, detected_dpi) where detected_dpi
    may vary per image if auto-detected from EXIF.
    """
    pil_format = get_image_format_pil_name(image_format)
    
    for name, img_full_res, img_source_dpi in batch:
        Print("PROGRESS", f"Processing page {current_page} of {total_pages}: {name}")
        if debug:
            Print("DEBUG", f"Image source DPI: {img_source_dpi}, Output DPI: {output_dpi}")
            Print("DEBUG", CPU_and_Mem_usage())

        # STEP 1: OCR on FULL RESOLUTION image
        Print("STATE", f"Running OCR on full resolution image ({img_full_res.width}x{img_full_res.height} px)")
        start_time = time.time()
        try:
            # Convert PIL Image to numpy array for EasyOCR
            img_array = np.array(img_full_res)
            results = reader.readtext(img_array, detail=1, paragraph=False)
            ocr_time = time.time() - start_time
            Print("INFO", f"OCR took {ocr_time:.2f}s, found {len(results)} text regions")
        except Exception as e:
            Print("WARNING", f"OCR failed for {name}: {e}")
            results = []

        # STEP 1.5: Dehyphenate if enabled
        if dehyphenate and results:
            results = dehyphenate_lines(results, debug)

        # STEP 2: Downsample image if needed (AFTER OCR)
        img_for_pdf = downsample_image(img_full_res, img_source_dpi, output_dpi, debug)
        
        # Calculate page dimensions based on OUTPUT DPI
        w_px, h_px = img_for_pdf.size
        w_pt = (w_px / output_dpi) * 72.0
        h_pt = (h_px / output_dpi) * 72.0

        # Create new page
        page = doc.new_page(width=w_pt, height=h_pt)

        # STEP 3: Encode and embed the (possibly downsampled) image
        img_buffer = io.BytesIO()
        try:
            # Apply compression for JPEG2000
            if pil_format == 'JPEG2000':
                # Pillow JPEG2000 params:
                # - quality_mode='rates' with quality_layers=[ratio] where ratio is compression ratio
                # - irreversible=True for lossy compression (better compression)
                img_for_pdf.save(
                    img_buffer, 
                    format=pil_format,
                    irreversible=True,  # Lossy compression
                    quality_mode='rates',
                    quality_layers=[jpeg2000_ratio]  # Compression ratio
                )
            else:
                img_for_pdf.save(img_buffer, format=pil_format, quality=95)
            
            img_bytes = img_buffer.getvalue()
            if debug:
                Print("DEBUG", f"Encoded image as {pil_format}, size: {len(img_bytes)} bytes (compression ratio: {jpeg2000_ratio}:1)")
        except Exception as e:
            Print("WARNING", f"Failed to save image in {pil_format} format: {e}")
            # Fallback to PNG
            img_buffer = io.BytesIO()
            img_for_pdf.save(img_buffer, format='PNG')
            img_bytes = img_buffer.getvalue()
            Print("WARNING", "Falling back to PNG format")

        # Insert image as native stream
        try:
            page.insert_image(
                fitz.Rect(0, 0, w_pt, h_pt),
                stream=img_bytes
            )
        except Exception as e:
            Print("FAILURE", f"Failed to insert image: {e}")
            current_page += 1
            continue

        # STEP 4: Add OCR text overlay
        # Important: OCR bbox coordinates are from FULL RES image at img_source_dpi
        # Need to scale to output_dpi
        scale_factor = output_dpi / img_source_dpi
        
        for (bbox, text, conf) in results:
            if debug:
                Print("DEBUG", f"OCR Text: '{text}' (conf: {conf:.3f})")
            try:
                (x1, y1), (x2, y2), *_ = bbox
                
                # Scale coordinates from source DPI to output DPI
                x1_scaled = x1 * scale_factor
                y1_scaled = y1 * scale_factor
                x2_scaled = x2 * scale_factor
                y2_scaled = y2 * scale_factor
                
                # Convert pixel coordinates to points
                x_pt = (x1_scaled / output_dpi) * 72.0
                y_pt = h_pt - (y2_scaled / output_dpi) * 72.0  # Flip Y-axis
                
                font_size = max(6, int(((y2_scaled - y1_scaled) / output_dpi) * 72.0 * 0.8))
                
                page.insert_text(
                    fitz.Point(x_pt, y_pt),
                    text,
                    fontsize=font_size,
                    color=(1, 1, 1),  # White text (invisible on white background)
                    overlay=True
                )
            except Exception as e:
                if debug:
                    Print("DEBUG", f"Failed to render text '{text[:40]}': {e}")
                continue
                
        current_page += 1
    
    return current_page

def count_total_pages(args) -> int:
    """Count total pages for progress tracking."""
    if args.input_pdf_file:
        try:
            from pdf2image import pdfinfo_from_path
            info = pdfinfo_from_path(str(args.input_pdf_file))
            return info["Pages"]
        except:
            return 0
    else:
        return len(get_image_files(args.input_image_folder))

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Morphic - OCR PDF/image tool with intelligent post-processing",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic: PDF to searchable PDF at same resolution
  %(prog)s --input-pdf-file book.pdf --output-pdf-file searchable.pdf
  
  # With downsampling: OCR at 600 DPI, output at 300 DPI
  %(prog)s --input-pdf-file scan.pdf --source-dpi 600 --output-pdf-dpi 300 --output-pdf-file out.pdf
  
  # High compression for web distribution
  %(prog)s --input-pdf-file book.pdf --output-pdf-file web.pdf --jpeg2000-compression-ratio 40
  
  # Process folder of images
  %(prog)s --input-image-folder pages/ --output-pdf-file book.pdf
        """
    )
    
    parser.add_argument('--input-pdf-file', type=Path, 
                       help="Input PDF file to OCR.")
    parser.add_argument('--input-image-folder', type=Path, 
                       help="Folder of image files (naturally sorted by filename).")
    parser.add_argument('--output-pdf-file', type=Path, required=True,
                       help="Output searchable PDF file.")
    parser.add_argument('--source-dpi', type=int, default=600,
                       help="Source DPI: For PDFs, the rasterization DPI for OCR. "
                            "For images, the default DPI if not found in EXIF metadata (default: 600). "
                            "Images with DPI in metadata will use their embedded DPI automatically.")
    parser.add_argument('--output-pdf-dpi', type=int, default=None,
                       help="Output DPI for embedded images in PDF. "
                            "If less than source-dpi, images are downsampled AFTER OCR. "
                            "If not specified, uses source-dpi (no downsampling).")
    parser.add_argument('--output-pdf-images-format', choices=['png', 'jpeg', 'jpg', 'jp2', 'jpx'], 
                       default='jp2',
                       help="Image format for embedding in PDF (default: jp2 for JPEG2000).")
    parser.add_argument('--jpeg2000-compression-ratio', type=int, default=20,
                       help="JPEG2000 compression ratio (default: 20). "
                            "Lower = better quality but larger file (10-15 for archival). "
                            "Higher = smaller file but lower quality (30-50 for web/email). "
                            "Only applies when using jp2/jpx format.")
    parser.add_argument('--dehyphenate', action='store_true', default=True,
                       help="Merge hyphenated words across line breaks (default: enabled). "
                            "Requires 'enchant' library (pip install pyenchant).")
    parser.add_argument('--no-dehyphenate', action='store_false', dest='dehyphenate',
                       help="Disable dehyphenation of line-break hyphens.")
    parser.add_argument('--page-queue-depth', type=int, default=5, choices=range(1, 11),
                       help="Number of pages to queue in memory at once (1-10, default: 5).")
    parser.add_argument('--debug', action='store_true', 
                       help="Enable verbose debug logging.")

    args = parser.parse_args()

    # Validation
    if bool(args.input_pdf_file) == bool(args.input_image_folder):
        Print("FAILURE", "Exactly one of --input-pdf-file or --input-image-folder must be provided.")
        sys.exit(1)

    # If output_dpi not specified, use source_dpi (no downsampling)
    if args.output_pdf_dpi is None:
        args.output_pdf_dpi = args.source_dpi
        Print("INFO", f"Output DPI not specified, using source DPI: {args.source_dpi}")
    
    # Validate DPI values
    if args.output_pdf_dpi > args.source_dpi:
        Print("WARNING", f"Output DPI ({args.output_pdf_dpi}) > source DPI ({args.source_dpi}). "
                        f"This will not increase quality, only file size. Consider using {args.source_dpi} DPI.")
    
    # Validate output format
    if not validate_output_format(args.output_pdf_images_format):
        sys.exit(1)
    
    # Check dehyphenation availability
    if args.dehyphenate and not ENCHANT_AVAILABLE:
        Print("WARNING", "Dehyphenation requested but 'enchant' library not installed.")
        Print("WARNING", "Install with: pip install pyenchant")
        Print("WARNING", "Continuing without dehyphenation...")
        args.dehyphenate = False

    if args.debug:
        Print("DEBUG", f"Arguments: {args}")
        Print("DEBUG", f"Source DPI: {args.source_dpi}, Output DPI: {args.output_pdf_dpi}")
        if args.output_pdf_dpi < args.source_dpi:
            Print("DEBUG", f"Images will be downsampled by factor: {args.output_pdf_dpi / args.source_dpi:.3f}")
        Print("DEBUG", f"JPEG2000 compression ratio: {args.jpeg2000_compression_ratio}:1")
        Print("DEBUG", f"Dehyphenation: {'enabled' if args.dehyphenate else 'disabled'}")

    return args

def main():
    """Main entry point."""
    args = parse_args()

    # Initialize EasyOCR
    Print("STARTING", "Initializing EasyOCR...")
    try:
        reader = easyocr.Reader(['en'], gpu=True)
        Print("SUCCESS", "EasyOCR initialized with GPU support.")
    except Exception as e:
        Print("WARNING", f"Failed to initialize EasyOCR with GPU: {e}")
        Print("STATE", "Falling back to CPU mode...")
        try:
            reader = easyocr.Reader(['en'], gpu=False)
            Print("SUCCESS", "EasyOCR initialized with CPU.")
        except Exception as e2:
            Print("FAILURE", f"Failed to initialize EasyOCR: {e2}")
            sys.exit(1)

    # Create output PDF document
    try:
        doc = fitz.open()  # New empty PDF
        Print("STATE", f"Output PDF will be saved to: {args.output_pdf_file}")
    except Exception as e:
        Print("FAILURE", f"Failed to create output PDF document: {e}")
        sys.exit(1)

    # Process pages
    source = args.input_pdf_file or args.input_image_folder
    loader = load_images_from_pdf if args.input_pdf_file else load_images_from_folder
    
    total_pages = count_total_pages(args)
    current_page = 1

    Print("STATE", f"Loading from: {source}")
    if args.output_pdf_dpi < args.source_dpi:
        Print("STATE", f"OCR will run at maximum available resolution")
        Print("STATE", f"Output will be downsampled to {args.output_pdf_dpi} DPI")
    else:
        Print("STATE", f"OCR will run at maximum available resolution")
        Print("STATE", f"Output will be at {args.output_pdf_dpi} DPI")
    
    for batch in loader(source, args.source_dpi, args.page_queue_depth, args.debug):
        current_page = ocr_and_render_batch(
            batch,
            reader,
            doc,
            args.output_pdf_images_format,
            args.output_pdf_dpi,
            args.jpeg2000_compression_ratio,
            args.dehyphenate,
            args.debug,
            current_page,
            total_pages if total_pages > 0 else "unknown"
        )

    # Save PDF
    Print("STATE", "Saving output PDF...")
    try:
        doc.save(
            str(args.output_pdf_file),
            garbage=4,  # Clean up unused objects
            deflate=True,  # Compress streams
            clean=True  # Clean page contents
        )
        doc.close()
        Print("COMPLETED", f"Saved OCR PDF to: {args.output_pdf_file}")
    except Exception as e:
        Print("FAILURE", f"Failed to save PDF: {e}")
        sys.exit(1)

if __name__ == "__main__":
    # Show help if no arguments
    if len(sys.argv) == 1:
        print("╔" + "═" * 58 + "╗")
        print("║" + " " * 20 + "MORPHIC" + " " * 31 + "║")
        print("║" + " " * 10 + "PDF OCR with Intelligence" + " " * 23 + "║")
        print("╠" + "═" * 58 + "╣")
        print("║" + " " * 58 + "║")
        print("║  Usage: ./morphic.py [OPTIONS]" + " " * 26 + "║")
        print("║" + " " * 58 + "║")
        print("║  Try: ./morphic.py --help" + " " * 31 + "║")
        print("║" + " " * 58 + "║")
        print("║  Quick example:" + " " * 43 + "║")
        print("║    ./morphic.py \\" + " " * 41 + "║")
        print("║      --input-pdf-file book.pdf \\" + " " * 26 + "║")
        print("║      --output-pdf-file searchable.pdf" + " " * 19 + "║")
        print("║" + " " * 58 + "║")
        print("╚" + "═" * 58 + "╝")
        sys.exit(0)
    
    main()
