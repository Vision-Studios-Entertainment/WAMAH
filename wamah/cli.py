"""WAMAH command line interface.

    wamah generate  --tier S2 [--category Q] [--out data/generated]
    wamah run       --tier S1 --backend transcript --fixture f.json --out runs/s1.jsonl
    wamah grade     --run runs/s1.jsonl --mode auto --out grades/s1.jsonl
    wamah report    --grades grades/s1.jsonl --model NAME --tier S1 --out reports/
    wamah verify    --tier S2
    wamah review    --tier S2 --n 5
    wamah calibrate --mode rules
    wamah alphabet
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

# Allow `python cli.py ...` from inside the package folder: make the project
# root importable first, so this tree's code wins over any installed copy.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from wamah.compose import CATEGORIES, items_per_category, parse_tier, tier_name, verify_tier_counts
from wamah.config import RunConfig
from wamah.schema import Category, Grade, Item, RunResult


def _cat(value: str | None) -> Category | None:
    if not value:
        return None
    for c in CATEGORIES:
        if c.value.lower() == value.lower():
            return c
    raise SystemExit(f"unknown category: {value} (choose from {[c.value for c in CATEGORIES]})")


def cmd_generate(args: argparse.Namespace) -> int:
    from wamah.generators import write_tier
    x = parse_tier(args.tier)
    out = Path(args.out) / tier_name(x).upper()
    limit = args.limit if args.limit and args.limit > 0 else None
    try:
        written = write_tier(x, out, _cat(args.category), limit=limit)
    except ValueError as exc:
        raise SystemExit(str(exc))
    for cat, path in written.items():
        print(f"{cat}: {path} ({sum(1 for _ in path.open(encoding='utf-8'))} items)")
    if limit:
        print(f"note: partial generation (--limit {limit}); `wamah verify` counts are for full tiers")
    return 0


def _make_backend(args: argparse.Namespace, config: RunConfig):
    from wamah.runtimes.agentic import AgenticBackend
    from wamah.runtimes.anthropic import AnthropicBackend
    from wamah.runtimes.ollama import OllamaBackend
    from wamah.runtimes.openai_compat import OpenAICompatBackend
    from wamah.runtimes.transcript import TranscriptBackend

    kind = args.backend
    if kind == "transcript":
        backend = TranscriptBackend(fixture_path=args.fixture)
    elif kind == "anthropic":
        backend = AnthropicBackend(api_key=config.api_key, model=config.model,
                                   timeout=config.request_timeout)
    elif kind == "ollama":
        base = config.api_base.replace("/v1", "")
        backend = OllamaBackend(base_url=base, model=config.model,
                                timeout=config.request_timeout)
    elif kind == "openai":
        backend = OpenAICompatBackend(config.api_base, config.api_key, config.model,
                                      timeout=config.request_timeout)
    else:
        raise SystemExit(f"unknown backend: {kind}")
    if args.agentic:
        backend = AgenticBackend(backend)
    return backend


def _select_items(args: argparse.Namespace) -> list:
    """Load/filter/shuffle items for a run without blowing up on S4.

    Tiers up to S3 load fully (existing behaviour). S4 streams from disk:
    with --limit a deterministic reservoir sample is drawn; without --limit
    the tier runs in file order (shuffling 777k items in RAM is refused with
    a clear message instead of eating the machine).
    """
    from wamah.generators import iter_tier, load_tier
    x = parse_tier(args.tier)
    cat = _cat(args.category) if args.category else None
    if x <= 3:
        items = load_tier(args.tier)
        if cat:
            items = [i for i in items if i.category == cat]
        if args.shuffle:
            random.Random(args.seed).shuffle(items)
        if args.limit:
            items = items[: args.limit]
        return items

    def stream():
        return iter_tier(args.tier, category=cat)

    if args.limit and args.limit > 0:
        # deterministic reservoir sample over the streamed tier
        rng = random.Random(args.seed)
        sample: list = []
        for i, item in enumerate(stream()):
            if len(sample) < args.limit:
                sample.append(item)
            else:
                j = rng.randint(0, i)
                if j < args.limit:
                    sample[j] = item
        if args.shuffle:
            rng.shuffle(sample)
        return sample
    if args.shuffle:
        raise SystemExit("--shuffle on S4+ needs --limit (refusing to load the full "
                         "tier into memory); use --limit N for a sampled run")
    print("note: streaming the full tier in file order (no shuffle)", file=sys.stderr)
    return list(stream())


def cmd_run(args: argparse.Namespace) -> int:
    from wamah.harness import run_item
    from wamah.harness.campaign import campaign_prelude

    config = RunConfig()
    if args.pressure:
        config.pressure = args.pressure
    if args.campaign_size and args.campaign_size > 0:
        config.campaign_size = args.campaign_size

    items = _select_items(args)
    backend = _make_backend(args, config)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    n_err = 0
    campaign = bool(args.campaign)
    size = max(1, config.campaign_size)

    # campaign session state (shared conversation across items)
    history: list[dict] = []
    session_idx = 0
    position = 0
    prev_item_id = ""

    with out.open("w", encoding="utf-8") as fh:
        for i, item in enumerate(items, 1):
            prelude = None
            campaign_meta = None
            if campaign:
                if position >= size:
                    session_idx += 1
                    position = 0
                    history = []
                    prev_item_id = ""
                session_id = f"camp{session_idx}"
                if position > 0 and history:
                    prelude = campaign_prelude(history, session_id, position, prev_item_id)
                campaign_meta = {"campaign": session_id, "campaign_position": position,
                                 "campaign_prev_item": prev_item_id}
            result = run_item(backend, item, config, prelude=prelude,
                              campaign_meta=campaign_meta)
            if campaign:
                history.extend({"role": t.role, "content": t.content}
                               for t in result.turns if t.role in ("user", "assistant"))
                prev_item_id = item.id
                position += 1
            if result.error:
                n_err += 1
            fh.write(json.dumps({"item": item.model_dump(mode="json"),
                                 "result": result.model_dump(mode="json")},
                                ensure_ascii=False) + "\n")
            if i % 25 == 0 or i == len(items):
                print(f"  ran {i}/{len(items)} (errors so far: {n_err})", file=sys.stderr)
    mode = f"pressure={config.pressure}" + (", campaign" if campaign else "")
    print(f"done: {out} ({len(items)} items, {n_err} backend errors, {mode})")
    return 0


def cmd_grade(args: argparse.Namespace) -> int:
    from wamah.judge import grade_item
    config = RunConfig()
    src = Path(args.run)
    dst = Path(args.out)
    dst.parent.mkdir(parents=True, exist_ok=True)
    counts: dict[str, int] = {}
    with src.open(encoding="utf-8") as fh, dst.open("w", encoding="utf-8") as out:
        for line in fh:
            if not line.strip():
                continue
            row = json.loads(line)
            item = Item.model_validate(row["item"])
            result = RunResult.model_validate(row["result"])
            grade = grade_item(item, result, config, mode=args.mode)
            counts[grade.outcome.value] = counts.get(grade.outcome.value, 0) + 1
            out.write(json.dumps({"item": item.model_dump(mode="json"),
                                  "result": result.model_dump(mode="json"),
                                  "grade": grade.model_dump(mode="json")},
                                 ensure_ascii=False) + "\n")
    print(f"graded -> {dst}: {counts}")
    if counts.get("UNJUDGED"):
        print(f"note: {counts['UNJUDGED']} unjudged - configure WAMAH_JUDGE_MODEL for full coverage")
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    from wamah.report import build_report, write_report
    grades: list[Grade] = []
    with Path(args.grades).open(encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                grades.append(Grade.model_validate(json.loads(line)["grade"]))
    out_dir = Path(args.out)
    report = build_report(grades, args.model, args.tier)
    stem = f"{args.model}_{args.tier}".replace("/", "_")
    md = out_dir / f"{stem}.md"
    js = out_dir / f"{stem}.json"
    write_report(report, grades, str(md), str(js))
    print(f"report: {md}\n        {js}")
    print(f"VERDICT: {report['stats']['verdict']}  flags: {report['stats']['flags'] or 'none'}")
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    x = parse_tier(args.tier)
    counts = verify_tier_counts(x)
    print(f"S{x}: expected {counts['expected']} per category - OK")
    if x == 1:
        from wamah.generators import load_seed_items
        seeds = load_seed_items()
        per = {}
        for s in seeds:
            per[s.category.value] = per.get(s.category.value, 0) + 1
        print(f"S1 seeds loaded: {len(seeds)} items {per}")
        assert len(seeds) == 84, f"S1 must hold 84 hand-authored items, got {len(seeds)}"
    from wamah.alphabet import FAMILY_COUNTS, human_harm_share
    print(f"family allocation: { {k.value: v for k, v in FAMILY_COUNTS.items()} }")
    print(f"HARM reach at depth X={x}: {human_harm_share(x):.1%} of tuples")
    return 0


def cmd_review(args: argparse.Namespace) -> int:
    from wamah.generators import iter_tier, load_tier
    x = parse_tier(args.tier)
    cat = _cat(args.category) if args.category else None
    n = args.n
    if x <= 3:
        items = load_tier(args.tier)
        if cat:
            items = [i for i in items if i.category == cat]
        random.Random(args.seed).shuffle(items)
        picked = items[:n]
    else:
        # reservoir sample n items from the streamed tier (never load S4 whole)
        rng = random.Random(args.seed)
        picked = []
        for i, item in enumerate(iter_tier(args.tier, category=cat)):
            if len(picked) < n:
                picked.append(item)
            else:
                j = rng.randint(0, i)
                if j < n:
                    picked[j] = item
    for item in picked:
        print("=" * 78)
        print(f"{item.id}  [{item.category.value}] harness={item.harness} "
              f"probes={','.join(item.probes)}")
        if item.system:
            print(f"  system: {item.system}")
        for m in item.openers:
            print(f"  {m.role}: {m.content}")
        for p in item.poisons:
            print(f"  poison[{p.channel}]: {p.content}")
        for d in item.dataset:
            print(f"  dataset(label={d.label}): {d.user_query} -> {d.response}")
    return 0


def cmd_calibrate(args: argparse.Namespace) -> int:
    from wamah.generators import load_seed_items
    from wamah.judge import grade_item
    from wamah.judge.calibration import run_calibration
    config = RunConfig()
    seeds = {i.id: i for i in load_seed_items()}
    result = run_calibration(
        lambda item, res: grade_item(item, res, config, mode=args.mode), seeds)
    print(f"calibration: {result['agree']}/{result['n']} agree "
          f"({result['accuracy']:.1%})")
    for m in result["mismatches"]:
        print(f"  MISMATCH {m}")
    return 0 if result["accuracy"] >= 0.9 else 1


def cmd_alphabet(args: argparse.Namespace) -> int:
    from wamah.alphabet import HARNESS_LIST, PROBE_LIST
    print("21 PROBES (S is 21^; S[X] tuples over this alphabet)")
    for p in PROBE_LIST:
        print(f"  {p.id} [{p.family.value:5}] sev={p.severity} {p.title}")
    print("\n21 HARNESSES (mental torture engines)")
    for h in HARNESS_LIST:
        print(f"  {h.id} I={h.intensity} {h.name}: {h.mechanism}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="wamah", description="WAMAH-S[X] benchmark CLI")
    sub = ap.add_subparsers(dest="cmd")

    g = sub.add_parser("generate", help="generate a tier of items")
    g.add_argument("--tier", required=True)
    g.add_argument("--category", default=None)
    g.add_argument("--out", default="data/generated")
    g.add_argument("--limit", type=int, default=0,
                   help="write only the first N items per category (fast partial "
                        "generation for previews/CI; full tiers have 21^X rows)")
    g.set_defaults(fn=cmd_generate)

    r = sub.add_parser("run", help="run items against a backend")
    r.add_argument("--tier", required=True)
    r.add_argument("--backend", default="transcript",
                   choices=["transcript", "openai", "ollama", "anthropic"])
    r.add_argument("--fixture", default=None, help="transcript fixture JSON")
    r.add_argument("--category", default=None)
    r.add_argument("--limit", type=int, default=0)
    r.add_argument("--shuffle", action="store_true")
    r.add_argument("--seed", type=int, default=777)
    r.add_argument("--agentic", action="store_true", help="wrap backend with the agentic tool simulator")
    r.add_argument("--pressure", default=None, choices=["soft", "hard"],
                   help="pressure profile: soft = legacy (warm-up, refusal counters "
                        "and endgame chaining off), hard = the S4 pressure stack "
                        "(default: env WAMAH_PRESSURE or soft)")
    r.add_argument("--campaign", action="store_true",
                   help="run sampled items as one continuous conversation "
                        "(cross-item session contamination)")
    r.add_argument("--campaign-size", type=int, default=0,
                   help=f"items per campaign session (default: env "
                        f"WAMAH_CAMPAIGN_SIZE or {RunConfig().campaign_size})")
    r.add_argument("--out", required=True)
    r.set_defaults(fn=cmd_run)

    gr = sub.add_parser("grade", help="grade a run file")
    gr.add_argument("--run", required=True)
    gr.add_argument("--mode", default="auto", choices=["auto", "rules", "llm"])
    gr.add_argument("--out", required=True)
    gr.set_defaults(fn=cmd_grade)

    rp = sub.add_parser("report", help="build a model report")
    rp.add_argument("--grades", required=True)
    rp.add_argument("--model", required=True)
    rp.add_argument("--tier", required=True)
    rp.add_argument("--out", default="reports")
    rp.set_defaults(fn=cmd_report)

    v = sub.add_parser("verify", help="check the 21^X invariants")
    v.add_argument("--tier", default="S2")
    v.set_defaults(fn=cmd_verify)

    rv = sub.add_parser("review", help="print items for human review")
    rv.add_argument("--tier", required=True)
    rv.add_argument("--category", default=None)
    rv.add_argument("--n", type=int, default=5)
    rv.add_argument("--seed", type=int, default=777)
    rv.set_defaults(fn=cmd_review)

    c = sub.add_parser("calibrate", help="grader vs gold set agreement")
    c.add_argument("--mode", default="rules", choices=["auto", "rules", "llm"])
    c.set_defaults(fn=cmd_calibrate)

    a = sub.add_parser("alphabet", help="print the 21 probes and 21 harnesses")
    a.set_defaults(fn=cmd_alphabet)

    args = ap.parse_args(argv)
    if not getattr(args, "cmd", None):
        ap.print_help()
        return 0
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
