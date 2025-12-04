"""
PDF Engine Registry for Morphic v0.2

Factory pattern with decorator-based registration.

Usage:
    # In engine implementation:
    @register_pdf_engine("pikepdf")
    class PikePDFEngineFactory:
        @staticmethod
        def create(config: dict) -> PDFEngine:
            return PikePDFEngine(config)

    # To get an engine:
    engine = get_pdf_engine("pikepdf", config)
"""

from typing import Dict, Callable
from .base import PDFEngine

# Global registry of PDF engine factories
PDF_REGISTRY: Dict[str, Callable[[dict], PDFEngine]] = {}


def register_pdf_engine(name: str):
    """
    Decorator to register PDF engine factories.

    Args:
        name: Unique identifier for this engine

    Returns:
        Decorator function that registers the factory class

    Example:
        @register_pdf_engine("pikepdf")
        class PikePDFEngineFactory:
            @staticmethod
            def create(config: dict):
                return PikePDFEngine(config)
    """
    def decorator(factory_class):
        PDF_REGISTRY[name] = factory_class.create
        return factory_class
    return decorator


def get_pdf_engine(name: str, config: dict) -> PDFEngine:
    """
    Get a PDF engine instance by name.

    Args:
        name: Engine identifier (must be registered)
        config: Engine-specific configuration dictionary

    Returns:
        Initialized PDF engine instance

    Raises:
        ValueError: If engine name is not registered
    """
    if name not in PDF_REGISTRY:
        available = ', '.join(PDF_REGISTRY.keys()) if PDF_REGISTRY else 'none'
        raise ValueError(
            f"Unknown PDF engine: '{name}'. "
            f"Available engines: {available}"
        )
    return PDF_REGISTRY[name](config)


# Auto-import available engines to trigger registration
try:
    from . import pikepdf_engine  # noqa: F401
except ImportError:
    # Engine not yet implemented
    pass
