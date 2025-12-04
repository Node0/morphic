# 🚀 Morphic Quick Start Guide

## What You've Got

✅ **morphic.py** - The main OCR tool with smart DPI handling  
✅ **requirements.txt** - Python dependencies  
✅ **README.md** - Full GitHub documentation  
✅ **UV_INSTALL.md** - Fast installation with UV (optional)

---

## Install & Run (2 Minutes)

### Step 1: Install Dependencies

**Fast way (with UV - recommended):**
```bash
# Install UV (one-time setup)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dependencies (~5 seconds)
uv pip install -r requirements.txt
```

**Traditional way (with pip):**
```bash
pip3.11 install -r requirements.txt  # Takes ~45 seconds
```

### Step 2: Install Poppler (for PDF processing)
```bash
# macOS
brew install poppler

# Ubuntu/Debian
sudo apt-get install poppler-utils
```

### Step 3: Copy Your utilities.py
Morphic needs your `utilities.py` file with:
- `Print(logType: str, message: str)`
- `CPU_and_Mem_usage() -> str`

Put it in the same folder as `morphic.py`.

---

## First Run

### Test the Help (No dependencies needed yet)
```bash
python3.11 morphic.py
```

You'll see:
```
╔══════════════════════════════════════════════════════════╗
║                    MORPHIC                               ║
║          Intelligent OCR with Downsampling              ║
╚══════════════════════════════════════════════════════════╝
```

### Your First OCR
```bash
# Simple: PDF → Searchable PDF
python3.11 morphic.py \
  --input-pdf-file your_scan.pdf \
  --output-pdf-file searchable.pdf

# With downsampling: 600 DPI OCR → 300 DPI output
python3.11 morphic.py \
  --input-pdf-file your_scan.pdf \
  --output-pdf-file web.pdf \
  --source-dpi 600 \
  --output-pdf-dpi 300 \
  --output-pdf-images-format jp2
```

---

## Your Use Case: Multiple Versions

```bash
# Master (600 DPI, ~800 MB for 200 pages)
python3.11 morphic.py \
  --input-image-folder ~/scans/book/ \
  --output-pdf-file master_600dpi.pdf \
  --output-pdf-dpi 600 \
  --output-pdf-images-format jp2

# Web (300 DPI, ~200 MB, same OCR quality!)
python3.11 morphic.py \
  --input-image-folder ~/scans/book/ \
  --output-pdf-file web_300dpi.pdf \
  --output-pdf-dpi 300 \
  --output-pdf-images-format jp2

# Email (150 DPI, ~50 MB, same OCR quality!)
python3.11 morphic.py \
  --input-image-folder ~/scans/book/ \
  --output-pdf-file email_150dpi.pdf \
  --output-pdf-dpi 150 \
  --output-pdf-images-format jpeg
```

All three PDFs have **identical OCR text** - only image resolution differs!

---

## Key Features You Asked For

✅ **Auto-DPI Detection** - Reads from image EXIF, no guessing  
✅ **Post-OCR Downsampling** - OCR at max resolution, downsample after  
✅ **JPEG2000 Support** - True JP2/JPX via PyMuPDF (not reportlab)  
✅ **No False Claims** - WebP properly rejected (not supported in PDF)  
✅ **Clean Help** - Running with no args shows usage, not hanging

---

## Common Options

| Flag | Purpose | Example |
|------|---------|---------|
| `--input-pdf-file` | OCR a PDF | `scan.pdf` |
| `--input-image-folder` | OCR image folder | `./scans/` |
| `--output-pdf-file` | Save result (required) | `output.pdf` |
| `--source-dpi` | OCR resolution | `600` (default) |
| `--output-pdf-dpi` | Output resolution | `300` (downsamples) |
| `--output-pdf-images-format` | Compression | `jp2`, `png`, `jpeg` |
| `--debug` | Verbose logging | (flag) |

---

## Troubleshooting

### "ModuleNotFoundError: No module named 'easyocr'"
Run: `pip3.11 install -r requirements.txt`

### "ModuleNotFoundError: No module named 'utilities'"
Copy your `utilities.py` to the morphic folder

### "Unable to find pdftoppm"
Install poppler: `brew install poppler` (macOS) or `sudo apt-get install poppler-utils` (Linux)

### "Program just hangs with no output"
- Check if utilities.py is in the same directory
- Make sure all dependencies are installed
- Try running with `--debug` flag

---

## What's Different from ChatGPT/Qwen Versions?

✅ **Fixed**: JPEG2000 actually works (uses PyMuPDF not reportlab)  
✅ **Fixed**: WebP explicitly rejected (was claiming support)  
✅ **Fixed**: Text color is white (was black in Qwen3's v2)  
✅ **Added**: Auto-DPI detection from EXIF  
✅ **Added**: Nice help display when run with no args  
✅ **Added**: UV installation support (10-100× faster)

---

## File Structure

```
morphic/
├── morphic.py              # Main tool
├── utilities.py            # Your logging (you provide this)
├── requirements.txt        # Python dependencies
├── README.md              # Full documentation
└── UV_INSTALL.md          # Fast install guide
```

---

## Next Steps

1. ✅ Install dependencies  
2. ✅ Copy your utilities.py  
3. ✅ Test with: `python3.11 morphic.py --help`  
4. ✅ Run your first OCR  
5. 🚀 Push to GitHub!

**You're ready to process your 600dpi scans! 🔮**

---

## Need More Help?

- Full docs: `README.md`
- UV guide: `UV_INSTALL.md`
- Source code: `morphic.py` (well commented)

Happy OCR'ing!
