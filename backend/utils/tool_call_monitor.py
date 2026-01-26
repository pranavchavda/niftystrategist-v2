"""
Tool Call Monitor - Track and verify tool execution

Monitors agent runs to detect when tools are called vs. when the agent
describes calling tools without actually doing so.
"""

import logging
from typing import Dict, List, Optional, Set
from datetime import datetime
from dataclasses import dataclass, field
from collections import defaultdict
import asyncio

logger = logging.getLogger(__name__)


@dataclass
class ToolCallRecord:
    """Record of a tool call"""

    tool_name: str
    timestamp: datetime
    thread_id: str
    arguments: Dict = field(default_factory=dict)
    result: Optional[str] = None
    duration_ms: Optional[int] = None
    success: bool = True


@dataclass
class RunAnalysis:
    """Analysis of an agent run"""

    thread_id: str
    start_time: datetime
    end_time: Optional[datetime] = None
    tools_called: List[ToolCallRecord] = field(default_factory=list)
    output_generated: bool = False
    output_without_tools: bool = False  # Critical: output but no tools
    total_duration_ms: Optional[int] = None

    def get_tools_used(self) -> Set[str]:
        """Get set of unique tool names used"""
        return {call.tool_name for call in self.tools_called}

    def had_tool_calls(self) -> bool:
        """Check if any tools were called"""
        return len(self.tools_called) > 0

    def is_suspicious(self) -> bool:
        """
        Detect suspicious patterns:
        - Output generated but no tools called (for tasks that require tools)
        """
        return self.output_generated and not self.had_tool_calls()


class ToolCallMonitor:
    """
    Monitor tool calls during agent runs to detect role-playing.

    Usage:
        monitor = ToolCallMonitor()

        # Start monitoring a run
        monitor.start_run(thread_id="conv_123")

        # Record tool calls as they happen
        monitor.record_tool_call(
            thread_id="conv_123",
            tool_name="execute_bash",
            arguments={"command": "..."}
        )

        # Mark when output is generated
        monitor.mark_output_generated(thread_id="conv_123")

        # Get analysis
        analysis = monitor.finish_run(thread_id="conv_123")
        if analysis.is_suspicious():
            logger.warning("Agent generated output without calling tools!")
    """

    def __init__(self):
        self._active_runs: Dict[str, RunAnalysis] = {}
        self._completed_runs: List[RunAnalysis] = []
        self._stats = defaultdict(int)
        self._lock = asyncio.Lock()

    async def start_run(self, thread_id: str) -> None:
        """Start monitoring a new agent run"""
        async with self._lock:
            self._active_runs[thread_id] = RunAnalysis(
                thread_id=thread_id, start_time=datetime.now()
            )
            logger.debug(f"Started monitoring run: {thread_id}")

    async def record_tool_call(
        self,
        thread_id: str,
        tool_name: str,
        arguments: Optional[Dict] = None,
        result: Optional[str] = None,
        duration_ms: Optional[int] = None,
    ) -> None:
        """Record a tool call during a run"""
        async with self._lock:
            if thread_id not in self._active_runs:
                logger.warning(
                    f"Attempted to record tool call for unknown run: {thread_id}"
                )
                return

            record = ToolCallRecord(
                tool_name=tool_name,
                timestamp=datetime.now(),
                thread_id=thread_id,
                arguments=arguments or {},
                result=result,
                duration_ms=duration_ms,
            )

            self._active_runs[thread_id].tools_called.append(record)
            self._stats["total_tool_calls"] += 1
            self._stats[f"tool_{tool_name}"] += 1

            logger.debug(f"Recorded tool call: {tool_name} for run {thread_id}")

    async def mark_output_generated(self, thread_id: str) -> None:
        """Mark that output was generated for this run"""
        async with self._lock:
            if thread_id not in self._active_runs:
                logger.warning(
                    f"Attempted to mark output for unknown run: {thread_id}"
                )
                return

            run = self._active_runs[thread_id]
            run.output_generated = True

            # Check if this is suspicious (output without tools)
            if not run.had_tool_calls():
                run.output_without_tools = True
                self._stats["suspicious_runs"] += 1
                logger.warning(
                    f"⚠️ SUSPICIOUS: Run {thread_id} generated output without calling ANY tools"
                )

    async def finish_run(self, thread_id: str) -> Optional[RunAnalysis]:
        """Finish monitoring a run and return analysis"""
        async with self._lock:
            if thread_id not in self._active_runs:
                logger.warning(f"Attempted to finish unknown run: {thread_id}")
                return None

            run = self._active_runs.pop(thread_id)
            run.end_time = datetime.now()

            if run.start_time:
                duration = (run.end_time - run.start_time).total_seconds() * 1000
                run.total_duration_ms = int(duration)

            # Update stats
            self._stats["total_runs"] += 1
            if run.is_suspicious():
                self._stats["suspicious_runs"] += 1

            self._completed_runs.append(run)

            # Keep only last 100 completed runs to prevent memory issues
            if len(self._completed_runs) > 100:
                self._completed_runs = self._completed_runs[-100:]

            logger.debug(
                f"Finished monitoring run {thread_id}: "
                f"{len(run.tools_called)} tools called, "
                f"suspicious={run.is_suspicious()}"
            )

            return run

    def get_stats(self) -> Dict:
        """Get monitoring statistics"""
        return dict(self._stats)

    def get_suspicious_runs(self, limit: int = 10) -> List[RunAnalysis]:
        """Get recent suspicious runs"""
        return [run for run in self._completed_runs if run.is_suspicious()][-limit:]

    def get_recent_runs(self, limit: int = 10) -> List[RunAnalysis]:
        """Get recent completed runs"""
        return self._completed_runs[-limit:]


# Global monitor instance
_global_monitor: Optional[ToolCallMonitor] = None


def get_monitor() -> ToolCallMonitor:
    """Get the global tool call monitor instance"""
    global _global_monitor
    if _global_monitor is None:
        _global_monitor = ToolCallMonitor()
    return _global_monitor
