/**
 * Permission utility functions for RBAC
 */

/**
 * Check if user has a specific permission
 * @param {Object} user - User object with permissions array
 * @param {string} permission - Permission name (e.g., "chat.access")
 * @returns {boolean}
 */
export function hasPermission(user, permission) {
  if (!user || !user.permissions) return false;
  return user.permissions.includes(permission);
}

/**
 * Check if user has any of the specified permissions
 * @param {Object} user - User object with permissions array
 * @param {string[]} permissions - Array of permission names
 * @returns {boolean}
 */
export function hasAnyPermission(user, permissions) {
  if (!user || !user.permissions) return false;
  return permissions.some(perm => user.permissions.includes(perm));
}

/**
 * Check if user has all of the specified permissions
 * @param {Object} user - User object with permissions array
 * @param {string[]} permissions - Array of permission names
 * @returns {boolean}
 */
export function hasAllPermissions(user, permissions) {
  if (!user || !user.permissions) return false;
  return permissions.every(perm => user.permissions.includes(perm));
}

/**
 * Permission constants
 */
export const PERMISSIONS = {
  CHAT_ACCESS: 'chat.access',
  CMS_ACCESS: 'cms.access',
  DASHBOARD_ACCESS: 'dashboard.access',
  PRICE_MONITOR_ACCESS: 'price_monitor.access',
  INVENTORY_ACCESS: 'inventory.access',
  MEMORY_ACCESS: 'memory.access',
  SETTINGS_ACCESS: 'settings.access',
  GOOGLE_WORKSPACE_ACCESS: 'google_workspace.access',
  ADMIN_MANAGE_USERS: 'admin.manage_users',
  ADMIN_MANAGE_ROLES: 'admin.manage_roles',
};
