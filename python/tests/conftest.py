"""pytest path 装配 — 保证 dingda_sidecar 可导入。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
