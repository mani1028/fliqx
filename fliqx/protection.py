"""Queue overflow and adaptive load protection for FLIQ."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from threading import Lock
from time import monotonic
from collections import deque


@dataclass(slots=True)
class LoadProtectionConfig:
    """Configuration for load protection."""
    queue_warn_threshold: int = 500
    queue_drop_threshold: int = 1000
    cpu_threshold: float = 85.0
    gpu_threshold: float = 90.0
    recognition_cooldown_max: float = 30.0
    frame_skip_max: int = 30


class QueueOverflowProtector:
    """Protect against queue overflow by dropping old frames."""
    
    def __init__(self, config: LoadProtectionConfig | None = None):
        """Initialize protector.
        
        Args:
            config: Protection configuration
        """
        self.config = config or LoadProtectionConfig()
        self._lock = Lock()
        self.queue_depth_samples: deque = deque(maxlen=100)
    
    def should_drop_frame(self, current_queue_depth: int) -> bool:
        """Check if frame should be dropped to reduce queue pressure.
        
        Args:
            current_queue_depth: Current queue depth
        
        Returns:
            True if frame should be dropped
        """
        return current_queue_depth > self.config.queue_drop_threshold
    
    def should_warn_queue(self, current_queue_depth: int) -> bool:
        """Check if queue depth warrants a warning.
        
        Args:
            current_queue_depth: Current queue depth
        
        Returns:
            True if queue is approaching limits
        """
        return current_queue_depth > self.config.queue_warn_threshold
    
    def get_recommended_action(self, current_queue_depth: int) -> dict[str, Any]:
        """Get recommended protective actions.
        
        Args:
            current_queue_depth: Current queue depth
        
        Returns:
            Dictionary with recommended actions
        """
        actions = {
            "drop_frames": False,
            "increase_frame_skip": False,
            "reduce_recognition": False,
            "lower_resolution": False,
            "severity": "normal",
        }
        
        if current_queue_depth > self.config.queue_drop_threshold:
            actions["drop_frames"] = True
            actions["increase_frame_skip"] = True
            actions["reduce_recognition"] = True
            actions["severity"] = "critical"
        elif current_queue_depth > self.config.queue_warn_threshold:
            actions["increase_frame_skip"] = True
            actions["reduce_recognition"] = True
            actions["severity"] = "warning"
        
        with self._lock:
            self.queue_depth_samples.append(current_queue_depth)
        
        return actions


class AdaptiveLoadProtector:
    """Adapt system parameters based on load and resource usage."""
    
    def __init__(self, config: LoadProtectionConfig | None = None):
        """Initialize adaptive protector.
        
        Args:
            config: Protection configuration
        """
        self.config = config or LoadProtectionConfig()
        self._lock = Lock()
        self.cpu_sample: float = 0.0
        self.gpu_sample: float = 0.0
        self.resource_samples: deque = deque(maxlen=100)
    
    def update_resources(
        self,
        cpu_percent: float = 0.0,
        gpu_percent: float = 0.0,
    ) -> None:
        """Update current resource usage.
        
        Args:
            cpu_percent: Current CPU usage percentage
            gpu_percent: Current GPU usage percentage
        """
        with self._lock:
            self.cpu_sample = cpu_percent
            self.gpu_sample = gpu_percent
            self.resource_samples.append({
                "cpu": cpu_percent,
                "gpu": gpu_percent,
                "timestamp": monotonic(),
            })
    
    def get_frame_skip_adjustment(self, current_frame_skip: int) -> int:
        """Get recommended frame skip adjustment.
        
        Args:
            current_frame_skip: Current frame skip value
        
        Returns:
            Recommended frame skip value
        """
        with self._lock:
            cpu = self.cpu_sample
            gpu = self.gpu_sample
        
        new_skip = current_frame_skip
        
        # Increase skip if resources are constrained
        if cpu > self.config.cpu_threshold or gpu > self.config.gpu_threshold:
            new_skip = min(new_skip + 2, self.config.frame_skip_max)
        
        # Decrease skip if resources are available
        elif cpu < 30.0 and gpu < 30.0 and new_skip > 1:
            new_skip = max(1, new_skip - 1)
        
        return new_skip
    
    def get_recognition_cooldown_adjustment(self, current_cooldown: float) -> float:
        """Get recommended recognition cooldown adjustment.
        
        Args:
            current_cooldown: Current recognition cooldown
        
        Returns:
            Recommended recognition cooldown value
        """
        with self._lock:
            cpu = self.cpu_sample
            gpu = self.gpu_sample
        
        new_cooldown = current_cooldown
        
        # Increase cooldown if resources are constrained
        if cpu > self.config.cpu_threshold or gpu > self.config.gpu_threshold:
            new_cooldown = min(
                new_cooldown * 1.5,
                self.config.recognition_cooldown_max,
            )
        
        return new_cooldown
    
    def is_under_pressure(self) -> bool:
        """Check if system is under resource pressure.
        
        Returns:
            True if system is under pressure
        """
        with self._lock:
            return (
                self.cpu_sample > self.config.cpu_threshold or
                self.gpu_sample > self.config.gpu_threshold
            )
    
    def get_load_level(self) -> str:
        """Get current load level.
        
        Returns:
            Load level: 'low', 'normal', 'high', or 'critical'
        """
        with self._lock:
            cpu = self.cpu_sample
            gpu = self.gpu_sample
            max_load = max(cpu, gpu)
        
        if max_load < 50.0:
            return "low"
        elif max_load < 75.0:
            return "normal"
        elif max_load < 90.0:
            return "high"
        else:
            return "critical"


class StreamRecoveryManager:
    """Manage stream recovery and reconnection strategies."""
    
    def __init__(self):
        """Initialize recovery manager."""
        self.recovery_attempts: dict[str, int] = {}
        self.recovery_timestamps: dict[str, float] = {}
        self._lock = Lock()
        self.max_retries = 3
        self.retry_delay_base = 1.0
    
    def should_retry(self, stream_id: str) -> bool:
        """Check if stream should be retried.
        
        Args:
            stream_id: Stream identifier
        
        Returns:
            True if stream should be retried
        """
        with self._lock:
            attempts = self.recovery_attempts.get(stream_id, 0)
            if attempts > self.max_retries:
                return False
            return True
    
    def record_failure(self, stream_id: str) -> None:
        """Record a stream failure.
        
        Args:
            stream_id: Stream identifier
        """
        with self._lock:
            self.recovery_attempts[stream_id] = self.recovery_attempts.get(stream_id, 0) + 1
            self.recovery_timestamps[stream_id] = monotonic()
    
    def record_recovery(self, stream_id: str) -> None:
        """Record successful stream recovery.
        
        Args:
            stream_id: Stream identifier
        """
        with self._lock:
            self.recovery_attempts[stream_id] = 0
    
    def get_retry_delay(self, stream_id: str) -> float:
        """Get recommended retry delay.
        
        Args:
            stream_id: Stream identifier
        
        Returns:
            Delay in seconds before retry
        """
        with self._lock:
            attempts = self.recovery_attempts.get(stream_id, 0)
        
        # Exponential backoff
        return self.retry_delay_base * (2 ** min(attempts, 5))
    
    def reset(self, stream_id: str) -> None:
        """Reset recovery state for a stream.
        
        Args:
            stream_id: Stream identifier
        """
        with self._lock:
            self.recovery_attempts.pop(stream_id, None)
            self.recovery_timestamps.pop(stream_id, None)


@dataclass(slots=True)
class SceneStabilityConfig:
    """Configuration for scene stability optimization."""
    motion_threshold: float = 12.0
    tracking_confidence_threshold: float = 0.85
    stability_cooldown_multiplier: float = 2.0
    stable_scene_cooldown_multiplier: float = 3.0


class SceneStabilityOptimizer:
    """Optimize recognition frequency based on scene stability."""
    
    def __init__(self, config: SceneStabilityConfig | None = None):
        """Initialize optimizer.
        
        Args:
            config: Scene stability configuration
        """
        self.config = config or SceneStabilityConfig()
        self._lock = Lock()
        self.scene_stability: dict[str, dict[str, Any]] = {}
    
    def analyze_frame_stability(
        self,
        class_id: str | None,
        motion_score: float,
        tracking_confidence: float,
        tracked_faces_count: int,
    ) -> dict[str, Any]:
        """Analyze frame stability for a classroom scene.
        
        Args:
            class_id: Classroom ID
            motion_score: Motion detection score
            tracking_confidence: Overall tracking confidence
            tracked_faces_count: Number of tracked faces
        
        Returns:
            Stability analysis
        """
        class_key = class_id or "default"
        
        is_stable = (
            motion_score < self.config.motion_threshold and
            tracking_confidence >= self.config.tracking_confidence_threshold
        )
        
        with self._lock:
            if class_key not in self.scene_stability:
                self.scene_stability[class_key] = {
                    "stable_frames": 0,
                    "unstable_frames": 0,
                    "last_update": monotonic(),
                }
            
            stability_data = self.scene_stability[class_key]
            
            if is_stable:
                stability_data["stable_frames"] += 1
            else:
                stability_data["unstable_frames"] = 0
            
            stability_data["last_update"] = monotonic()
            
            # Scene is considered stable if many consecutive frames are stable
            stability_pct = 100.0 * stability_data["stable_frames"] / max(1, stability_data["stable_frames"] + stability_data["unstable_frames"])
        
        return {
            "is_stable": is_stable,
            "stability_percentage": min(100.0, stability_pct),
            "tracked_faces": tracked_faces_count,
            "recommended_cooldown_multiplier": (
                self.config.stable_scene_cooldown_multiplier if stability_pct > 80 else
                self.config.stability_cooldown_multiplier if is_stable else
                1.0
            ),
        }
