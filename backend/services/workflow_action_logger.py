"""
Log tool calls and actions executed during workflow runs.

Provides audit trail for autonomous trading decisions made during awakenings and automations.
"""

import logging
from typing import Optional, Dict, Any
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import insert

from database.models import WorkflowActionLog, utc_now

logger = logging.getLogger(__name__)


class WorkflowActionLogger:
    """Log tool invocations during workflow execution"""

    def __init__(self, session: AsyncSession, workflow_run_id: int, user_id: int):
        self.session = session
        self.workflow_run_id = workflow_run_id
        self.user_id = user_id
        self.sequence_counter = 0

    async def log_tool_call(
        self,
        tool_name: str,
        tool_args: Dict[str, Any],
        tool_result: Optional[Dict[str, Any]] = None,
        execution_status: str = "pending",
        error_message: Optional[str] = None,
        duration_ms: Optional[int] = None,
        agent_reasoning: Optional[str] = None,
        market_context: Optional[Dict[str, Any]] = None,
    ) -> int:
        """
        Log a single tool call during workflow execution.

        Args:
            tool_name: Name of the tool (e.g., 'nf-order', 'nf-portfolio')
            tool_args: Arguments passed to the tool
            tool_result: Result/output from tool execution
            execution_status: 'success', 'failed', 'pending'
            error_message: Error if execution failed
            duration_ms: How long the tool took to execute
            agent_reasoning: Why the agent called this tool
            market_context: Market state at time of execution (optional)

        Returns:
            log_id: ID of the created log entry
        """
        self.sequence_counter += 1

        log_entry = WorkflowActionLog(
            workflow_run_id=self.workflow_run_id,
            user_id=self.user_id,
            tool_name=tool_name,
            tool_args=tool_args,
            tool_result=tool_result,
            execution_status=execution_status,
            error_message=error_message,
            started_at=utc_now(),
            completed_at=utc_now() if execution_status in ("success", "failed") else None,
            duration_ms=duration_ms,
            sequence_order=self.sequence_counter,
            agent_reasoning=agent_reasoning,
            market_context=market_context,
        )

        self.session.add(log_entry)
        await self.session.flush()

        logger.info(
            f"[WF-ACTION-LOG] workflow={self.workflow_run_id} seq={self.sequence_counter} "
            f"tool={tool_name} status={execution_status} duration={duration_ms}ms"
        )

        return log_entry.id

    async def log_order_placement(
        self,
        symbol: str,
        action: str,  # 'buy' or 'sell'
        quantity: int,
        order_type: str = "market",
        price: Optional[float] = None,
        upstox_order_id: Optional[str] = None,
        execution_status: str = "pending",
        error_message: Optional[str] = None,
        agent_reasoning: Optional[str] = None,
        market_context: Optional[Dict[str, Any]] = None,
    ) -> int:
        """Specialized logging for nf-order tool calls"""
        tool_args = {
            "command": f"nf-order {action} {symbol} {quantity}",
            "symbol": symbol,
            "action": action,
            "quantity": quantity,
            "order_type": order_type,
        }
        if price:
            tool_args["price"] = price

        tool_result = None
        if upstox_order_id:
            tool_result = {"order_id": upstox_order_id, "status": "submitted"}

        reasoning = agent_reasoning or f"{action.upper()} {quantity} shares of {symbol}"

        return await self.log_tool_call(
            tool_name="nf-order",
            tool_args=tool_args,
            tool_result=tool_result,
            execution_status=execution_status,
            error_message=error_message,
            agent_reasoning=reasoning,
            market_context=market_context,
        )

    async def get_workflow_actions(self) -> list:
        """Get all logged actions for this workflow run, ordered by sequence"""
        from sqlalchemy import select, asc

        stmt = select(WorkflowActionLog).where(
            WorkflowActionLog.workflow_run_id == self.workflow_run_id
        ).order_by(asc(WorkflowActionLog.sequence_order))

        result = await self.session.execute(stmt)
        return result.scalars().all()
