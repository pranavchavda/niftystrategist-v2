"""
Admin API routes for user and role management (RBAC)
"""

import logging
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from auth import User, get_current_user, requires_permission
from database.session import AsyncSessionLocal
from database.models import User as DBUser, Role, Permission, AIModel

logger = logging.getLogger(__name__)

router = APIRouter()


# ========================================
# Pydantic Models
# ========================================

class PermissionResponse(BaseModel):
    """Permission response model"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: Optional[str]
    category: Optional[str]


class RoleResponse(BaseModel):
    """Role response model"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: Optional[str]
    is_system: bool
    permissions: List[PermissionResponse]


class UserResponse(BaseModel):
    """User response model with roles"""
    id: int
    email: str
    name: str
    is_admin: bool
    roles: List[str]  # List of role names


class RoleCreate(BaseModel):
    """Model for creating a new role"""
    name: str
    description: Optional[str] = None
    permission_ids: List[int]  # List of permission IDs


class RoleUpdate(BaseModel):
    """Model for updating a role"""
    name: Optional[str] = None
    description: Optional[str] = None
    permission_ids: Optional[List[int]] = None


class UserRolesUpdate(BaseModel):
    """Model for updating user's roles"""
    role_ids: List[int]  # List of role IDs to assign


# ========================================
# Permission Endpoints
# ========================================

@router.get("/api/admin/permissions", response_model=List[PermissionResponse])
async def list_permissions(
    current_user: User = Depends(requires_permission("admin.manage_users"))
):
    """
    List all available permissions.
    Requires: admin.manage_users permission
    """
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Permission))
            permissions = result.scalars().all()

            return [
                PermissionResponse(
                    id=p.id,
                    name=p.name,
                    description=p.description,
                    category=p.category
                )
                for p in permissions
            ]

    except Exception as e:
        logger.error(f"Error fetching permissions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ========================================
# Role Endpoints
# ========================================

@router.get("/api/admin/roles", response_model=List[RoleResponse])
async def list_roles(
    current_user: User = Depends(requires_permission("admin.manage_users"))
):
    """
    List all roles with their permissions.
    Requires: admin.manage_users permission
    """
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Role).options(selectinload(Role.permissions))
            )
            roles = result.scalars().all()

            return [
                RoleResponse(
                    id=r.id,
                    name=r.name,
                    description=r.description,
                    is_system=r.is_system,
                    permissions=[
                        PermissionResponse(
                            id=p.id,
                            name=p.name,
                            description=p.description,
                            category=p.category
                        )
                        for p in r.permissions
                    ]
                )
                for r in roles
            ]

    except Exception as e:
        logger.error(f"Error fetching roles: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/admin/roles", response_model=RoleResponse)
async def create_role(
    role_data: RoleCreate,
    current_user: User = Depends(requires_permission("admin.manage_roles"))
):
    """
    Create a new custom role.
    Requires: admin.manage_roles permission
    """
    try:
        async with AsyncSessionLocal() as db:
            # Check if role name already exists
            result = await db.execute(
                select(Role).where(Role.name == role_data.name)
            )
            existing = result.scalar_one_or_none()

            if existing:
                raise HTTPException(
                    status_code=400,
                    detail=f"Role '{role_data.name}' already exists"
                )

            # Fetch permissions
            result = await db.execute(
                select(Permission).where(Permission.id.in_(role_data.permission_ids))
            )
            permissions = result.scalars().all()

            if len(permissions) != len(role_data.permission_ids):
                raise HTTPException(
                    status_code=400,
                    detail="Some permission IDs are invalid"
                )

            # Create role
            new_role = Role(
                name=role_data.name,
                description=role_data.description,
                is_system=False  # Custom roles are never system roles
            )
            new_role.permissions = permissions

            db.add(new_role)
            await db.commit()
            await db.refresh(new_role)

            logger.info(f"Created new role: {new_role.name} by {current_user.email}")

            return RoleResponse(
                id=new_role.id,
                name=new_role.name,
                description=new_role.description,
                is_system=new_role.is_system,
                permissions=[
                    PermissionResponse(
                        id=p.id,
                        name=p.name,
                        description=p.description,
                        category=p.category
                    )
                    for p in new_role.permissions
                ]
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating role: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/api/admin/roles/{role_id}", response_model=RoleResponse)
async def update_role(
    role_id: int,
    role_data: RoleUpdate,
    current_user: User = Depends(requires_permission("admin.manage_roles"))
):
    """
    Update a role's name, description, or permissions.
    System roles cannot be deleted but can be updated.
    Requires: admin.manage_roles permission
    """
    try:
        async with AsyncSessionLocal() as db:
            # Fetch role
            result = await db.execute(
                select(Role)
                .where(Role.id == role_id)
                .options(selectinload(Role.permissions))
            )
            role = result.scalar_one_or_none()

            if not role:
                raise HTTPException(status_code=404, detail="Role not found")

            # Update fields
            if role_data.name:
                # Check for name conflict
                result = await db.execute(
                    select(Role).where(Role.name == role_data.name, Role.id != role_id)
                )
                conflict = result.scalar_one_or_none()
                if conflict:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Role name '{role_data.name}' already exists"
                    )
                role.name = role_data.name

            if role_data.description is not None:
                role.description = role_data.description

            if role_data.permission_ids is not None:
                # Fetch new permissions
                result = await db.execute(
                    select(Permission).where(Permission.id.in_(role_data.permission_ids))
                )
                permissions = result.scalars().all()

                if len(permissions) != len(role_data.permission_ids):
                    raise HTTPException(
                        status_code=400,
                        detail="Some permission IDs are invalid"
                    )

                role.permissions.clear()
                role.permissions.extend(permissions)

            await db.commit()
            await db.refresh(role)

            logger.info(f"Updated role: {role.name} by {current_user.email}")

            return RoleResponse(
                id=role.id,
                name=role.name,
                description=role.description,
                is_system=role.is_system,
                permissions=[
                    PermissionResponse(
                        id=p.id,
                        name=p.name,
                        description=p.description,
                        category=p.category
                    )
                    for p in role.permissions
                ]
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating role: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/api/admin/roles/{role_id}")
async def delete_role(
    role_id: int,
    current_user: User = Depends(requires_permission("admin.manage_roles"))
):
    """
    Delete a custom role.
    System roles cannot be deleted.
    Requires: admin.manage_roles permission
    """
    try:
        async with AsyncSessionLocal() as db:
            # Fetch role
            result = await db.execute(
                select(Role).where(Role.id == role_id)
            )
            role = result.scalar_one_or_none()

            if not role:
                raise HTTPException(status_code=404, detail="Role not found")

            if role.is_system:
                raise HTTPException(
                    status_code=400,
                    detail="Cannot delete system roles"
                )

            await db.delete(role)
            await db.commit()

            logger.info(f"Deleted role: {role.name} by {current_user.email}")

            return {"success": True, "message": f"Role '{role.name}' deleted"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting role: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ========================================
# User Management Endpoints
# ========================================

@router.get("/api/admin/users", response_model=List[UserResponse])
async def list_users(
    current_user: User = Depends(requires_permission("admin.manage_users"))
):
    """
    List all users with their roles.
    Requires: admin.manage_users permission
    """
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(DBUser).options(selectinload(DBUser.roles))
            )
            users = result.scalars().all()

            return [
                UserResponse(
                    id=u.id,
                    email=u.email,
                    name=u.name,
                    is_admin=u.is_admin,
                    roles=[r.name for r in u.roles]
                )
                for u in users
            ]

    except Exception as e:
        logger.error(f"Error fetching users: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/api/admin/users/{user_id}/roles")
async def update_user_roles(
    user_id: int,
    role_update: UserRolesUpdate,
    current_user: User = Depends(requires_permission("admin.manage_users"))
):
    """
    Update a user's assigned roles.
    Requires: admin.manage_users permission

    Security protections:
    - Users cannot modify their own roles (prevents self-privilege escalation)
    - Only Super Admins can assign the Super Admin role to others
    - Cannot remove the last Super Admin (prevents lockout)
    """
    try:
        async with AsyncSessionLocal() as db:
            # SECURITY: Prevent self-modification
            if user_id == current_user.id:
                raise HTTPException(
                    status_code=403,
                    detail="You cannot modify your own roles. Ask another administrator for assistance."
                )

            # Fetch target user
            result = await db.execute(
                select(DBUser)
                .where(DBUser.id == user_id)
                .options(selectinload(DBUser.roles))
            )
            user = result.scalar_one_or_none()

            if not user:
                raise HTTPException(status_code=404, detail="User not found")

            # Fetch requested roles
            result = await db.execute(
                select(Role)
                .where(Role.id.in_(role_update.role_ids))
                .options(selectinload(Role.permissions))
            )
            roles = result.scalars().all()

            if len(roles) != len(role_update.role_ids):
                raise HTTPException(
                    status_code=400,
                    detail="Some role IDs are invalid"
                )

            # SECURITY: Check if trying to assign Super Admin role
            super_admin_role = next((r for r in roles if r.name == "Super Admin"), None)

            if super_admin_role:
                # Only Super Admins can assign Super Admin role
                if "admin.manage_roles" not in current_user.permissions:
                    raise HTTPException(
                        status_code=403,
                        detail="Only Super Admins can assign the Super Admin role"
                    )

            # SECURITY: Prevent removing the last Super Admin
            # Check if this user currently has Super Admin and we're removing it
            user_has_super_admin = any(r.name == "Super Admin" for r in user.roles)
            new_roles_have_super_admin = any(r.name == "Super Admin" for r in roles)

            if user_has_super_admin and not new_roles_have_super_admin:
                # Count total Super Admins
                result = await db.execute(
                    select(DBUser)
                    .join(DBUser.roles)
                    .where(Role.name == "Super Admin")
                )
                super_admins = result.scalars().all()

                if len(super_admins) <= 1:
                    raise HTTPException(
                        status_code=403,
                        detail="Cannot remove the last Super Admin. Assign another Super Admin first."
                    )

            # Update user's roles
            user.roles.clear()
            user.roles.extend(roles)

            await db.commit()
            await db.refresh(user)

            logger.info(
                f"Updated roles for user {user.email} by {current_user.email}. "
                f"New roles: {[r.name for r in user.roles]}"
            )

            return {
                "success": True,
                "user_id": user.id,
                "email": user.email,
                "roles": [r.name for r in user.roles]
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating user roles: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ========================================
# AI Model Management Endpoints
# ========================================

class AIModelResponse(BaseModel):
    """AI Model response model"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    model_id: str
    name: str
    slug: str
    provider: str
    description: Optional[str]
    context_window: int
    max_output: int
    cost_input: Optional[str]
    cost_output: Optional[str]
    supports_thinking: bool
    speed: Optional[str]
    intelligence: Optional[str]
    recommended_for: Optional[List[str]]
    is_enabled: bool
    is_default: bool


class AIModelCreate(BaseModel):
    """AI Model creation request"""
    model_id: str
    name: str
    slug: str
    provider: str
    description: Optional[str] = None
    context_window: int
    max_output: int
    cost_input: Optional[str] = None
    cost_output: Optional[str] = None
    supports_thinking: bool = False
    speed: Optional[str] = None
    intelligence: Optional[str] = None
    recommended_for: Optional[List[str]] = None
    is_enabled: bool = True
    is_default: bool = False


class AIModelUpdate(BaseModel):
    """AI Model update request"""
    name: Optional[str] = None
    slug: Optional[str] = None
    provider: Optional[str] = None
    description: Optional[str] = None
    context_window: Optional[int] = None
    max_output: Optional[int] = None
    cost_input: Optional[str] = None
    cost_output: Optional[str] = None
    supports_thinking: Optional[bool] = None
    speed: Optional[str] = None
    intelligence: Optional[str] = None
    recommended_for: Optional[List[str]] = None
    is_enabled: Optional[bool] = None
    is_default: Optional[bool] = None


@router.get("/api/admin/models", response_model=List[AIModelResponse])
async def get_all_ai_models(
    current_user: User = Depends(requires_permission("admin.manage_users"))
):
    """
    Get all AI models (superadmin only)
    """
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(AIModel).order_by(AIModel.is_default.desc(), AIModel.name)
            )
            models = result.scalars().all()
            return models

    except Exception as e:
        logger.error(f"Error fetching AI models: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/admin/models", response_model=AIModelResponse)
async def create_ai_model(
    model_data: AIModelCreate,
    current_user: User = Depends(requires_permission("admin.manage_users"))
):
    """
    Create a new AI model (superadmin only)
    """
    try:
        async with AsyncSessionLocal() as db:
            # Check if model_id already exists
            result = await db.execute(
                select(AIModel).where(AIModel.model_id == model_data.model_id)
            )
            if result.scalar_one_or_none():
                raise HTTPException(status_code=400, detail="Model ID already exists")

            # If this is set as default, unset other defaults
            if model_data.is_default:
                await db.execute(
                    select(AIModel).where(AIModel.is_default == True)
                )
                existing_defaults = (await db.execute(
                    select(AIModel).where(AIModel.is_default == True)
                )).scalars().all()
                for existing in existing_defaults:
                    existing.is_default = False

            # Create new model
            new_model = AIModel(**model_data.model_dump())
            db.add(new_model)
            await db.commit()
            await db.refresh(new_model)

            logger.info(f"Created AI model {new_model.model_id} by {current_user.email}")
            return new_model

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating AI model: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/api/admin/models/{model_id}", response_model=AIModelResponse)
async def update_ai_model(
    model_id: str,
    model_data: AIModelUpdate,
    current_user: User = Depends(requires_permission("admin.manage_users"))
):
    """
    Update an AI model (superadmin only)
    """
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(AIModel).where(AIModel.model_id == model_id)
            )
            model = result.scalar_one_or_none()

            if not model:
                raise HTTPException(status_code=404, detail="Model not found")

            # If setting as default, unset other defaults
            if model_data.is_default:
                existing_defaults = (await db.execute(
                    select(AIModel).where(AIModel.is_default == True, AIModel.id != model.id)
                )).scalars().all()
                for existing in existing_defaults:
                    existing.is_default = False

            # Update fields
            update_data = model_data.model_dump(exclude_unset=True)
            for key, value in update_data.items():
                setattr(model, key, value)

            await db.commit()
            await db.refresh(model)

            logger.info(f"Updated AI model {model.model_id} by {current_user.email}")
            return model

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating AI model: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/api/admin/models/{model_id}")
async def delete_ai_model(
    model_id: str,
    current_user: User = Depends(requires_permission("admin.manage_users"))
):
    """
    Delete an AI model (superadmin only)
    """
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(AIModel).where(AIModel.model_id == model_id)
            )
            model = result.scalar_one_or_none()

            if not model:
                raise HTTPException(status_code=404, detail="Model not found")

            # Prevent deleting the default model
            if model.is_default:
                raise HTTPException(status_code=400, detail="Cannot delete the default model")

            await db.delete(model)
            await db.commit()

            logger.info(f"Deleted AI model {model_id} by {current_user.email}")
            return {"success": True, "message": f"Model {model_id} deleted"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting AI model: {e}")
        raise HTTPException(status_code=500, detail=str(e))
