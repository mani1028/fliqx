"""Main stress test runner for FLIQ production validation."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable
from threading import Thread, Lock, Event
from time import sleep, monotonic
from collections import deque
import json

import numpy as np

from ..engine import Fliq
from .stream_spawner import StreamSpawner, StreamMetrics
from .classroom_load import ClassroomLoad, ClassroomConfig


@dataclass(slots=True)
class StressTestConfig:
    """Configuration for stress tests."""
    classrooms: int = 5
    duration_minutes: float = 5.0
    fps_target: int = 30
    synthetic: bool = True
    video_paths: list[str] | None = None
    frame_skip: int = 5
    mode: str = "speed"
    recognition_cooldown: float = 5.0
    detection_size: int = 640
    max_concurrent_streams: int = 20
    adaptive_scheduler: bool = True


@dataclass(slots=True)
class StressTestMetrics:
    """Collected metrics from stress test."""
    start_time: float = field(default_factory=monotonic)
    end_time: float | None = None
    
    # Stream metrics
    total_frames_processed: int = 0
    total_frames_skipped: int = 0
    total_frames_dropped: int = 0
    peak_fps: float = 0.0
    avg_fps: float = 0.0
    min_fps: float = float('inf')
    
    # Engine metrics
    total_recognitions: int = 0
    recognition_results: int = 0
    stream_failures: int = 0
    stream_recoveries: int = 0
    
    # System metrics
    peak_cpu_percent: float = 0.0
    avg_cpu_percent: float = 0.0
    peak_gpu_percent: float = 0.0
    avg_gpu_percent: float = 0.0
    peak_rss_mb: float = 0.0
    avg_rss_mb: float = 0.0
    
    # Load testing
    concurrent_classrooms: int = 0
    active_streams: int = 0
    queue_depth: int = 0
    peak_queue_depth: int = 0
    
    # Errors
    stream_errors: int = 0
    processing_errors: int = 0
    
    # Derived metrics
    recognition_reduction_pct: float = 0.0
    
    def duration_seconds(self) -> float:
        """Get test duration in seconds."""
        if self.end_time is None:
            return monotonic() - self.start_time
        return self.end_time - self.start_time
    
    def to_dict(self) -> dict[str, Any]:
        """Export metrics as dict."""
        return {
            "duration_seconds": round(self.duration_seconds(), 2),
            "total_frames_processed": self.total_frames_processed,
            "total_frames_skipped": self.total_frames_skipped,
            "total_frames_dropped": self.total_frames_dropped,
            "peak_fps": round(self.peak_fps, 2),
            "avg_fps": round(self.avg_fps, 2),
            "min_fps": round(self.min_fps, 2) if self.min_fps != float('inf') else 0.0,
            "total_recognitions": self.total_recognitions,
            "recognition_results": self.recognition_results,
            "stream_failures": self.stream_failures,
            "stream_recoveries": self.stream_recoveries,
            "peak_cpu_percent": round(self.peak_cpu_percent, 2),
            "avg_cpu_percent": round(self.avg_cpu_percent, 2),
            "peak_gpu_percent": round(self.peak_gpu_percent, 2),
            "avg_gpu_percent": round(self.avg_gpu_percent, 2),
            "peak_rss_mb": round(self.peak_rss_mb, 2),
            "avg_rss_mb": round(self.avg_rss_mb, 2),
            "concurrent_classrooms": self.concurrent_classrooms,
            "active_streams": self.active_streams,
            "peak_queue_depth": self.peak_queue_depth,
            "stream_errors": self.stream_errors,
            "processing_errors": self.processing_errors,
            "recognition_reduction_pct": round(self.recognition_reduction_pct, 2),
        }


class StressTestRunner:
    """Run comprehensive stress tests on FLIQ engine."""
    
    def __init__(
        self,
        engine: Fliq | None = None,
        config: StressTestConfig | None = None,
    ):
        """Initialize stress test runner.
        
        Args:
            engine: Fliq engine instance (created if None)
            config: Stress test configuration
        """
        self.engine = engine or Fliq(
            mode="speed",
            adaptive_scheduler=True,
            frame_skip=3,
        )
        self.config = config or StressTestConfig()
        self.metrics = StressTestMetrics()
        self.spawner = StreamSpawner(
            fps_target=self.config.fps_target,
            max_concurrent=self.config.max_concurrent_streams,
        )
        self._stop_event = Event()
        self._metric_samples = deque(maxlen=1000)
        self._lock = Lock()
    
    def run(self) -> StressTestMetrics:
        """Run the stress test.
        
        Returns:
            StressTestMetrics with collected data
        """
        self._stop_event.clear()
        
        # Create classroom loads
        classroom_loads = [
            ClassroomLoad(ClassroomConfig())
            for _ in range(self.config.classrooms)
        ]
        
        # Start monitoring thread
        monitor_thread = Thread(
            target=self._monitor_loop,
            daemon=True,
            name="stress-monitor",
        )
        monitor_thread.start()
        
        # Start processing streams
        try:
            self._process_classrooms(classroom_loads)
        finally:
            self._stop_event.set()
            self.spawner.stop_all()
            monitor_thread.join(timeout=5.0)
        
        self.metrics.end_time = monotonic()
        self._finalize_metrics()
        
        return self.metrics
    
    def _process_classrooms(self, classroom_loads: list[ClassroomLoad]) -> None:
        """Process multiple classroom loads."""
        duration_seconds = self.config.duration_minutes * 60.0
        
        for classroom_idx, classroom in enumerate(classroom_loads):
            if self._stop_event.is_set():
                break
            
            stream_id = f"classroom-{classroom_idx}"
            
            # Create frame stream
            if self.config.synthetic:
                frames = classroom.stream_synthetic(int(duration_seconds * self.config.fps_target))
            else:
                if self.config.video_paths and classroom_idx < len(self.config.video_paths):
                    frames = ClassroomLoad.load_video(self.config.video_paths[classroom_idx])
                else:
                    frames = classroom.stream_synthetic(int(duration_seconds * self.config.fps_target))
            
            # Create callback to process frames
            def make_callback(class_idx: int):
                def callback(stream_id: str, frame: Any) -> None:
                    self._process_frame(frame, f"classroom-{class_idx}")
                return callback
            
            self.spawner.spawn_video_stream(
                stream_id,
                frames,
                callback=make_callback(classroom_idx),
            )
        
        # Wait for test duration
        start = monotonic()
        while monotonic() - start < duration_seconds and not self._stop_event.is_set():
            if self.spawner.active_count() == 0:
                break
            sleep(0.1)
    
    def _process_frame(self, frame_data: Any, class_id: str) -> None:
        """Process a single frame through the engine."""
        try:
            if hasattr(frame_data, 'frame'):
                frame = frame_data.frame
            else:
                frame = frame_data
            
            # Track video through engine
            results = list(self.engine.track_video(
                [frame],
                include_tracking=True,
                class_id=class_id,
            ))
            
            with self._lock:
                self.metrics.total_frames_processed += 1
        
        except Exception as e:
            with self._lock:
                self.metrics.processing_errors += 1
    
    def _monitor_loop(self) -> None:
        """Monitor system metrics during test."""
        try:
            import psutil
        except ImportError:
            psutil = None
        
        fps_samples = deque(maxlen=100)
        cpu_samples = deque(maxlen=100)
        gpu_samples = deque(maxlen=100)
        rss_samples = deque(maxlen=100)
        
        while not self._stop_event.is_set():
            try:
                # Collect stream metrics
                stream_metrics_map = self.spawner.get_all_metrics()
                active_count = self.spawner.active_count()
                
                # Collect FPS
                for metrics in stream_metrics_map.values():
                    if metrics.fps_current > 0:
                        fps_samples.append(metrics.fps_current)
                
                # Collect system metrics
                if psutil is not None:
                    try:
                        proc = psutil.Process()
                        cpu_percent = proc.cpu_percent(interval=0.1)
                        cpu_samples.append(cpu_percent)
                        
                        rss_mb = proc.memory_info().rss / (1024 * 1024)
                        rss_samples.append(rss_mb)
                    except Exception:
                        pass
                
                # Collect engine metrics
                with self._lock:
                    engine_snapshot = self.engine.snapshot_metrics()
                    self.metrics.total_recognitions = engine_snapshot.get("recognition_calls", 0)
                    self.metrics.recognition_results = engine_snapshot.get("recognition_results", 0)
                    self.metrics.stream_failures = engine_snapshot.get("stream_failures", 0)
                    self.metrics.stream_recoveries = engine_snapshot.get("stream_recoveries", 0)
                    self.metrics.concurrent_classrooms = len(self.engine.classroom_cache)
                    self.metrics.active_streams = active_count
                
                # Update peaks and averages
                if fps_samples:
                    self.metrics.peak_fps = max(self.metrics.peak_fps, max(fps_samples))
                    self.metrics.avg_fps = sum(fps_samples) / len(fps_samples)
                    if len(fps_samples) > 0:
                        self.metrics.min_fps = min(self.metrics.min_fps, min(fps_samples))
                
                if cpu_samples:
                    self.metrics.peak_cpu_percent = max(self.metrics.peak_cpu_percent, max(cpu_samples))
                    self.metrics.avg_cpu_percent = sum(cpu_samples) / len(cpu_samples)
                
                if rss_samples:
                    self.metrics.peak_rss_mb = max(self.metrics.peak_rss_mb, max(rss_samples))
                    self.metrics.avg_rss_mb = sum(rss_samples) / len(rss_samples)
                
                sleep(1.0)
            
            except Exception:
                sleep(1.0)
    
    def _finalize_metrics(self) -> None:
        """Finalize metrics after test."""
        # Calculate recognition reduction percentage
        total_frames = self.metrics.total_frames_processed
        if total_frames > 0:
            # Expected recognitions without cooldown would be total_frames / frame_skip
            # Actual recognitions is recognition_results
            # Reduction = (1 - actual / expected) * 100
            expected = total_frames / max(1, self.config.frame_skip)
            if expected > 0:
                actual = self.metrics.recognition_results
                reduction = max(0, (1.0 - actual / expected) * 100.0)
                self.metrics.recognition_reduction_pct = reduction
