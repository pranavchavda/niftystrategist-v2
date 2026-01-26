"""API routes for Google Tasks - AI-Enhanced Task Management"""
import os
import logging
import uuid
from datetime import datetime, timedelta
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from database.models import User
from auth import get_current_user, requires_permission
from google_auth import refresh_google_token

# Agent imports for natural language routing
from agents.google_workspace_agent import GoogleWorkspaceAgent, GoogleWorkspaceDeps
from models.state import ConversationState

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/tasks",
    tags=["google-tasks"],
    dependencies=[Depends(requires_permission("google_workspace.access"))]
)


# ============== Pydantic Models ==============

class CreateTaskRequest(BaseModel):
    """Request to create a task - supports both structured and natural language"""
    text: str = Field(..., min_length=1, description="Task text (natural language or title)")
    notes: Optional[str] = None
    due_date: Optional[str] = None  # ISO format or natural language
    tasklist_id: Optional[str] = Field(default=None, description="Target task list ID (defaults to @default)")
    parse_natural_language: bool = Field(default=True, description="Whether to AI-parse the text")


class UpdateTaskRequest(BaseModel):
    """Request to update a task"""
    title: Optional[str] = None
    notes: Optional[str] = None
    due_date: Optional[str] = None
    status: Optional[str] = None  # "needsAction" or "completed"


class ParsedTask(BaseModel):
    """AI-parsed task structure"""
    title: str
    due_date: Optional[str] = None  # ISO datetime
    priority: str = "normal"  # low, normal, high, urgent
    notes: Optional[str] = None


class TaskResponse(BaseModel):
    """Single task response"""
    id: str
    tasklist_id: Optional[str] = None  # For operations on non-default lists
    tasklist_title: Optional[str] = None  # Display name of the task list
    title: str
    notes: Optional[str] = None
    status: str  # "needsAction" or "completed"
    due: Optional[str] = None
    completed: Optional[str] = None
    updated: str
    position: Optional[str] = None
    parent: Optional[str] = None  # Parent task ID if this is a subtask


class GroupedTasksResponse(BaseModel):
    """Tasks grouped by priority/timing"""
    overdue: List[TaskResponse] = []
    today: List[TaskResponse] = []
    this_week: List[TaskResponse] = []
    someday: List[TaskResponse] = []
    completed_today: List[TaskResponse] = []


class NaturalLanguageRequest(BaseModel):
    """Request for natural language task operations via the workspace agent"""
    text: str = Field(..., min_length=1, description="Natural language task instruction")


class NaturalLanguageResponse(BaseModel):
    """Response from natural language task operation"""
    success: bool
    message: str
    agent_response: str


class TaskListResponse(BaseModel):
    """Response for a single task list"""
    id: str
    title: str


class MoveTaskRequest(BaseModel):
    """Request to move a task to another list"""
    source_tasklist_id: str = Field(..., description="Current task list ID")
    destination_tasklist_id: str = Field(..., description="Target task list ID")


class CreateTaskListRequest(BaseModel):
    """Request to create a new task list"""
    title: str = Field(..., min_length=1, description="Title of the new list")


# ============== Helper Functions ==============

async def get_tasks_service(user: User):
    """Build Google Tasks service for user with fresh credentials"""
    # Get fresh access token (this handles refresh automatically)
    access_token = await refresh_google_token(user.email)

    if not access_token:
        raise HTTPException(
            status_code=401,
            detail="Google account not connected or token expired. Please reconnect in Settings."
        )

    # Build credentials with just the access token
    # refresh_google_token already ensures we have a valid token
    credentials = Credentials(token=access_token)

    return build('tasks', 'v1', credentials=credentials)


def parse_due_date(due_str: Optional[str]) -> Optional[datetime]:
    """Parse Google Tasks due date string to datetime"""
    if not due_str:
        return None
    try:
        # Google Tasks returns RFC3339 format
        return datetime.fromisoformat(due_str.replace('Z', '+00:00'))
    except:
        return None


def group_tasks(tasks: List[dict]) -> GroupedTasksResponse:
    """Group tasks by timing: overdue, today, this_week, someday, completed_today"""
    from datetime import timezone

    # Use UTC for consistent timezone-aware comparisons
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)
    week_end = today_start + timedelta(days=7)

    groups = GroupedTasksResponse()

    for task in tasks:
        task_response = TaskResponse(
            id=task['id'],
            tasklist_id=task.get('tasklist_id'),  # For non-default lists
            tasklist_title=task.get('tasklist_title'),  # Display name
            title=task.get('title', ''),
            notes=task.get('notes'),
            status=task.get('status', 'needsAction'),
            due=task.get('due'),
            completed=task.get('completed'),
            updated=task.get('updated', ''),
            position=task.get('position'),
            parent=task.get('parent')  # Include parent ID for subtask hierarchy
        )

        # Check if completed today
        if task.get('status') == 'completed':
            completed_time = parse_due_date(task.get('completed'))
            if completed_time and completed_time >= today_start:
                groups.completed_today.append(task_response)
            continue

        # Parse due date for active tasks
        due = parse_due_date(task.get('due'))

        if not due:
            groups.someday.append(task_response)
        elif due < now:
            groups.overdue.append(task_response)
        elif due < today_end:
            groups.today.append(task_response)
        elif due < week_end:
            groups.this_week.append(task_response)
        else:
            groups.someday.append(task_response)

    return groups


async def parse_task_text(text: str) -> ParsedTask:
    """
    Use AI to parse natural language task into structured data.

    Examples:
    - "Call John tomorrow at 2pm" -> title="Call John", due=tomorrow 14:00
    - "URGENT: Review contract by Friday" -> title="Review contract", due=friday, priority=urgent
    """
    from pydantic_ai import Agent

    today = datetime.now()

    parser_agent = Agent(
        model="anthropic:claude-haiku-4-5-20251001",
        system_prompt=f"""You are a task parser. Extract structured task data from natural language.

Today is {today.strftime('%A, %B %d, %Y')} at {today.strftime('%H:%M')}.

Parse the input and return JSON with:
- title: The core task description (without date/time/priority words)
- due_date: ISO datetime string if mentioned, or null. Convert relative dates like "tomorrow", "next week", "Friday" to actual dates.
- priority: "urgent", "high", "normal", or "low" based on language cues
- notes: Any additional context that shouldn't be in the title, or null

Examples:
- "Call John tomorrow at 2pm" -> {{"title": "Call John", "due_date": "{(today + timedelta(days=1)).strftime('%Y-%m-%d')}T14:00:00", "priority": "normal", "notes": null}}
- "URGENT: Review contract" -> {{"title": "Review contract", "due_date": null, "priority": "urgent", "notes": null}}
- "Buy groceries" -> {{"title": "Buy groceries", "due_date": null, "priority": "normal", "notes": null}}

Return ONLY valid JSON, no explanation.""",
        output_type=ParsedTask
    )

    result = await parser_agent.run(text)
    return result.output


# ============== API Endpoints ==============

@router.post("/natural", response_model=NaturalLanguageResponse)
async def process_natural_language(
    request: NaturalLanguageRequest,
    user: User = Depends(get_current_user)
):
    """
    Process natural language task commands through the Google Workspace agent.

    This routes the request through the same AI agent used in chat, providing
    consistent intelligence whether you're using the Tasks UI or chat interface.

    Examples:
    - "Add a task to call John tomorrow at 2pm"
    - "Create a reminder to review the proposal by Friday"
    - "Add task: Buy groceries"

    The agent will parse the intent and create/modify tasks accordingly.
    """
    try:
        logger.info(f"[Tasks NL] Processing: {request.text[:100]}...")

        # Create minimal state for the agent
        state = ConversationState(
            thread_id=f"tasks-{uuid.uuid4().hex[:8]}",
            user_id=str(user.id),
            user_request=request.text
        )

        # Create dependencies for the workspace agent
        deps = GoogleWorkspaceDeps(
            state=state,
            google_access_token=None,  # Will be refreshed by agent
            google_refresh_token=None,
            google_token_expiry=None
        )

        # Create and run the workspace agent with task-focused prompt
        agent = GoogleWorkspaceAgent()

        # Build a task-focused prompt
        task_prompt = f"""The user wants to manage their Google Tasks. Please help with the following request:

"{request.text}"

Important:
- Use tasks_create_task to create new tasks
- Use tasks_list_tasks to see existing tasks (returns task IDs needed for other operations)
- Use tasks_complete_task to mark a task as done (requires task ID)
- Use tasks_update_task to change title, notes, or due date (requires task ID)
- Use tasks_delete_task to remove a task (requires task ID)

CRITICAL: For complete, update, or delete operations, you MUST first call tasks_list_tasks to get the actual task IDs. Never guess or make up task IDs.

- Parse any dates/times mentioned (like "tomorrow", "next Friday", "at 2pm")
- For due dates, use ISO format (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)
- Today's date is {datetime.now().strftime('%Y-%m-%d')}

Execute the appropriate task operation and confirm what you did."""

        # Run the agent
        result = await agent.agent.run(task_prompt, deps=deps)

        logger.info(f"[Tasks NL] Agent completed successfully")

        return NaturalLanguageResponse(
            success=True,
            message="Task operation completed",
            agent_response=str(result.output) if hasattr(result, 'output') else str(result.data)
        )

    except Exception as e:
        logger.error(f"[Tasks NL] Error: {e}", exc_info=True)
        return NaturalLanguageResponse(
            success=False,
            message=f"Failed to process request: {str(e)}",
            agent_response=""
        )


@router.get("/lists", response_model=List[TaskListResponse])
async def list_task_lists(user: User = Depends(get_current_user)):
    """
    Get all task lists for the current user.
    Used by the frontend to populate list selection dropdowns.
    """
    try:
        service = await get_tasks_service(user)
        
        tasklists_result = service.tasklists().list().execute()
        tasklists = tasklists_result.get('items', [])
        
        logger.info(f"[Tasks] Returning {len(tasklists)} task lists")
        
        return [
            TaskListResponse(
                id=tl['id'],
                title=tl.get('title', 'Untitled')
            )
            for tl in tasklists
        ]
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list task lists: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list task lists: {str(e)}")


@router.post("/lists", response_model=TaskListResponse)
async def create_task_list(
    request: CreateTaskListRequest,
    user: User = Depends(get_current_user)
):
    """Create a new task list"""
    try:
        service = await get_tasks_service(user)
        
        result = service.tasklists().insert(
            body={'title': request.title}
        ).execute()
        
        logger.info(f"[Tasks] Created list '{request.title}' ({result['id']})")
        
        return TaskListResponse(
            id=result['id'],
            title=result.get('title', 'Untitled')
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create task list: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create task list: {str(e)}")


@router.delete("/lists/{tasklist_id}")
async def delete_task_list(
    tasklist_id: str,
    user: User = Depends(get_current_user)
):
    """
    Delete a task list.
    
    WARNING: This deletes all tasks in the list!
    Note: The default list cannot be deleted (API will return error).
    """
    try:
        service = await get_tasks_service(user)
        
        service.tasklists().delete(tasklist=tasklist_id).execute()
        
        logger.info(f"[Tasks] Deleted list {tasklist_id}")
        
        return {"success": True, "deleted_id": tasklist_id}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete task list: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete task list: {str(e)}")


@router.post("/{task_id}/move")
async def move_task(
    task_id: str,
    request: MoveTaskRequest,
    user: User = Depends(get_current_user)
):
    """
    Move a task from one list to another.
    
    Uses Google Tasks API's tasks.move() method with destinationTasklist parameter.
    Note: Recurrent tasks cannot be moved between lists.
    """
    try:
        service = await get_tasks_service(user)
        
        logger.info(f"[Tasks] Moving task {task_id} from {request.source_tasklist_id} to {request.destination_tasklist_id}")
        
        # Use tasks.move() with destinationTasklist to move between lists
        result = service.tasks().move(
            tasklist=request.source_tasklist_id,
            task=task_id,
            destinationTasklist=request.destination_tasklist_id
        ).execute()
        
        logger.info(f"[Tasks] Task {task_id} moved successfully")
        
        return {
            "success": True,
            "task": TaskResponse(
                id=result['id'],
                tasklist_id=request.destination_tasklist_id,
                title=result.get('title', ''),
                notes=result.get('notes'),
                status=result.get('status', 'needsAction'),
                due=result.get('due'),
                completed=result.get('completed'),
                updated=result.get('updated', ''),
                position=result.get('position'),
                parent=result.get('parent')
            )
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to move task: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to move task: {str(e)}")


@router.get("", response_model=GroupedTasksResponse)
async def list_tasks(
    include_completed: bool = False,
    max_results: int = 100,
    user: User = Depends(get_current_user)
):
    """
    List all tasks from ALL task lists, grouped by timing.
    Includes tasks from Google Docs and other linked sources.
    """
    try:
        service = await get_tasks_service(user)

        # First, get all task lists
        tasklists_result = service.tasklists().list().execute()
        tasklists = tasklists_result.get('items', [])

        logger.info(f"[Tasks] Found {len(tasklists)} task lists: {[t.get('title', 'Untitled') for t in tasklists]}")

        all_tasks = []

        # Fetch tasks from each list
        for tasklist in tasklists:
            tasklist_id = tasklist['id']
            tasklist_title = tasklist.get('title', 'Untitled')

            result = service.tasks().list(
                tasklist=tasklist_id,
                maxResults=max_results,
                showCompleted=include_completed,
                showHidden=True  # Include tasks from Google Docs which may be "hidden"
            ).execute()

            tasks = result.get('items', [])
            logger.info(f"[Tasks] List '{tasklist_title}' ({tasklist_id}): {len(tasks)} tasks")

            # Add tasklist info to each task for later operations
            for task in tasks:
                task['tasklist_id'] = tasklist_id
                task['tasklist_title'] = tasklist_title
                all_tasks.append(task)

        logger.info(f"[Tasks] Total tasks across all lists: {len(all_tasks)}")

        # Group by timing
        grouped = group_tasks(all_tasks)

        return grouped

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list tasks: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list tasks: {str(e)}")


@router.get("/raw")
async def list_tasks_raw(
    include_completed: bool = False,
    max_results: int = 100,
    user: User = Depends(get_current_user)
):
    """List all tasks without grouping (raw Google API response)"""
    try:
        service = await get_tasks_service(user)

        result = service.tasks().list(
            tasklist='@default',
            maxResults=max_results,
            showCompleted=include_completed,
            showHidden=False
        ).execute()

        return {"tasks": result.get('items', [])}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list tasks: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list tasks: {str(e)}")


@router.post("")
async def create_task(
    request: CreateTaskRequest,
    user: User = Depends(get_current_user)
):
    """
    Create a new task. Supports natural language input.

    Example: "Call John tomorrow at 2pm about the project"
    -> Creates task with title "Call John about the project", due tomorrow at 2pm
    """
    try:
        service = await get_tasks_service(user)

        # Parse natural language if enabled
        if request.parse_natural_language:
            parsed = await parse_task_text(request.text)
            title = parsed.title
            due_date = parsed.due_date
            notes = parsed.notes or request.notes
        else:
            title = request.text
            due_date = request.due_date
            notes = request.notes

        # Build task body
        task_body = {'title': title}

        if notes:
            task_body['notes'] = notes

        if due_date:
            # Ensure RFC3339 format for Google Tasks API
            if 'T' not in due_date:
                # Date only (e.g., "2024-12-14") - add midnight UTC
                due_date = due_date + 'T00:00:00.000Z'
            elif not due_date.endswith('Z') and '+' not in due_date:
                # Has time but no timezone - add Z for UTC
                due_date = due_date + 'Z'
            task_body['due'] = due_date

        # Create task in specified list or default
        target_list = request.tasklist_id or '@default'
        result = service.tasks().insert(
            tasklist=target_list,
            body=task_body
        ).execute()

        logger.info(f"Task created: {result['id']} - {title}")

        return {
            "success": True,
            "task": TaskResponse(
                id=result['id'],
                tasklist_id=target_list if target_list != '@default' else None,
                title=result.get('title', ''),
                notes=result.get('notes'),
                status=result.get('status', 'needsAction'),
                due=result.get('due'),
                completed=result.get('completed'),
                updated=result.get('updated', ''),
                position=result.get('position'),
                parent=result.get('parent')
            ),
            "parsed": {
                "original": request.text,
                "title": title,
                "due_date": due_date,
                "notes": notes
            } if request.parse_natural_language else None
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create task: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create task: {str(e)}")


@router.get("/{task_id}")
async def get_task(
    task_id: str,
    user: User = Depends(get_current_user)
):
    """Get a single task by ID"""
    try:
        service = await get_tasks_service(user)

        result = service.tasks().get(
            tasklist='@default',
            task=task_id
        ).execute()

        return TaskResponse(
            id=result['id'],
            title=result.get('title', ''),
            notes=result.get('notes'),
            status=result.get('status', 'needsAction'),
            due=result.get('due'),
            completed=result.get('completed'),
            updated=result.get('updated', ''),
            position=result.get('position'),
            parent=result.get('parent')
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get task: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get task: {str(e)}")


@router.patch("/{task_id}")
async def update_task(
    task_id: str,
    request: UpdateTaskRequest,
    tasklist_id: str = "@default",
    user: User = Depends(get_current_user)
):
    """Update a task"""
    try:
        service = await get_tasks_service(user)

        # Get current task
        current = service.tasks().get(
            tasklist=tasklist_id,
            task=task_id
        ).execute()

        # Update fields
        if request.title is not None:
            current['title'] = request.title
        if request.notes is not None:
            current['notes'] = request.notes
        if request.due_date is not None:
            current['due'] = request.due_date
        if request.status is not None:
            current['status'] = request.status

        # Save
        result = service.tasks().update(
            tasklist=tasklist_id,
            task=task_id,
            body=current
        ).execute()

        return {
            "success": True,
            "task": TaskResponse(
                id=result['id'],
                tasklist_id=tasklist_id,
                title=result.get('title', ''),
                notes=result.get('notes'),
                status=result.get('status', 'needsAction'),
                due=result.get('due'),
                completed=result.get('completed'),
                updated=result.get('updated', ''),
                position=result.get('position'),
                parent=result.get('parent')
            )
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update task: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update task: {str(e)}")


@router.patch("/{task_id}/complete")
async def complete_task(
    task_id: str,
    tasklist_id: str = "@default",
    user: User = Depends(get_current_user)
):
    """Mark a task as completed"""
    try:
        service = await get_tasks_service(user)

        # Get current task
        current = service.tasks().get(
            tasklist=tasklist_id,
            task=task_id
        ).execute()

        # Mark complete
        current['status'] = 'completed'

        result = service.tasks().update(
            tasklist=tasklist_id,
            task=task_id,
            body=current
        ).execute()

        logger.info(f"Task completed: {task_id}")

        return {
            "success": True,
            "task": TaskResponse(
                id=result['id'],
                title=result.get('title', ''),
                notes=result.get('notes'),
                status=result.get('status', 'completed'),
                due=result.get('due'),
                completed=result.get('completed'),
                updated=result.get('updated', ''),
                position=result.get('position'),
                parent=result.get('parent')
            )
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to complete task: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to complete task: {str(e)}")


@router.patch("/{task_id}/uncomplete")
async def uncomplete_task(
    task_id: str,
    tasklist_id: str = "@default",
    user: User = Depends(get_current_user)
):
    """Mark a task as not completed (reopen)"""
    try:
        service = await get_tasks_service(user)

        # Get current task
        current = service.tasks().get(
            tasklist=tasklist_id,
            task=task_id
        ).execute()

        # Mark incomplete
        current['status'] = 'needsAction'
        # Remove completed timestamp
        if 'completed' in current:
            del current['completed']

        result = service.tasks().update(
            tasklist=tasklist_id,
            task=task_id,
            body=current
        ).execute()

        logger.info(f"Task reopened: {task_id}")

        return {
            "success": True,
            "task": TaskResponse(
                id=result['id'],
                tasklist_id=tasklist_id,
                title=result.get('title', ''),
                notes=result.get('notes'),
                status=result.get('status', 'needsAction'),
                due=result.get('due'),
                completed=result.get('completed'),
                updated=result.get('updated', ''),
                position=result.get('position'),
                parent=result.get('parent')
            )
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to uncomplete task: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to uncomplete task: {str(e)}")


@router.delete("/{task_id}")
async def delete_task(
    task_id: str,
    tasklist_id: str = "@default",
    user: User = Depends(get_current_user)
):
    """Delete a task"""
    try:
        service = await get_tasks_service(user)

        service.tasks().delete(
            tasklist=tasklist_id,
            task=task_id
        ).execute()

        logger.info(f"Task deleted: {task_id}")

        return {"success": True, "deleted_id": task_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete task: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete task: {str(e)}")


@router.post("/{task_id}/subtasks")
async def create_subtask(
    task_id: str,
    request: CreateTaskRequest,
    tasklist_id: str = "@default",
    user: User = Depends(get_current_user)
):
    """
    Create a new subtask under a parent task.

    Google Tasks only supports 1 level of subtask nesting.
    The subtask is created and then moved under the parent using the move API.

    Note: Assigned tasks (from Docs/Chat) and repeating tasks cannot be parents.
    """
    try:
        service = await get_tasks_service(user)

        # Parse natural language if enabled
        if request.parse_natural_language:
            parsed = await parse_task_text(request.text)
            title = parsed.title
            due_date = parsed.due_date
            notes = parsed.notes or request.notes
        else:
            title = request.text
            due_date = request.due_date
            notes = request.notes

        # Build task body
        task_body = {'title': title}

        if notes:
            task_body['notes'] = notes

        if due_date:
            # Ensure RFC3339 format for Google Tasks API
            if 'T' not in due_date:
                due_date = due_date + 'T00:00:00.000Z'
            elif not due_date.endswith('Z') and '+' not in due_date:
                due_date = due_date + 'Z'
            task_body['due'] = due_date

        # Step 1: Create the task
        created = service.tasks().insert(
            tasklist=tasklist_id,
            body=task_body
        ).execute()

        logger.info(f"[Subtask] Created task {created['id']}, now moving under parent {task_id}")

        # Step 2: Move it under the parent to make it a subtask
        result = service.tasks().move(
            tasklist=tasklist_id,
            task=created['id'],
            parent=task_id  # This makes it a subtask
        ).execute()

        logger.info(f"[Subtask] Task {result['id']} is now a subtask of {task_id}")

        return {
            "success": True,
            "task": TaskResponse(
                id=result['id'],
                tasklist_id=tasklist_id if tasklist_id != '@default' else None,
                title=result.get('title', ''),
                notes=result.get('notes'),
                status=result.get('status', 'needsAction'),
                due=result.get('due'),
                completed=result.get('completed'),
                updated=result.get('updated', ''),
                position=result.get('position'),
                parent=result.get('parent')
            ),
            "parsed": {
                "original": request.text,
                "title": title,
                "due_date": due_date,
                "notes": notes
            } if request.parse_natural_language else None
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create subtask: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create subtask: {str(e)}")


@router.post("/{task_id}/promote")
async def promote_subtask(
    task_id: str,
    tasklist_id: str = "@default",
    user: User = Depends(get_current_user)
):
    """
    Promote a subtask to a top-level task.

    This removes the parent relationship by moving the task without specifying a parent.
    """
    try:
        service = await get_tasks_service(user)

        # Move without parent parameter = promote to top level
        result = service.tasks().move(
            tasklist=tasklist_id,
            task=task_id
            # No parent parameter = top-level task
        ).execute()

        logger.info(f"[Subtask] Task {task_id} promoted to top-level")

        return {
            "success": True,
            "task": TaskResponse(
                id=result['id'],
                tasklist_id=tasklist_id if tasklist_id != '@default' else None,
                title=result.get('title', ''),
                notes=result.get('notes'),
                status=result.get('status', 'needsAction'),
                due=result.get('due'),
                completed=result.get('completed'),
                updated=result.get('updated', ''),
                position=result.get('position'),
                parent=result.get('parent')  # Should be None after promotion
            )
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to promote subtask: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to promote subtask: {str(e)}")
