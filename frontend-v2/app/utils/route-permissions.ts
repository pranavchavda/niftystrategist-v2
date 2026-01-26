/**
 * Route-level permission checking utilities
 */

// Decode JWT to extract permissions
export function decodeJWT(token: string) {
  // Handle dev tokens - grant all permissions
  if (token.startsWith('dev-token-')) {
    return {
      permissions: [
        'chat.access',
        'cms.access',
        'dashboard.access',
        'price_monitor.access',
        'memory.access',
        'notes.access',
        'settings.access',
        'google_workspace.access',
        'admin.manage_users',
        'admin.manage_roles',
      ],
    };
  }

  try {
    const base64Url = token.split('.')[1];
    const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
    const jsonPayload = decodeURIComponent(
      atob(base64)
        .split('')
        .map((c) => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
        .join('')
    );
    return JSON.parse(jsonPayload);
  } catch (e) {
    return null;
  }
}

/**
 * Check if user has required permission and redirect if not
 * Call this from clientLoader functions
 */
export function requirePermission(permission: string) {
  const token = localStorage.getItem('auth_token');

  if (!token) {
    throw new Response(null, {
      status: 302,
      headers: { Location: '/login' },
    });
  }

  const payload = decodeJWT(token);
  if (!payload || !payload.permissions || !payload.permissions.includes(permission)) {
    // Redirect to home page if permission denied
    throw new Response(null, {
      status: 302,
      headers: { Location: '/' },
    });
  }
}

/**
 * Check if user has ANY of the required permissions
 */
export function requireAnyPermission(permissions: string[]) {
  const token = localStorage.getItem('auth_token');

  if (!token) {
    throw new Response(null, {
      status: 302,
      headers: { Location: '/login' },
    });
  }

  const payload = decodeJWT(token);
  if (!payload || !payload.permissions) {
    throw new Response(null, {
      status: 302,
      headers: { Location: '/' },
    });
  }

  const hasPermission = permissions.some(perm => payload.permissions.includes(perm));
  if (!hasPermission) {
    throw new Response(null, {
      status: 302,
      headers: { Location: '/' },
    });
  }
}

/**
 * Check authentication only (no permission check)
 */
export function requireAuth() {
  const token = localStorage.getItem('auth_token');
  if (!token) {
    throw new Response(null, {
      status: 302,
      headers: { Location: '/login' },
    });
  }
}
