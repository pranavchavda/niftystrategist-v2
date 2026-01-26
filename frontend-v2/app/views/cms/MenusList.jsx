import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Heading, Subheading } from '../../components/catalyst/heading';
import { Text } from '../../components/catalyst/text';
import { Button } from '../../components/catalyst/button';
import { Bars3Icon, PencilIcon } from '@heroicons/react/24/outline';

export default function MenusList({ authToken }) {
  const navigate = useNavigate();
  const [menus, setMenus] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    loadMenus();
  }, []);

  async function loadMenus() {
    try {
      setLoading(true);
      setError(null);

      const response = await fetch('/api/cms/menus', {
        headers: {
          'Authorization': `Bearer ${authToken}`
        }
      });

      if (!response.ok) {
        throw new Error('Failed to load menus');
      }

      const data = await response.json();
      setMenus(data.menus || []);
    } catch (err) {
      console.error('Error loading menus:', err);
      setError(err instanceof Error ? err.message : 'Failed to load menus');
    } finally {
      setLoading(false);
    }
  }

  function handleEditMenu(menu) {
    navigate(`/cms/menus/${menu.handle}/edit`);
  }

  return (
    <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-10">
      {/* Header */}
      <div className="mb-8">
        <Heading>Menus</Heading>
        <Text className="mt-2">Manage navigation menus and menu items</Text>
      </div>

      {/* Loading State */}
      {loading && (
        <div className="flex items-center justify-center py-12">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-zinc-200 border-t-purple-600 dark:border-zinc-700 dark:border-t-purple-400" />
          <Text className="ml-3 text-zinc-600 dark:text-zinc-400">Loading menus...</Text>
        </div>
      )}

      {/* Error State */}
      {error && (
        <div className="rounded-lg bg-red-50 dark:bg-red-900/20 p-4 mb-6">
          <Text className="text-sm text-red-800 dark:text-red-200">{error}</Text>
        </div>
      )}

      {/* Menus Grid */}
      {!loading && !error && (
        <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {menus.map((menu) => (
            <div
              key={menu.id}
              className="group relative rounded-lg border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 p-6 shadow-sm hover:shadow-md transition-all duration-200"
            >
              {/* Icon */}
              <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-lg bg-purple-100 dark:bg-purple-900/30">
                <Bars3Icon className="h-6 w-6 text-purple-600 dark:text-purple-400" />
              </div>

              {/* Menu Info */}
              <div className="mb-4">
                <Subheading className="mb-1">{menu.title}</Subheading>
                <Text className="text-sm text-zinc-500 dark:text-zinc-400">
                  Handle: {menu.handle}
                </Text>
                <Text className="text-sm text-zinc-500 dark:text-zinc-400">
                  {menu.itemCount} {menu.itemCount === 1 ? 'item' : 'items'}
                </Text>
              </div>

              {/* Actions */}
              <div className="flex gap-2">
                <Button
                  onClick={() => handleEditMenu(menu)}
                  className="flex-1"
                  color="purple"
                >
                  <PencilIcon className="h-4 w-4" />
                  <span>Edit</span>
                </Button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Empty State */}
      {!loading && !error && menus.length === 0 && (
        <div className="text-center py-12">
          <Bars3Icon className="mx-auto h-12 w-12 text-zinc-400 dark:text-zinc-600" />
          <Heading className="mt-4 text-lg">No menus found</Heading>
          <Text className="mt-2">No navigation menus are available in your store.</Text>
        </div>
      )}
    </div>
  );
}
