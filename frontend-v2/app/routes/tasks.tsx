import { useOutletContext } from 'react-router';
import TasksApp from '../components/TasksApp';
import { requirePermission } from '../utils/route-permissions';

interface AuthContext {
  authToken: string;
}

export function clientLoader() {
  requirePermission('google_workspace.access');
  return null;
}

export default function TasksRoute() {
  const { authToken } = useOutletContext<AuthContext>();
  return <TasksApp authToken={authToken} />;
}
