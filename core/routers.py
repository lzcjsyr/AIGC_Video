"""
Routers: public API entrypoints that route to implementations in core.text,
core.media, and other submodules.
"""

from typing import Optional, Dict, Any, List, Tuple

from core.text import (
    intelligent_summarize,
    process_raw_to_script,
    extract_keywords,
)
from core.media import (
    generate_opening_image,
    generate_images_for_segments,
    synthesize_voice_for_segments,
)
from core.document_reader import DocumentReader


def read_document(file_path: str) -> Tuple[str, int]:
    reader = DocumentReader()
    return reader.read(file_path)


__all__ = [
    'read_document',
    'intelligent_summarize',
    'process_raw_to_script',
    'extract_keywords',
    'generate_opening_image',
    'generate_images_for_segments',
    'synthesize_voice_for_segments',
]


