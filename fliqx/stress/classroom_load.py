"""Classroom load simulation for stress testing."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator
import numpy as np

from ..video.stream import StreamFrame


@dataclass(slots=True)
class ClassroomConfig:
    """Configuration for simulated classroom."""
    num_students: int = 30
    num_desks: int = 30
    movement_intensity: float = 0.5
    occlusion_rate: float = 0.1
    lighting_variation: float = 0.15
    frame_width: int = 1280
    frame_height: int = 720
    seed: int | None = None


class ClassroomLoad:
    """Generate simulated or replay classroom video frames."""
    
    def __init__(self, config: ClassroomConfig | None = None):
        """Initialize classroom load generator.
        
        Args:
            config: Classroom configuration
        """
        self.config = config or ClassroomConfig()
        if self.config.seed is not None:
            np.random.seed(self.config.seed)
    
    def generate_synthetic_frame(self, frame_index: int) -> np.ndarray:
        """Generate a synthetic classroom frame with motion and variation.
        
        Args:
            frame_index: Current frame index
        
        Returns:
            RGB frame as numpy array
        """
        frame = np.ones(
            (self.config.frame_height, self.config.frame_width, 3),
            dtype=np.uint8,
        ) * 200
        
        # Add some variation to simulate lighting changes
        if frame_index % 100 == 0:
            intensity = 200 + int(20 * np.sin(frame_index / 50.0))
            frame[:] = np.clip(intensity, 180, 220)
        
        # Add some simple motion pattern
        for student_idx in range(self.config.num_students):
            # Simulate students at desk positions
            desk_x = (student_idx % 10) * 128
            desk_y = (student_idx // 10) * 150
            
            # Add motion
            motion = (frame_index + student_idx) * self.config.movement_intensity
            x = desk_x + int(20 * np.sin(motion * 0.02))
            y = desk_y + int(15 * np.cos(motion * 0.01))
            
            # Add simple face-like boxes
            size = 30
            x1, y1 = max(0, x), max(0, y)
            x2, y2 = min(self.config.frame_width, x + size), min(self.config.frame_height, y + size)
            
            if x2 > x1 and y2 > y1:
                # Add face-like pattern
                color = np.array([200, 150, 100], dtype=np.uint8)
                noise = np.random.randint(-20, 20, size=(y2-y1, x2-x1, 3), dtype=np.int16)
                face_patch = np.clip(color[np.newaxis, np.newaxis, :] + noise, 0, 255).astype(np.uint8)
                
                # Random occlusion
                if np.random.random() < self.config.occlusion_rate:
                    face_patch = np.clip(face_patch * 0.5, 0, 255).astype(np.uint8)
                
                frame[y1:y2, x1:x2, :] = face_patch
        
        # Add some noise for realism
        noise = np.random.randint(-5, 5, frame.shape, dtype=np.int16)
        frame = np.clip(frame.astype(np.int16) + noise, 0, 255).astype(np.uint8)
        
        return frame
    
    def stream_synthetic(self, num_frames: int) -> Iterator[StreamFrame]:
        """Generate a stream of synthetic frames.
        
        Args:
            num_frames: Number of frames to generate
        
        Yields:
            StreamFrame objects
        """
        for i in range(num_frames):
            frame = self.generate_synthetic_frame(i)
            yield StreamFrame(index=i, frame=frame)
    
    @staticmethod
    def load_video(video_path: str | Path, loop: bool = False) -> Iterator[StreamFrame]:
        """Load frames from a video file.
        
        Args:
            video_path: Path to video file
            loop: Whether to loop the video
        
        Yields:
            StreamFrame objects
        """
        from ..video.stream import VideoStream
        
        if loop:
            index = 0
            while True:
                for stream_frame in VideoStream(video_path):
                    yield StreamFrame(index=index, frame=stream_frame.frame)
                    index += 1
        else:
            for stream_frame in VideoStream(video_path):
                yield stream_frame


class ClassroomSceneAnalyzer:
    """Analyze classroom frame for stability metrics."""
    
    @staticmethod
    def detect_motion_level(frame: np.ndarray, prev_frame: np.ndarray | None = None) -> float:
        """Detect motion level in frame.
        
        Args:
            frame: Current frame
            prev_frame: Previous frame for motion calculation
        
        Returns:
            Motion level (0.0 to 1.0)
        """
        if prev_frame is None:
            return 0.5
        
        diff = np.abs(frame.astype(np.float32) - prev_frame.astype(np.float32)).mean()
        return min(1.0, diff / 255.0)
    
    @staticmethod
    def estimate_face_count(frame: np.ndarray) -> int:
        """Rough estimate of face count based on frame analysis.
        
        Args:
            frame: Frame to analyze
        
        Returns:
            Estimated number of faces
        """
        # Simple heuristic: count skin-colored regions
        # This is intentionally basic for stress testing purposes
        skin_lower = np.array([95, 40, 20])
        skin_upper = np.array([270, 220, 205])
        
        mask = np.all((frame >= skin_lower) & (frame <= skin_upper), axis=2)
        face_pixels = np.count_nonzero(mask)
        
        # Rough estimate: ~2000-3000 pixels per face
        estimated_faces = max(0, face_pixels // 2500)
        return estimated_faces
