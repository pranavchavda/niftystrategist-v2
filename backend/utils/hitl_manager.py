"""
Human-in-the-Loop (HITL) Approval Manager

Manages approval requests and responses for tool executions in the agent workflow.
"""

import asyncio
import uuid
from typing import Dict, Optional, Any
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)


class ApprovalRequest:
    """Represents a pending approval request"""

    def __init__(self, approval_id: str, tool_name: str, tool_args: Dict[str, Any], explanation: str):
        self.approval_id = approval_id
        self.tool_name = tool_name
        self.tool_args = tool_args
        self.explanation = explanation
        self.created_at = datetime.now(timezone.utc)
        self.future: asyncio.Future = asyncio.Future()

    def approve(self):
        """Mark this request as approved"""
        if not self.future.done():
            self.future.set_result({"approved": True})

    def reject(self, reason: Optional[str] = None):
        """Mark this request as rejected"""
        if not self.future.done():
            self.future.set_result({"approved": False, "reason": reason})

    def timeout(self):
        """Mark this request as timed out"""
        if not self.future.done():
            self.future.set_result({"approved": False, "reason": "Timeout"})

    async def wait(self, timeout_seconds: int = 60) -> Dict[str, Any]:
        """Wait for approval with timeout"""
        try:
            result = await asyncio.wait_for(self.future, timeout=timeout_seconds)
            return result
        except asyncio.TimeoutError:
            self.timeout()
            return {"approved": False, "reason": "Timeout"}


class HITLManager:
    """
    Singleton manager for human-in-the-loop approval requests

    Handles:
    - Creating and tracking approval requests
    - Waiting for user responses
    - Timeout management
    - Thread-safe access across concurrent agent runs
    """

    _instance: Optional['HITLManager'] = None
    _lock = asyncio.Lock()

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._pending_requests: Dict[str, ApprovalRequest] = {}
        self._request_lock = asyncio.Lock()
        self._initialized = True
        logger.info("HITLManager initialized")

    async def request_approval(
        self,
        tool_name: str,
        tool_args: Dict[str, Any],
        explanation: str,
        timeout_seconds: int = 60,
        thread_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Request approval for a tool execution

        Args:
            tool_name: Name of the tool to execute
            tool_args: Arguments for the tool
            explanation: Human-readable explanation of what the tool will do
            timeout_seconds: How long to wait for approval (default 60s)
            thread_id: Conversation thread ID for event streaming

        Returns:
            Dict with keys:
                - approved: bool - Whether the action was approved
                - reason: Optional[str] - Reason for rejection (if rejected)
                - approval_id: str - Unique ID for this approval request
        """
        # Generate unique approval ID
        approval_id = f"approval_{uuid.uuid4().hex[:12]}"

        # Create approval request
        request = ApprovalRequest(approval_id, tool_name, tool_args, explanation)

        # Store in pending requests
        async with self._request_lock:
            self._pending_requests[approval_id] = request

        logger.info(f"[HITL] Created approval request {approval_id} for tool {tool_name}")

        # Emit approval request event to global streamer
        if thread_id:
            from .hitl_streamer import hitl_streamer, HITLEvent
            from datetime import datetime

            try:
                await hitl_streamer.emit(HITLEvent(
                    thread_id=thread_id,
                    event_type="approval_request",
                    approval_id=approval_id,
                    timestamp=datetime.now(),
                    tool_name=tool_name,
                    tool_args=tool_args,
                    explanation=explanation
                ))
            except Exception as e:
                logger.error(f"[HITL] Error emitting approval request event: {e}")

        try:
            # Wait for approval (with timeout)
            result = await request.wait(timeout_seconds)
            result["approval_id"] = approval_id

            if result["approved"]:
                logger.info(f"[HITL] Approval {approval_id} was approved")
                # Emit approved event
                if thread_id:
                    from .hitl_streamer import hitl_streamer, HITLEvent
                    from datetime import datetime
                    try:
                        await hitl_streamer.emit(HITLEvent(
                            thread_id=thread_id,
                            event_type="approved",
                            approval_id=approval_id,
                            timestamp=datetime.now()
                        ))
                    except Exception as e:
                        logger.error(f"[HITL] Error emitting approved event: {e}")
            else:
                logger.info(f"[HITL] Approval {approval_id} was rejected: {result.get('reason')}")
                # Emit rejected event
                if thread_id:
                    from .hitl_streamer import hitl_streamer, HITLEvent
                    from datetime import datetime
                    try:
                        await hitl_streamer.emit(HITLEvent(
                            thread_id=thread_id,
                            event_type="rejected",
                            approval_id=approval_id,
                            timestamp=datetime.now(),
                            reason=result.get('reason')
                        ))
                    except Exception as e:
                        logger.error(f"[HITL] Error emitting rejected event: {e}")

            return result

        finally:
            # Clean up the request
            async with self._request_lock:
                self._pending_requests.pop(approval_id, None)

    async def respond_to_approval(
        self,
        approval_id: str,
        approved: bool,
        reason: Optional[str] = None
    ) -> bool:
        """
        Respond to a pending approval request

        Args:
            approval_id: ID of the approval request
            approved: Whether the action is approved
            reason: Optional reason for rejection

        Returns:
            bool: True if response was recorded, False if approval not found
        """
        async with self._request_lock:
            request = self._pending_requests.get(approval_id)

            if not request:
                logger.warning(f"[HITL] Approval request {approval_id} not found")
                return False

            if approved:
                request.approve()
            else:
                request.reject(reason)

            return True

    async def cancel_approval(self, approval_id: str) -> bool:
        """
        Cancel a pending approval request

        Args:
            approval_id: ID of the approval request

        Returns:
            bool: True if cancellation was successful, False if not found
        """
        async with self._request_lock:
            request = self._pending_requests.get(approval_id)

            if not request:
                return False

            request.reject("Cancelled")
            self._pending_requests.pop(approval_id, None)
            return True

    def get_pending_approvals(self) -> Dict[str, ApprovalRequest]:
        """Get all pending approval requests (for debugging)"""
        return self._pending_requests.copy()


# Global singleton instance
_hitl_manager: Optional[HITLManager] = None


def get_hitl_manager() -> HITLManager:
    """Get the global HITL manager instance"""
    global _hitl_manager
    if _hitl_manager is None:
        _hitl_manager = HITLManager()
    return _hitl_manager
