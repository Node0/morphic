"""
Image Compressor Registry for Morphic v0.2

Factory pattern with decorator-based registration.

Usage:
    # In compressor implementation:
    @register_compressor("jpeg2000")
    class JPEG2000CompressorFactory:
        @staticmethod
        def create(config: dict) -> ImageCompressor:
            return JPEG2000Compressor(config)

    # To get a compressor:
    compressor = get_compressor("jpeg2000", config)
"""

from typing import Dict, Callable
from .base import ImageCompressor

# Global registry of image compressor factories
COMPRESSOR_REGISTRY: Dict[str, Callable[[dict], ImageCompressor]] = {}


def register_compressor(name: str):
    """
    Decorator to register image compressor factories.

    Args:
        name: Unique identifier for this compressor

    Returns:
        Decorator function that registers the factory class

    Example:
        @register_compressor("jpeg2000")
        class JPEG2000CompressorFactory:
            @staticmethod
            def create(config: dict):
                return JPEG2000Compressor(config)
    """
    def decorator(factory_class):
        COMPRESSOR_REGISTRY[name] = factory_class.create
        return factory_class
    return decorator


def get_compressor(name: str, config: dict) -> ImageCompressor:
    """
    Get an image compressor instance by name.

    Args:
        name: Compressor identifier (must be registered)
        config: Compressor-specific configuration dictionary

    Returns:
        Initialized image compressor instance

    Raises:
        ValueError: If compressor name is not registered
    """
    if name not in COMPRESSOR_REGISTRY:
        available = ', '.join(COMPRESSOR_REGISTRY.keys()) if COMPRESSOR_REGISTRY else 'none'
        raise ValueError(
            f"Unknown compressor: '{name}'. "
            f"Available compressors: {available}"
        )
    return COMPRESSOR_REGISTRY[name](config)


# Auto-import available compressors to trigger registration
try:
    from . import jpeg2000  # noqa: F401
except ImportError:
    # Compressor not yet implemented
    pass
