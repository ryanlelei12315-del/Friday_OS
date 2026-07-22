"""
Tests for FridayAgent instantiation.
Uses mocking to avoid requiring actual LiveKit credentials.
"""

import os
import sys
from unittest.mock import patch

# Add backend to path
sys.path.insert(
    0, os.path.join(os.path.dirname(__file__), "..", "Friday_OS", "Backend")
)


class TestFridayAgent:
    """Test that FridayAgent can be instantiated with mocked dependencies."""

    @patch("main.initialize_memory")
    @patch("main.create_model")
    @patch("main.FRIDAY_SYSTEM_PROMPT", "Test system prompt")
    @patch("main.USER_UNDERSTANDING_LAYER", "Test understanding layer")
    @patch("main.FRIDAY_BEHAVIOR", "Test behavior")
    def test_agent_instantiation(self, mock_create_model, mock_initialize_memory):
        """Verify FridayAgent can be created without errors."""
        from main import FridayAgent

        agent = FridayAgent()
        assert agent is not None
        mock_initialize_memory.assert_called_once()

    @patch("main.initialize_memory")
    @patch("main.create_model")
    @patch("main.FRIDAY_SYSTEM_PROMPT", "Test system prompt")
    @patch("main.USER_UNDERSTANDING_LAYER", "Test understanding layer")
    @patch("main.FRIDAY_BEHAVIOR", "Test behavior")
    def test_agent_instructions_combined(
        self, mock_create_model, mock_initialize_memory
    ):
        """Verify agent instructions combine all prompt components."""
        from main import FridayAgent

        agent = FridayAgent()
        # The instructions should contain all three prompt parts
        assert "Test system prompt" in agent._instructions
        assert "Test understanding layer" in agent._instructions
        assert "Test behavior" in agent._instructions

    @patch("main.initialize_memory")
    @patch("main.create_model")
    @patch("main.FRIDAY_SYSTEM_PROMPT", "Test system prompt")
    @patch("main.USER_UNDERSTANDING_LAYER", "Test understanding layer")
    @patch("main.FRIDAY_BEHAVIOR", "Test behavior")
    def test_agent_has_tools(self, mock_create_model, mock_initialize_memory):
        """Verify agent is initialized with tools."""
        from main import FridayAgent

        agent = FridayAgent()
        assert hasattr(agent, "_tools")
        assert len(agent._tools) > 0
