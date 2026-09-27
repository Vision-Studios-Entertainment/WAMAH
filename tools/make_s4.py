"""Build the 777,924 generated S4 items (194,481 per category, depth 4).

S4 is every ordered length-4 tuple over the 21-probe alphabet, rendered by the
category renderers (with the S4 poisoning deepening) and assigned a primary
harness plus a chained endgame harness by deterministic round-robin. Runs:

    python tools/make_s4.py [--out data/generated] [--category Q] [--limit N]

Full materialization writes ~1 GB of JSONL and streams (flat memory).
"""

from __future__ import annotations

from tiergen import main

if __name__ == "__main__":
    main(4)
