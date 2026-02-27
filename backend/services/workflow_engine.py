"""
Workflow Engine - Execute and manage automated workflows

This engine handles:
1. Email auto-labeling
2. Sales reports
3. Any workflow that can use EspressoBot agents

Each workflow type has its own executor that can use agents, direct APIs, or both.
"""

import logging
import json
import base64
from email.mime.text import MIMEText
from datetime import datetime, timedelta, timezone
from utils.datetime_utils import utc_now_naive
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

logger = logging.getLogger(__name__)


class WorkflowType(str, Enum):
    """Available workflow types"""
    EMAIL_AUTOLABEL = "email_autolabel"
    DAILY_SALES_REPORT = "daily_sales_report"
    COMPETITOR_PRICE_CHECK = "competitor_price_check"
    LOW_STOCK_ALERT = "low_stock_alert"


class WorkflowStatus(str, Enum):
    """Workflow run status"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class TriggerType(str, Enum):
    """How the workflow was triggered"""
    MANUAL = "manual"
    SCHEDULED = "scheduled"


@dataclass
class WorkflowResult:
    """Result of a workflow execution"""
    success: bool
    data: Dict[str, Any]
    error: Optional[str] = None
    duration_ms: Optional[int] = None


class EmailAutolabelConfig(BaseModel):
    """Configuration for email auto-labeling workflow"""
    email_count: int = 50
    skip_labeled: bool = True
    max_age_days: int = 7
    search_query: str = "in:inbox"


# Label categories from docs/misc/gmail-labels.md
LABEL_CATEGORIES = {
    "To Respond": "Emails requiring a reply or action",
    "FYI": "Informational emails, no action needed",
    "Meeting Update": "Calendar invites, meeting notes, scheduling",
    "Notification": "Automated system alerts, service notifications",
    "Marketing": "Promotional content, newsletters, advertising",
    "Cold Email": "Unsolicited sales/marketing outreach",
    "Actioned": "Completed tasks, resolved issues"
}


class WorkflowEngine:
    """
    Execute automated workflows using EspressoBot agents and APIs.

    This engine is the core of the automation system. It:
    1. Loads user configuration from database
    2. Executes workflow-specific logic
    3. Records results and updates scheduling
    """

    def __init__(self, db_session: AsyncSession):
        self.db = db_session
        self._label_cache: Dict[int, Dict[str, str]] = {}  # user_id -> {label_name: label_id}

    async def execute_workflow(
        self,
        user_id: int,
        workflow_type: str,
        trigger_type: str = "manual",
        config_override: Optional[Dict[str, Any]] = None
    ) -> WorkflowResult:
        """
        Execute a workflow for a user.

        Args:
            user_id: The user ID
            workflow_type: Type of workflow to run
            trigger_type: 'manual' or 'scheduled'
            config_override: Optional config to override stored config

        Returns:
            WorkflowResult with success status and data
        """
        from database.models import WorkflowConfig, WorkflowRun, User

        start_time = utc_now_naive()

        # Get or create workflow config
        result = await self.db.execute(
            select(WorkflowConfig).where(
                WorkflowConfig.user_id == user_id,
                WorkflowConfig.workflow_type == workflow_type
            )
        )
        config = result.scalar_one_or_none()

        if not config:
            # Create default config
            config = WorkflowConfig(
                user_id=user_id,
                workflow_type=workflow_type,
                enabled=False,
                config={}
            )
            self.db.add(config)
            await self.db.commit()
            await self.db.refresh(config)

        # Merge config with override
        workflow_config = {**(config.config or {}), **(config_override or {})}

        # Create run record (strip tzinfo for naive datetime DB columns)
        run = WorkflowRun(
            workflow_config_id=config.id,
            user_id=user_id,
            workflow_type=workflow_type,
            status=WorkflowStatus.RUNNING,
            trigger_type=trigger_type,
            started_at=start_time.replace(tzinfo=None)
        )
        self.db.add(run)
        await self.db.commit()
        await self.db.refresh(run)

        try:
            # Get user for credentials
            user_result = await self.db.execute(
                select(User).where(User.id == user_id)
            )
            user = user_result.scalar_one_or_none()

            if not user:
                raise ValueError(f"User {user_id} not found")

            # Execute workflow based on type
            if workflow_type == WorkflowType.EMAIL_AUTOLABEL:
                result = await self._execute_email_autolabel(user, workflow_config)
            elif workflow_type == WorkflowType.DAILY_SALES_REPORT:
                result = await self._execute_sales_report(user, workflow_config)
            else:
                raise ValueError(f"Unknown workflow type: {workflow_type}")

            # Calculate duration
            end_time = utc_now_naive()
            duration_ms = int((end_time - start_time).total_seconds() * 1000)
            result.duration_ms = duration_ms

            # Update run record (strip tzinfo for naive datetime DB columns)
            run.status = WorkflowStatus.COMPLETED if result.success else WorkflowStatus.FAILED
            run.completed_at = end_time.replace(tzinfo=None)
            run.duration_ms = duration_ms
            run.result = result.data
            run.error_message = result.error

            # Update config last_run
            config.last_run_at = end_time.replace(tzinfo=None)
            if config.enabled:
                config.next_run_at = self._calculate_next_run(config.frequency)

            await self.db.commit()

            return result

        except Exception as e:
            logger.exception(f"Workflow {workflow_type} failed for user {user_id}")

            # Update run record with error (strip tzinfo for naive datetime DB columns)
            run.status = WorkflowStatus.FAILED
            run.completed_at = utc_now_naive().replace(tzinfo=None)
            run.error_message = str(e)
            await self.db.commit()

            return WorkflowResult(
                success=False,
                data={},
                error=str(e)
            )

    async def _execute_email_autolabel(
        self,
        user,
        config: Dict[str, Any]
    ) -> WorkflowResult:
        """
        Execute email auto-labeling workflow.

        1. Fetch recent emails
        2. Filter out already-labeled (optional)
        3. Classify with LLM
        4. Apply labels via Gmail API
        """
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        from google_auth import refresh_google_token
        import os

        # Parse config
        email_count = config.get("email_count", 50)
        skip_labeled = config.get("skip_labeled", True)
        max_age_days = config.get("max_age_days", 7)

        # Check user has Google credentials
        if not user.google_access_token:
            return WorkflowResult(
                success=False,
                data={},
                error="User has no Google credentials. Please re-authenticate with Google."
            )

        # Get refreshed credentials
        try:
            creds = await self._get_google_credentials(user)
        except Exception as e:
            return WorkflowResult(
                success=False,
                data={},
                error=f"Failed to get Google credentials: {str(e)}"
            )

        # Build Gmail service
        gmail = build('gmail', 'v1', credentials=creds)

        # Step 1: Fetch recent emails
        query = f"in:inbox newer_than:{max_age_days}d"

        try:
            messages_result = gmail.users().messages().list(
                userId='me',
                q=query,
                maxResults=email_count
            ).execute()
        except Exception as e:
            return WorkflowResult(
                success=False,
                data={},
                error=f"Failed to fetch emails: {str(e)}"
            )

        messages = messages_result.get('messages', [])

        if not messages:
            return WorkflowResult(
                success=True,
                data={
                    "emails_processed": 0,
                    "labels_applied": {},
                    "message": "No emails found matching criteria"
                }
            )

        # Step 2: Get full message details
        emails_to_classify = []

        # Get label IDs for this user (cache them)
        label_map = await self._get_or_create_labels(gmail, user.id)

        # Custom label IDs to check if email is already labeled
        custom_label_ids = set(label_map.values())

        for msg in messages:
            try:
                full_msg = gmail.users().messages().get(
                    userId='me',
                    id=msg['id'],
                    format='metadata',
                    metadataHeaders=['Subject', 'From', 'Date']
                ).execute()

                # Check if already has custom labels
                msg_labels = set(full_msg.get('labelIds', []))
                if skip_labeled and msg_labels.intersection(custom_label_ids):
                    continue  # Skip already labeled

                # Extract headers
                headers = {h['name']: h['value'] for h in full_msg.get('payload', {}).get('headers', [])}

                emails_to_classify.append({
                    'id': msg['id'],
                    'subject': headers.get('Subject', '(no subject)'),
                    'from': headers.get('From', 'unknown'),
                    'snippet': full_msg.get('snippet', '')[:200]
                })

            except Exception as e:
                logger.warning(f"Failed to get message {msg['id']}: {e}")
                continue

        if not emails_to_classify:
            return WorkflowResult(
                success=True,
                data={
                    "emails_processed": 0,
                    "labels_applied": {},
                    "skipped": len(messages),
                    "message": "All emails already labeled"
                }
            )

        # Step 3: Classify with LLM
        try:
            classifications = await self._classify_emails_with_llm(emails_to_classify)
        except Exception as e:
            return WorkflowResult(
                success=False,
                data={"emails_fetched": len(emails_to_classify)},
                error=f"Failed to classify emails: {str(e)}"
            )

        # Step 4: Apply labels in batches (grouped by category)
        labels_applied = {}
        errors = []

        for category, email_ids in self._group_by_category(classifications).items():
            if category not in label_map:
                logger.warning(f"Unknown category: {category}")
                continue

            label_id = label_map[category]

            try:
                gmail.users().messages().batchModify(
                    userId='me',
                    body={
                        'ids': email_ids,
                        'addLabelIds': [label_id]
                    }
                ).execute()

                labels_applied[category] = len(email_ids)

            except Exception as e:
                logger.error(f"Failed to apply label {category}: {e}")
                errors.append(f"{category}: {str(e)}")

        return WorkflowResult(
            success=len(errors) == 0,
            data={
                "emails_processed": len(emails_to_classify),
                "labels_applied": labels_applied,
                "skipped": len(messages) - len(emails_to_classify),
                "errors": errors if errors else None
            },
            error="; ".join(errors) if errors else None
        )

    async def _get_google_credentials(self, user):
        """Get refreshed Google credentials for a user"""
        from google.oauth2.credentials import Credentials
        from google_auth import refresh_google_token
        import os

        # Check if token needs refresh
        # Note: DB stores naive UTC datetimes, so compare with naive UTC
        now_utc = utc_now_naive().replace(tzinfo=None)
        if user.google_token_expiry and user.google_token_expiry < now_utc:
            # Refresh token
            new_tokens = await refresh_google_token(user.google_refresh_token)
            if new_tokens:
                user.google_access_token = new_tokens.get('access_token')
                if new_tokens.get('refresh_token'):
                    user.google_refresh_token = new_tokens['refresh_token']
                # Store as naive UTC datetime
                new_expiry = utc_now_naive() + timedelta(seconds=new_tokens.get('expires_in', 3600))
                user.google_token_expiry = new_expiry.replace(tzinfo=None)
                await self.db.commit()

        return Credentials(
            token=user.google_access_token,
            refresh_token=user.google_refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=os.getenv("GOOGLE_CLIENT_ID"),
            client_secret=os.getenv("GOOGLE_CLIENT_SECRET")
        )

    async def _get_or_create_labels(self, gmail, user_id: int) -> Dict[str, str]:
        """Get or create Gmail labels for categories, with caching"""

        if user_id in self._label_cache:
            return self._label_cache[user_id]

        # Get existing labels
        labels_result = gmail.users().labels().list(userId='me').execute()
        existing_labels = {l['name']: l['id'] for l in labels_result.get('labels', [])}

        label_map = {}

        for category in LABEL_CATEGORIES.keys():
            if category in existing_labels:
                label_map[category] = existing_labels[category]
            else:
                # Create label
                try:
                    new_label = gmail.users().labels().create(
                        userId='me',
                        body={
                            'name': category,
                            'labelListVisibility': 'labelShow',
                            'messageListVisibility': 'show'
                        }
                    ).execute()
                    label_map[category] = new_label['id']
                    logger.info(f"Created Gmail label: {category}")
                except Exception as e:
                    logger.error(f"Failed to create label {category}: {e}")

        self._label_cache[user_id] = label_map
        return label_map

    async def _classify_emails_with_llm(
        self,
        emails: List[Dict[str, Any]]
    ) -> Dict[str, str]:
        """
        Classify emails using LLM.

        Returns: {email_id: category}
        """
        from pydantic_ai import Agent
        from pydantic_ai.models.openai import OpenAIChatModel

        # Build prompt
        categories_desc = "\n".join([f"- {k}: {v}" for k, v in LABEL_CATEGORIES.items()])

        emails_json = json.dumps([
            {
                "id": e["id"],
                "subject": e["subject"],
                "from": e["from"],
                "snippet": e["snippet"]
            }
            for e in emails
        ], indent=2)

        prompt = f"""Classify each email into exactly ONE category based on its subject, sender, and snippet.

Categories:
{categories_desc}

Emails to classify:
{emails_json}

Respond with a JSON object mapping email ID to category name. Example:
{{"abc123": "To Respond", "def456": "Marketing"}}

Only use the exact category names listed above. Classify ALL emails

ensure to think carefully about the classification before making a decision.

."""

        # Use a fast model for classification
        model = OpenAIChatModel("gpt-5-nano")
        agent = Agent(model=model)

        result = await agent.run(prompt)

        # Parse JSON response
        try:
            # Extract JSON from response (Pydantic AI uses .output, not .data)
            response_text = result.output

            # Find JSON in response
            if "{" in response_text and "}" in response_text:
                json_start = response_text.index("{")
                json_end = response_text.rindex("}") + 1
                json_str = response_text[json_start:json_end]
                return json.loads(json_str)
            else:
                raise ValueError("No JSON found in response")

        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Failed to parse LLM response: {e}")
            logger.error(f"Response was: {result.output}")
            raise ValueError(f"Failed to parse classification response: {e}")

    def _group_by_category(self, classifications: Dict[str, str]) -> Dict[str, List[str]]:
        """Group email IDs by their category"""
        grouped = {}
        for email_id, category in classifications.items():
            if category not in grouped:
                grouped[category] = []
            grouped[category].append(email_id)
        return grouped

    async def _execute_sales_report(
        self,
        user,
        config: Dict[str, Any]
    ) -> WorkflowResult:
        """
        Execute daily sales report workflow.

        Uses ShopifyQL to get sales data and formats it.
        """
        import subprocess
        import os
        from pathlib import Path

        # Get the bash-tools directory
        tools_dir = Path(__file__).parent.parent / "bash-tools"

        # Build the ShopifyQL query for yesterday's sales
        query = "FROM sales SHOW total_sales, orders, average_order_value BY day SINCE -1d UNTIL today ORDER BY day"

        try:
            # Use the analytics.py script to run ShopifyQL
            env = os.environ.copy()
            env['SHOPIFY_SHOP_URL'] = os.getenv('SHOPIFY_SHOP_URL', '')
            env['SHOPIFY_ACCESS_TOKEN'] = os.getenv('SHOPIFY_ACCESS_TOKEN', '')

            result = subprocess.run(
                ['python3', str(tools_dir / 'analytics.py'), '--query', query],
                capture_output=True,
                text=True,
                timeout=60,
                env=env,
                cwd=str(tools_dir)
            )

            if result.returncode != 0:
                return WorkflowResult(
                    success=False,
                    data={"stderr": result.stderr[:500]},
                    error=f"ShopifyQL query failed: {result.stderr[:200]}"
                )

            # Parse the output
            output = result.stdout.strip()

            # Try to extract key metrics from the output
            report_data = {
                "query": query,
                "raw_output": output[:1000],
                "generated_at": utc_now_naive().isoformat()
            }

            # If configured to send email, we could do that here
            # For now, just store the report
            send_email = config.get("send_email", False)
            if send_email and user.email:
                # TODO: Send email with report
                report_data["email_sent"] = False
                report_data["email_note"] = "Email sending not yet implemented"

            return WorkflowResult(
                success=True,
                data=report_data
            )

        except subprocess.TimeoutExpired:
            return WorkflowResult(
                success=False,
                data={},
                error="ShopifyQL query timed out after 60 seconds"
            )
        except Exception as e:
            logger.exception(f"Failed to run sales report: {e}")
            return WorkflowResult(
                success=False,
                data={},
                error=f"Failed to run sales report: {str(e)}"
            )

    def _calculate_next_run(self, frequency: str) -> datetime:
        """Calculate next run time based on frequency.

        Returns naive UTC datetime for DB storage (TIMESTAMP WITHOUT TIME ZONE).
        """
        now = utc_now_naive()

        if frequency == "hourly":
            result = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
        elif frequency == "6hours":
            # Next 6-hour mark (0, 6, 12, 18)
            current_hour = now.hour
            next_hour = ((current_hour // 6) + 1) * 6
            if next_hour >= 24:
                next_hour = 0
                result = (now + timedelta(days=1)).replace(hour=next_hour, minute=0, second=0, microsecond=0)
            else:
                result = now.replace(hour=next_hour, minute=0, second=0, microsecond=0)
        elif frequency == "daily":
            # Next day at 8 AM
            result = now.replace(hour=8, minute=0, second=0, microsecond=0)
            if result <= now:
                result += timedelta(days=1)
        elif frequency == "weekly":
            # Next Monday at 8 AM
            days_until_monday = (7 - now.weekday()) % 7
            if days_until_monday == 0 and now.hour >= 8:
                days_until_monday = 7
            result = now + timedelta(days=days_until_monday)
            result = result.replace(hour=8, minute=0, second=0, microsecond=0)
        elif frequency == "once":
            # One-time run - no next run after execution
            return None
        else:
            # Manual - no next run
            return None

        # Strip timezone for naive datetime DB columns
        return result.replace(tzinfo=None)

    async def _load_thread_messages(self, thread_id: str) -> list:
        """Load up to 50 most recent messages from a thread for context replay."""
        from database.models import Message
        from pydantic_ai.messages import ModelRequest, ModelResponse, UserPromptPart, TextPart

        result = await self.db.execute(
            select(Message)
            .where(Message.conversation_id == thread_id)
            .order_by(Message.timestamp.desc())
            .limit(50)
        )
        messages = list(reversed(result.scalars().all()))

        history = []
        for msg in messages:
            if msg.role == "user":
                history.append(ModelRequest(parts=[UserPromptPart(content=msg.content)]))
            elif msg.role == "assistant" and msg.content:
                history.append(ModelResponse(parts=[TextPart(msg.content)]))
            # system messages skipped — they're injected via system prompt
        return history

    async def _write_followup_to_thread(
        self,
        thread_id: str,
        user_id: int,
        response_text: str,
    ) -> None:
        """Write a system trigger + assistant response back to the thread."""
        import uuid
        from database.models import Message, Conversation
        from datetime import timedelta

        now = utc_now_naive()

        # System message marking the automated trigger
        trigger_msg = Message(
            conversation_id=thread_id,
            message_id=f"followup_trigger_{uuid.uuid4().hex}",
            role="system",
            content="Scheduled follow-up triggered",
            timestamp=now,
            extra_metadata={"auto_followup": True, "workflow_user_id": user_id},
        )
        self.db.add(trigger_msg)

        # Assistant response (1 microsecond after trigger for ordering)
        response_msg = Message(
            conversation_id=thread_id,
            message_id=f"followup_response_{uuid.uuid4().hex}",
            role="assistant",
            content=response_text,
            timestamp=now + timedelta(microseconds=1),
            extra_metadata={"auto_followup": True},
        )
        self.db.add(response_msg)

        # Bump conversation.updated_at so thread surfaces in sidebar
        await self.db.execute(
            update(Conversation)
            .where(Conversation.id == thread_id)
            .values(updated_at=now + timedelta(microseconds=2))
        )
        await self.db.commit()
        logger.info(f"Thread awakening: wrote follow-up response to thread {thread_id}")

    async def execute_custom_workflow(
        self,
        user_id: int,
        workflow_def_id: int,
        trigger_type: str = "manual"
    ) -> WorkflowResult:
        """
        Execute a user-defined prompt-based workflow.

        If the workflow has a thread_id, this is a thread-bound follow-up: it loads
        the thread's message history as context, runs the prompt autonomously, and
        writes the result back to the thread (Thread Awakening).

        Args:
            user_id: The user ID
            workflow_def_id: The workflow definition ID
            trigger_type: 'manual' or 'scheduled'

        Returns:
            WorkflowResult with success status and data
        """
        from database.models import WorkflowDefinition, WorkflowRun, User
        from agents.orchestrator import OrchestratorDeps
        from models.state import ConversationState
        from config.models import DEFAULT_MODEL_ID
        from main import get_orchestrator_for_model

        start_time = utc_now_naive()

        # Get workflow definition
        result = await self.db.execute(
            select(WorkflowDefinition).where(
                WorkflowDefinition.id == workflow_def_id,
                WorkflowDefinition.user_id == user_id
            )
        )
        workflow_def = result.scalar_one_or_none()

        if not workflow_def:
            return WorkflowResult(
                success=False,
                data={},
                error=f"Workflow definition {workflow_def_id} not found"
            )

        # Get user for credentials
        user_result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        user = user_result.scalar_one_or_none()

        if not user:
            return WorkflowResult(
                success=False,
                data={},
                error=f"User {user_id} not found"
            )

        is_followup = bool(workflow_def.thread_id)

        # Create a workflow run record
        run = WorkflowRun(
            workflow_config_id=None,  # No config for custom workflows
            user_id=user_id,
            workflow_type=f"custom_{workflow_def_id}",
            status=WorkflowStatus.RUNNING,
            trigger_type=trigger_type,
            started_at=start_time.replace(tzinfo=None)
        )
        self.db.add(run)
        await self.db.commit()
        await self.db.refresh(run)

        try:
            # Select model: prefer user's saved preference
            model_id = (user.preferred_model or DEFAULT_MODEL_ID)
            # Use get_orchestrator_for_model so sub-agents (web_search, vision) are registered
            orchestrator = await get_orchestrator_for_model(model_id, user_id=user_id)

            if is_followup:
                # Thread Awakening: run in the original thread with full message history
                thread_id = workflow_def.thread_id
                state = ConversationState(
                    user_id=user.email,
                    thread_id=thread_id,
                )
                message_history = await self._load_thread_messages(thread_id)
                logger.info(
                    f"Thread awakening for workflow {workflow_def_id}: "
                    f"loaded {len(message_history)} messages from thread {thread_id}"
                )
                # Autonomous-mode prompt — no user is present
                effective_prompt = (
                    "[AUTOMATED FOLLOW-UP — NO USER PRESENT]\n"
                    "You are executing a scheduled follow-up in an existing conversation thread. "
                    "The user is NOT available to respond. Rules:\n"
                    "- Execute the task described below completely\n"
                    "- Report your findings clearly\n"
                    "- Do NOT ask questions or request clarification\n"
                    "- Do NOT propose further actions that require user input\n"
                    "- If you encounter an issue that requires human decision, note it and stop\n"
                    f"Task: {workflow_def.prompt}"
                )
            else:
                # Regular automation: ephemeral thread ID
                thread_id = f"workflow_{workflow_def_id}_{int(start_time.timestamp())}"
                state = ConversationState(
                    user_id=user.email,
                    thread_id=thread_id,
                )
                message_history = None
                effective_prompt = workflow_def.prompt

            # Resolve live Upstox token: decrypt + expiry check + TOTP auto-refresh
            from api.upstox_oauth import get_user_upstox_token
            upstox_token = await get_user_upstox_token(user.id)

            deps = OrchestratorDeps(
                state=state,
                upstox_access_token=upstox_token,
                user_id=user.id,
                trading_mode=user.trading_mode or "paper",
                is_awakening=True,  # Scheduled awakenings run without a live user
            )

            # Execute the prompt — agent.run() handles full multi-turn tool loops and
            # returns the complete final response (stream_text only captures first model call)
            import asyncio
            try:
                kwargs = {}
                if message_history:
                    kwargs["message_history"] = message_history

                run_result = await asyncio.wait_for(
                    orchestrator.agent.run(effective_prompt, deps=deps, **kwargs),
                    timeout=workflow_def.timeout_seconds
                )
                orchestrator_result = run_result.output if run_result.output else ""
            except asyncio.TimeoutError:
                raise TimeoutError(f"Workflow timed out after {workflow_def.timeout_seconds} seconds")

            # Calculate duration
            end_time = utc_now_naive()
            duration_ms = int((end_time - start_time).total_seconds() * 1000)

            # For thread follow-ups: write result back to the thread
            if is_followup and orchestrator_result:
                await self._write_followup_to_thread(
                    thread_id=workflow_def.thread_id,
                    user_id=user_id,
                    response_text=orchestrator_result,
                )

            # Update run record
            run.status = WorkflowStatus.COMPLETED
            run.completed_at = end_time.replace(tzinfo=None)
            run.duration_ms = duration_ms
            run.result = {
                "prompt": workflow_def.prompt,
                "response": orchestrator_result[:5000] if orchestrator_result else None,
                "workflow_name": workflow_def.name
            }

            # Update workflow definition tracking
            workflow_def.last_run_at = end_time.replace(tzinfo=None)
            workflow_def.run_count = (workflow_def.run_count or 0) + 1

            # For one-time runs, disable after execution
            if workflow_def.frequency == "once":
                workflow_def.enabled = False
                workflow_def.next_run_at = None
                logger.info(f"One-time workflow {workflow_def.id} completed and disabled")
            elif workflow_def.enabled:
                workflow_def.next_run_at = self._calculate_next_run(workflow_def.frequency)

            await self.db.commit()

            # Send success notification if enabled (skip for thread follow-ups — result is in the thread)
            if workflow_def.notify_on_complete and not is_followup:
                await self._send_workflow_notification(
                    user=user,
                    workflow_name=workflow_def.name,
                    success=True,
                    result_summary=orchestrator_result[:2000] if orchestrator_result else None,
                    duration_ms=duration_ms
                )

            return WorkflowResult(
                success=True,
                data={
                    "output": orchestrator_result,
                    "response": orchestrator_result,
                    "workflow_name": workflow_def.name,
                    "run_id": run.id
                },
                duration_ms=duration_ms
            )

        except TimeoutError as e:
            end_time = utc_now_naive()
            duration_ms = int((end_time - start_time).total_seconds() * 1000)
            run.status = WorkflowStatus.FAILED
            run.completed_at = end_time.replace(tzinfo=None)
            run.duration_ms = duration_ms
            run.error_message = str(e)
            await self.db.commit()

            if workflow_def.notify_on_failure:
                await self._send_workflow_notification(
                    user=user,
                    workflow_name=workflow_def.name,
                    success=False,
                    error_message=str(e),
                    duration_ms=duration_ms
                )

            return WorkflowResult(
                success=False,
                data={"workflow_name": workflow_def.name},
                error=str(e)
            )

        except Exception as e:
            logger.exception(f"Custom workflow {workflow_def.name} failed for user {user_id}")

            end_time = utc_now_naive()
            duration_ms = int((end_time - start_time).total_seconds() * 1000)
            run.status = WorkflowStatus.FAILED
            run.completed_at = end_time.replace(tzinfo=None)
            run.duration_ms = duration_ms
            run.error_message = str(e)
            await self.db.commit()

            if workflow_def.notify_on_failure:
                await self._send_workflow_notification(
                    user=user,
                    workflow_name=workflow_def.name,
                    success=False,
                    error_message=str(e),
                    duration_ms=duration_ms
                )

            return WorkflowResult(
                success=False,
                data={"workflow_name": workflow_def.name},
                error=str(e)
            )

    async def _send_workflow_notification(
        self,
        user,
        workflow_name: str,
        success: bool,
        result_summary: Optional[str] = None,
        error_message: Optional[str] = None,
        duration_ms: Optional[int] = None
    ) -> bool:
        """
        Send email notification about workflow completion or failure.

        Uses the user's Gmail credentials to send an email to themselves.

        Args:
            user: User object with Google credentials
            workflow_name: Name of the workflow
            success: Whether workflow succeeded
            result_summary: Brief summary of result (for success)
            error_message: Error details (for failure)
            duration_ms: Execution duration in milliseconds

        Returns:
            True if email sent successfully, False otherwise
        """
        from googleapiclient.discovery import build

        if not user.google_access_token or not user.email:
            logger.warning(f"Cannot send notification: user {user.id} missing credentials or email")
            return False

        try:
            creds = await self._get_google_credentials(user)
            gmail = build('gmail', 'v1', credentials=creds)

            # Format duration
            duration_str = ""
            if duration_ms:
                if duration_ms > 60000:
                    duration_str = f"{duration_ms / 60000:.1f} minutes"
                elif duration_ms > 1000:
                    duration_str = f"{duration_ms / 1000:.1f} seconds"
                else:
                    duration_str = f"{duration_ms}ms"

            # Build email content
            if success:
                subject = f"✅ Workflow Complete: {workflow_name}"
                body = f"""Your automated workflow "{workflow_name}" completed successfully.

Duration: {duration_str or 'N/A'}

Result Summary:
{result_summary[:2000] if result_summary else 'No details available.'}

---
This is an automated notification from EspressoBot.
"""
            else:
                subject = f"❌ Workflow Failed: {workflow_name}"
                body = f"""Your automated workflow "{workflow_name}" failed.

Duration: {duration_str or 'N/A'}

Error:
{error_message or 'Unknown error'}

---
This is an automated notification from EspressoBot.
Please check your workflow configuration or try running it manually.
"""

            # Create email message
            message = MIMEText(body)
            message['to'] = user.email
            message['subject'] = subject
            raw = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')

            # Send email
            gmail.users().messages().send(
                userId='me',
                body={'raw': raw}
            ).execute()

            logger.info(f"Sent {'success' if success else 'failure'} notification for workflow '{workflow_name}' to {user.email}")
            return True

        except Exception as e:
            logger.error(f"Failed to send workflow notification: {e}")
            return False
