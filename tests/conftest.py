import sys
from unittest.mock import MagicMock

# External AI/ML deps are only available inside Docker.
# Mock them here so tests can import app modules without the full stack.
_MOCK_MODULES = [
    "langchain_google_genai",
    "langchain_core",
    "langchain_core.prompts",
    "langchain_core.output_parsers",
    "chromadb",
]

for _mod in _MOCK_MODULES:
    if _mod not in sys.modules:
        sys.modules[_mod] = MagicMock()
