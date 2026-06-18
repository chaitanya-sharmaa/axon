"""pytest configuration for the Axon bridge test suite.

Adds the ``bridge/`` directory to ``sys.path`` so that tests can import
production modules (``services.*``, ``core.*``, etc.) without needing the
package to be installed.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Resolve the ``bridge/`` directory (two levels up from this conftest.py)
# and prepend it to sys.path so that absolute imports like
# ``from services.token_optimizer import TokenOptimizer`` work in tests.
_BRIDGE_ROOT = Path(__file__).parent.parent.resolve()
if str(_BRIDGE_ROOT) not in sys.path:
    sys.path.insert(0, str(_BRIDGE_ROOT))
