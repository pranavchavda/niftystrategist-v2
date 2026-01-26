#!/usr/bin/env python3
"""
Tool Call Results Cache

Stores expensive tool call results per-conversation to avoid redundant operations.
The orchestrator can explicitly browse, retrieve, and store cache entries.
"""

import os
import sys
import json
import uuid
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

# Get the directory where this script is located
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Construct the path to the database directory
DATABASE_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, '..', '..', 'database'))

# Ensure the database directory exists
if not os.path.exists(DATABASE_DIR):
    os.makedirs(DATABASE_DIR)


class ToolCache:
    """
    Thread-specific cache for tool call results.

    Stores expensive operation results to avoid redundant calls.
    Supports smart invalidation when related actions occur.
    """

    def __init__(self, thread_id: str):
        """
        Initialize the tool cache for a specific thread.

        Args:
            thread_id: The conversation thread ID
        """
        if not thread_id:
            raise ValueError("A thread_id is required to initialize the tool cache.")

        self.thread_id = thread_id
        self.cache_file = os.path.join(DATABASE_DIR, f'tool_cache_thread_{self.thread_id}.json')
        self._data = self._load_cache()

    def _load_cache(self) -> Dict[str, Any]:
        """Load cache from JSON file."""
        if not os.path.exists(self.cache_file):
            return {
                "cache_entries": [],
                "invalidation_log": []
            }

        try:
            with open(self.cache_file, 'r') as f:
                return json.load(f)
        except (IOError, json.JSONDecodeError) as e:
            print(f"Error loading cache: {e}", file=sys.stderr)
            return {
                "cache_entries": [],
                "invalidation_log": []
            }

    def _save_cache(self):
        """Save cache to JSON file."""
        try:
            with open(self.cache_file, 'w') as f:
                json.dump(self._data, f, indent=2)
        except IOError as e:
            print(f"Error saving cache: {e}", file=sys.stderr)

    def store(
        self,
        tool_name: str,
        parameters: Dict[str, Any],
        result: Any,
        summary: str = "",
        invalidation_triggers: Optional[List[str]] = None,
        tokens_saved: int = 0,
        execution_time_ms: int = 0
    ) -> str:
        """
        Store a tool call result in the cache.

        Args:
            tool_name: Name of the tool that was called
            parameters: Parameters used in the tool call
            result: The result from the tool call
            summary: Brief description of what this result contains
            invalidation_triggers: List of actions that should invalidate this cache
            tokens_saved: Estimated tokens saved by caching
            execution_time_ms: Original execution time in milliseconds

        Returns:
            cache_id: Unique identifier for this cache entry
        """
        cache_id = str(uuid.uuid4())

        entry = {
            "cache_id": cache_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "tool_name": tool_name,
            "parameters": parameters,
            "result": result,
            "summary": summary,
            "metadata": {
                "tokens_saved": tokens_saved,
                "execution_time_ms": execution_time_ms,
                "invalidation_triggers": invalidation_triggers or [],
                "is_valid": True
            }
        }

        self._data["cache_entries"].append(entry)
        self._save_cache()

        return cache_id

    def lookup(self, query: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        List cache entries (optionally filtered by query).

        Args:
            query: Optional search term to filter entries

        Returns:
            List of cache entry summaries (without full results)
        """
        valid_entries = [
            e for e in self._data["cache_entries"]
            if e.get("metadata", {}).get("is_valid", True)
        ]

        # Filter by query if provided
        if query:
            query_lower = query.lower()
            valid_entries = [
                e for e in valid_entries
                if query_lower in e.get("tool_name", "").lower()
                or query_lower in e.get("summary", "").lower()
                or query_lower in json.dumps(e.get("parameters", {})).lower()
            ]

        # Return summary info only (not full results)
        return [
            {
                "cache_id": e["cache_id"],
                "timestamp": e["timestamp"],
                "tool_name": e["tool_name"],
                "parameters": e["parameters"],
                "summary": e.get("summary", ""),
                "age_minutes": self._calculate_age_minutes(e["timestamp"]),
                "tokens_saved": e.get("metadata", {}).get("tokens_saved", 0)
            }
            for e in valid_entries
        ]

    def get_entry(self, cache_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the full cached result by cache_id.

        Args:
            cache_id: The unique cache identifier

        Returns:
            Full cache entry including result, or None if not found
        """
        for entry in self._data["cache_entries"]:
            if entry["cache_id"] == cache_id:
                if entry.get("metadata", {}).get("is_valid", True):
                    return entry
                else:
                    return None

        return None

    def invalidate(self, trigger: str):
        """
        Invalidate cache entries matching a trigger.

        Args:
            trigger: The invalidation trigger (e.g., "product_create")
        """
        invalidated_ids = []

        for entry in self._data["cache_entries"]:
            triggers = entry.get("metadata", {}).get("invalidation_triggers", [])
            if trigger in triggers and entry.get("metadata", {}).get("is_valid", True):
                entry["metadata"]["is_valid"] = False
                invalidated_ids.append(entry["cache_id"])

        if invalidated_ids:
            self._data["invalidation_log"].append({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "trigger": trigger,
                "invalidated_entries": invalidated_ids
            })

            self._save_cache()

        return len(invalidated_ids)

    def delete_entry(self, cache_id: str) -> bool:
        """
        Manually delete a cache entry.

        Args:
            cache_id: The unique cache identifier

        Returns:
            True if entry was deleted, False if not found
        """
        original_length = len(self._data["cache_entries"])
        self._data["cache_entries"] = [
            e for e in self._data["cache_entries"]
            if e["cache_id"] != cache_id
        ]

        deleted = len(self._data["cache_entries"]) < original_length

        if deleted:
            self._save_cache()

        return deleted

    def clear(self):
        """Clear all cache entries."""
        self._data = {
            "cache_entries": [],
            "invalidation_log": []
        }
        self._save_cache()

    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache usage statistics
        """
        valid_entries = [
            e for e in self._data["cache_entries"]
            if e.get("metadata", {}).get("is_valid", True)
        ]

        invalid_entries = [
            e for e in self._data["cache_entries"]
            if not e.get("metadata", {}).get("is_valid", True)
        ]

        total_tokens_saved = sum(
            e.get("metadata", {}).get("tokens_saved", 0)
            for e in valid_entries
        )

        total_time_saved_ms = sum(
            e.get("metadata", {}).get("execution_time_ms", 0)
            for e in valid_entries
        )

        return {
            "total_entries": len(self._data["cache_entries"]),
            "valid_entries": len(valid_entries),
            "invalid_entries": len(invalid_entries),
            "total_tokens_saved": total_tokens_saved,
            "total_time_saved_ms": total_time_saved_ms,
            "total_time_saved_seconds": round(total_time_saved_ms / 1000, 2),
            "invalidation_count": len(self._data["invalidation_log"])
        }

    def _calculate_age_minutes(self, timestamp_iso: str) -> int:
        """Calculate age in minutes from ISO timestamp."""
        try:
            cached_time = datetime.fromisoformat(timestamp_iso.replace('Z', '+00:00'))
            age = datetime.now(timezone.utc) - cached_time.replace(tzinfo=None)
            return int(age.total_seconds() / 60)
        except (ValueError, AttributeError):
            return 0


def print_json(data):
    """Print data in JSON format."""
    print(json.dumps(data, indent=2))


if __name__ == '__main__':
    # Simple CLI for testing
    import argparse

    parser = argparse.ArgumentParser(description='Tool Call Cache Management')
    parser.add_argument('--thread-id', required=True, help='Thread ID')
    parser.add_argument('command', choices=['lookup', 'get', 'stats', 'clear'])
    parser.add_argument('--cache-id', help='Cache ID (for get command)')
    parser.add_argument('--query', help='Search query (for lookup command)')

    args = parser.parse_args()

    cache = ToolCache(args.thread_id)

    if args.command == 'lookup':
        results = cache.lookup(args.query)
        print_json(results)
    elif args.command == 'get':
        if not args.cache_id:
            print("Error: --cache-id required for get command", file=sys.stderr)
            sys.exit(1)
        entry = cache.get_entry(args.cache_id)
        print_json(entry)
    elif args.command == 'stats':
        stats = cache.get_stats()
        print_json(stats)
    elif args.command == 'clear':
        cache.clear()
        print("Cache cleared.")
