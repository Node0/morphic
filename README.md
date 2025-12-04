# 🔮 Morphic

### Version 0.1

**Intelligent OCR with Post-Processing Downsampling**

Transform scanned documents into searchable PDFs while maintaining maximum OCR accuracy and flexible output resolutions.

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## ✨ What Makes Morphic Different?

Traditional OCR tools force you to choose between accuracy and file size. Morphic gives you both.

### The Problem
```
❌ OCR at 300 DPI → Poor accuracy, small files
❌ OCR at 600 DPI → Great accuracy, huge files
```

### The Morphic Solution
```
✅ OCR at 600 DPI → Downsample to 300 DPI → Great accuracy, small files
```

**OCR always runs on the highest resolution images for maximum accuracy. Downsampling happens AFTER OCR is complete, preserving text recognition quality while reducing file size.**

---

## 🎯 Key Features

- **🧠 Smart DPI Handling**: Auto-detects DPI from image EXIF metadata
- **📉 Post-OCR Downsampling**: OCR on full resolution, output at any target DPI
- **🗜️ JPEG2000 Support**: Native JP2/JPX embedding via PyMuPDF for superior compression
- **📁 Flexible Input**: Process PDFs or folders of images
- **🔤 Natural Sorting**: Images sorted correctly (page-2 before page-10)
- **💾 Memory Efficient**: Configurable batch processing
- **📊 Rich Logging**: Detailed progress with CPU/memory monitoring

---

## 🚀 Quick Start

### Installation

#### Option 1: Traditional pip

```bash
# Clone the repository
git clone https://github.com/yourusername/morphic.git
cd morphic

# Install dependencies
pip install -r requirements.txt

# Install poppler for PDF processing
# macOS:
brew install poppler

# Ubuntu/Debian:
sudo apt-get install poppler-utils
```

#### Option 2: UV (10-100× Faster!) ⚡

[UV](https://github.com/astral-sh/uv) is a fast Python package installer written in Rust.

```bash
# Install UV
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone repository
git clone https://github.com/yourusername/morphic.git
cd morphic

# Install dependencies (much faster!)
uv pip install -r requirements.txt

# Install poppler (same as above)
brew install poppler  # macOS
# or
sudo apt-get install poppler-utils  # Linux
```

See [UV_INSTALL.md](UV_INSTALL.md) for detailed UV setup and advanced features.

### Basic Usage

```bash
# Show quick help (no installation needed)
python morphic.py

# Show full help
python morphic.py --help

# Maximum quality (no downsampling)
python morphic.py \
  --input-pdf-file scan.pdf \
  --output-pdf-file output.pdf \
  --source-dpi 600 \
  --output-pdf-dpi 600

# Web-optimized (OCR at 600, output at 300)
python morphic.py \
  --input-pdf-file scan.pdf \
  --output-pdf-file web.pdf \
  --source-dpi 600 \
  --output-pdf-dpi 300 \
  --output-pdf-images-format jp2
```

When you run `python morphic.py` with no arguments, you'll see:

```
╔══════════════════════════════════════════════════════════╗
║                    MORPHIC                               ║
║          Intelligent OCR with Downsampling               ║
╚══════════════════════════════════════════════════════════╝

Usage: python morphic.py [OPTIONS]

Required: Choose ONE input source
  --input-pdf-file PATH         OCR a PDF file
  --input-image-folder PATH     OCR a folder of images
...
```

---

## 📖 Use Cases

### 1. Create Multiple Versions from High-Res Scans

```bash
# Master archive (full quality)
python morphic.py \
  --input-image-folder ./scans/ \
  --output-pdf-file master_600dpi.pdf \
  --output-pdf-dpi 600 \
  --output-pdf-images-format jp2

# Web distribution (smaller, same OCR quality)
python morphic.py \
  --input-image-folder ./scans/ \
  --output-pdf-file web_300dpi.pdf \
  --output-pdf-dpi 300 \
  --output-pdf-images-format jp2

# Email-friendly (tiny, same OCR quality)
python morphic.py \
  --input-image-folder ./scans/ \
  --output-pdf-file email_150dpi.pdf \
  --output-pdf-dpi 150 \
  --output-pdf-images-format jpeg
```

**All three PDFs have identical OCR quality** - only the embedded image resolution differs!

### 2. Optimize Existing PDF Scans

```bash
# Your scanner produced a 500MB PDF at 600 DPI
python morphic.py \
  --input-pdf-file huge_scan.pdf \
  --output-pdf-file optimized.pdf \
  --source-dpi 600 \
  --output-pdf-dpi 300 \
  --output-pdf-images-format jp2

# Result: ~125MB file with perfect OCR
```

### 3. Process Folder of Mixed-DPI Images

```bash
# Images have DPI in EXIF - Morphic auto-detects!
python morphic.py \
  --input-image-folder ./photos/ \
  --output-pdf-file result.pdf \
  --output-pdf-dpi 300

# Images without EXIF default to 600 DPI
```

---

## 🎛️ Command-Line Options

### Input (Required - Pick One)
- `--input-pdf-file PATH` - Input PDF file to OCR
- `--input-image-folder PATH` - Folder of page images (auto-sorted)

### Output (Required)
- `--output-pdf-file PATH` - Where to save searchable PDF

### DPI Control (Optional)
- `--source-dpi INT` - DPI for OCR processing (default: 600)
  - **PDFs**: Rasterization resolution
  - **Images**: Fallback if no EXIF DPI (auto-detected when available)
  
- `--output-pdf-dpi INT` - Target DPI for output (default: same as source)
  - Lower than source = downsampling for smaller files
  - Same as source = no downsampling

### Format & Performance
- `--output-pdf-images-format {jp2,jpx,png,jpeg}` - Image codec (default: jp2)
  - `jp2`/`jpx`: JPEG2000 - best for high-DPI (recommended)
  - `png`: Lossless, larger files
  - `jpeg`: Lossy, smallest files
  
- `--page-queue-depth INT` - Pages in memory at once (1-10, default: 5)
  - Lower = less RAM
  - Higher = faster on powerful systems

- `--debug` - Verbose logging with resource monitoring

---

## 📐 How It Works

### The Workflow

```
┌─────────────────┐
│  Input Source   │ (PDF or images)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Auto-Detect DPI │ (from EXIF or --source-dpi)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   EasyOCR at    │ (Always maximum resolution)
│  Native/Max DPI │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   Downsample    │ (If output-dpi < source-dpi)
│  (Optional)     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Embed in PDF   │ (JPEG2000 or PNG/JPEG)
│  + OCR Text     │ (Coordinates auto-scaled)
└─────────────────┘
```

### Coordinate Scaling

When downsampling, OCR bounding boxes are automatically scaled:

```python
# OCR detects text at 600 DPI: bbox = (1200, 800)
# Output is 300 DPI: scale_factor = 300/600 = 0.5
# Final coords: (600, 400)
```

Text remains perfectly aligned with downsampled images!

---

## 📊 Expected Results

### File Size Comparison
For a 200-page 8×10" book:

| Configuration | File Size | OCR Quality | Use Case |
|---------------|-----------|-------------|----------|
| 600 DPI JP2   | ~800 MB   | ⭐⭐⭐⭐⭐ | Master archive |
| 300 DPI JP2   | ~200 MB   | ⭐⭐⭐⭐⭐ | Web distribution |
| 150 DPI JPEG  | ~50 MB    | ⭐⭐⭐⭐⭐ | Email attachments |

**Note**: OCR quality is identical in all cases - only image resolution differs!

### Performance
- **OCR Speed**: ~3-5 seconds per page (GPU) or ~10-15 seconds (CPU)
- **Memory Usage**: ~500MB - 1GB with default queue depth
- **Compression**: JPEG2000 at 600 DPI ≈ 60-70% size of PNG

---

## 🔧 Technical Details

### Why JPEG2000?

JPEG2000 (JP2/JPX) provides superior compression for high-DPI scans:
- 2-4× smaller than PNG at equivalent quality
- Native PDF support via `JPXDecode` filter
- No quality loss from re-encoding (unlike reportlab)

### DPI Auto-Detection

Morphic checks image EXIF data for DPI:
```python
# Pillow extracts DPI from EXIF tags
img.info['dpi']  # e.g., (600, 600)
```

If no EXIF data, falls back to `--source-dpi`.

### Verification

Confirm JPEG2000 is properly embedded:
```bash
qpdf --stream-data=uncompress output.pdf | grep JPXDecode
```

You should see `JPXDecode` filters in the PDF structure.

---

## 🐛 Troubleshooting

### "EasyOCR failed to initialize"
- **GPU mode**: Check CUDA installation
- **Auto-fallback**: Tool switches to CPU automatically

### "WebP is not supported"
- PDF specification doesn't support WebP codec
- Use `jp2`, `png`, or `jpeg` instead

### "Out of memory"
- Reduce `--page-queue-depth` to 2 or 3
- Lower `--source-dpi` if OCR quality permits

### "Pages out of order"
- Images use natural sort (1, 2, 10 not 1, 10, 2)
- Zero-pad filenames if needed: `page-001.png`

---

## 🤝 Contributing

Contributions welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Add tests for new features
4. Submit a pull request

---

## 📄 License

MIT License - see [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

Built with:
- [EasyOCR](https://github.com/JaidedAI/EasyOCR) - Neural network OCR
- [PyMuPDF](https://github.com/pymupdf/PyMuPDF) - PDF manipulation
- [pdf2image](https://github.com/Belval/pdf2image) - PDF to image conversion
- [Pillow](https://python-pillow.org/) - Image processing

---

## 📬 Contact

Questions? Open an issue or reach out!

**Happy OCR'ing! 🔮**
