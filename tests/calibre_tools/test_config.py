# tests/calibre_tools/test_config.py
import os
import pytest
import platform
from unittest.mock import patch, MagicMock


class TestConfig:
    """Test configuration settings and device detection"""

    def test_default_paths_exist(self):
        """Test that default paths are properly set"""
        from calibre_tools.config import (
            DEFAULT_CALIBRE_LIBRARY,
            DEFAULT_DATA_DIR,
            DEFAULT_EMBEDDING_FILE,
            DEFAULT_METADATA_FILE
        )

        assert DEFAULT_CALIBRE_LIBRARY is not None
        assert DEFAULT_DATA_DIR is not None
        assert DEFAULT_EMBEDDING_FILE is not None
        assert DEFAULT_METADATA_FILE is not None

        # Check that data directory was created
        assert os.path.exists(DEFAULT_DATA_DIR)

    def test_default_model_name(self):
        """Test that default model name is set"""
        from calibre_tools.config import DEFAULT_MODEL_NAME

        assert DEFAULT_MODEL_NAME == "all-MiniLM-L6-v2"

    def test_cache_settings(self):
        """Test cache refresh settings"""
        from calibre_tools.config import FORCE_REFRESH, CACHE_EXPIRY_DAYS

        assert isinstance(FORCE_REFRESH, bool)
        assert isinstance(CACHE_EXPIRY_DAYS, int)
        assert CACHE_EXPIRY_DAYS >= 0

    @patch.dict(os.environ, {"USE_CUDA": "1"})
    @patch("torch.cuda.is_available", return_value=True)
    def test_cuda_device_detection(self, mock_cuda):
        """Test CUDA device detection when available"""
        from calibre_tools.config import get_default_device

        device = get_default_device()
        assert device == "cuda"

    @patch("platform.system", return_value="Darwin")
    @patch("torch.backends.mps.is_available", return_value=True)
    @patch("torch.zeros", return_value=MagicMock())
    def test_mps_device_detection(self, mock_zeros, mock_mps, mock_platform):
        """Test MPS device detection on Mac"""
        from calibre_tools.config import get_default_device

        device = get_default_device()
        assert device == "mps"

    @patch("platform.system", return_value="Darwin")
    @patch("torch.backends.mps.is_available", return_value=True)
    @patch("torch.zeros", side_effect=RuntimeError("MPS not working"))
    def test_mps_fallback_to_cpu(self, mock_zeros, mock_mps, mock_platform):
        """Test MPS fallback to CPU when MPS fails"""
        from calibre_tools.config import get_default_device

        device = get_default_device()
        assert device == "cpu"

    @patch("platform.system", return_value="Linux")
    @patch("torch.cuda.is_available", return_value=False)
    def test_cpu_fallback(self, mock_cuda, mock_platform):
        """Test CPU fallback when no accelerator available"""
        from calibre_tools.config import get_default_device

        device = get_default_device()
        assert device == "cpu"

    @patch.dict(os.environ, {"FORCE_REFRESH": "1"})
    def test_force_refresh_env_var(self):
        """Test FORCE_REFRESH environment variable"""
        # Need to reload module to pick up env var
        import importlib
        import calibre_tools.config as config_module
        importlib.reload(config_module)

        from calibre_tools.config import FORCE_REFRESH
        assert FORCE_REFRESH is True

    @patch.dict(os.environ, {"CACHE_EXPIRY_DAYS": "14"})
    def test_cache_expiry_env_var(self):
        """Test CACHE_EXPIRY_DAYS environment variable"""
        # Need to reload module to pick up env var
        import importlib
        import calibre_tools.config as config_module
        importlib.reload(config_module)

        from calibre_tools.config import CACHE_EXPIRY_DAYS
        assert CACHE_EXPIRY_DAYS == 14
