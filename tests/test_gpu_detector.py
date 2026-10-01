"""
Unit tests for GPU Detection, PyTorch/MPS/DirectML detection and transparent CPU fallback.
"""

import unittest
from src.core.gpu_detector import GpuDetector, GpuBackend, GpuInfo
from src.audio.gpu_analyzer import BatchGpuAcousticEngine


class TestGpuDetector(unittest.TestCase):
    """Tests hardware detection logic."""

    def test_get_gpu_info_returns_valid_object(self):
        """GpuDetector.get_gpu_info should return a valid GpuInfo instance without crashing."""
        info = GpuDetector.get_gpu_info()
        self.assertIsInstance(info, GpuInfo)
        self.assertIsInstance(info.name, str)
        self.assertIsInstance(info.backend, str)
        self.assertIn(info.backend, [GpuBackend.CUDA, GpuBackend.MPS, GpuBackend.DIRECTML, GpuBackend.CPU])
        self.assertIsInstance(info.memory_total_mb, int)
        self.assertIsInstance(info.is_available, bool)

    def test_get_best_device_name(self):
        """get_best_device should return 'cuda', 'mps', or 'cpu'."""
        device_str = GpuDetector.get_best_device()
        self.assertIn(device_str, ["cuda", "mps", "cpu"])

    def test_directml_and_mps_check_no_error(self):
        """DirectML and Apple Silicon queries should safely return booleans."""
        dml = GpuDetector.is_directml_available()
        self.assertIsInstance(dml, bool)
        mps = GpuDetector.is_mps_available()
        self.assertIsInstance(mps, bool)


class TestBatchGpuAcousticEngine(unittest.TestCase):
    """Tests batch GPU acoustic engine with CPU fallback."""

    def test_engine_initialization(self):
        """Engine should initialize with CPU fallback when GPU is disabled or unavailable."""
        engine = BatchGpuAcousticEngine(prefer_gpu=False)
        self.assertEqual(engine.device_type, "cpu")
        self.assertFalse(engine.using_gpu)

    def test_batch_analyze_handles_empty_or_missing(self):
        """Engine handles missing or empty paths gracefully without raising unhandled exceptions."""
        engine = BatchGpuAcousticEngine(prefer_gpu=False)
        results = engine.analyze_batch(["non_existent_path.wav"])
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].filepath, "non_existent_path.wav")
        self.assertFalse(results[0].success)


if __name__ == "__main__":
    unittest.main()
