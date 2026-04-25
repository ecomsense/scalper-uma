import pytest


class TestTickRunner:
    def test_dummy_passes(self):
        """Simple test that always passes."""
        assert True

    def test_simple_assertion(self):
        """Simple test with assert."""
        assert 1 + 1 == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])