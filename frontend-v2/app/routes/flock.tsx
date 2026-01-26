import { useOutletContext } from 'react-router';
import FlockLayout from '../views/flock/FlockLayout';
import { requirePermission } from '../utils/route-permissions';

interface AuthContext {
  authToken: string;
}

export function clientLoader() {
  requirePermission('chat.access');
  return null;
}

export default function FlockRoute() {
  const { authToken } = useOutletContext<AuthContext>();
  return <FlockLayout authToken={authToken} />;
}
