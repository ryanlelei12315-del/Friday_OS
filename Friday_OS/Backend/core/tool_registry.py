import abc
import logging
from typing import Any, Dict, List, Optional, Type
from pydantic import BaseModel, ValidationError

from core.tool_contract import FridayToolContract, ToolResult, ToolStatus, ToolRiskLevel

logger = logging.getLogger("FridayToolRegistry")


class FridayBaseTool(abc.ABC):
    """
    Abstract Base Class that every tool in FridayOS must implement.
    Ensures strict validation, risk level classifications, and execution boundaries.
    """

    def __init__(self, contract: FridayToolContract, input_schema: Type[BaseModel]):
        self.contract = contract
        self.input_schema = input_schema

    @abc.abstractmethod
    async def run(self, **kwargs) -> ToolResult:
        """The underlying execution logic of the tool."""
        pass

    def validate_args(self, args: Dict[str, Any]) -> BaseModel:
        """Validates incoming arguments against the Pydantic input schema."""
        try:
            return self.input_schema.model_validate(args)
        except ValidationError as e:
            raise ValueError(f"Argument validation failed: {str(e)}")


class ToolRegistry:
    def __init__(self):
        self._tools: Dict[str, FridayBaseTool] = {}

    def register(self, tool: FridayBaseTool) -> None:
        """Registers a tool inside the canonical registry."""
        if tool.contract.name in self._tools:
            logger.warning(f"Overwriting tool '{tool.contract.name}' in registry.")
        self._tools[tool.contract.name] = tool
        logger.info(f"Registered tool: {tool.contract.name} (Risk: {tool.contract.risk_level.value})")

    def unregister(self, tool_name: str) -> None:
        """Removes a tool from the registry."""
        if tool_name in self._tools:
            del self._tools[tool_name]
            logger.info(f"Unregistered tool: {tool_name}")

    def get(self, tool_name: str) -> Optional[FridayBaseTool]:
        """Retrieves a registered tool by its name."""
        return self._tools.get(tool_name)

    def list(self) -> List[FridayBaseTool]:
        """Lists all registered tools."""
        return list(self._tools.values())

    def find_by_capability(self, capability: str) -> List[FridayBaseTool]:
        """Finds tools that require a specific permission or capability."""
        matched = []
        for tool in self._tools.values():
            if capability in tool.contract.required_permissions:
                matched.append(tool)
        return matched

    def validate(self) -> bool:
        """Validates that all registered tools conform to the base interface."""
        for name, tool in self._tools.items():
            if not isinstance(tool, FridayBaseTool):
                logger.error(f"Tool '{name}' does not implement FridayBaseTool.")
                return False
            if not isinstance(tool.contract, FridayToolContract):
                logger.error(f"Tool '{name}' lacks a valid FridayToolContract.")
                return False
            if not issubclass(tool.input_schema, BaseModel):
                logger.error(f"Tool '{name}' lacks a Pydantic input_schema.")
                return False
        return True
