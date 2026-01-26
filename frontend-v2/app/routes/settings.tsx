import React from 'react';
import { useOutletContext } from 'react-router';
import Settings from '../components/Settings';
import { requirePermission } from '../utils/route-permissions';

interface AuthContext {
  authToken: string;
  user?: any;
  setUser?: (user: any) => void;
}

export function clientLoader() {
  requirePermission('settings.access');
  return null;
}

export default function SettingsRoute() {
  const { authToken, user, setUser } = useOutletContext<AuthContext>();
  return <Settings authToken={authToken} user={user} setUser={setUser} />;
}
