import { useOutletContext } from 'react-router';
import PriceMonitorLayout from '../views/price-monitor/PriceMonitorLayout';
import { requirePermission } from '../utils/route-permissions';

interface AuthContext {
  authToken: string;
}

export function clientLoader() {
  requirePermission('price_monitor.access');
  return null;
}

// PriceMonitorLayout handles its own internal routing with <Routes>
// This is a legacy pattern that works fine - the layout acts as a mini-SPA
export default function PriceMonitorRoute() {
  const { authToken } = useOutletContext<AuthContext>();
  return <PriceMonitorLayout authToken={authToken} />;
}
