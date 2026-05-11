"""FLIQ command-line interface for benchmarking and stress testing."""

from __future__ import annotations

import sys
import argparse
from pathlib import Path
from typing import Any

from .engine import Fliq
from .benchmarks.benchmark import benchmark_video, benchmark_classroom_video
from .benchmarks.report import BenchmarkReporter, BenchmarkHistoryManager
from .stress.stress_runner import StressTestRunner, StressTestConfig
from .stress.report import StressTestReport


def build_parser() -> argparse.ArgumentParser:
    """Build command-line argument parser.
    
    Returns:
        ArgumentParser instance
    """
    parser = argparse.ArgumentParser(
        prog="fliq",
        description="FLIQ: Production-grade classroom attendance infrastructure",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run benchmark on video
  fliq benchmark classroom.mp4
  
  # Run stress test with 10 classrooms for 5 minutes
  fliq stress --streams 10 --duration 5
  
  # Run stress test with synthetic data
  fliq stress --streams 5 --duration 2 --synthetic
  
  # Generate report from history
  fliq report history.csv
        """,
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # Benchmark command
    benchmark_parser = subparsers.add_parser("benchmark", help="Run benchmarks")
    benchmark_parser.add_argument(
        "video",
        nargs="?",
        help="Video file to benchmark (optional)",
    )
    benchmark_parser.add_argument(
        "--output",
        "-o",
        help="Output file for results (JSON or CSV)",
    )
    benchmark_parser.add_argument(
        "--mode",
        default="speed",
        choices=["speed", "balanced", "accuracy"],
        help="Engine mode",
    )
    benchmark_parser.add_argument(
        "--device",
        default="auto",
        help="Device (cpu, cuda, auto)",
    )
    benchmark_parser.add_argument(
        "--frame-skip",
        type=int,
        default=5,
        help="Frame skip value",
    )
    
    # Stress command
    stress_parser = subparsers.add_parser("stress", help="Run stress tests")
    stress_parser.add_argument(
        "--streams",
        type=int,
        default=5,
        help="Number of concurrent classroom streams",
    )
    stress_parser.add_argument(
        "--duration",
        type=float,
        default=5.0,
        help="Duration in minutes",
    )
    stress_parser.add_argument(
        "--fps",
        type=int,
        default=30,
        help="Target FPS for streams",
    )
    stress_parser.add_argument(
        "--synthetic",
        action="store_true",
        help="Use synthetic data instead of real video",
    )
    stress_parser.add_argument(
        "--output",
        "-o",
        help="Output file for results (JSON or CSV)",
    )
    stress_parser.add_argument(
        "--mode",
        default="speed",
        choices=["speed", "balanced", "accuracy"],
        help="Engine mode",
    )
    
    # Report command
    report_parser = subparsers.add_parser("report", help="Generate reports")
    report_parser.add_argument(
        "input",
        help="Input history or benchmark file",
    )
    report_parser.add_argument(
        "--output",
        "-o",
        help="Output file for report",
    )
    report_parser.add_argument(
        "--format",
        default="json",
        choices=["json", "csv", "summary"],
        help="Output format",
    )
    
    return parser


def cmd_benchmark(args: argparse.Namespace) -> int:
    """Run benchmark command.
    
    Args:
        args: Parsed arguments
    
    Returns:
        Exit code
    """
    try:
        engine = Fliq(
            mode=args.mode,
            device=args.device,
            frame_skip=args.frame_skip,
            adaptive_scheduler=True,
        )
        
        print("Initializing FLIQ engine...")
        
        if args.video:
            print(f"Running benchmark on video: {args.video}")
            result = benchmark_video(engine, args.video)
        else:
            print("Running benchmark on classroom detection...")
            result = benchmark_classroom_video(engine)
        
        reporter = BenchmarkReporter([result])
        
        # Print summary
        reporter.print_summary()
        
        # Save results if requested
        if args.output:
            output_path = Path(args.output)
            if output_path.suffix.lower() == ".csv":
                reporter.save_csv(output_path)
                print(f"Results saved to {output_path} (CSV)")
            else:
                reporter.save_json(output_path)
                print(f"Results saved to {output_path} (JSON)")
        
        return 0
    
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_stress(args: argparse.Namespace) -> int:
    """Run stress test command.
    
    Args:
        args: Parsed arguments
    
    Returns:
        Exit code
    """
    try:
        config = StressTestConfig(
            classrooms=args.streams,
            duration_minutes=args.duration,
            fps_target=args.fps,
            synthetic=args.synthetic,
            mode=args.mode,
        )
        
        print(f"Starting stress test...")
        print(f"  Classrooms: {config.classrooms}")
        print(f"  Duration: {config.duration_minutes} minutes")
        print(f"  FPS target: {config.fps_target}")
        print(f"  Mode: {config.mode}")
        
        engine = Fliq(
            mode=config.mode,
            adaptive_scheduler=True,
        )
        
        runner = StressTestRunner(engine=engine, config=config)
        metrics = runner.run()
        
        # Generate report
        report = StressTestReport(metrics)
        report.print_summary()
        
        # Save results if requested
        if args.output:
            output_path = Path(args.output)
            if output_path.suffix.lower() == ".csv":
                report.save_csv(output_path)
                print(f"Results saved to {output_path} (CSV)")
            else:
                report.save_json(output_path)
                print(f"Results saved to {output_path} (JSON)")
        
        # Calculate scores
        stability_score = report.get_stability_score()
        scalability_score = report.get_scalability_score()
        
        print(f"\nStability Score: {stability_score:.1f}/100")
        print(f"Scalability Score: {scalability_score:.1f}/100")
        
        return 0
    
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


def cmd_report(args: argparse.Namespace) -> int:
    """Generate report command.
    
    Args:
        args: Parsed arguments
    
    Returns:
        Exit code
    """
    try:
        input_path = Path(args.input)
        
        if not input_path.exists():
            print(f"Error: File not found: {input_path}", file=sys.stderr)
            return 1
        
        # Load results from file
        if input_path.suffix.lower() == ".csv":
            # Load CSV as benchmarks
            import csv
            from .benchmarks.benchmark import BenchmarkResult
            
            results = []
            with open(input_path, "r") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # Convert types
                    try:
                        result = BenchmarkResult(
                            iterations=int(row.get("iterations", 0)),
                            total_seconds=float(row.get("total_seconds", 0.0)),
                            per_call_ms=float(row.get("per_call_ms", 0.0)),
                            fps=float(row.get("fps", 0.0)),
                            recognition_calls=int(row.get("recognition_calls", 0)),
                            recognition_results=int(row.get("recognition_results", 0)),
                            cpu_percent=float(row.get("cpu_percent", 0.0)) if row.get("cpu_percent") else None,
                            gpu_percent=float(row.get("gpu_percent", 0.0)) if row.get("gpu_percent") else None,
                            rss_delta_mb=float(row.get("rss_delta_mb", 0.0)) if row.get("rss_delta_mb") else None,
                            queue_peak_size=int(row.get("queue_peak_size", 0)),
                            concurrent_streams=int(row.get("concurrent_streams", 0)),
                            stream_recoveries=int(row.get("stream_recoveries", 0)),
                        )
                        results.append(result)
                    except (ValueError, TypeError):
                        continue
            
            reporter = BenchmarkReporter(results)
        else:
            # Try loading as JSON
            import json
            from .benchmarks.benchmark import BenchmarkResult
            
            with open(input_path, "r") as f:
                data = json.load(f)
            
            # Handle single result or list
            if isinstance(data, dict):
                data = [data]
            
            results = []
            for item in data:
                try:
                    result = BenchmarkResult(**item)
                    results.append(result)
                except (ValueError, TypeError):
                    continue
            
            reporter = BenchmarkReporter(results)
        
        # Output report
        if args.format == "summary":
            reporter.print_summary()
        elif args.format == "csv":
            if args.output:
                reporter.save_csv(args.output)
            else:
                print(",".join(reporter.results[0].to_dict().keys()))
                for result in reporter.results:
                    print(",".join(str(v) for v in result.to_dict().values()))
        else:  # json
            if args.output:
                reporter.save_json(args.output)
            else:
                print(reporter.to_json())
        
        return 0
    
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


def main(argv: list[str] | None = None) -> int:
    """Main CLI entry point.
    
    Args:
        argv: Command-line arguments (defaults to sys.argv[1:])
    
    Returns:
        Exit code
    """
    parser = build_parser()
    args = parser.parse_args(argv)
    
    if not args.command:
        parser.print_help()
        return 0
    
    if args.command == "benchmark":
        return cmd_benchmark(args)
    elif args.command == "stress":
        return cmd_stress(args)
    elif args.command == "report":
        return cmd_report(args)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
