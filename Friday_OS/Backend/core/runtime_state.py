from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class StepStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


class PlanStep(BaseModel):
    step_id: int
    description: str
    status: StepStatus = StepStatus.QUEUED
    tool_name: Optional[str] = None
    tool_args: Dict[str, Any] = Field(default_factory=dict)
    observation: Optional[str] = None
    error: Optional[str] = None
    verification_check: Optional[str] = None


class TaskState(BaseModel):
    task_id: str
    goal: str
    current_step_id: int = 1
    plan: List[PlanStep] = Field(default_factory=list)
    constraints: List[str] = Field(default_factory=list)
    approval_state: str = "pending"  # approved, rejected, none
    cancellation_state: bool = False
    max_retries_per_step: int = 3
    retry_counts: Dict[int, int] = Field(default_factory=dict)  # step_id -> count
    plan_revisions: List[str] = Field(default_factory=list)  # tracks historical plan updates
    max_replans: int = 3
    final_result: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
