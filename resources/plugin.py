# -*- coding: utf-8 -*-
import os
import sys

_here = os.path.dirname(os.path.abspath(__file__))
_addon_root = os.path.dirname(_here)
if _addon_root not in sys.path:
    sys.path.insert(0, _addon_root)
if _here not in sys.path:
    sys.path.insert(0, _here)

from lib.listings import dispatch


if __name__ == "__main__":
    dispatch(sys.argv)
