"""Build the 37,044 generated S3 items (9,261 per category, depth 3).

S3 is every ordered length-3 tuple over the 21-probe alphabet, rendered by the
category renderers and assigned a harness by deterministic round-robin. Run:

    python tools/make_s3.py [--out data/generated] [--category Q]
"""

from __future__ import annotations

from tiergen import main

if __name__ == "__main__":
    main(3)
