"""
Initialize RBAC (Role-Based Access Control) system
Creates permissions, roles, and assigns default roles to existing users
"""

import asyncio
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from sqlalchemy.orm import selectinload
from database.models import User, Role, Permission, Base, DatabaseManager

# Define all permissions
PERMISSIONS = [
    # Chat
    {"name": "chat.access", "description": "Access to chat interface", "category": "chat"},

    # CMS
    {"name": "cms.access", "description": "Access to Content Management System", "category": "cms"},

    # Dashboard
    {"name": "dashboard.access", "description": "Access to analytics dashboard", "category": "dashboard"},

    # Price Monitor
    {"name": "price_monitor.access", "description": "Access to price monitoring", "category": "price_monitor"},

    # Inventory Prediction
    {"name": "inventory.access", "description": "Access to inventory prediction and forecasting", "category": "inventory"},

    # Memory
    {"name": "memory.access", "description": "Access to memory management", "category": "memory"},

    # Notes
    {"name": "notes.access", "description": "Access to notes system (second brain)", "category": "notes"},

    # Google Workspace (Gmail, Calendar, Drive, Tasks)
    {"name": "google_workspace.access", "description": "Access to Google Workspace features (Tasks, Gmail, Calendar)", "category": "google_workspace"},

    # Settings
    {"name": "settings.access", "description": "Access to user settings", "category": "settings"},

    # Admin
    {"name": "admin.manage_users", "description": "Manage user roles and permissions", "category": "admin"},
    {"name": "admin.manage_roles", "description": "Create/edit/delete roles", "category": "admin"},
]

# Define roles with their permissions
ROLES = [
    {
        "name": "Super Admin",
        "description": "Full system access",
        "is_system": True,
        "permissions": [p["name"] for p in PERMISSIONS]  # All permissions
    },
    {
        "name": "Admin",
        "description": "Administrator with full access except role management",
        "is_system": True,
        "permissions": [
            "chat.access",
            "cms.access",
            "dashboard.access",
            "price_monitor.access",
            "inventory.access",
            "memory.access",
            "notes.access",
            "google_workspace.access",
            "settings.access",
            "admin.manage_users",
        ]
    },
    {
        "name": "Employee",
        "description": "Standard employee - dashboard and monitoring only",
        "is_system": True,
        "permissions": [
            "dashboard.access",
            "price_monitor.access",
            "inventory.access",
            "memory.access",
            "notes.access",
            "google_workspace.access",
            "settings.access",
        ]
    },
    {
        "name": "CMS Editor",
        "description": "Content management access",
        "is_system": True,
        "permissions": [
            "cms.access",
            "dashboard.access",
            "notes.access",
            "settings.access",
        ]
    },
    {
        "name": "Chat User",
        "description": "AI assistant chat access",
        "is_system": True,
        "permissions": [
            "chat.access",
            "dashboard.access",
            "memory.access",
            "notes.access",
            "google_workspace.access",
            "settings.access",
        ]
    },
    {
        "name": "Viewer",
        "description": "Read-only dashboard access",
        "is_system": True,
        "permissions": [
            "dashboard.access",
            "settings.access",
        ]
    },
]


async def init_rbac(database_url: str):
    """Initialize RBAC system"""
    print("🔐 Initializing RBAC system...")

    db_manager = DatabaseManager(database_url)

    # Create tables
    print("📊 Creating tables...")
    await db_manager.create_tables()

    async with db_manager.async_session() as session:
        # Create permissions
        print("\n✨ Creating permissions...")
        permission_map = {}
        for perm_data in PERMISSIONS:
            # Check if permission already exists
            result = await session.execute(
                select(Permission).where(Permission.name == perm_data["name"])
            )
            existing = result.scalar_one_or_none()

            if existing:
                print(f"  ✓ {perm_data['name']} (already exists)")
                permission_map[perm_data["name"]] = existing
            else:
                perm = Permission(**perm_data)
                session.add(perm)
                await session.flush()
                permission_map[perm_data["name"]] = perm
                print(f"  + {perm_data['name']}")

        await session.commit()

        # Create roles
        print("\n👥 Creating roles...")
        role_map = {}
        for role_data in ROLES:
            # Check if role already exists
            result = await session.execute(
                select(Role)
                .where(Role.name == role_data["name"])
                .options(selectinload(Role.permissions))
            )
            existing = result.scalar_one_or_none()

            perm_names = role_data.pop("permissions")

            if existing:
                print(f"  ✓ {role_data['name']} (already exists)")
                role = existing
                # Update permissions (replace existing with new list)
                role.permissions.clear()
                role.permissions.extend([permission_map[pname] for pname in perm_names])
            else:
                role = Role(
                    name=role_data["name"],
                    description=role_data["description"],
                    is_system=role_data["is_system"]
                )
                role.permissions = [permission_map[pname] for pname in perm_names]
                session.add(role)
                await session.flush()
                print(f"  + {role_data['name']} ({len(perm_names)} permissions)")

            role_map[role_data["name"]] = role

        await session.commit()

        # Migrate existing users
        print("\n🔄 Migrating existing users...")
        result = await session.execute(
            select(User).options(selectinload(User.roles))
        )
        users = result.scalars().all()

        for user in users:
            # Check if user already has roles
            if len(user.roles) > 0:
                print(f"  ✓ {user.email} (already has roles)")
                continue

            # Assign role based on is_admin flag
            if user.is_admin:
                user.roles.append(role_map["Super Admin"])
                print(f"  + {user.email} → Super Admin")
            else:
                # Default to Employee for non-admin users
                user.roles.append(role_map["Employee"])
                print(f"  + {user.email} → Employee")

        await session.commit()

        print("\n✅ RBAC initialization complete!")
        print("\n📋 Summary:")
        print(f"  Permissions: {len(PERMISSIONS)}")
        print(f"  Roles: {len(ROLES)}")
        print(f"  Users migrated: {len(users)}")

    await db_manager.close()


if __name__ == "__main__":
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("❌ DATABASE_URL environment variable not set")
        exit(1)

    asyncio.run(init_rbac(database_url))
