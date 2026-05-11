"""Stability monitoring and memory leak detection for long-running FLIQ sessions."""

from __future__ import annotations

from dataclasses import dataclass, field
from threading import Thread, Lock, Event
from time import sleep, monotonic
from collections import deque
from typing import Any, Callable

try:
    import psutil  # type: ignore
except ImportError:
    psutil = None


@dataclass(slots=True)
class MemorySample:
    """Single memory sample."""
    timestamp: float
    rss_mb: float
    vms_mb: float
    heap_mb: float | None = None


@dataclass(slots=True)
class ResourceSample:
    """Single resource usage sample."""
    timestamp: float
    cpu_percent: float
    gpu_percent: float | None = None
    rss_mb: float
    vms_mb: float
    thread_count: int
    queue_depth: int = 0


class MemoryLeakDetector:
    """Detect memory leaks through trend analysis."""
    
    def __init__(self, window_size: int = 100, threshold_pct: float = 5.0):
        """Initialize leak detector.
        
        Args:
            window_size: Number of samples to use for trend analysis
            threshold_pct: Threshold for leak detection (% growth per hour)
        """
        self.window_size = window_size
        self.threshold_pct = threshold_pct
        self.samples: deque[MemorySample] = deque(maxlen=window_size)
        self._lock = Lock()
    
    def add_sample(self, sample: MemorySample) -> None:
        """Add a memory sample.
        
        Args:
            sample: MemorySample to add
        """
        with self._lock:
            self.samples.append(sample)
    
    def detect_leak(self) -> tuple[bool, float]:
        """Detect if memory is leaking.
        
        Returns:
            Tuple of (is_leaking, growth_rate_pct_per_hour)
        """
        with self._lock:
            if len(self.samples) < 10:
                return False, 0.0
            
            oldest = self.samples[0]
            newest = self.samples[-1]
            
            time_span_hours = (newest.timestamp - oldest.timestamp) / 3600.0
            if time_span_hours < 0.01:  # Need at least a bit of time
                return False, 0.0
            
            rss_growth_pct = ((newest.rss_mb - oldest.rss_mb) / oldest.rss_mb) * 100.0
            growth_per_hour = rss_growth_pct / time_span_hours
            
            is_leaking = growth_per_hour > self.threshold_pct
            
            return is_leaking, growth_per_hour
    
    def get_trend(self) -> dict[str, Any]:
        """Get memory trend information.
        
        Returns:
            Dictionary with trend information
        """
        with self._lock:
            if not self.samples:
                return {
                    "current_mb": 0.0,
                    "min_mb": 0.0,
                    "max_mb": 0.0,
                    "trend": "unknown",
                }
            
            current = self.samples[-1].rss_mb
            min_rss = min(s.rss_mb for s in self.samples)
            max_rss = max(s.rss_mb for s in self.samples)
            
            # Simple trend: compare first half vs second half
            mid = len(self.samples) // 2
            if mid > 0:
                first_half_avg = sum(s.rss_mb for s in list(self.samples)[:mid]) / mid
                second_half_avg = sum(s.rss_mb for s in list(self.samples)[mid:]) / (len(self.samples) - mid)
                growth_pct = ((second_half_avg - first_half_avg) / first_half_avg) * 100.0
                
                if growth_pct > 5:
                    trend = "increasing"
                elif growth_pct < -5:
                    trend = "decreasing"
                else:
                    trend = "stable"
            else:
                trend = "unknown"
            
            return {
                "current_mb": round(current, 2),
                "min_mb": round(min_rss, 2),
                "max_mb": round(max_rss, 2),
                "trend": trend,
            }


class RuntimeMonitor:
    """Monitor runtime metrics over long sessions."""
    
    def __init__(
        self,
        sampling_interval: float = 30.0,
        max_samples: int = 2880,  # ~24 hours at 30s intervals
    ):
        """Initialize runtime monitor.
        
        Args:
            sampling_interval: Seconds between samples
            max_samples: Maximum samples to keep
        """
        self.sampling_interval = sampling_interval
        self.max_samples = max_samples
        self.samples: deque[ResourceSample] = deque(maxlen=max_samples)
        self.memory_detector = MemoryLeakDetector(window_size=min(100, max_samples))
        self._lock = Lock()
        self._stop_event = Event()
        self._monitor_thread: Thread | None = None
        self._callbacks: list[Callable[[ResourceSample], None]] = []
    
    def start(
        self,
        engine: Any | None = None,
        queue_depth_getter: Callable[[], int] | None = None,
    ) -> None:
        """Start monitoring.
        
        Args:
            engine: Optional FLIQ engine for snapshot metrics
            queue_depth_getter: Optional callable to get queue depth
        """
        if self._monitor_thread is not None:
            return
        
        self._stop_event.clear()
        self._monitor_thread = Thread(
            target=self._monitor_loop,
            args=(engine, queue_depth_getter),
            daemon=True,
            name="runtime-monitor",
        )
        self._monitor_thread.start()
    
    def stop(self) -> None:
        """Stop monitoring."""
        self._stop_event.set()
        if self._monitor_thread is not None:
            self._monitor_thread.join(timeout=5.0)
            self._monitor_thread = None
    
    def add_callback(self, callback: Callable[[ResourceSample], None]) -> None:
        """Add callback for each sample.
        
        Args:
            callback: Function to call with each ResourceSample
        """
        self._callbacks.append(callback)
    
    def _monitor_loop(
        self,
        engine: Any | None,
        queue_depth_getter: Callable[[], int] | None,
    ) -> None:
        """Main monitoring loop."""
        while not self._stop_event.is_set():
            try:
                sample = self._collect_sample(queue_depth_getter)
                
                with self._lock:
                    self.samples.append(sample)
                    
                    # Add to memory detector
                    mem_sample = MemorySample(
                        timestamp=sample.timestamp,
                        rss_mb=sample.rss_mb,
                        vms_mb=sample.vms_mb,
                    )
                    self.memory_detector.add_sample(mem_sample)
                
                # Call callbacks
                for callback in self._callbacks:
                    try:
                        callback(sample)
                    except Exception:
                        pass
                
                self._stop_event.wait(timeout=self.sampling_interval)
            
            except Exception:
                self._stop_event.wait(timeout=self.sampling_interval)
    
    def _collect_sample(
        self,
        queue_depth_getter: Callable[[], int] | None,
    ) -> ResourceSample:
        """Collect a single resource sample."""
        timestamp = monotonic()
        cpu_percent = 0.0
        rss_mb = 0.0
        vms_mb = 0.0
        thread_count = 0
        gpu_percent = None
        
        if psutil is not None:
            try:
                proc = psutil.Process()
                cpu_percent = proc.cpu_percent(interval=0.1)
                mem_info = proc.memory_info()
                rss_mb = mem_info.rss / (1024 * 1024)
                vms_mb = mem_info.vms / (1024 * 1024)
                thread_count = proc.num_threads()
            except Exception:
                pass
        
        queue_depth = 0
        if queue_depth_getter is not None:
            try:
                queue_depth = queue_depth_getter()
            except Exception:
                pass
        
        return ResourceSample(
            timestamp=timestamp,
            cpu_percent=cpu_percent,
            gpu_percent=gpu_percent,
            rss_mb=rss_mb,
            vms_mb=vms_mb,
            thread_count=thread_count,
            queue_depth=queue_depth,
        )
    
    def get_stats(self) -> dict[str, Any]:
        """Get aggregated statistics.
        
        Returns:
            Dictionary with statistics
        """
        with self._lock:
            if not self.samples:
                return {}
            
            samples_list = list(self.samples)
            
            # Memory stats
            memory_values = [s.rss_mb for s in samples_list]
            memory_trend = self.memory_detector.get_trend()
            
            # CPU stats
            cpu_values = [s.cpu_percent for s in samples_list]
            
            # Thread stats
            thread_values = [s.thread_count for s in samples_list]
            
            # Queue stats
            queue_values = [s.queue_depth for s in samples_list]
            
            return {
                "samples_count": len(samples_list),
                "duration_seconds": round(samples_list[-1].timestamp - samples_list[0].timestamp, 2),
                "memory": {
                    "current_mb": round(memory_values[-1], 2),
                    "avg_mb": round(sum(memory_values) / len(memory_values), 2),
                    "peak_mb": round(max(memory_values), 2),
                    **memory_trend,
                },
                "cpu": {
                    "current_pct": round(cpu_values[-1], 2),
                    "avg_pct": round(sum(cpu_values) / len(cpu_values), 2),
                    "peak_pct": round(max(cpu_values), 2),
                },
                "threads": {
                    "current": thread_values[-1],
                    "max": max(thread_values),
                    "avg": int(sum(thread_values) / len(thread_values)),
                },
                "queue": {
                    "current_depth": queue_values[-1],
                    "max_depth": max(queue_values),
                    "avg_depth": int(sum(queue_values) / len(queue_values)),
                },
            }
    
    def detect_anomalies(self) -> list[str]:
        """Detect runtime anomalies.
        
        Returns:
            List of detected anomalies
        """
        anomalies = []
        stats = self.get_stats()
        
        if not stats:
            return anomalies
        
        # Check for memory leak
        is_leaking, growth_rate = self.memory_detector.detect_leak()
        if is_leaking:
            anomalies.append(f"Memory leak detected: {growth_rate:.2f}% growth/hour")
        
        # Check for thread explosion
        thread_stats = stats.get("threads", {})
        if thread_stats.get("max", 0) > 100:
            anomalies.append(f"Thread explosion: {thread_stats['max']} threads")
        
        # Check for queue buildup
        queue_stats = stats.get("queue", {})
        if queue_stats.get("max_depth", 0) > 1000:
            anomalies.append(f"Queue buildup: {queue_stats['max_depth']} max depth")
        
        # Check for sustained high CPU
        cpu_stats = stats.get("cpu", {})
        if cpu_stats.get("avg_pct", 0) > 90:
            anomalies.append(f"High sustained CPU: {cpu_stats['avg_pct']:.2f}%")
        
        return anomalies


class ProductionWatchdog:
    """Monitor stream and thread health during production."""
    
    def __init__(self, check_interval: float = 10.0):
        """Initialize watchdog.
        
        Args:
            check_interval: Seconds between health checks
        """
        self.check_interval = check_interval
        self.stream_health: dict[str, dict[str, Any]] = {}
        self.thread_health: dict[str, dict[str, Any]] = {}
        self._lock = Lock()
        self._stop_event = Event()
        self._monitor_thread: Thread | None = None
    
    def start(self) -> None:
        """Start watchdog monitoring."""
        if self._monitor_thread is not None:
            return
        
        self._stop_event.clear()
        self._monitor_thread = Thread(
            target=self._watchdog_loop,
            daemon=True,
            name="watchdog",
        )
        self._monitor_thread.start()
    
    def stop(self) -> None:
        """Stop watchdog."""
        self._stop_event.set()
        if self._monitor_thread is not None:
            self._monitor_thread.join(timeout=5.0)
            self._monitor_thread = None
    
    def report_stream(
        self,
        stream_id: str,
        is_healthy: bool,
        frames_processed: int = 0,
        errors: int = 0,
    ) -> None:
        """Report stream health.
        
        Args:
            stream_id: Stream identifier
            is_healthy: Whether stream is healthy
            frames_processed: Frames processed by stream
            errors: Error count for stream
        """
        with self._lock:
            self.stream_health[stream_id] = {
                "healthy": is_healthy,
                "frames_processed": frames_processed,
                "errors": errors,
                "last_update": monotonic(),
            }
    
    def _watchdog_loop(self) -> None:
        """Main watchdog loop."""
        while not self._stop_event.is_set():
            with self._lock:
                current_time = monotonic()
                
                # Check for stale streams
                stale_threshold = current_time - (self.check_interval * 3)
                for stream_id, health in list(self.stream_health.items()):
                    if health["last_update"] < stale_threshold:
                        health["healthy"] = False
            
            self._stop_event.wait(timeout=self.check_interval)
    
    def get_health_summary(self) -> dict[str, Any]:
        """Get overall health summary.
        
        Returns:
            Health summary dictionary
        """
        with self._lock:
            if not self.stream_health:
                return {"status": "no_streams"}
            
            healthy_count = sum(1 for h in self.stream_health.values() if h["healthy"])
            total_streams = len(self.stream_health)
            total_errors = sum(h["errors"] for h in self.stream_health.values())
            
            return {
                "healthy_streams": healthy_count,
                "total_streams": total_streams,
                "health_percentage": (healthy_count / total_streams * 100) if total_streams > 0 else 0,
                "total_errors": total_errors,
                "status": "healthy" if healthy_count == total_streams else "degraded",
            }
