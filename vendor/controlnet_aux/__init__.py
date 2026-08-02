import os
import sys
from pathlib import Path

os.environ.setdefault('NPU_DEVICE_COUNT', '0')
os.environ.setdefault('MMCV_WITH_OPS', '0')
_root = Path(__file__).resolve().parent
for _path in (_root / 'src', _root / 'src' / 'custom_controlnet_aux', _root / 'src' / 'custom_mmpkg'):
    _text = str(_path)
    if _text not in sys.path:
        sys.path.append(_text)
