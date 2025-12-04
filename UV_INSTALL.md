# Installing Morphic with UV

[UV](https://github.com/astral-sh/uv) is a fast Python package installer and resolver, written in Rust. It's significantly faster than pip.

## Installation

### 1. Install UV

```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Or with pip
pip install uv

# Or with Homebrew (macOS)
brew install uv
```

### 2. Install Morphic Dependencies with UV

```bash
# Navigate to morphic directory
cd morphic

# Install dependencies
uv pip install -r requirements.txt

# Or create a virtual environment and install
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uv pip install -r requirements.txt
```

### 3. Install System Dependencies

UV handles Python packages, but you still need poppler for PDF processing:

```bash
# macOS
brew install poppler

# Ubuntu/Debian
sudo apt-get install poppler-utils

# Fedora/RHEL
sudo dnf install poppler-utils

# Arch Linux
sudo pacman -S poppler
```

## Usage After UV Installation

```bash
# If using virtual environment
source .venv/bin/activate

# Run Morphic
python morphic.py --input-pdf-file scan.pdf --output-pdf-file out.pdf
```

## Why UV?

### Speed Comparison

```bash
# Traditional pip
time pip install -r requirements.txt
# ~45 seconds

# UV
time uv pip install -r requirements.txt
# ~5 seconds
```

UV is **10-100× faster** than pip for package installation!

### Other Benefits

- **Faster dependency resolution** - Uses a more efficient algorithm
- **Better caching** - Reuses downloaded packages across projects
- **Drop-in replacement** - Works with existing requirements.txt
- **Cross-platform** - Works on Linux, macOS, and Windows

## Creating a UV Project (Optional)

For more advanced UV features:

```bash
# Initialize a UV project
uv init morphic
cd morphic

# Add dependencies directly
uv add easyocr pdf2image PyMuPDF natsort psutil rich Pillow

# Run scripts without activation
uv run morphic.py --help
```

This creates a `pyproject.toml` instead of `requirements.txt`.

## Troubleshooting

### "uv: command not found"

Make sure UV's bin directory is in your PATH:

```bash
export PATH="$HOME/.cargo/bin:$PATH"
```

Add this to your `~/.bashrc` or `~/.zshrc` to make it permanent.

### "Failed to find Python 3.11"

UV can install Python versions for you:

```bash
uv python install 3.11
uv python pin 3.11
```

### GPU Support for EasyOCR

If you have CUDA available:

```bash
# Install PyTorch with CUDA support first
uv pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118

# Then install other dependencies
uv pip install -r requirements.txt
```

## Comparison: pip vs UV

| Feature | pip | UV |
|---------|-----|-----|
| Speed | Baseline | 10-100× faster |
| Dependency resolution | Good | Excellent |
| Cache reuse | Limited | Aggressive |
| Lock files | pip-tools needed | Built-in |
| Python version management | No | Yes |
| Written in | Python | Rust |

## Using UV with Morphic Development

```bash
# Create development environment
uv venv --python 3.11
source .venv/bin/activate

# Install dev dependencies
uv pip install -r requirements.txt
uv pip install pytest black mypy  # Testing and linting

# Run tests (if you add them later)
uv run pytest

# Format code
uv run black morphic.py
```

## Docker with UV (Bonus)

If you want to containerize Morphic:

```dockerfile
FROM python:3.11-slim

# Install UV
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Install system dependencies
RUN apt-get update && apt-get install -y poppler-utils

# Set working directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN uv pip install --system -r requirements.txt

# Copy application
COPY morphic.py utilities.py ./

ENTRYPOINT ["python", "morphic.py"]
```

Build and run:

```bash
docker build -t morphic .
docker run -v $(pwd)/scans:/scans morphic \
  --input-image-folder /scans \
  --output-pdf-file /scans/output.pdf \
  --output-pdf-dpi 300
```

## Resources

- [UV Documentation](https://github.com/astral-sh/uv)
- [UV vs pip Benchmarks](https://github.com/astral-sh/uv#benchmarks)
- [Python Packaging with UV](https://docs.astral.sh/uv/)
