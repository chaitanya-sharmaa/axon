"""Bridge application package.

This keeps intra-package absolute imports (e.g. core.*, services.*) working
when modules are imported via bridge.* from the workspace root.
"""

from pathlib import Path
import sys

_PKG_DIR = Path(__file__).resolve().parent
if str(_PKG_DIR) not in sys.path:
	sys.path.insert(0, str(_PKG_DIR))
