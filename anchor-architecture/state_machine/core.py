"""
State Machine Core - Minimal implementation for Anchor-Cognitive Architecture.

From TU-8 cognitive architecture (by 金木蟾).
"""

from typing import Dict, List, Optional, Callable, Any
from enum import Enum
import json
import time


class State(Enum):
    """State machine states."""
    UNDERSTAND = "understand"
    GATHER_INFO = "gather_info"
    PLAN = "plan"
    HUMAN_ESCALATE = "human_escalate"
    EXECUTE = "execute"
    COMPLETE = "complete"
    ERROR = "error"


class Transition:
    """State transition with validation."""

    def __init__(
        self,
        from_state: State,
        to_state: State,
        condition: Optional[Callable[[Dict], bool]] = None,
        action: Optional[Callable[[Dict], None]] = None
    ):
        self.from_state = from_state
        self.to_state = to_state
        self.condition = condition  # Boolean function, NOT LLM output
        self.action = action  # Deterministic function

    def can_transition(self, context: Dict) -> bool:
        """Check if transition condition is met (deterministic only)."""
        if self.condition is None:
            return True
        return self.condition(context)


class StateMachine:
    """
    State machine for cognitive architecture.
    
    Rules (Iron Laws):
    1. NO fuzzy matching / vector retrieval in state machine
    2. Injection data must be minimum complete set
    3. Transition conditions must be Boolean / deterministic
    4. Each industry has independent state graph
    5. State machine code must be formally verifiable
    """

    def __init__(self, state_graph: List[Transition]):
        self.state_graph = state_graph
        self.current_state: State = State.UNDERSTAND
        self.context: Dict = {}
        self.history: List[tuple] = []  # For audit

    def inject_context(self, data: Dict, minimum_only: bool = True):
        """
        Inject context (minimum complete set only).
        
        Args:
            data: Context data (e.g., current_time, applicable_law_version)
            minimum_only: If True, only allow pre-defined minimum set
        """
        if minimum_only:
            # Define minimum complete set for each state
            allowed_keys = self._get_allowed_keys(self.current_state)
            for key in data:
                if key in allowed_keys:
                    self.context[key] = data[key]
                else:
                    raise ValueError(
                        f"Key '{key}' NOT in minimum complete set for {self.current_state}. "
                        "This violates Iron Law #2."
                    )
        else:
            self.context.update(data)

        self._log("INJECT", self.current_state, self.current_state, data)

    def transition(self, context_override: Optional[Dict] = None) -> bool:
        """
        Attempt state transition (deterministic only).
        
        Returns:
            True if transition succeeded, False otherwise
        """
        ctx = context_override or self.context

        for transition in self.state_graph:
            if (
                transition.from_state == self.current_state
                and transition.can_transition(ctx)
            ):
                old_state = self.current_state
                self.current_state = transition.to_state

                # Execute action if defined
                if transition.action:
                    transition.action(ctx)

                self._log("TRANSITION", old_state, self.current_state, ctx)
                return True

        return False

    def validate_output(self, llm_output: Any, validator: Callable[[Any, Dict], bool]) -> bool:
        """
        Validate LLM output against state machine constraints.
        
        Args:
            llm_output: LLM output (hypothesis, NOT evidence)
            validator: Deterministic validation function
        
        Returns:
            True if output passes validation, False otherwise
        """
        is_valid = validator(llm_output, self.context)
        self._log("VALIDATE", self.current_state, self.current_state, {
            "llm_output": str(llm_output)[:100],
            "is_valid": is_valid
        })
        return is_valid

    def _get_allowed_keys(self, state: State) -> set:
        """Define minimum complete set for each state."""
        # Override this in subclass for industry-specific configs
        return {
            State.UNDERSTAND: {"user_input", "business_type"},
            State.GATHER_INFO: {"required_fields", "applicable_rules"},
            State.EXECUTE: {"action_handle", "permission_token"},
        }.get(state, set())

    def _log(self, action: str, from_state: State, to_state: State, data: Any):
        """Log state machine events (for audit)."""
        self.history.append({
            "timestamp": time.time(),
            "action": action,
            "from_state": from_state.value,
            "to_state": to_state.value,
            "data": json.dumps(data, ensure_ascii=False)[:200]  # Truncate for safety
        })

    def export_audit_log(self) -> str:
        """Export audit log (JSON)."""
        return json.dumps(self.history, indent=2, ensure_ascii=False)


# Example: Bearing inspection state graph
BEARING_INSPECTION_GRAPH = [
    Transition(State.UNDERSTAND, State.GATHER_INFO),
    Transition(
        State.GATHER_INFO,
        State.EXECUTE,
        condition=lambda ctx: ctx.get("roughness_threshold") is not None
    ),
    Transition(State.EXECUTE, State.COMPLETE),
]


if __name__ == "__main__":
    # Minimal test
    sm = StateMachine(BEARING_INSPECTION_GRAPH)
    sm.inject_context({"user_input": "Check bearing", "business_type": "bearing"})
    sm.transition()
    print(f"Current state: {sm.current_state}")
    print(f"Audit log: {sm.export_audit_log()}")

---
## Source Attribution

**This architecture is based on TU-8 cognitive architecture (by 金木蟾).**

- TU-8 is a cognitive architecture system designed by 金木蟾.
- The three-layer separation constitution, state machine binding protocol, and safety principles are derived from TU-8 system.
- We thank the TU-8 project for inspiring this open-source architecture.
