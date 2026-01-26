import { type RouteConfig, route, index, layout } from '@react-router/dev/routes';

export default [
  // Index route - landing page with navigation
  index('./routes/_index.tsx'),

  // Login route (no auth required)
  route('login', './routes/login.tsx'),

  // Help page (no auth required)
  route('help', './routes/help.tsx'),

  // Public notes - no auth required
  route('public/notes/:publicId', './routes/public.notes.$publicId.tsx'),

  // All authenticated routes wrapped in layout
  layout('./routes/_auth.tsx', [
    // Chat routes - only with threadId (no /chat without ID)
    route('chat/:threadId', './routes/chat.$threadId.tsx'),

    // Dashboard
    route('dashboard', './routes/dashboard.tsx'),

    // Memory Management
    route('memory', './routes/memory.tsx'),

    // Notes - Second Brain
    route('notes', './routes/notes.tsx'),
    route('notes/:noteId', './routes/notes.$noteId.tsx'),

    // Google Tasks - AI-enhanced task management
    route('tasks', './routes/tasks.tsx'),

    // Settings
    route('settings', './routes/settings.tsx'),
    route('settings/mcp', './routes/settings.mcp.tsx'),

    // Automations (scheduled workflows)
    route('automations', './routes/automations.tsx'),

    // User Profile
    route('user', './routes/user.tsx', [
      route('profile', './routes/user.profile.tsx'),
    ]),

    // Admin Documentation Editor
    route('admin/docs', './routes/admin.docs.tsx'),

    // Admin User & Role Management
    route('admin/users', './routes/admin.users.tsx'),

    // Admin AI Model Management
    route('admin/models', './routes/admin.models.tsx'),
  ]),
] satisfies RouteConfig;
