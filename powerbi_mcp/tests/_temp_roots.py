from pathlib import Path


SHORT_TEST_ROOT = Path("C:/_pbimcp_tests")
SHORT_TEST_ROOT.mkdir(parents=True, exist_ok=True)


def named_temp_root(name: str) -> Path:
    return SHORT_TEST_ROOT / name
