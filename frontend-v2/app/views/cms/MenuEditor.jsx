import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
} from '@dnd-kit/core';
import {
  SortableContext,
  sortableKeyboardCoordinates,
  verticalListSortingStrategy,
  useSortable,
} from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';

import { Heading } from '../../components/catalyst/heading';
import { Text } from '../../components/catalyst/text';
import { Button } from '../../components/catalyst/button';
import {
  ArrowLeftIcon,
  ChevronRightIcon,
  ChevronDownIcon,
  PencilIcon,
  PlusIcon,
  TrashIcon,
  CursorArrowRaysIcon,
  RectangleStackIcon,
  Bars3Icon,
} from '@heroicons/react/24/outline';
import MenuItemEditor from '../../components/MenuItemEditor';

function SortableMenuItem({ item, path, depth, onEdit, onDelete, onAddChild, expandedItems, onToggleExpand, children }) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: item.id || `${item.title}-${path.join('-')}` });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
  };

  const hasChildren = item.items && item.items.length > 0;
  const isExpanded = item.id ? expandedItems.has(item.id) : false;

  function getPatternIcon(item) {
    if (item.type === 'cta') {
      return <CursorArrowRaysIcon className="h-4 w-4 text-blue-600 dark:text-blue-400" title="CTA" />;
    }
    if (item.type === 'button') {
      return <RectangleStackIcon className="h-4 w-4 text-green-600 dark:text-green-400" title="Button" />;
    }
    if (item.speciallink) {
      return <span className="text-yellow-600 dark:text-yellow-400 text-xs" title="Special Link">⭐</span>;
    }
    return null;
  }

  return (
    <div ref={setNodeRef} style={style} className="border-b border-zinc-200 dark:border-zinc-700">
      {/* Item Row */}
      <div
        className={`flex items-center gap-3 py-3 px-4 hover:bg-zinc-50 dark:hover:bg-zinc-800/50 ${depth > 0 ? 'ml-' + (depth * 6) : ''}`}
      >
        {/* Drag Handle */}
        <button
          {...attributes}
          {...listeners}
          className="flex-shrink-0 cursor-grab active:cursor-grabbing p-1 hover:bg-zinc-200 dark:hover:bg-zinc-700 rounded"
          title="Drag to reorder"
        >
          <Bars3Icon className="h-4 w-4 text-zinc-500" />
        </button>

        {/* Expand/Collapse Button */}
        <button
          onClick={() => item.id && onToggleExpand(item.id)}
          className={`flex-shrink-0 ${hasChildren ? 'visible' : 'invisible'}`}
        >
          {isExpanded ? (
            <ChevronDownIcon className="h-4 w-4 text-zinc-500" />
          ) : (
            <ChevronRightIcon className="h-4 w-4 text-zinc-500" />
          )}
        </button>

        {/* Pattern Icon */}
        <div className="flex-shrink-0 w-5 flex items-center justify-center">
          {getPatternIcon(item)}
        </div>

        {/* Item Info */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <Text className="font-medium truncate">{item.title}</Text>
            {item.hide_us && (
              <span className="inline-flex items-center rounded-full bg-orange-100 dark:bg-orange-900/30 px-2 py-0.5 text-xs font-medium text-orange-800 dark:text-orange-200">
                Hidden US
              </span>
            )}
            {item.hide_ca && (
              <span className="inline-flex items-center rounded-full bg-orange-100 dark:bg-orange-900/30 px-2 py-0.5 text-xs font-medium text-orange-800 dark:text-orange-200">
                Hidden CA
              </span>
            )}
          </div>
          <Text className="text-xs text-zinc-500 dark:text-zinc-400 truncate">{item.url}</Text>
          {item.description && (
            <Text className="text-xs text-zinc-600 dark:text-zinc-300 italic truncate mt-0.5">
              {item.description}
            </Text>
          )}
        </div>

        {/* Actions */}
        <div className="flex-shrink-0 flex gap-2">
          {/* Only show "Add Child" button if depth < 2 (max 3 levels: 0, 1, 2) */}
          {depth < 2 && (
            <button
              onClick={() => onAddChild(path)}
              className="p-1.5 text-zinc-600 hover:text-green-600 dark:text-zinc-400 dark:hover:text-green-400 hover:bg-green-50 dark:hover:bg-green-900/30 rounded transition-colors"
              title="Add child item"
            >
              <PlusIcon className="h-4 w-4" />
            </button>
          )}
          <button
            onClick={() => onEdit(item, path)}
            className="p-1.5 text-zinc-600 hover:text-purple-600 dark:text-zinc-400 dark:hover:text-purple-400 hover:bg-purple-50 dark:hover:bg-purple-900/30 rounded transition-colors"
            title="Edit"
          >
            <PencilIcon className="h-4 w-4" />
          </button>
          <button
            onClick={() => onDelete(path)}
            className="p-1.5 text-zinc-600 hover:text-red-600 dark:text-zinc-400 dark:hover:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/30 rounded transition-colors"
            title="Delete"
          >
            <TrashIcon className="h-4 w-4" />
          </button>
        </div>
      </div>

      {/* Nested Items */}
      {hasChildren && isExpanded && (
        <div className="bg-zinc-50/50 dark:bg-zinc-900/20">
          {children}
        </div>
      )}
    </div>
  );
}

export default function MenuEditor({ authToken }) {
  const { handle } = useParams();
  const navigate = useNavigate();

  const [menu, setMenu] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [expandedItems, setExpandedItems] = useState(new Set());

  // Item editor state
  const [editingItem, setEditingItem] = useState(null);
  const [editingPath, setEditingPath] = useState([]);
  const [showEditor, setShowEditor] = useState(false);
  const [isCreating, setIsCreating] = useState(false);

  // Drag and drop sensors
  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    })
  );

  useEffect(() => {
    if (handle) {
      loadMenu(handle);
    }
  }, [handle]);

  async function loadMenu(menuHandle) {
    try {
      setLoading(true);
      setError(null);

      const token = authToken;
      const response = await fetch(`/api/cms/menus/${menuHandle}`, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });

      if (!response.ok) {
        throw new Error('Failed to load menu');
      }

      const data = await response.json();
      setMenu(data.menu);

      // Expand all top-level items by default
      if (data.menu?.items) {
        const topLevelIds = data.menu.items
          .filter((item) => item.id)
          .map((item) => item.id);
        setExpandedItems(new Set(topLevelIds));
      }
    } catch (err) {
      console.error('Error loading menu:', err);
      setError(err instanceof Error ? err.message : 'Failed to load menu');
    } finally {
      setLoading(false);
    }
  }

  async function handleSave() {
    if (!menu) return;

    try {
      setSaving(true);
      setError(null);

      const token = authToken;
      const response = await fetch(`/api/cms/menus/${encodeURIComponent(menu.id)}`, {
        method: 'PUT',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          title: menu.title,
          items: menu.items
        })
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        const errorDetail = errorData.detail || 'Failed to save menu';

        // Format error message for better readability
        const formattedError = errorDetail
          .replace(/\\n/g, '\n')
          .replace(/Command failed: Error: /g, '');

        throw new Error(formattedError);
      }

      // Show success message
      alert('Menu saved successfully!');

      // Reload menu to get updated data from Shopify
      if (handle) {
        await loadMenu(handle);
      }
    } catch (err) {
      console.error('Error saving menu:', err);
      setError(err instanceof Error ? err.message : 'Failed to save menu');
    } finally {
      setSaving(false);
    }
  }

  function toggleExpanded(itemId) {
    setExpandedItems((prev) => {
      const next = new Set(prev);
      if (next.has(itemId)) {
        next.delete(itemId);
      } else {
        next.add(itemId);
      }
      return next;
    });
  }

  function getItemAtPath(items, path) {
    let current = null;
    let currentItems = items;

    for (const index of path) {
      if (!currentItems || index >= currentItems.length) {
        return null;
      }
      current = currentItems[index];
      currentItems = current.items || [];
    }

    return current;
  }

  function setItemAtPath(items, path, newItem) {
    if (path.length === 0) return items;

    const newItems = [...items];
    let current = newItems;

    for (let i = 0; i < path.length - 1; i++) {
      const index = path[i];
      if (!current[index].items) {
        current[index].items = [];
      }
      current[index] = { ...current[index], items: [...current[index].items] };
      current = current[index].items;
    }

    current[path[path.length - 1]] = newItem;
    return newItems;
  }

  function deleteItemAtPath(items, path) {
    if (path.length === 0) return items;

    const newItems = [...items];

    if (path.length === 1) {
      // Top-level item
      newItems.splice(path[0], 1);
      return newItems;
    }

    // Nested item
    let current = newItems;
    for (let i = 0; i < path.length - 1; i++) {
      const index = path[i];
      current[index] = { ...current[index], items: [...(current[index].items || [])] };
      current = current[index].items;
    }

    current.splice(path[path.length - 1], 1);
    return newItems;
  }

  function handleEditItem(item, path) {
    setEditingItem({ ...item });
    setEditingPath(path);
    setIsCreating(false);
    setShowEditor(true);
  }

  function handleDeleteItem(path) {
    if (!menu) return;

    const item = getItemAtPath(menu.items, path);
    if (!item) return;

    if (confirm(`Are you sure you want to delete "${item.title}"?`)) {
      const newItems = deleteItemAtPath(menu.items, path);
      setMenu({ ...menu, items: newItems });
    }
  }

  function handleAddTopLevelItem() {
    // Create empty item for new top-level item
    const newItem = {
      type: 'standard',
      title: '',
      url: '',
      item_type: 'HTTP',
      speciallink: false,
      hide_us: false,
      hide_ca: false,
      items: []
    };

    setEditingItem(newItem);
    setEditingPath([menu.items.length]); // Path will be at the end of top-level items
    setIsCreating(true);
    setShowEditor(true);
  }

  function handleAddChildItem(parentPath) {
    // Create empty item for new child item
    const newItem = {
      type: 'standard',
      title: '',
      url: '',
      item_type: 'HTTP',
      speciallink: false,
      hide_us: false,
      hide_ca: false,
      items: []
    };

    // Get parent item to check depth
    const parent = getItemAtPath(menu.items, parentPath);
    if (!parent) return;

    // Calculate depth (0-indexed: top=0, first child=1, second child=2)
    const depth = parentPath.length;

    // Enforce 3-level maximum (0, 1, 2)
    if (depth >= 3) {
      alert('Maximum menu depth reached. Cannot add more nested items.');
      return;
    }

    // Path will be at the end of parent's items
    const childItems = parent.items || [];
    const newPath = [...parentPath, childItems.length];

    setEditingItem(newItem);
    setEditingPath(newPath);
    setIsCreating(true);
    setShowEditor(true);
  }

  function handleSaveItem(updatedItem) {
    if (!menu) return;

    if (isCreating) {
      // Add new item
      const pathCopy = [...editingPath];
      const lastIndex = pathCopy.pop();

      if (pathCopy.length === 0) {
        // Adding top-level item
        const newItems = [...menu.items, updatedItem];
        setMenu({ ...menu, items: newItems });
      } else {
        // Adding child item
        const parent = getItemAtPath(menu.items, pathCopy);
        if (parent) {
          const updatedParent = {
            ...parent,
            items: [...(parent.items || []), updatedItem]
          };
          const newItems = setItemAtPath(menu.items, pathCopy, updatedParent);
          setMenu({ ...menu, items: newItems });
        }
      }
    } else {
      // Edit existing item
      const newItems = setItemAtPath(menu.items, editingPath, updatedItem);
      setMenu({ ...menu, items: newItems });
    }

    setShowEditor(false);
    setEditingItem(null);
    setIsCreating(false);
  }

  function handleDragEnd(event, parentPath = []) {
    const { active, over } = event;

    if (!over || active.id === over.id) return;

    setMenu((currentMenu) => {
      if (!currentMenu) return currentMenu;

      // Get the parent items array
      let items;
      if (parentPath.length === 0) {
        items = currentMenu.items;
      } else {
        const parent = getItemAtPath(currentMenu.items, parentPath);
        items = parent?.items || [];
      }

      // Find old and new indices
      const oldIndex = items.findIndex(
        (item) => (item.id || `${item.title}-${parentPath.join('-')}-${items.indexOf(item)}`) === active.id
      );
      const newIndex = items.findIndex(
        (item) => (item.id || `${item.title}-${parentPath.join('-')}-${items.indexOf(item)}`) === over.id
      );

      if (oldIndex === -1 || newIndex === -1) return currentMenu;

      // Reorder items
      const reorderedItems = [...items];
      const [removed] = reorderedItems.splice(oldIndex, 1);
      reorderedItems.splice(newIndex, 0, removed);

      // Update menu
      if (parentPath.length === 0) {
        return { ...currentMenu, items: reorderedItems };
      } else {
        const newItems = setItemAtPath(currentMenu.items, parentPath, {
          ...getItemAtPath(currentMenu.items, parentPath),
          items: reorderedItems,
        });
        return { ...currentMenu, items: newItems };
      }
    });
  }

  function renderMenuItem(item, path, depth = 0) {
    const hasChildren = item.items && item.items.length > 0;
    const isExpanded = item.id ? expandedItems.has(item.id) : false;

    return (
      <SortableMenuItem
        key={item.id || `${item.title}-${path.join('-')}`}
        item={item}
        path={path}
        depth={depth}
        onEdit={handleEditItem}
        onDelete={handleDeleteItem}
        onAddChild={handleAddChildItem}
        expandedItems={expandedItems}
        onToggleExpand={toggleExpanded}
      >
        {hasChildren && isExpanded && (
          <DndContext
            sensors={sensors}
            collisionDetection={closestCenter}
            onDragEnd={(event) => handleDragEnd(event, path)}
          >
            <SortableContext
              items={item.items.map((child, idx) => child.id || `${child.title}-${[...path, idx].join('-')}`)}
              strategy={verticalListSortingStrategy}
            >
              {item.items.map((childItem, index) =>
                renderMenuItem(childItem, [...path, index], depth + 1)
              )}
            </SortableContext>
          </DndContext>
        )}
      </SortableMenuItem>
    );
  }

  if (loading) {
    return (
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-10">
        <div className="flex items-center justify-center py-12">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-zinc-200 border-t-purple-600 dark:border-zinc-700 dark:border-t-purple-400" />
          <Text className="ml-3 text-zinc-600 dark:text-zinc-400">Loading menu...</Text>
        </div>
      </div>
    );
  }

  if (error || !menu) {
    return (
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-10">
        <div className="rounded-lg bg-red-50 dark:bg-red-900/20 p-4 mb-6">
          <Text className="text-sm text-red-800 dark:text-red-200">
            {error || 'Menu not found'}
          </Text>
        </div>
        <Button onClick={() => navigate('/cms/menus')}>
          <ArrowLeftIcon className="h-4 w-4" />
          Back to Menus
        </Button>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-10">
      {/* Header */}
      <div className="mb-6 flex items-center justify-between">
        <div>
          <Button plain onClick={() => navigate('/cms/menus')} className="mb-4">
            <ArrowLeftIcon className="h-4 w-4" />
            Back to Menus
          </Button>
          <Heading>{menu.title}</Heading>
          <Text className="mt-1 text-sm text-zinc-500 dark:text-zinc-400">
            Handle: {menu.handle} · {menu.items.length} top-level items
          </Text>
        </div>
        <Button
          onClick={handleSave}
          disabled={saving}
          color="purple"
        >
          {saving ? 'Saving...' : 'Save Changes'}
        </Button>
      </div>

      {/* Error Message */}
      {error && (
        <div className="rounded-lg bg-red-50 dark:bg-red-900/20 p-4 mb-6 border border-red-200 dark:border-red-800">
          <div className="flex items-start gap-3">
            <div className="flex-shrink-0">
              <svg className="h-5 w-5 text-red-600 dark:text-red-400" viewBox="0 0 20 20" fill="currentColor">
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.28 7.22a.75.75 0 00-1.06 1.06L8.94 10l-1.72 1.72a.75.75 0 101.06 1.06L10 11.06l1.72 1.72a.75.75 0 101.06-1.06L11.06 10l1.72-1.72a.75.75 0 00-1.06-1.06L10 8.94 8.28 7.22z" clipRule="evenodd" />
              </svg>
            </div>
            <div className="flex-1">
              <h3 className="text-sm font-semibold text-red-800 dark:text-red-200 mb-1">Error Saving Menu</h3>
              <pre className="text-xs text-red-700 dark:text-red-300 whitespace-pre-wrap font-mono">{error}</pre>
            </div>
          </div>
        </div>
      )}

      {/* Menu Tree with Drag and Drop */}
      <div className="rounded-lg border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 overflow-hidden">
        <div className="border-b border-zinc-200 dark:border-zinc-700 bg-zinc-50 dark:bg-zinc-900/30 px-4 py-3 flex items-center justify-between">
          <Text className="font-semibold">Menu Items</Text>
          <Button
            onClick={handleAddTopLevelItem}
            color="green"
            className="flex items-center gap-2"
          >
            <PlusIcon className="h-4 w-4" />
            Add Top-Level Item
          </Button>
        </div>
        <div>
          <DndContext
            sensors={sensors}
            collisionDetection={closestCenter}
            onDragEnd={handleDragEnd}
          >
            <SortableContext
              items={menu.items.map((item, idx) => item.id || `${item.title}-${idx}`)}
              strategy={verticalListSortingStrategy}
            >
              {menu.items.map((item, index) => renderMenuItem(item, [index]))}
            </SortableContext>
          </DndContext>
        </div>
      </div>

      {/* Legend */}
      <div className="mt-6 rounded-lg border border-zinc-200 dark:border-zinc-700 bg-zinc-50 dark:bg-zinc-900/30 p-4">
        <Text className="font-semibold mb-2">Pattern Legend:</Text>
        <div className="grid grid-cols-2 gap-2 text-sm">
          <div className="flex items-center gap-2">
            <CursorArrowRaysIcon className="h-4 w-4 text-blue-600 dark:text-blue-400" />
            <Text>CTA (Call to Action)</Text>
          </div>
          <div className="flex items-center gap-2">
            <RectangleStackIcon className="h-4 w-4 text-green-600 dark:text-green-400" />
            <Text>Button</Text>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-yellow-600 dark:text-yellow-400">⭐</span>
            <Text>Special Link</Text>
          </div>
        </div>
      </div>

      {/* Item Editor Modal */}
      {showEditor && editingItem && (
        <MenuItemEditor
          item={editingItem}
          isCreating={isCreating}
          onSave={handleSaveItem}
          onClose={() => {
            setShowEditor(false);
            setEditingItem(null);
            setIsCreating(false);
          }}
        />
      )}
    </div>
  );
}
