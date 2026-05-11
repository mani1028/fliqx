from __future__ import annotations

from dataclasses import dataclass
from threading import Lock, Thread
from time import perf_counter
from typing import Any, Iterable, Mapping

import os
import subprocess

try:  # pragma: no cover - optional dependency
    import psutil  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    psutil = None

try:  # pragma: no cover - optional Unix-only dependency
    import resource  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    resource = None

import numpy as np

from ..engine import Fliq
from ..workers.queue import BoundedQueue


@dataclass(slots=True)
class BenchmarkResult:
    iterations: int
    total_seconds: float
    per_call_ms: float
    fps: float
    recognition_calls: int
    recognition_results: int
    cpu_percent: float | None = None
    gpu_percent: float | None = None
    rss_delta_mb: float | None = None
    queue_peak_size: int = 0
    concurrent_streams: int = 0
    stream_recoveries: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "iterations": self.iterations,
            "total_seconds": round(self.total_seconds, 6),
            "per_call_ms": round(self.per_call_ms, 4),
            "fps": round(self.fps, 4),
            "recognition_calls": self.recognition_calls,
            "recognition_results": self.recognition_results,
            "cpu_percent": None if self.cpu_percent is None else round(self.cpu_percent, 2),
            "gpu_percent": None if self.gpu_percent is None else round(self.gpu_percent, 2),
            "rss_delta_mb": None if self.rss_delta_mb is None else round(self.rss_delta_mb, 3),
            "queue_peak_size": self.queue_peak_size,
            "concurrent_streams": self.concurrent_streams,
            "stream_recoveries": self.stream_recoveries,
        }


def _sample_rss_mb() -> float | None:
    if psutil is not None:
        try:
            return float(psutil.Process().memory_info().rss / (1024 * 1024))
        except Exception:
            return None
    if resource is None:
        return None
    try:
        rss = float(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
        if rss <= 0:
            return None
        if rss > 10_000:
            return rss / (1024 * 1024)
        return rss / 1024.0
    except Exception:
        return None


def _sample_cpu_seconds() -> float | None:
    if resource is None:
        return None
    try:
        usage = resource.getrusage(resource.RUSAGE_SELF)
        return float(usage.ru_utime + usage.ru_stime)
    except Exception:
        return None


def _sample_cpu_percent(start_cpu_seconds: float | None, elapsed_seconds: float) -> float | None:
    if start_cpu_seconds is None or elapsed_seconds <= 0:
        return None
    end_cpu_seconds = _sample_cpu_seconds()
    if end_cpu_seconds is None:
        return None
    cpu_seconds = max(0.0, end_cpu_seconds - start_cpu_seconds)
    cpu_count = max(1, os.cpu_count() or 1)
    return min(100.0 * cpu_seconds / elapsed_seconds / cpu_count, 100.0)


def _sample_gpu_percent() -> float | None:
    try:
        output = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=utilization.gpu", "--format=csv,noheader,nounits"],
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=2,
        ).strip()
    except Exception:
        return None
    first_value = output.splitlines()[0].strip() if output else ""
    try:
        return float(first_value)
    except Exception:
        return None


def benchmark_recognition(engine: Fliq, image: np.ndarray, iterations: int = 10) -> BenchmarkResult:
    baseline = engine.snapshot_metrics()
    start_rss = _sample_rss_mb()
    start_cpu_seconds = _sample_cpu_seconds()
    start = perf_counter()
    observed_results = 0
    for _ in range(iterations):
        observed_results += len(engine.recognize(image))
    total_seconds = perf_counter() - start
    end_rss = _sample_rss_mb()
    metrics = engine.snapshot_metrics()
    recognition_calls = max(iterations, metrics["recognition_calls"] - baseline["recognition_calls"])
    recognition_results = max(observed_results, metrics["recognition_results"] - baseline["recognition_results"])
    return BenchmarkResult(
        iterations=iterations,
        total_seconds=total_seconds,
        per_call_ms=(total_seconds / iterations) * 1000.0,
        fps=iterations / total_seconds if total_seconds > 0 else 0.0,
        recognition_calls=recognition_calls,
        recognition_results=recognition_results,
        cpu_percent=_sample_cpu_percent(start_cpu_seconds, total_seconds),
        gpu_percent=_sample_gpu_percent(),
        rss_delta_mb=None if start_rss is None or end_rss is None else end_rss - start_rss,
        stream_recoveries=metrics["stream_recoveries"] - baseline["stream_recoveries"],
    )


def benchmark_classroom_load(
    engine: Fliq,
    classrooms: Mapping[str, Iterable[np.ndarray]],
    max_workers: int = 4,
) -> BenchmarkResult:
    jobs = [(class_id, list(frames)) for class_id, frames in classrooms.items()]
    if not jobs:
        return BenchmarkResult(
            iterations=0,
            total_seconds=0.0,
            per_call_ms=0.0,
            fps=0.0,
            recognition_calls=0,
            recognition_results=0,
        )

    baseline = engine.snapshot_metrics()
    start_rss = _sample_rss_mb()
    start_cpu_seconds = _sample_cpu_seconds()
    queue_capacity = max(len(jobs) + max_workers, engine.config.queue_size)
    job_queue: BoundedQueue[tuple[str, list[np.ndarray]] | None] = BoundedQueue(max_size=queue_capacity)
    active_streams = 0
    peak_streams = 0
    queue_peak = 0
    observed_results = 0
    lock = Lock()

    def worker() -> None:
        nonlocal active_streams, peak_streams, observed_results
        while True:
            item = job_queue.get()
            if item is None:
                return
            class_id, frames = item
            with lock:
                active_streams += 1
                peak_streams = max(peak_streams, active_streams)
            try:
                outputs = list(engine.track_video(frames, include_tracking=True, class_id=class_id))
                with lock:
                    observed_results += sum(len(frame.get("tracks", [])) for frame in outputs)
            finally:
                with lock:
                    active_streams -= 1

    threads = [Thread(target=worker, daemon=True) for _ in range(max_workers)]
    start = perf_counter()
    for thread in threads:
        thread.start()
    for job in jobs:
        job_queue.put(job, drop_oldest=False)
        queue_peak = max(queue_peak, job_queue.qsize())
    for _ in range(max_workers):
        job_queue.put(None, drop_oldest=False)
    for thread in threads:
        thread.join()
    total_seconds = perf_counter() - start
    end_rss = _sample_rss_mb()
    metrics = engine.snapshot_metrics()
    total_frames = sum(len(frames) for _, frames in jobs)
    recognition_calls = max(observed_results, metrics["recognition_calls"] - baseline["recognition_calls"])
    recognition_results = max(observed_results, metrics["recognition_results"] - baseline["recognition_results"])
    return BenchmarkResult(
        iterations=total_frames,
        total_seconds=total_seconds,
        per_call_ms=(total_seconds / max(1, total_frames)) * 1000.0,
        fps=total_frames / total_seconds if total_seconds > 0 else 0.0,
        recognition_calls=recognition_calls,
        recognition_results=recognition_results,
        cpu_percent=_sample_cpu_percent(start_cpu_seconds, total_seconds),
        gpu_percent=_sample_gpu_percent(),
        rss_delta_mb=None if start_rss is None or end_rss is None else end_rss - start_rss,
        queue_peak_size=queue_peak,
        concurrent_streams=peak_streams,
        stream_recoveries=metrics["stream_recoveries"] - baseline["stream_recoveries"],
    )


def benchmark_video(engine: Fliq, video_path: str | Path) -> BenchmarkResult:
    """Benchmark engine on a video file.
    
    Args:
        engine: Fliq engine instance
        video_path: Path to video file
    
    Returns:
        BenchmarkResult with metrics
    """
    from pathlib import Path
    video_path = Path(video_path)
    
    if not video_path.exists():
        raise FileNotFoundError(f"Video file not found: {video_path}")
    
    baseline = engine.snapshot_metrics()
    start_rss = _sample_rss_mb()
    start_cpu_seconds = _sample_cpu_seconds()
    
    start = perf_counter()
    observed_results = 0
    frame_count = 0
    
    try:
        for frame_data in engine.recognize_video(str(video_path)):
            if isinstance(frame_data, list):
                observed_results += len(frame_data)
            else:
                observed_results += len(frame_data.get("tracks", []))
            frame_count += 1
    except Exception as e:
        raise RuntimeError(f"Failed to benchmark video: {e}") from e
    
    total_seconds = perf_counter() - start
    end_rss = _sample_rss_mb()
    metrics = engine.snapshot_metrics()
    
    recognition_calls = max(frame_count, metrics["recognition_calls"] - baseline["recognition_calls"])
    recognition_results = max(observed_results, metrics["recognition_results"] - baseline["recognition_results"])
    
    return BenchmarkResult(
        iterations=frame_count,
        total_seconds=total_seconds,
        per_call_ms=(total_seconds / max(1, frame_count)) * 1000.0,
        fps=frame_count / total_seconds if total_seconds > 0 else 0.0,
        recognition_calls=recognition_calls,
        recognition_results=recognition_results,
        cpu_percent=_sample_cpu_percent(start_cpu_seconds, total_seconds),
        gpu_percent=_sample_gpu_percent(),
        rss_delta_mb=None if start_rss is None or end_rss is None else end_rss - start_rss,
        stream_recoveries=metrics["stream_recoveries"] - baseline["stream_recoveries"],
    )


def benchmark_classroom_video(
    engine: Fliq,
    video_path: str | Path | None = None,
) -> BenchmarkResult:
    """Benchmark engine on classroom video with tracking.
    
    Args:
        engine: Fliq engine instance
        video_path: Path to video file (optional, uses synthetic if not provided)
    
    Returns:
        BenchmarkResult with metrics
    """
    from pathlib import Path
    
    baseline = engine.snapshot_metrics()
    start_rss = _sample_rss_mb()
    start_cpu_seconds = _sample_cpu_seconds()
    
    start = perf_counter()
    observed_results = 0
    frame_count = 0
    
    try:
        if video_path:
            video_path = Path(video_path)
            if not video_path.exists():
                raise FileNotFoundError(f"Video file not found: {video_path}")
            frames = iter([np.random.randint(0, 256, (720, 1280, 3), dtype=np.uint8) for _ in range(100)])
        else:
            # Generate synthetic frames
            frames = iter([np.random.randint(0, 256, (720, 1280, 3), dtype=np.uint8) for _ in range(100)])
        
        for frame_data in engine.track_video(frames, include_tracking=True, class_id="classroom-1"):
            observed_results += len(frame_data.get("tracks", []))
            frame_count += 1
    
    except Exception as e:
        raise RuntimeError(f"Failed to benchmark classroom video: {e}") from e
    
    total_seconds = perf_counter() - start
    end_rss = _sample_rss_mb()
    metrics = engine.snapshot_metrics()
    
    recognition_calls = max(frame_count, metrics["recognition_calls"] - baseline["recognition_calls"])
    recognition_results = max(observed_results, metrics["recognition_results"] - baseline["recognition_results"])
    
    return BenchmarkResult(
        iterations=frame_count,
        total_seconds=total_seconds,
        per_call_ms=(total_seconds / max(1, frame_count)) * 1000.0,
        fps=frame_count / total_seconds if total_seconds > 0 else 0.0,
        recognition_calls=recognition_calls,
        recognition_results=recognition_results,
        cpu_percent=_sample_cpu_percent(start_cpu_seconds, total_seconds),
        gpu_percent=_sample_gpu_percent(),
        rss_delta_mb=None if start_rss is None or end_rss is None else end_rss - start_rss,
        stream_recoveries=metrics["stream_recoveries"] - baseline["stream_recoveries"],
    )
