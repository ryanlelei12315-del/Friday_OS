from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ToolRiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ToolStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    DENIED = "denied"
    CANCELLED = "cancelled"
    INVALID_INPUT = "invalid_input"
    NOT_AVAILABLE = "not_available"


class ToolResult(BaseModel):
    status: ToolStatus
    observation: str = ""
    error: Optional[str] = None
    execution_time: Optional[float] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class FridayToolContract(BaseModel):
    name: str
    description: str
    version: str = "1.0.0"
    risk_level: ToolRiskLevel = ToolRiskLevel.LOW
    required_permissions: List[str] = Field(default_factory=list)
    timeout: float = 30.0
