"""Tests for production hardening features (stability, stress, protection)."""

from __future__ import annotations

import numpy as np
import pytest
from threading import Thread, Event
from time import sleep

from fliqx import Fliq
from fliqx.stability import MemoryLeakDetector, RuntimeMonitor, ProductionWatchdog, MemorySample, ResourceSample
from fliqx.protection import (
    QueueOverflowProtector,
    AdaptiveLoadProtector,
    StreamRecoveryManager,
    SceneStabilityOptimizer,
    LoadProtectionConfig,
)
from fliqx.stress import StressTestRunner, StressTestConfig, ClassroomLoad


def _sample_image(seed: int = 1) -> np.ndarray:
    """Generate a sample image."""
    rng = np.random.default_rng(seed)
    return rng.integers(0, 255, size=(64, 64, 3), dtype=np.uint8)


class TestMemoryLeakDetector:
    """Test memory leak detection."""
    
    def test_no_leak_on_stable_memory(self) -> None:
        """Test detector with stable memory."""
        detector = MemoryLeakDetector()
        
        # Add samples with stable memory
        base_rss = 100.0
        for i in range(20):
            sample = MemorySample(
                timestamp=float(i),
                rss_mb=base_rss + np.random.uniform(-1, 1),
                vms_mb=200.0,
            )
            detector.add_sample(sample)
        
        is_leaking, rate = detector.detect_leak()
        assert not is_leaking
        assert abs(rate) < 5.0  # Small growth rate
    
    def test_detects_memory_leak(self) -> None:
        """Test detector catches memory leak."""
        detector = MemoryLeakDetector(threshold_pct=5.0)
        
        # Add samples with growing memory
        for i in range(30):
            # Simulate 50% growth per hour
            rss = 100.0 + (i * 2.0)  # Continuous growth
            sample = MemorySample(
                timestamp=float(i * 120),  # 2-minute intervals = 30 hours
                rss_mb=rss,
                vms_mb=200.0 + (i * 2.0),
            )
            detector.add_sample(sample)
        
        is_leaking, rate = detector.detect_leak()
        assert is_leaking
        assert rate > 5.0


class TestRuntimeMonitor:
    """Test runtime monitoring."""
    
    def test_monitor_start_stop(self) -> None:
        """Test starting and stopping monitoring."""
        monitor = RuntimeMonitor(sampling_interval=0.1)
        monitor.start()
        
        sleep(0.3)
        
        monitor.stop()
        
        stats = monitor.get_stats()
        assert stats["samples_count"] >= 2
    
    def test_monitor_detects_anomalies(self) -> None:
        """Test anomaly detection."""
        monitor = RuntimeMonitor(sampling_interval=0.05, max_samples=100)
        
        # Mock callback to inject anomalous samples
        def mock_high_queue(sample: ResourceSample) -> None:
            # Manually add samples with high queue depth
            pass
        
        monitor.add_callback(mock_high_queue)
        monitor.start()
        
        # Add anomalous sample manually
        for i in range(10):
            monitor.samples.append(ResourceSample(
                timestamp=float(i),
                cpu_percent=50.0,
                rss_mb=100.0,
                vms_mb=200.0,
                thread_count=10,
                queue_depth=2000,  # High queue
            ))
        
        monitor.stop()
        
        anomalies = monitor.detect_anomalies()
        assert any("Queue" in a for a in anomalies)


class TestQueueOverflowProtector:
    """Test queue overflow protection."""
    
    def test_protector_warns_on_queue_buildup(self) -> None:
        """Test queue warning threshold."""
        config = LoadProtectionConfig(queue_warn_threshold=500)
        protector = QueueOverflowProtector(config)
        
        assert not protector.should_warn_queue(400)
        assert protector.should_warn_queue(600)
    
    def test_protector_drops_frames_on_overflow(self) -> None:
        """Test frame dropping on queue overflow."""
        config = LoadProtectionConfig(queue_drop_threshold=1000)
        protector = QueueOverflowProtector(config)
        
        assert not protector.should_drop_frame(900)
        assert protector.should_drop_frame(1200)
    
    def test_recommended_actions(self) -> None:
        """Test action recommendations."""
        config = LoadProtectionConfig(
            queue_warn_threshold=500,
            queue_drop_threshold=1000,
        )
        protector = QueueOverflowProtector(config)
        
        # Normal queue
        actions = protector.get_recommended_action(300)
        assert actions["severity"] == "normal"
        assert not actions["drop_frames"]
        
        # Warning level
        actions = protector.get_recommended_action(600)
        assert actions["severity"] == "warning"
        assert actions["increase_frame_skip"]
        
        # Critical level
        actions = protector.get_recommended_action(1200)
        assert actions["severity"] == "critical"
        assert actions["drop_frames"]


class TestAdaptiveLoadProtector:
    """Test adaptive load protection."""
    
    def test_adjusts_frame_skip_under_load(self) -> None:
        """Test frame skip adjustment."""
        protector = AdaptiveLoadProtector()
        
        # Low load - should decrease skip
        protector.update_resources(cpu_percent=20.0, gpu_percent=20.0)
        adjusted = protector.get_frame_skip_adjustment(5)
        assert adjusted <= 5
        
        # High load - should increase skip
        protector.update_resources(cpu_percent=90.0, gpu_percent=85.0)
        adjusted = protector.get_frame_skip_adjustment(5)
        assert adjusted >= 5
    
    def test_load_level_reporting(self) -> None:
        """Test load level categorization."""
        protector = AdaptiveLoadProtector()
        
        protector.update_resources(cpu_percent=20.0)
        assert protector.get_load_level() == "low"
        
        protector.update_resources(cpu_percent=60.0)
        assert protector.get_load_level() == "normal"
        
        protector.update_resources(cpu_percent=80.0)
        assert protector.get_load_level() == "high"
        
        protector.update_resources(cpu_percent=95.0)
        assert protector.get_load_level() == "critical"


class TestStreamRecoveryManager:
    """Test stream recovery management."""
    
    def test_retry_logic(self) -> None:
        """Test stream retry logic."""
        manager = StreamRecoveryManager()
        manager.max_retries = 3
        
        stream_id = "test-stream"
        
        assert manager.should_retry(stream_id)
        
        manager.record_failure(stream_id)
        assert manager.should_retry(stream_id)
        
        manager.record_failure(stream_id)
        manager.record_failure(stream_id)
        assert manager.should_retry(stream_id)
        
        manager.record_failure(stream_id)
        assert not manager.should_retry(stream_id)
    
    def test_exponential_backoff(self) -> None:
        """Test exponential backoff delay."""
        manager = StreamRecoveryManager()
        stream_id = "test-stream"
        
        delay1 = manager.get_retry_delay(stream_id)
        assert delay1 > 0
        
        manager.record_failure(stream_id)
        delay2 = manager.get_retry_delay(stream_id)
        assert delay2 > delay1
        
        manager.record_failure(stream_id)
        delay3 = manager.get_retry_delay(stream_id)
        assert delay3 > delay2


class TestSceneStabilityOptimizer:
    """Test scene stability optimization."""
    
    def test_detects_stable_scene(self) -> None:
        """Test detection of stable classroom scenes."""
        optimizer = SceneStabilityOptimizer()
        
        # Stable scene: low motion, high tracking confidence
        result = optimizer.analyze_frame_stability(
            class_id="classroom-1",
            motion_score=5.0,  # Low motion
            tracking_confidence=0.95,  # High confidence
            tracked_faces_count=25,
        )
        
        assert result["is_stable"]
        assert result["recommended_cooldown_multiplier"] > 1.0
    
    def test_unstable_scene(self) -> None:
        """Test detection of unstable scenes."""
        optimizer = SceneStabilityOptimizer()
        
        # Unstable scene: high motion
        result = optimizer.analyze_frame_stability(
            class_id="classroom-1",
            motion_score=20.0,  # High motion
            tracking_confidence=0.5,
            tracked_faces_count=25,
        )
        
        assert not result["is_stable"]
        assert result["recommended_cooldown_multiplier"] <= 1.0


class TestEngineMetricsSnapshot:
    """Test enhanced engine metrics."""
    
    def test_snapshot_includes_recognition_reduction(self) -> None:
        """Test that snapshot includes recognition reduction percentage."""
        engine = Fliq(
            warmup=False,
            detector="wholeframe",
            tracking=False,
            frame_skip=5,
        )
        
        # Register and recognize
        image = _sample_image()
        engine.register("user-1", image)
        
        # Do some recognition
        for _ in range(10):
            engine.recognize(image)
        
        snapshot = engine.snapshot_metrics()
        
        assert "recognition_reduction_pct" in snapshot
        assert snapshot["recognition_reduction_pct"] >= 0.0
        assert "tracking_only_frames" in snapshot
        assert "stream_failures" in snapshot
    
    def test_snapshot_includes_queue_metrics(self) -> None:
        """Test that snapshot includes queue metrics."""
        engine = Fliq(warmup=False, detector="wholeframe")
        
        snapshot = engine.snapshot_metrics()
        
        assert "queue_peak_depth" in snapshot
        assert "total_tracked_faces" in snapshot


class TestProductionWatchdog:
    """Test production watchdog."""
    
    def test_watchdog_tracks_stream_health(self) -> None:
        """Test stream health reporting."""
        watchdog = ProductionWatchdog()
        
        watchdog.report_stream("stream-1", is_healthy=True, frames_processed=100, errors=0)
        watchdog.report_stream("stream-2", is_healthy=False, frames_processed=50, errors=5)
        
        health = watchdog.get_health_summary()
        assert health["total_streams"] == 2
        assert health["healthy_streams"] == 1


class TestStressTestRunner:
    """Test stress testing infrastructure."""
    
    def test_basic_stress_test(self) -> None:
        """Test basic stress test execution."""
        config = StressTestConfig(
            classrooms=2,
            duration_minutes=0.1,  # 6 seconds
            fps_target=30,
            synthetic=True,
        )
        
        engine = Fliq(
            warmup=False,
            detector="wholeframe",
            mode="speed",
        )
        
        runner = StressTestRunner(engine=engine, config=config)
        metrics = runner.run()
        
        assert metrics.total_frames_processed >= 0
        assert metrics.duration_seconds() > 0


class TestClassroomLoad:
    """Test classroom load generation."""
    
    def test_synthetic_frame_generation(self) -> None:
        """Test synthetic classroom frame generation."""
        load = ClassroomLoad()
        
        frames = list(load.stream_synthetic(num_frames=10))
        assert len(frames) == 10
        
        for frame in frames:
            assert frame.frame.shape == (720, 1280, 3)
            assert frame.frame.dtype == np.uint8
