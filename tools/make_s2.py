"""Build the 1,764 generated S2 items (441 per category, depth 2).

S2 is every ordered length-2 tuple over the 21-probe alphabet, rendered by the
category renderers and assigned a harness by deterministic round-robin. Run:

    python tools/make_s2.py [--out data/generated] [--category Q]
"""

from __future__ import annotations

from tiergen import main

if __name__ == "__main__":
    main(2)
