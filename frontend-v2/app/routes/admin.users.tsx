import { useState, useEffect } from 'react';
import { useOutletContext } from 'react-router';
import { Shield, Users, Plus, Edit, Trash2, Loader2, AlertCircle, CheckCircle } from 'lucide-react';
import { requirePermission } from '../utils/route-permissions';

export function clientLoader() {
  requirePermission('admin.manage_users');
  return null;
}

export default function AdminUsersPage() {
  const { authToken }: any = useOutletContext();

  const [users, setUsers] = useState([]);
  const [roles, setRoles] = useState([]);
  const [permissions, setPermissions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);

  const [selectedUser, setSelectedUser] = useState(null);
  const [selectedUserRoles, setSelectedUserRoles] = useState([]);
  const [showUserRoleModal, setShowUserRoleModal] = useState(false);

  const [showRoleModal, setShowRoleModal] = useState(false);
  const [editingRole, setEditingRole] = useState(null);
  const [roleFormData, setRoleFormData] = useState({
    name: '',
    description: '',
    permission_ids: []
  });

  // Load initial data
  useEffect(() => {
    loadData();
  }, [authToken]);

  const loadData = async () => {
    try {
      setLoading(true);
      setError(null);

      const [usersRes, rolesRes, permsRes] = await Promise.all([
        fetch('/api/admin/users', {
          headers: { 'Authorization': `Bearer ${authToken}` }
        }),
        fetch('/api/admin/roles', {
          headers: { 'Authorization': `Bearer ${authToken}` }
        }),
        fetch('/api/admin/permissions', {
          headers: { 'Authorization': `Bearer ${authToken}` }
        })
      ]);

      if (!usersRes.ok || !rolesRes.ok || !permsRes.ok) {
        throw new Error('Failed to load admin data');
      }

      const [usersData, rolesData, permsData] = await Promise.all([
        usersRes.json(),
        rolesRes.json(),
        permsRes.json()
      ]);

      setUsers(usersData);
      setRoles(rolesData);
      setPermissions(permsData);
    } catch (err) {
      setError(err.message || 'Failed to load data');
    } finally {
      setLoading(false);
    }
  };

  const handleAssignRoles = (user) => {
    setSelectedUser(user);
    // Get role IDs for this user
    const userRoleNames = user.roles || [];
    const userRoleIds = roles
      .filter(r => userRoleNames.includes(r.name))
      .map(r => r.id);
    setSelectedUserRoles(userRoleIds);
    setShowUserRoleModal(true);
  };

  const handleSaveUserRoles = async () => {
    try {
      setError(null);
      const response = await fetch(`/api/admin/users/${selectedUser.id}/roles`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${authToken}`
        },
        body: JSON.stringify({
          role_ids: selectedUserRoles
        })
      });

      if (!response.ok) {
        throw new Error('Failed to update user roles');
      }

      setSuccess(`Successfully updated roles for ${selectedUser.email}`);
      setShowUserRoleModal(false);
      await loadData();
    } catch (err) {
      setError(err.message);
    }
  };

  const handleCreateRole = () => {
    setEditingRole(null);
    setRoleFormData({
      name: '',
      description: '',
      permission_ids: []
    });
    setShowRoleModal(true);
  };

  const handleEditRole = (role) => {
    setEditingRole(role);
    setRoleFormData({
      name: role.name,
      description: role.description || '',
      permission_ids: role.permissions.map(p => p.id)
    });
    setShowRoleModal(true);
  };

  const handleSaveRole = async () => {
    try {
      setError(null);

      if (editingRole) {
        // Update existing role
        const response = await fetch(`/api/admin/roles/${editingRole.id}`, {
          method: 'PUT',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${authToken}`
          },
          body: JSON.stringify(roleFormData)
        });

        if (!response.ok) {
          const errorData = await response.json();
          throw new Error(errorData.detail || 'Failed to update role');
        }

        setSuccess(`Successfully updated role: ${roleFormData.name}`);
      } else {
        // Create new role
        const response = await fetch('/api/admin/roles', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${authToken}`
          },
          body: JSON.stringify(roleFormData)
        });

        if (!response.ok) {
          const errorData = await response.json();
          throw new Error(errorData.detail || 'Failed to create role');
        }

        setSuccess(`Successfully created role: ${roleFormData.name}`);
      }

      setShowRoleModal(false);
      await loadData();
    } catch (err) {
      setError(err.message);
    }
  };

  const handleDeleteRole = async (role) => {
    if (!confirm(`Are you sure you want to delete the role "${role.name}"?`)) {
      return;
    }

    try {
      setError(null);
      const response = await fetch(`/api/admin/roles/${role.id}`, {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${authToken}` }
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to delete role');
      }

      setSuccess(`Successfully deleted role: ${role.name}`);
      await loadData();
    } catch (err) {
      setError(err.message);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <Loader2 className="h-8 w-8 animate-spin text-blue-600" />
      </div>
    );
  }

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="mb-8">
        <div className="flex items-center gap-3 mb-2">
          <Shield className="h-8 w-8 text-blue-600" />
          <h1 className="text-3xl font-bold text-zinc-900 dark:text-zinc-100">
            User & Role Management
          </h1>
        </div>
        <p className="text-zinc-600 dark:text-zinc-400">
          Manage user permissions and role assignments
        </p>
      </div>

      {/* Success/Error Messages */}
      {error && (
        <div className="mb-6 p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg flex gap-3">
          <AlertCircle className="h-5 w-5 text-red-600 dark:text-red-400 flex-shrink-0 mt-0.5" />
          <div>
            <p className="text-sm font-medium text-red-600 dark:text-red-400">Error</p>
            <p className="text-sm text-red-600 dark:text-red-400 mt-1">{error}</p>
            <button
              onClick={() => setError(null)}
              className="mt-2 text-sm font-medium text-red-600 dark:text-red-400 hover:underline"
            >
              Dismiss
            </button>
          </div>
        </div>
      )}

      {success && (
        <div className="mb-6 p-4 bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg flex gap-3">
          <CheckCircle className="h-5 w-5 text-green-600 dark:text-green-400 flex-shrink-0 mt-0.5" />
          <div className="flex-1">
            <p className="text-sm font-medium text-green-600 dark:text-green-400">{success}</p>
          </div>
          <button
            onClick={() => setSuccess(null)}
            className="text-sm font-medium text-green-600 dark:text-green-400 hover:underline"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Users Section */}
      <div className="mb-8">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-semibold text-zinc-900 dark:text-zinc-100 flex items-center gap-2">
            <Users className="h-5 w-5" />
            Users ({users.length})
          </h2>
        </div>

        <div className="bg-white dark:bg-zinc-800 rounded-lg border border-zinc-200 dark:border-zinc-700 overflow-hidden">
          <table className="w-full">
            <thead className="bg-zinc-50 dark:bg-zinc-900 border-b border-zinc-200 dark:border-zinc-700">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium text-zinc-500 dark:text-zinc-400 uppercase tracking-wider">
                  User
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-zinc-500 dark:text-zinc-400 uppercase tracking-wider">
                  Roles
                </th>
                <th className="px-4 py-3 text-right text-xs font-medium text-zinc-500 dark:text-zinc-400 uppercase tracking-wider">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-200 dark:divide-zinc-700">
              {users.map((user) => (
                <tr key={user.id} className="hover:bg-zinc-50 dark:hover:bg-zinc-900/50">
                  <td className="px-4 py-3">
                    <div>
                      <div className="text-sm font-medium text-zinc-900 dark:text-zinc-100">
                        {user.name}
                      </div>
                      <div className="text-sm text-zinc-500 dark:text-zinc-400">
                        {user.email}
                      </div>
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex flex-wrap gap-1">
                      {user.roles.length > 0 ? (
                        user.roles.map((roleName, idx) => (
                          <span
                            key={idx}
                            className="inline-block px-2 py-1 text-xs font-medium rounded bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400"
                          >
                            {roleName}
                          </span>
                        ))
                      ) : (
                        <span className="text-sm text-zinc-500 dark:text-zinc-400">No roles</span>
                      )}
                    </div>
                  </td>
                  <td className="px-4 py-3 text-right">
                    <button
                      onClick={() => handleAssignRoles(user)}
                      className="text-sm text-blue-600 dark:text-blue-400 hover:underline"
                    >
                      Manage Roles
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Roles Section */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-semibold text-zinc-900 dark:text-zinc-100">
            Roles ({roles.length})
          </h2>
          <button
            onClick={handleCreateRole}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
          >
            <Plus className="h-4 w-4" />
            Create Role
          </button>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {roles.map((role) => (
            <div
              key={role.id}
              className="bg-white dark:bg-zinc-800 border border-zinc-200 dark:border-zinc-700 rounded-lg p-4"
            >
              <div className="flex items-start justify-between mb-2">
                <div className="flex-1">
                  <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100 flex items-center gap-2">
                    {role.name}
                    {role.is_system && (
                      <span className="px-2 py-0.5 text-xs bg-zinc-100 dark:bg-zinc-700 text-zinc-600 dark:text-zinc-400 rounded">
                        System
                      </span>
                    )}
                  </h3>
                  {role.description && (
                    <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-1">
                      {role.description}
                    </p>
                  )}
                </div>
                <div className="flex gap-1">
                  <button
                    onClick={() => handleEditRole(role)}
                    className="p-1 text-zinc-600 dark:text-zinc-400 hover:text-blue-600 dark:hover:text-blue-400"
                    title="Edit role"
                  >
                    <Edit className="h-4 w-4" />
                  </button>
                  {!role.is_system && (
                    <button
                      onClick={() => handleDeleteRole(role)}
                      className="p-1 text-zinc-600 dark:text-zinc-400 hover:text-red-600 dark:hover:text-red-400"
                      title="Delete role"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  )}
                </div>
              </div>

              <div className="mt-3">
                <p className="text-xs font-medium text-zinc-600 dark:text-zinc-400 mb-2">
                  Permissions ({role.permissions.length}):
                </p>
                <div className="flex flex-wrap gap-1">
                  {role.permissions.map((perm) => (
                    <span
                      key={perm.id}
                      className="inline-block px-2 py-0.5 text-xs rounded bg-zinc-100 dark:bg-zinc-700 text-zinc-700 dark:text-zinc-300"
                    >
                      {perm.name}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* User Role Assignment Modal */}
      {showUserRoleModal && selectedUser && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white dark:bg-zinc-800 rounded-lg max-w-md w-full p-6">
            <h3 className="text-lg font-semibold text-zinc-900 dark:text-zinc-100 mb-4">
              Assign Roles to {selectedUser.name}
            </h3>

            <div className="space-y-2 mb-6">
              {roles.map((role) => (
                <label
                  key={role.id}
                  className="flex items-center gap-3 p-3 rounded-lg hover:bg-zinc-50 dark:hover:bg-zinc-700 cursor-pointer"
                >
                  <input
                    type="checkbox"
                    checked={selectedUserRoles.includes(role.id)}
                    onChange={(e) => {
                      if (e.target.checked) {
                        setSelectedUserRoles([...selectedUserRoles, role.id]);
                      } else {
                        setSelectedUserRoles(selectedUserRoles.filter(id => id !== role.id));
                      }
                    }}
                    className="rounded border-zinc-300 dark:border-zinc-600"
                  />
                  <div className="flex-1">
                    <div className="text-sm font-medium text-zinc-900 dark:text-zinc-100">
                      {role.name}
                    </div>
                    {role.description && (
                      <div className="text-xs text-zinc-500 dark:text-zinc-400">
                        {role.description}
                      </div>
                    )}
                  </div>
                </label>
              ))}
            </div>

            <div className="flex gap-3">
              <button
                onClick={() => setShowUserRoleModal(false)}
                className="flex-1 px-4 py-2 border border-zinc-300 dark:border-zinc-600 text-zinc-700 dark:text-zinc-300 rounded-lg hover:bg-zinc-50 dark:hover:bg-zinc-700"
              >
                Cancel
              </button>
              <button
                onClick={handleSaveUserRoles}
                className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
              >
                Save
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Role Create/Edit Modal */}
      {showRoleModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4 overflow-y-auto">
          <div className="bg-white dark:bg-zinc-800 rounded-lg max-w-2xl w-full p-6 my-8">
            <h3 className="text-lg font-semibold text-zinc-900 dark:text-zinc-100 mb-4">
              {editingRole ? `Edit Role: ${editingRole.name}` : 'Create New Role'}
            </h3>

            <div className="space-y-4 mb-6">
              <div>
                <label className="block text-sm font-medium text-zinc-900 dark:text-zinc-100 mb-2">
                  Role Name
                </label>
                <input
                  type="text"
                  value={roleFormData.name}
                  onChange={(e) => setRoleFormData({ ...roleFormData, name: e.target.value })}
                  className="w-full px-3 py-2 border border-zinc-300 dark:border-zinc-600 rounded-lg bg-white dark:bg-zinc-900 text-zinc-900 dark:text-zinc-100"
                  placeholder="e.g., Custom Editor"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-zinc-900 dark:text-zinc-100 mb-2">
                  Description
                </label>
                <textarea
                  value={roleFormData.description}
                  onChange={(e) => setRoleFormData({ ...roleFormData, description: e.target.value })}
                  className="w-full px-3 py-2 border border-zinc-300 dark:border-zinc-600 rounded-lg bg-white dark:bg-zinc-900 text-zinc-900 dark:text-zinc-100"
                  rows={2}
                  placeholder="Optional description"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-zinc-900 dark:text-zinc-100 mb-2">
                  Permissions
                </label>
                <div className="border border-zinc-300 dark:border-zinc-600 rounded-lg p-3 max-h-60 overflow-y-auto">
                  {permissions.map((perm) => (
                    <label
                      key={perm.id}
                      className="flex items-start gap-3 p-2 rounded hover:bg-zinc-50 dark:hover:bg-zinc-700 cursor-pointer"
                    >
                      <input
                        type="checkbox"
                        checked={roleFormData.permission_ids.includes(perm.id)}
                        onChange={(e) => {
                          if (e.target.checked) {
                            setRoleFormData({
                              ...roleFormData,
                              permission_ids: [...roleFormData.permission_ids, perm.id]
                            });
                          } else {
                            setRoleFormData({
                              ...roleFormData,
                              permission_ids: roleFormData.permission_ids.filter(id => id !== perm.id)
                            });
                          }
                        }}
                        className="mt-0.5 rounded border-zinc-300 dark:border-zinc-600"
                      />
                      <div className="flex-1">
                        <div className="text-sm font-medium text-zinc-900 dark:text-zinc-100">
                          {perm.name}
                        </div>
                        {perm.description && (
                          <div className="text-xs text-zinc-500 dark:text-zinc-400">
                            {perm.description}
                          </div>
                        )}
                      </div>
                    </label>
                  ))}
                </div>
              </div>
            </div>

            <div className="flex gap-3">
              <button
                onClick={() => setShowRoleModal(false)}
                className="flex-1 px-4 py-2 border border-zinc-300 dark:border-zinc-600 text-zinc-700 dark:text-zinc-300 rounded-lg hover:bg-zinc-50 dark:hover:bg-zinc-700"
              >
                Cancel
              </button>
              <button
                onClick={handleSaveRole}
                disabled={!roleFormData.name || roleFormData.permission_ids.length === 0}
                className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {editingRole ? 'Update Role' : 'Create Role'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
