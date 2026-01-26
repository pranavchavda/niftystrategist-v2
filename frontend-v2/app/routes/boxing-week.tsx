import { useOutletContext } from 'react-router';
import BoxingWeekDashboard from '../components/BoxingWeekDashboard';
import { requirePermission } from '../utils/route-permissions';

interface AuthContext {
    authToken: string;
}

export function clientLoader() {
    requirePermission('dashboard.access');
    return null;
}

export default function BoxingWeekRoute() {
    const { authToken } = useOutletContext<AuthContext>();
    return <BoxingWeekDashboard authToken={authToken} />;
}
