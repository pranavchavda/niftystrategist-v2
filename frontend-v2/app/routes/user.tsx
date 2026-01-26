import { Outlet, useOutletContext } from 'react-router';

export default function UserLayout() {
  const context = useOutletContext();
  return <Outlet context={context} />;
}
