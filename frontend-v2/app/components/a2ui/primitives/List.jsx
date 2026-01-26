/**
 * List - Dynamic list display
 *
 * Props:
 * - items: array of items to display
 * - renderItem: optional template for rendering (not used in basic mode)
 * - onInteraction: callback for item interactions
 */

export function List({ items = [], onInteraction, id }) {
  const handleItemClick = (item, index) => {
    if (onInteraction) {
      onInteraction('item_click', { item, index });
    }
  };

  if (!items.length) {
    return (
      <div id={id} className="text-zinc-500 dark:text-zinc-400 text-sm">
        No items
      </div>
    );
  }

  return (
    <ul
      id={id}
      className="divide-y divide-zinc-200 dark:divide-zinc-700 rounded-lg border border-zinc-200 dark:border-zinc-700 overflow-hidden"
    >
      {items.map((item, index) => (
        <li
          key={index}
          onClick={() => handleItemClick(item, index)}
          className="px-4 py-3 bg-white dark:bg-zinc-800 hover:bg-zinc-50 dark:hover:bg-zinc-700/50 cursor-pointer transition-colors text-sm text-zinc-900 dark:text-zinc-100"
        >
          {typeof item === 'object' ? JSON.stringify(item) : String(item)}
        </li>
      ))}
    </ul>
  );
}
