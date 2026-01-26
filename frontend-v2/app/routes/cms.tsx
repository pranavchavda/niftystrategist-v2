import { useOutletContext } from 'react-router';
import CMSLayout from '../views/cms/CMSLayout';
import { requirePermission } from '../utils/route-permissions';

interface AuthContext {
  authToken: string;
}

export function clientLoader() {
  requirePermission('cms.access');
  return null;
}

export default function CMSRoute() {
  const { authToken } = useOutletContext<AuthContext>();
  return <CMSLayout authToken={authToken} />;
}
