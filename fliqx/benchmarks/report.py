"""Enhanced benchmark reporting and export."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from datetime import datetime
import json
import csv

from .benchmark import BenchmarkResult


class BenchmarkReporter:
    """Generate reports from benchmark results."""
    
    def __init__(self, results: list[BenchmarkResult] | BenchmarkResult | None = None):
        """Initialize reporter.
        
        Args:
            results: Single or list of benchmark results
        """
        if results is None:
            self.results = []
        elif isinstance(results, list):
            self.results = results
        else:
            self.results = [results]
    
    def add_result(self, result: BenchmarkResult) -> None:
        """Add a benchmark result.
        
        Args:
            result: BenchmarkResult to add
        """
        self.results.append(result)
    
    def to_dict_list(self) -> list[dict[str, Any]]:
        """Convert results to list of dicts.
        
        Returns:
            List of result dictionaries
        """
        return [r.to_dict() for r in self.results]
    
    def to_json(self, pretty: bool = True) -> str:
        """Convert results to JSON string.
        
        Args:
            pretty: Whether to format JSON with indentation
        
        Returns:
            JSON string
        """
        if pretty:
            return json.dumps(self.to_dict_list(), indent=2)
        else:
            return json.dumps(self.to_dict_list())
    
    def save_json(self, path: str | Path) -> None:
        """Save results as JSON file.
        
        Args:
            path: Output file path
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(path, "w") as f:
            f.write(self.to_json(pretty=True))
    
    def save_csv(
        self,
        path: str | Path,
        include_header: bool = True,
        append: bool = False,
    ) -> None:
        """Save results as CSV file.
        
        Args:
            path: Output file path
            include_header: Whether to include header row
            append: Whether to append to existing file
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        if not self.results:
            return
        
        # Get all possible keys from all results
        all_keys = set()
        for result_dict in self.to_dict_list():
            all_keys.update(result_dict.keys())
        
        fieldnames = sorted(all_keys)
        mode = "a" if append else "w"
        file_exists = path.exists() and append
        
        with open(path, mode, newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            
            # Write header only if new file or include_header
            if not file_exists or (not append and include_header):
                writer.writeheader()
            
            for result_dict in self.to_dict_list():
                # Ensure all fields exist
                row = {k: result_dict.get(k, "") for k in fieldnames}
                writer.writerow(row)
    
    def get_summary(self) -> dict[str, Any]:
        """Get summary statistics.
        
        Returns:
            Summary statistics
        """
        if not self.results:
            return {}
        
        dict_results = self.to_dict_list()
        
        # Collect numeric values
        fps_values = [r["fps"] for r in dict_results if "fps" in r]
        latency_values = [r["per_call_ms"] for r in dict_results if "per_call_ms" in r]
        recognition_calls = [r["recognition_calls"] for r in dict_results]
        recognition_results = [r["recognition_results"] for r in dict_results]
        
        return {
            "num_benchmarks": len(self.results),
            "fps": {
                "min": min(fps_values) if fps_values else 0.0,
                "max": max(fps_values) if fps_values else 0.0,
                "avg": sum(fps_values) / len(fps_values) if fps_values else 0.0,
            },
            "latency_ms": {
                "min": min(latency_values) if latency_values else 0.0,
                "max": max(latency_values) if latency_values else 0.0,
                "avg": sum(latency_values) / len(latency_values) if latency_values else 0.0,
            },
            "total_recognition_calls": sum(recognition_calls),
            "total_recognition_results": sum(recognition_results),
        }
    
    def print_summary(self) -> None:
        """Print summary to console."""
        summary = self.get_summary()
        
        if not summary:
            print("No benchmark results to summarize")
            return
        
        print("\n" + "="*60)
        print("BENCHMARK SUMMARY")
        print("="*60)
        
        print(f"\nNumber of benchmarks: {summary['num_benchmarks']}")
        
        fps = summary['fps']
        print(f"\nFPS (frames per second):")
        print(f"  Min: {fps['min']:.2f}")
        print(f"  Max: {fps['max']:.2f}")
        print(f"  Avg: {fps['avg']:.2f}")
        
        latency = summary['latency_ms']
        print(f"\nLatency (ms per frame):")
        print(f"  Min: {latency['min']:.4f}")
        print(f"  Max: {latency['max']:.4f}")
        print(f"  Avg: {latency['avg']:.4f}")
        
        print(f"\nRecognition Operations:")
        print(f"  Total calls: {summary['total_recognition_calls']}")
        print(f"  Total results: {summary['total_recognition_results']}")
        
        print("\n" + "="*60 + "\n")


class BenchmarkHistoryManager:
    """Manage benchmark history for tracking regression."""
    
    def __init__(self, history_file: str | Path):
        """Initialize history manager.
        
        Args:
            history_file: Path to history CSV file
        """
        self.history_file = Path(history_file)
    
    def add_benchmark(self, result: BenchmarkResult) -> None:
        """Add benchmark result to history.
        
        Args:
            result: BenchmarkResult to add
        """
        reporter = BenchmarkReporter([result])
        reporter.save_csv(self.history_file, include_header=True, append=True)
    
    def get_history(self) -> list[dict[str, Any]]:
        """Get all historical benchmarks.
        
        Returns:
            List of benchmark dictionaries
        """
        if not self.history_file.exists():
            return []
        
        history = []
        with open(self.history_file, "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Convert numeric fields
                for key in ["fps", "per_call_ms", "cpu_percent", "gpu_percent", "rss_delta_mb"]:
                    if key in row and row[key]:
                        try:
                            row[key] = float(row[key])
                        except ValueError:
                            pass
                
                for key in ["iterations", "recognition_calls", "recognition_results", "queue_peak_size", "concurrent_streams", "stream_recoveries"]:
                    if key in row and row[key]:
                        try:
                            row[key] = int(row[key])
                        except ValueError:
                            pass
                
                history.append(row)
        
        return history
    
    def detect_regression(self, new_result: BenchmarkResult, tolerance_pct: float = 10.0) -> dict[str, Any]:
        """Detect performance regression.
        
        Args:
            new_result: New benchmark result
            tolerance_pct: Tolerance percentage for regression
        
        Returns:
            Dictionary with regression analysis
        """
        history = self.get_history()
        if not history:
            return {"regression_detected": False, "reason": "No history"}
        
        # Get latest baseline
        baseline = history[-1]
        
        regression_detected = False
        issues = []
        
        # Check FPS regression
        baseline_fps = baseline.get("fps", 0.0)
        new_fps = new_result.fps
        if baseline_fps > 0 and new_fps < baseline_fps * (1.0 - tolerance_pct / 100.0):
            regression_detected = True
            pct_drop = (1.0 - new_fps / baseline_fps) * 100.0
            issues.append(f"FPS regression: {pct_drop:.1f}% drop ({new_fps:.2f} vs {baseline_fps:.2f})")
        
        # Check latency regression
        baseline_latency = baseline.get("per_call_ms", 0.0)
        new_latency = new_result.per_call_ms
        if baseline_latency > 0 and new_latency > baseline_latency * (1.0 + tolerance_pct / 100.0):
            regression_detected = True
            pct_increase = (new_latency / baseline_latency - 1.0) * 100.0
            issues.append(f"Latency regression: {pct_increase:.1f}% increase ({new_latency:.4f} vs {baseline_latency:.4f} ms)")
        
        return {
            "regression_detected": regression_detected,
            "issues": issues,
            "baseline": baseline,
            "new_result": new_result.to_dict(),
        }
