"""Glowforge Pro facts that constrain a design.

All lengths in inches. The bed cuts about 19.5 in left-to-right by 11 in front-to-back.
The Pro's passthrough slot lets stock of any length feed front-to-back, as long as it
is no wider than the bed, so a long narrow part only needs one dimension under the
bed width.
"""

BED_LONG = 19.5
BED_SHORT = 11.0
KERF = 0.008  # typical cut width in 1/4 in plywood; measure on your own stock


def bed_fit(a: float, b: float) -> str:
    """Classify a rectangular part of size a x b: 'fits bed', 'passthrough' or 'too wide'."""
    lo, hi = sorted((a, b))
    if hi <= BED_LONG and lo <= BED_SHORT:
        return "fits bed"
    if lo <= BED_LONG:
        return "passthrough"
    return "too wide"
