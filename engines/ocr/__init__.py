"""
OCR Engine Registry for Morphic v0.2

Factory pattern with decorator-based registration.
Inspired by Crystallizer's provider system.

Usage:
    # In engine implementation:
    @register_ocr_engine("tesseract")
    class TesseractEngineFactory:
        @staticmethod
        def create(config: dict) -> OCREngine:
            return TesseractEngine(config)

    # To get an engine:
    engine = get_ocr_engine("tesseract", config)
"""

from typing import Dict, Callable
from .base import OCREngine

# Global registry of OCR engine factories
OCR_REGISTRY: Dict[str, Callable[[dict], OCREngine]] = {}


def register_ocr_engine(name: str):
    """
    Decorator to register OCR engine factories.

    Args:
        name: Unique identifier for this engine

    Returns:
        Decorator function that registers the factory class

    Example:
        @register_ocr_engine("tesseract")
        class TesseractEngineFactory:
            @staticmethod
            def create(config: dict):
                return TesseractEngine(config)
    """
    def decorator(factory_class):
        OCR_REGISTRY[name] = factory_class.create
        return factory_class
    return decorator


def get_ocr_engine(name: str, config: dict) -> OCREngine:
    """
    Get an OCR engine instance by name.

    Args:
        name: Engine identifier (must be registered)
        config: Engine-specific configuration dictionary

    Returns:
        Initialized OCR engine instance

    Raises:
        ValueError: If engine name is not registered
    """
    if name not in OCR_REGISTRY:
        available = ', '.join(OCR_REGISTRY.keys()) if OCR_REGISTRY else 'none'
        raise ValueError(
            f"Unknown OCR engine: '{name}'. "
            f"Available engines: {available}"
        )
    return OCR_REGISTRY[name](config)


# Auto-import available engines to trigger registration
# Engines will register themselves via @register_ocr_engine decorator
try:
    from . import tesseract  # noqa: F401
except ImportError:
    # Engine not yet implemented
    pass
