import { useOutletContext } from 'react-router';
import MemoryManagement from '../components/MemoryManagement';
import { requirePermission } from '../utils/route-permissions';

interface AuthContext {
  authToken: string;
}

export function clientLoader() {
  requirePermission('memory.access');
  return null;
}

export default function MemoryRoute() {
  const { authToken } = useOutletContext<AuthContext>();
  return <MemoryManagement authToken={authToken} />;
}
