# FLIQ

FLIQ is a lightweight face recognition acceleration layer for Python that combines detection, embedding, tracking, caching, vector search, and streaming helpers in a single package. It is designed to run with only NumPy installed, while optional extras unlock FastAPI, OpenCV, FAISS, and ONNX-backed acceleration paths.

## What It Does

FLIQ provides a practical face recognition engine for image, video, and streaming workloads. The package centers on the `Fliq` engine and exposes:

- face registration and recognition for still images
- video and iterable-based stream processing
- tracking-aware recognition with classroom/session-style caches
- motion detection and adaptive frame scheduling support
- FAISS-backed similarity search with a NumPy fallback path
- optional FastAPI routes for service integration
- benchmark helpers for measuring throughput, latency, memory, and stream behavior

The package exports `Fliq`, `FliqConfig`, and `RecognitionMatch` from the top-level `fliq` module.

## Installation

FLIQ requires Python 3.10 or newer.

Install the core package from source:

```bash
pip install .
```

Install with optional extras depending on your use case:

```bash
pip install .[full]
```

Available extras:

- `api` for FastAPI and Uvicorn
- `video` for OpenCV-based video support
- `onnx` for ONNX Runtime-based detector and embedder adapters
- `faiss` for FAISS vector search support
- `dev` for local testing
- `full` for API, video, and test dependencies together

For local development from the repository:

```bash
pip install -e .[dev]
```

## Quick Start

```python
import numpy as np
from fliq import Fliq

engine = Fliq()
image = np.zeros((256, 256, 3), dtype=np.uint8)

engine.register("person-001", image)
results = engine.recognize(image)
print(results)
```

If you want to process video or frame iterables:

```python
frames = [np.zeros((256, 256, 3), dtype=np.uint8) for _ in range(5)]

for frame_result in engine.track_video(frames):
	print(frame_result)
```

## Public API

The main engine methods are:

- `register(user_id, image)` to add a known face
- `recognize(image, class_id=None)` to run recognition on a still frame
- `recognize_video(video)` to process a video source or iterable of frames
- `track_video(source, include_tracking=True, class_id=None)` for streaming recognition with tracking
- `save_index(directory=None)` and `load_index(directory=None)` for persistence
- `remove_user(user_id)` to delete a subject from the index
- `snapshot_metrics()` for runtime counters and uptime
- `optimize_existing(embeddings, ids)` for bulk index updates

The configuration object `FliqConfig` controls runtime behavior such as:

- device selection
- frame skipping and recognition cadence
- detector, embedder, tracker, and vector backend selection
- confidence thresholds
- cache sizes and concurrency limits
- warmup behavior and motion sensitivity

## Architecture

FLIQ is organized around a few cooperating layers:

- `fliq.detection` provides detector abstractions and adapters, including auto, whole-frame, RetinaFace, and SCRFD-based paths
- `fliq.embeddings` provides embedder abstractions, including lightweight, ArcFace, and Buffalo-style options
- `fliq.tracking` provides tracking implementations, including ByteTrack-inspired variants
- `fliq.vector` provides similarity search, persistence, and optional FAISS acceleration
- `fliq.cache` provides embedding, match, memory, and session caches
- `fliq.video` provides frame handling, motion detection, and scheduling helpers
- `fliq.api` exposes a FastAPI application and JSON routes
- `fliq.benchmarks` provides benchmark routines and result reporting

When optional acceleration packages are unavailable, the engine falls back to pure Python and NumPy implementations so the package remains usable in minimal environments.

## Configuration Examples

```python
from fliq import Fliq

engine = Fliq(
	mode="balanced",
	detector="scrfd",
	embedder="buffalo",
	tracker="bytetrack",
	vector_backend="faiss",
	warmup=True,
)
```

Common runtime modes:

- `speed` for higher throughput
- `balanced` for a middle ground between latency and quality
- `accuracy` for tighter recognition cadence and thresholding

## API Service

If you install the `api` extra, you can create a FastAPI app around the engine:

```python
from fliq.api.fastapi_app import create_app

app = create_app()
```

Available routes:

- `GET /` for a readiness response
- `GET /health` for a health check
- `POST /register` for user registration
- `POST /recognize` for recognition requests

## Benchmarks

The repository includes benchmark helpers for both single-frame recognition and concurrent classroom-style loads.

Run the benchmark script from the repository root:

```bash
python scripts/benchmark_runner.py
```

The benchmark output reports:

- total time and per-call latency
- frames per second
- recognition call and result counts
- concurrent stream usage
- queue peak size
- CPU and GPU utilization when available
- RSS memory deltas
- stream recovery counts

## Development

Run the test suite with:

```bash
pytest
```

The repository is configured for editable installs and includes package markers so the full `fliq` tree is discoverable during development and wheel builds.

## PyPI Distribution

**What's Included in PyPI Package:**
- Core FLIQ engine (`fliq/`)
- All detection, embedding, tracking, vector, video, and cache modules
- CLI tools (`fliq/cli.py`)
- Production hardening modules (stress, stability, protection)
- Type hints and markers

**What's Excluded from PyPI (GitHub only):**
- Test files (`fliq/tests/`)
- Development documentation:
  - `PRODUCTION.md` - Production deployment guide
  - `UPGRADE_SUMMARY.md` - Change summary
  - `CLI_REFERENCE.md` - CLI usage reference
  - `IMPLEMENTATION_COMPLETE.md` - Implementation details
  - `README_PRODUCTION.md` - File reference
- Benchmark reports directory (`benchmarks/reports/`)
- Scripts directory (`scripts/`)
- Build and configuration files (`setup.py`, `.github/`, etc.)

**Why?**
The PyPI package is kept lean (only production code) while the GitHub repository includes comprehensive testing, documentation, and development tools. This keeps package size small and installation fast while maintaining full transparency and documentation in the source repository.

**To Install from PyPI:**
```bash
pip install fliq
```

**To Get Development Version with All Tests and Docs:**
```bash
git clone https://github.com/your-org/fliq.git
cd fliq
pip install -e .[dev]
```

## Project Layout

- `fliq/engine.py` contains the main orchestration engine
- `fliq/config.py` contains runtime configuration defaults and validation
- `fliq/api/` contains the HTTP service layer
- `fliq/cache/` contains in-memory caches and session state
- `fliq/detection/` contains detector implementations and adapters
- `fliq/embeddings/` contains embedding models and wrappers
- `fliq/tracking/` contains tracking logic
- `fliq/vector/` contains vector search and persistence helpers
- `fliq/video/` contains frame, motion, and stream utilities
- `fliq/benchmarks/` contains benchmark helpers and metrics
- `fliq/stress/` contains stress testing framework (production hardening)
- `fliq/stability/` contains stability monitoring (production hardening)
- `fliq/protection.py` contains load protection systems (production hardening)
- `scripts/benchmark_runner.py` is a runnable benchmark entry point

## Notes

FLIQ is intentionally modular: you can use the core NumPy-only package for development and testing, then add optional extras only when your deployment needs them. Saved indexes are automatically loaded when an index directory is present, and recognition results are cached to reduce repeated work in high-throughput workloads.

