import { Routes, Route } from 'react-router-dom';
import MenusList from './MenusList';
import MenuEditor from './MenuEditor';

export default function MenusPage({ authToken }) {
  return (
    <Routes>
      <Route path="/" element={<MenusList authToken={authToken} />} />
      <Route path="/:handle/edit" element={<MenuEditor authToken={authToken} />} />
    </Routes>
  );
}
