import unittest
import os
from unittest.mock import patch
from src.core.settings import SettingsManager
from src.audio.gpu_analyzer import BatchGpuAcousticEngine
from src.core.gpu_detector import GpuDetector, GpuInfo

class TestGpuToggle(unittest.TestCase):
    def setUp(self):
        self.settings = SettingsManager.get_instance()

    def test_engine_respects_settings(self):
        # 1. When GPU disabled in settings
        self.settings.set("performance", "gpu_acceleration", False)
        engine_cpu = BatchGpuAcousticEngine()
        self.assertFalse(engine_cpu.using_gpu)
        self.assertEqual(engine_cpu.device_type, "cpu")

        # 2. When explicit override passed
        engine_override = BatchGpuAcousticEngine(enable_gpu=False)
        self.assertFalse(engine_override.using_gpu)

        # 3. When GPU enabled in settings
        self.settings.set("performance", "gpu_acceleration", True)
        engine_gpu = BatchGpuAcousticEngine()
        info = GpuDetector.get_gpu_info()
        if info.is_available:
            self.assertTrue(engine_gpu.using_gpu)
            self.assertIn(engine_gpu.device_type, ["cuda", "directml", "mps"])
        else:
            self.assertFalse(engine_gpu.using_gpu)
            self.assertEqual(engine_gpu.device_type, "cpu")

if __name__ == "__main__":
    unittest.main()
