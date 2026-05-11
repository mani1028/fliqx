from .config import FliqConfig
from .engine import Fliq
from .vector.faiss_index import RecognitionMatch

# Production hardening modules
from . import stress
from . import stability
from . import protection
from . import benchmarks
from . import cli

__all__ = [
    "Fliq",
    "FliqConfig",
    "RecognitionMatch",
    "stress",
    "stability",
    "protection",
    "benchmarks",
    "cli",
]
