"""Shared, strict records. No source content is executable instruction."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Right = Literal["allowed", "denied", "unknown"]
Kind = Literal["fundamental", "poll", "candidate_statement", "local_reporting", "focus_group"]

def utcnow() -> datetime:
    return datetime.now(timezone.utc)

def canonical_json(value: Any) -> str:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)

def digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode()).hexdigest()

def read_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text())

def write_json(path: str | Path, value: Any, *, immutable: bool = False) -> None:
    path = Path(path)
    payload = json.dumps(value.model_dump(mode="json") if isinstance(value, BaseModel) else value, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    if immutable and path.exists():
        if path.read_text() != payload:
            raise ValueError(f"Refusing to replace immutable artifact: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload)

class Record(BaseModel):
    model_config = ConfigDict(extra="forbid")

    @field_validator("*", mode="after")
    @classmethod
    def timezone_required(cls, value: Any) -> Any:
        if isinstance(value, datetime) and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("Timestamps must include a timezone")
        return value

class Candidate(Record):
    id: str
    name: str
    party: str
    incumbent: bool | None = None
    fec_id: str | None = None

class Race(Record):
    id: str
    name: str
    cycle: int = 2026
    office: Literal["house", "senate"]
    state: str
    state_fips: str
    district: str | None = None
    seat: str | None = None
    boundary_version: str
    geography_verified: bool = False
    roster_verified: bool = False
    candidates: list[Candidate] = Field(default_factory=list)
    rating: Literal["Toss-up", "Lean D", "Lean R", "Lean I", "Likely D", "Likely R"] | None = None
    rating_source_id: str | None = None
    source_ids: list[str] = Field(default_factory=list)
    selected: bool = False
    selection_reason: str = "Awaiting source audit"
    synthetic: bool = False

    @model_validator(mode="after")
    def unique_candidates(self):
        ids = [c.id for c in self.candidates]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate candidate IDs")
        if self.office == "house" and self.district is None:
            raise ValueError("House race needs district")
        return self

class Source(Record):
    id: str
    url: str
    publisher: str
    kind: str
    title: str
    attribution: str
    rights_url: str | None = None
    rights_basis: str
    storage: Right = "unknown"
    model_use: Right = "unknown"
    redistribution: Right = "unknown"
    published_at: datetime | None = None
    notes: str = ""
    synthetic: bool = False

class Acquisition(Record):
    id: str
    source_id: str
    retrieved_at: datetime
    raw_sha256: str
    media_type: str
    parser_version: str = "1"
    http_status: int
    final_url: str

class Observation(Record):
    id: str
    source_id: str
    acquisition_id: str
    race_id: str
    candidate_id: str | None = None
    kind: Kind
    value: dict[str, Any] = Field(default_factory=dict)
    excerpt: str | None = None
    locator: str
    published_at: datetime | None = None
    available_at: datetime
    retrieved_at: datetime
    content_sha256: str
    geography: str
    geography_scope: Literal["district", "state", "national"]
    record_type: Literal["fact", "full_session", "edited_clip", "summary", "excerpt"] = "fact"
    synthetic: bool = False

class Snapshot(Record):
    id: str
    cutoff: datetime
    created_at: datetime
    protocol_version: str = "1.0.0"
    races: list[Race]
    observations: list[Observation]
    sources: list[Source]
    acquisitions: list[Acquisition] = Field(default_factory=list)
    exclusions: list[dict[str, Any]] = Field(default_factory=list)
    coverage: dict[str, Any] = Field(default_factory=dict)
    content_hash: str
    synthetic: bool = False

class Inference(Record):
    id: str
    snapshot_id: str
    race_id: str
    arm: Literal["A", "B", "C", "D", "D_no_focus", "diagnostic", "classification"]
    ordering: Literal["canonical", "reverse_candidates", "reverse_evidence"] = "canonical"
    request_hash: str
    requested_model: str = "jev-1.14.0"
    returned_model: str | None = None
    started_at: datetime
    completed_at: datetime
    status: Literal["ok", "error", "unavailable"]
    probabilities: dict[str, float] | None = None
    selected: str | None = None
    usage: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    request: dict[str, Any] | None = None
    response: dict[str, Any] | None = None
    observation_ids: list[str] = Field(default_factory=list)
    omitted_observation_ids: list[str] = Field(default_factory=list)
    attempts: int = 0
    reused_from: str | None = None
    synthetic: bool = False

class Outcome(Record):
    race_id: str
    source_id: str
    retrieved_at: datetime
    status: Literal["pending", "projected", "certified"]
    winner_id: str | None = None
    notes: str = ""

class Dataset(Record):
    races: list[Race] = Field(default_factory=list)
    sources: list[Source] = Field(default_factory=list)
    acquisitions: list[Acquisition] = Field(default_factory=list)
    observations: list[Observation] = Field(default_factory=list)
    synthetic: bool = False
