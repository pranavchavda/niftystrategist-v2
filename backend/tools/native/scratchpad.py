#!/usr/bin/env python3
"""A tool for managing a scratchpad."""

import os
import sys
import argparse
import json
from datetime import datetime, timezone

# Get the directory where this script is located
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Construct the path to the database directory
DATABASE_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, '..', '..', 'database'))

# Ensure the database directory exists
if not os.path.exists(DATABASE_DIR):
    os.makedirs(DATABASE_DIR)

class Scratchpad:
    """A simple JSON-based scratchpad that is thread-specific."""

    def __init__(self, thread_id: str):
        if not thread_id:
            raise ValueError("A thread_id is required to initialize the scratchpad.")
        self.thread_id = thread_id
        self.scratchpad_file = os.path.join(DATABASE_DIR, f'scratchpad_thread_{self.thread_id}.json')
        self._entries = self._load_entries()

    def _load_entries(self) -> list:
        if not os.path.exists(self.scratchpad_file):
            return []
        try:
            with open(self.scratchpad_file, 'r') as f:
                return json.load(f)
        except (IOError, json.JSONDecodeError):
            return []

    def _save_entries(self):
        try:
            with open(self.scratchpad_file, 'w') as f:
                json.dump(self._entries, f, indent=2)
        except IOError as e:
            print(f"Error saving scratchpad: {e}", file=sys.stderr)

    def add_entry(self, content: str, author: str = "agent"):
        """Add a new entry to the scratchpad."""
        entry = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'author': author,
            'content': content
        }
        self._entries.append(entry)
        self._save_entries()
        return entry

    def get_entries(self) -> list:
        """Get all scratchpad entries."""
        return self._entries

    def update_entry(self, index: int, content: str):
        """Update an existing entry."""
        if 0 <= index < len(self._entries):
            self._entries[index]['content'] = content
            self._entries[index]['timestamp'] = datetime.now(timezone.utc).isoformat()
            self._save_entries()
        else:
            raise IndexError(f"Entry index {index} out of range")

    def delete_entry(self, index: int):
        """Delete an entry by index."""
        if 0 <= index < len(self._entries):
            del self._entries[index]
            self._save_entries()
        else:
            raise IndexError(f"Entry index {index} out of range")

    def clear_entries(self):
        """Clear all entries from the scratchpad."""
        self._entries = []
        self._save_entries()

def main():
    """Main function to run the scratchpad tool."""
    parser = argparse.ArgumentParser(
        description='A tool for managing a scratchpad.',
        formatter_class=argparse.RawTextHelpFormatter,
        epilog='''
Examples:
  # Add a new entry for a specific thread
  python scratchpad.py --thread-id 12345 add "This is a test entry."

  # Add an entry as a human
  python scratchpad.py --thread-id 12345 add "User note." --author human

  # Get all entries for a thread
  python scratchpad.py --thread-id 12345 get

  # Clear all entries for a thread
  python scratchpad.py --thread-id 12345 clear
'''
    )

    parser.add_argument('--thread-id', required=True, help='The thread ID for the scratchpad')
    subparsers = parser.add_subparsers(dest='command', required=True)

    # 'add' command
    add_parser = subparsers.add_parser('add', help='Add a new entry')
    add_parser.add_argument('content', help='The content of the entry')
    add_parser.add_argument('--author', default='agent', help='Author of the entry (agent or human)')

    # 'get' command
    get_parser = subparsers.add_parser('get', help='Get all entries')

    # 'clear' command
    clear_parser = subparsers.add_parser('clear', help='Clear all entries')

    args = parser.parse_args()

    scratchpad = Scratchpad(args.thread_id)

    if args.command == 'add':
        entry = scratchpad.add_entry(args.content, args.author)
        print_json(entry)
    elif args.command == 'get':
        entries = scratchpad.get_entries()
        print_json(entries)
    elif args.command == 'clear':
        scratchpad.clear_entries()
        print("Scratchpad cleared.")

def print_json(data):
    """Prints data in JSON format."""
    print(json.dumps(data, indent=2))

if __name__ == '__main__':
    main()
