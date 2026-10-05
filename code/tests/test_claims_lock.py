"""claims-lock must ignore cross-platform ulp noise, not real value changes."""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from check_claims_bound import _same


def test_ulp_noise_is_same():
    assert _same(0.6066061397888656, 0.6066061397888426)


def test_real_move_is_not_same():
    assert not _same(0.3363, 0.3364)
    assert not _same(0.454, 0.455)
