"""JARVIS Memory Package.

Provides persistent memory façade, hybrid vector + BM25 search, and fact extraction.
"""

from app.memory.service import MemoryService

__all__ = ["MemoryService"]
