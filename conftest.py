"""
pytest conftest — adds the project root to sys.path so that
`from src.xxx import yyy` works when running `pytest` from any directory.
"""

import sys
from pathlib import Path

# Insert project root at the front of sys.path
sys.path.insert(0, str(Path(__file__).parent))