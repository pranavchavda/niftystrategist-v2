import { useOutletContext } from 'react-router';
import NotesApp from '../components/NotesApp';
import { requirePermission } from '../utils/route-permissions';

interface AuthContext {
  authToken: string;
}

export function clientLoader() {
  requirePermission('notes.access');
  return null;
}

export default function NotesRoute() {
  const { authToken } = useOutletContext<AuthContext>();
  return <NotesApp authToken={authToken} />;
}
