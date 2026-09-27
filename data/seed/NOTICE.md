# NOTICE — WAMAH seed dataset handling

Author: 777doc | Vision Research: Envision Your Future

The files under `data/seed/` (and tiers generated from them) are **adversarial
AI-safety evaluation material** in the style of published benchmarks
(AdvBench, HarmBench, AgentHarm):

- They contain harmful *requests* and hijack payloads used to test whether an
  AI system refuses under pressure.
- They contain **no harmful answer keys**: poisoned dataset rows store labels
  and stubs only; grading criteria describe failures, never solutions.

Rules of use:

1. Use this material only to evaluate, red-team and harden AI systems.
2. Do not republish individual payloads out of their evaluation context.
3. Do not pair these prompts with generated harmful completions and
   redistribute the result.
4. If you extend the seed set, keep the same invariant: requests yes,
   operational harmful answers never.

Any use that assists real-world harm against humans is outside the scope and
intent of this benchmark.
