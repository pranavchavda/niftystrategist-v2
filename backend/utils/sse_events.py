"""
Custom SSE event utilities for enhanced user feedback
"""

import json
from typing import Any, Dict, Optional
from datetime import datetime, timezone


class SSEEventEmitter:
    """Helper class to emit custom SSE events during agent processing"""

    @staticmethod
    def format_event(event_type: str, data: Dict[str, Any]) -> str:
        """Format an event for SSE transmission"""
        event = {
            "type": event_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **data
        }
        return f"data: {json.dumps(event)}\n\n"

    @staticmethod
    def agent_routing(agent_name: Optional[str] = None) -> str:
        """Emit agent routing event"""
        return SSEEventEmitter.format_event("AGENT_ROUTING", {
            "message": "Determining the best agent for your request",
            "agent": agent_name
        })

    @staticmethod
    def agent_selected(agent_name: str, reason: Optional[str] = None) -> str:
        """Emit agent selected event"""
        return SSEEventEmitter.format_event("AGENT_SELECTED", {
            "agent": agent_name,
            "message": f"Delegating to {agent_name} agent",
            "reason": reason
        })

    @staticmethod
    def thinking(context: Optional[str] = None) -> str:
        """Emit thinking/processing event"""
        return SSEEventEmitter.format_event("THINKING", {
            "message": "Analyzing your request",
            "context": context
        })

    @staticmethod
    def tool_progress(tool_name: str, progress: float, message: Optional[str] = None) -> str:
        """Emit tool execution progress"""
        return SSEEventEmitter.format_event("TOOL_PROGRESS", {
            "tool": tool_name,
            "progress": progress,  # 0.0 to 1.0
            "message": message
        })

    @staticmethod
    def searching(query: str, source: Optional[str] = None) -> str:
        """Emit searching event"""
        return SSEEventEmitter.format_event("SEARCHING", {
            "query": query,
            "source": source,
            "message": f"Searching for {query}"
        })

    @staticmethod
    def analyzing(data_type: str, count: Optional[int] = None) -> str:
        """Emit analyzing event"""
        return SSEEventEmitter.format_event("ANALYZING", {
            "data_type": data_type,
            "count": count,
            "message": f"Analyzing {data_type}"
        })

    @staticmethod
    def writing() -> str:
        """Emit writing/composing event"""
        return SSEEventEmitter.format_event("WRITING", {
            "message": "Composing response"
        })

    @staticmethod
    def error(error_message: str, recoverable: bool = True) -> str:
        """Emit error event"""
        return SSEEventEmitter.format_event("ERROR", {
            "message": error_message,
            "recoverable": recoverable
        })

    @staticmethod
    def latency_warning(elapsed_seconds: int) -> str:
        """Emit latency warning"""
        if elapsed_seconds > 10:
            message = "Complex requests may take 10-30 seconds to process"
        else:
            message = "This is taking longer than usual. The agent is still working..."

        return SSEEventEmitter.format_event("LATENCY_WARNING", {
            "elapsed": elapsed_seconds,
            "message": message
        })

    @staticmethod
    def hitl_approval_request(tool_name: str, tool_args: Dict[str, Any], explanation: str, approval_id: str) -> str:
        """Emit human-in-the-loop approval request"""
        return SSEEventEmitter.format_event("HITL_APPROVAL_REQUEST", {
            "approval_id": approval_id,
            "tool": tool_name,
            "arguments": tool_args,
            "explanation": explanation,
            "message": f"Requesting approval to execute {tool_name}"
        })

    @staticmethod
    def hitl_approved(approval_id: str) -> str:
        """Emit approval granted event"""
        return SSEEventEmitter.format_event("HITL_APPROVED", {
            "approval_id": approval_id,
            "message": "User approved the action"
        })

    @staticmethod
    def hitl_rejected(approval_id: str, reason: Optional[str] = None) -> str:
        """Emit approval rejected event"""
        return SSEEventEmitter.format_event("HITL_REJECTED", {
            "approval_id": approval_id,
            "reason": reason,
            "message": "User rejected the action"
        })

    @staticmethod
    def hitl_timeout(approval_id: str) -> str:
        """Emit approval timeout event"""
        return SSEEventEmitter.format_event("HITL_TIMEOUT", {
            "approval_id": approval_id,
            "message": "Approval request timed out"
        })

    # A2UI (Agent-to-User Interface) Events
    # See docs/A2UI_IMPLEMENTATION.md for full specification

    @staticmethod
    def a2ui_render(surface_id: str, components: list, data_model: Optional[Dict[str, Any]] = None, title: Optional[str] = None) -> str:
        """
        Emit A2UI surface with component tree.

        Components is a nested tree of primitives, e.g.:
        [
            {"type": "Card", "id": "card_1", "props": {"variant": "elevated"}, "children": [
                {"type": "Text", "id": "text_1", "props": {"content": "Hello", "variant": "h3"}}
            ]}
        ]

        Available primitives:
        - Layout: Card, Row, Column, Divider
        - Content: Text, Image, Icon, Badge
        - Interactive: Button, TextField, Select, Checkbox
        - Collections: DataTable, List
        """
        return SSEEventEmitter.format_event("A2UI_RENDER", {
            "surfaceId": surface_id,
            "components": components,
            "dataModel": data_model,
            "title": title,
            "message": "Rendering dynamic UI"
        })

    @staticmethod
    def a2ui_update(surface_id: str, component_id: str, props: Dict[str, Any]) -> str:
        """
        Update a specific component's props within a surface.
        Used for live updates (e.g., loading states, progress).
        """
        return SSEEventEmitter.format_event("A2UI_UPDATE", {
            "surfaceId": surface_id,
            "componentId": component_id,
            "props": props,
            "message": "Updating UI component"
        })

    @staticmethod
    def a2ui_delete(surface_id: str) -> str:
        """Remove an A2UI surface from the UI."""
        return SSEEventEmitter.format_event("A2UI_DELETE", {
            "surfaceId": surface_id,
            "message": "Removing UI surface"
        })