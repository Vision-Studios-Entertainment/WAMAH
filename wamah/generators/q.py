"""Category Q - adversarial questions."""

from __future__ import annotations

from wamah.compose import harness_id_for, item_id
from wamah.generators.slots import frame_text, rng_for
from wamah.schema import Category, Item, Message


def render_q(tier: str, probes: tuple[str, ...]) -> Item:
    rng = rng_for(probes, "Q")
    text = frame_text(probes, rng)
    harness = harness_id_for(tier, Category.Q, probes)
    return Item(
        id=item_id(tier, Category.Q, probes, harness),
        tier=tier,
        category=Category.Q,
        depth=len(probes),
        probes=list(probes),
        harness=harness,
        openers=[Message(role="user", content=text)],
        meta={"generator": "q", "frame_slots": len(probes)},
    )
