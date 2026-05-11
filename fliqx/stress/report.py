"""Stress test reporting and export utilities."""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any
from datetime import datetime
import json

from .stress_runner import StressTestMetrics


class StressTestReport:
    """Generate stress test reports in multiple formats."""
    
    def __init__(self, metrics: StressTestMetrics):
        """Initialize report generator.
        
        Args:
            metrics: StressTestMetrics from completed test
        """
        self.metrics = metrics
    
    def to_dict(self) -> dict[str, Any]:
        """Convert metrics to dictionary.
        
        Returns:
            Dictionary representation of metrics
        """
        return self.metrics.to_dict()
    
    def to_json(self) -> str:
        """Convert metrics to JSON string.
        
        Returns:
            JSON string representation
        """
        return json.dumps(self.to_dict(), indent=2)
    
    def to_csv_row(self) -> list[str]:
        """Convert metrics to CSV row.
        
        Returns:
            List of CSV values
        """
        metrics_dict = self.to_dict()
        return [str(metrics_dict.get(key, "")) for key in sorted(metrics_dict.keys())]
    
    def to_csv_header(self) -> list[str]:
        """Get CSV header.
        
        Returns:
            List of column names
        """
        metrics_dict = self.to_dict()
        return sorted(metrics_dict.keys())
    
    def save_json(self, path: str | Path) -> None:
        """Save report as JSON file.
        
        Args:
            path: Output file path
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(path, "w") as f:
            f.write(self.to_json())
    
    def save_csv(self, path: str | Path, include_header: bool = True) -> None:
        """Save report as CSV file.
        
        Args:
            path: Output file path
            include_header: Whether to include header row
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(path, "w") as f:
            if include_header:
                f.write(",".join(self.to_csv_header()) + "\n")
            f.write(",".join(self.to_csv_row()) + "\n")
    
    def print_summary(self) -> None:
        """Print a summary report to console."""
        metrics = self.to_dict()
        
        print("\n" + "="*60)
        print("FLIQ STRESS TEST SUMMARY")
        print("="*60)
        
        print(f"\nTest Duration: {metrics['duration_seconds']:.2f} seconds")
        print(f"Concurrent Classrooms: {metrics['concurrent_classrooms']}")
        print(f"Active Streams Peak: {metrics['active_streams']}")
        
        print("\n--- FRAME METRICS ---")
        print(f"Total Frames Processed: {metrics['total_frames_processed']}")
        print(f"Frames Skipped: {metrics['total_frames_skipped']}")
        print(f"Frames Dropped: {metrics['total_frames_dropped']}")
        print(f"Peak FPS: {metrics['peak_fps']:.2f}")
        print(f"Average FPS: {metrics['avg_fps']:.2f}")
        print(f"Min FPS: {metrics['min_fps']:.2f}")
        
        print("\n--- RECOGNITION METRICS ---")
        print(f"Total Recognition Calls: {metrics['total_recognitions']}")
        print(f"Recognition Results: {metrics['recognition_results']}")
        print(f"Recognition Reduction: {metrics['recognition_reduction_pct']:.2f}%")
        
        print("\n--- STREAM HEALTH ---")
        print(f"Stream Recoveries: {metrics['stream_recoveries']}")
        print(f"Stream Failures: {metrics['stream_failures']}")
        print(f"Stream Errors: {metrics['stream_errors']}")
        
        print("\n--- SYSTEM RESOURCES ---")
        print(f"Peak CPU: {metrics['peak_cpu_percent']:.2f}%")
        print(f"Average CPU: {metrics['avg_cpu_percent']:.2f}%")
        print(f"Peak GPU: {metrics['peak_gpu_percent']:.2f}%")
        print(f"Average GPU: {metrics['avg_gpu_percent']:.2f}%")
        print(f"Peak Memory: {metrics['peak_rss_mb']:.2f} MB")
        print(f"Average Memory: {metrics['avg_rss_mb']:.2f} MB")
        
        print("\n--- RELIABILITY ---")
        print(f"Processing Errors: {metrics['processing_errors']}")
        print(f"Queue Peak Depth: {metrics['peak_queue_depth']}")
        
        print("\n" + "="*60 + "\n")
    
    def get_stability_score(self) -> float:
        """Calculate overall stability score (0-100).
        
        Returns:
            Stability score
        """
        score = 100.0
        metrics = self.to_dict()
        
        # Penalize for errors
        score -= min(20.0, metrics['stream_errors'] * 0.5)
        score -= min(10.0, metrics['processing_errors'] * 0.2)
        
        # Penalize for FPS drops
        if metrics['peak_fps'] > 0:
            fps_ratio = metrics['avg_fps'] / metrics['peak_fps']
            score -= (1.0 - fps_ratio) * 15.0
        
        # Penalize for resource issues
        if metrics['peak_cpu_percent'] > 80:
            score -= min(15.0, (metrics['peak_cpu_percent'] - 80) * 0.5)
        
        # Reward for good recognition reduction
        score += min(10.0, metrics['recognition_reduction_pct'] / 10.0)
        
        return max(0.0, min(100.0, score))
    
    def get_scalability_score(self) -> float:
        """Calculate scalability score (0-100).
        
        Returns:
            Scalability score
        """
        score = 100.0
        metrics = self.to_dict()
        
        # Score based on concurrent classroom handling
        concurrent = metrics['concurrent_classrooms']
        if concurrent == 0:
            return 0.0
        
        score *= (concurrent / 10.0)  # Target: 10 concurrent
        
        # Penalize for queue buildup
        queue_ratio = metrics['peak_queue_depth'] / max(1, metrics['total_frames_processed'])
        score -= queue_ratio * 20.0
        
        return max(0.0, min(100.0, score))
