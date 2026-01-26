import { useOutletContext } from 'react-router';
import InventoryPredictionLayout from '../views/inventory/InventoryPredictionLayout';
import { requirePermission } from '../utils/route-permissions';

interface AuthContext {
  authToken: string;
}

export function clientLoader() {
  requirePermission('inventory.access');
  return null;
}

// InventoryPredictionLayout handles its own internal routing
export default function InventoryRoute() {
  const { authToken } = useOutletContext<AuthContext>();
  return <InventoryPredictionLayout authToken={authToken} />;
}
