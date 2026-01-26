import { useOutletContext } from 'react-router';
import BFCMDashboard from '../components/BFCMDashboard';
import { requirePermission } from '../utils/route-permissions';

interface AuthContext {
  authToken: string;
}

export function clientLoader() {
  requirePermission('dashboard.access');
  return null;
}

export default function BFCMRoute() {
  const { authToken } = useOutletContext<AuthContext>();
  return <BFCMDashboard authToken={authToken} />;
}
