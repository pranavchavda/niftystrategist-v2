import { useOutletContext } from 'react-router';
import Dashboard from '../components/Dashboard';
import { requirePermission } from '../utils/route-permissions';

interface AuthContext {
  authToken: string;
}

export function clientLoader() {
  requirePermission('dashboard.access');
  return null;
}

export default function DashboardRoute() {
  const { authToken } = useOutletContext<AuthContext>();
  return <Dashboard authToken={authToken} />;
}
