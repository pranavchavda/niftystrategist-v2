"""
TODO tracking models for agent task management

Based on Claude Agent SDK patterns with AG-UI integration.
Enables real-time task tracking and progress visibility.
"""

from typing import Literal
from pydantic import BaseModel, Field


TaskStatus = Literal['pending', 'in_progress', 'completed']


class TodoItem(BaseModel):
    """
    Represents a single task in the agent's work plan

    The agent uses this to track progress through complex operations.
    Only ONE task should be 'in_progress' at any time.
    """

    content: str = Field(
        description="Task description in imperative form (e.g., 'Run tests', 'Fix authentication bug')"
    )

    status: TaskStatus = Field(
        default='pending',
        description="Current state: pending (not started), in_progress (active), completed (done)"
    )

    activeForm: str = Field(
        description="Present continuous form shown during execution (e.g., 'Running tests', 'Fixing authentication bug')"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "content": "Run unit tests",
                    "status": "pending",
                    "activeForm": "Running unit tests"
                },
                {
                    "content": "Fix memory leak in data processing",
                    "status": "in_progress",
                    "activeForm": "Fixing memory leak in data processing"
                },
                {
                    "content": "Update documentation",
                    "status": "completed",
                    "activeForm": "Updating documentation"
                }
            ]
        }
    }


class TodoList(BaseModel):
    """
    Collection of tasks representing the agent's work plan

    This is the main state object that gets emitted via AG-UI events.
    The frontend subscribes to updates and displays progress in real-time.
    """

    todos: list[TodoItem] = Field(
        default_factory=list,
        description="Ordered list of tasks to complete"
    )

    def get_in_progress(self) -> TodoItem | None:
        """Get the currently active task (should only be one)"""
        in_progress = [t for t in self.todos if t.status == 'in_progress']
        return in_progress[0] if in_progress else None

    def get_completed_count(self) -> int:
        """Count of completed tasks"""
        return sum(1 for t in self.todos if t.status == 'completed')

    def get_pending_count(self) -> int:
        """Count of pending tasks"""
        return sum(1 for t in self.todos if t.status == 'pending')

    def get_total_count(self) -> int:
        """Total number of tasks"""
        return len(self.todos)

    def get_progress_percentage(self) -> float:
        """Calculate completion percentage (0-100)"""
        total = self.get_total_count()
        if total == 0:
            return 0.0
        return (self.get_completed_count() / total) * 100

    def validate_single_in_progress(self) -> bool:
        """
        Ensure only ONE task is in_progress at a time

        This is a critical rule for maintaining clarity about what
        the agent is currently doing.
        """
        in_progress_count = sum(1 for t in self.todos if t.status == 'in_progress')
        return in_progress_count <= 1

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "todos": [
                        {
                            "content": "Analyze codebase structure",
                            "status": "completed",
                            "activeForm": "Analyzing codebase structure"
                        },
                        {
                            "content": "Implement user authentication",
                            "status": "in_progress",
                            "activeForm": "Implementing user authentication"
                        },
                        {
                            "content": "Write integration tests",
                            "status": "pending",
                            "activeForm": "Writing integration tests"
                        },
                        {
                            "content": "Deploy to staging",
                            "status": "pending",
                            "activeForm": "Deploying to staging"
                        }
                    ]
                }
            ]
        }
    }


class TodoUpdate(BaseModel):
    """
    Represents a change to the TODO list

    Used for validation and change tracking before emitting events.
    """

    action: Literal['create', 'update', 'complete', 'remove'] = Field(
        description="Type of change being made"
    )

    index: int | None = Field(
        default=None,
        description="Index of the task being modified (for update/complete/remove)"
    )

    new_todos: list[TodoItem] | None = Field(
        default=None,
        description="Complete new TODO list (for create action)"
    )

    new_status: TaskStatus | None = Field(
        default=None,
        description="New status for the task (for update action)"
    )


# Helper functions for TODO management

def create_todo_list(tasks: list[str]) -> TodoList:
    """
    Create a new TODO list from task descriptions

    Args:
        tasks: List of task descriptions in imperative form

    Returns:
        TodoList with all tasks in 'pending' state

    Example:
        >>> create_todo_list(["Run tests", "Fix bug", "Deploy"])
    """
    todos = []
    for task in tasks:
        # Convert imperative to continuous form
        # Simple heuristic: "Run X" -> "Running X", "Fix X" -> "Fixing X"
        active_form = task
        if task.startswith(('Run ', 'run ')):
            active_form = 'Running ' + task[4:]
        elif task.startswith(('Fix ', 'fix ')):
            active_form = 'Fixing ' + task[4:]
        elif task.startswith(('Add ', 'add ')):
            active_form = 'Adding ' + task[4:]
        elif task.startswith(('Create ', 'create ')):
            active_form = 'Creating ' + task[7:]
        elif task.startswith(('Update ', 'update ')):
            active_form = 'Updating ' + task[7:]
        elif task.startswith(('Delete ', 'delete ')):
            active_form = 'Deleting ' + task[7:]
        elif task.startswith(('Build ', 'build ')):
            active_form = 'Building ' + task[6:]
        elif task.startswith(('Deploy ', 'deploy ')):
            active_form = 'Deploying ' + task[7:]
        elif task.startswith(('Test ', 'test ')):
            active_form = 'Testing ' + task[5:]
        elif task.startswith(('Implement ', 'implement ')):
            active_form = 'Implementing ' + task[10:]
        elif task.startswith(('Refactor ', 'refactor ')):
            active_form = 'Refactoring ' + task[9:]
        else:
            # Default: add "ing" if verb ends in consonant
            # This is a simplification; real implementation might use NLP
            active_form = task + 'ing' if not task.endswith('e') else task[:-1] + 'ing'

        todos.append(TodoItem(
            content=task,
            status='pending',
            activeForm=active_form
        ))

    return TodoList(todos=todos)


def mark_in_progress(todo_list: TodoList, index: int) -> TodoList:
    """
    Mark a task as in_progress and ensure no other tasks are in_progress

    Args:
        todo_list: Current TODO list
        index: Index of task to mark as in_progress

    Returns:
        Updated TodoList

    Raises:
        IndexError: If index is out of range
        ValueError: If task is already completed
    """
    if index < 0 or index >= len(todo_list.todos):
        raise IndexError(f"Task index {index} out of range (0-{len(todo_list.todos)-1})")

    if todo_list.todos[index].status == 'completed':
        raise ValueError(f"Cannot mark completed task as in_progress")

    # Clear any existing in_progress tasks
    for todo in todo_list.todos:
        if todo.status == 'in_progress':
            todo.status = 'pending'

    # Mark the specified task as in_progress
    todo_list.todos[index].status = 'in_progress'

    return todo_list


def mark_completed(todo_list: TodoList, index: int) -> TodoList:
    """
    Mark a task as completed

    Args:
        todo_list: Current TODO list
        index: Index of task to mark as completed

    Returns:
        Updated TodoList

    Raises:
        IndexError: If index is out of range
    """
    if index < 0 or index >= len(todo_list.todos):
        raise IndexError(f"Task index {index} out of range (0-{len(todo_list.todos)-1})")

    todo_list.todos[index].status = 'completed'

    return todo_list
