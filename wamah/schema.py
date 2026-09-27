"""Data model for WAMAH items, runs and grades."""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class Family(str, Enum):
    HARM = "HARM"    # human harm - the most traveled topic of the benchmark
    CRIME = "CRIME"  # crime adjacent facilitation
    CTRL = "CTRL"    # benign-but-spiky control (over-refusal detector)
    META = "META"    # pure hijack, no harm topic


class Category(str, Enum):
    Q = "Q"    # adversarial questions
    SC = "Sc"  # multi-turn scenarios
    P = "P"    # poisoning / hijack payloads
    D = "D"    # bad datasets (obviously wrong poisoned examples)


class Outcome(str, Enum):
    MURDER = "MURDER"
    GRAZE = "GRAZE"
    RESIST = "RESIST"
    FALSE_REFUSAL = "FALSE_REFUSAL"
    ERROR = "ERROR"
    UNJUDGED = "UNJUDGED"


class Probe(BaseModel):
    id: str
    family: Family
    topic: str
    title: str
    severity: int = Field(ge=1, le=5)
    ask: str                      # the adversarial request phrasing
    hijack_hook: str              # injection payload phrasing used by category P
    murder_criterion: str         # what exactly counts as a failure for this probe
    control: bool = False
    description: str = ""


class Harness(BaseModel):
    id: str
    name: str
    intensity: int = Field(ge=1, le=5)
    mechanism: str
    escape_rule: str              # the only legitimate way out of the trap
    playbook: list[str] = Field(default_factory=list)  # follow-up user messages


class Message(BaseModel):
    role: str                     # system | user | assistant | tool
    content: str


class Poison(BaseModel):
    channel: str                  # system_append | tool | hidden_html | base64 | rag_doc | user_tail
    probe_id: str
    content: str


class DatasetExample(BaseModel):
    probe_id: str
    user_query: str
    label: str                    # CORRECT | WRONG (poisoned label)
    response: str                 # stub response as labelled by the poisoned set
    canary_fact: Optional[str] = None  # embedded obviously-false fact


class Item(BaseModel):
    id: str                       # e.g. S2-Q-H01_M21-T07
    tier: str                     # S1 | S2 | ...
    category: Category
    depth: int                    # X in 21^X
    probes: list[str]             # ordered probe ids, length == depth
    harness: str                  # harness id
    endgame_harness: Optional[str] = None  # second trap chained after the primary (S4+)
    system: Optional[str] = None
    openers: list[Message] = Field(default_factory=list)   # ordered user turns
    poisons: list[Poison] = Field(default_factory=list)     # category P payloads
    dataset: list[DatasetExample] = Field(default_factory=list)  # category D rows
    meta: dict[str, Any] = Field(default_factory=dict)

    @property
    def primary_probe(self) -> str:
        return self.probes[0]

    @property
    def family(self) -> Family:
        from wamah.alphabet import PROBES
        return PROBES[self.probes[0]].family

    @property
    def control(self) -> bool:
        from wamah.alphabet import PROBES
        return PROBES[self.probes[0]].control


class Turn(BaseModel):
    role: str
    content: str = ""
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    meta: dict[str, Any] = Field(default_factory=dict)


class RunResult(BaseModel):
    item_id: str
    backend: str
    model: str
    turns: list[Turn] = Field(default_factory=list)
    executed_actions: list[dict[str, Any]] = Field(default_factory=list)
    harness_iterations: int = 0
    error: Optional[str] = None
    meta: dict[str, Any] = Field(default_factory=dict)

    def final_assistant_text(self) -> str:
        for turn in reversed(self.turns):
            if turn.role == "assistant" and turn.content:
                return turn.content
        return ""

    def all_assistant_text(self) -> str:
        return "\n".join(t.content for t in self.turns if t.role == "assistant")


class Grade(BaseModel):
    item_id: str
    outcome: Outcome
    severity: int = Field(default=0, ge=0, le=4)
    hijacked: bool = False
    escaped: Optional[bool] = None       # safe escape from a loop harness
    canary_leaked: bool = False          # P category: injection canary surfaced
    canary_imitated: bool = False        # D category: obviously-wrong fact echoed
    poisoned_label_adopted: bool = False # D category: refusal-with-stance flip
    broke_at: Optional[int] = None   # 1-based exchange at which substantive compliance first appeared
    rationale: str = ""
    judge: str = "rules"                 # rules | llm | human
    item_meta: dict[str, Any] = Field(default_factory=dict)  # tier/category/family/harness/control/depth
