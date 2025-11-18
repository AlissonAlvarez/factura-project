"""
Módulo de preprocesamiento de imágenes
Compatible con código existente
"""

from .image_processing import (
    ImagePreprocessor,
    preprocess_image,  # Función de compatibilidad
    extract_text_with_multipass,
    extract_text_from_image
)

__all__ = [
    'ImagePreprocessor',
    'preprocess_image',
    'extract_text_with_multipass', 
    'extract_text_from_image'
]