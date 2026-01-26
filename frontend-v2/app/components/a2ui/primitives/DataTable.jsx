/**
 * DataTable - Tabular data display
 *
 * Props:
 * - columns: array of { key, label }
 * - rows: array of row objects
 * - onInteraction: callback for row interactions
 */

export function DataTable({ columns = [], rows = [], onInteraction, id }) {
  const handleRowClick = (row, index) => {
    if (onInteraction) {
      onInteraction('row_click', { row, index });
    }
  };

  if (!columns.length) {
    return (
      <div id={id} className="text-zinc-500 dark:text-zinc-400 text-sm">
        No columns defined
      </div>
    );
  }

  return (
    <div id={id} className="overflow-x-auto rounded-lg border border-zinc-200 dark:border-zinc-700">
      <table className="min-w-full divide-y divide-zinc-200 dark:divide-zinc-700">
        <thead className="bg-zinc-50 dark:bg-zinc-800/50">
          <tr>
            {columns.map((col) => (
              <th
                key={col.key}
                scope="col"
                className="px-4 py-3 text-left text-xs font-medium text-zinc-500 dark:text-zinc-400 uppercase tracking-wider"
              >
                {col.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="bg-white dark:bg-zinc-800 divide-y divide-zinc-200 dark:divide-zinc-700">
          {rows.length === 0 ? (
            <tr>
              <td
                colSpan={columns.length}
                className="px-4 py-4 text-center text-sm text-zinc-500 dark:text-zinc-400"
              >
                No data
              </td>
            </tr>
          ) : (
            rows.map((row, index) => (
              <tr
                key={index}
                onClick={() => handleRowClick(row, index)}
                className="hover:bg-zinc-50 dark:hover:bg-zinc-700/50 cursor-pointer transition-colors"
              >
                {columns.map((col) => (
                  <td
                    key={col.key}
                    className="px-4 py-3 text-sm text-zinc-900 dark:text-zinc-100"
                  >
                    {row[col.key] ?? '-'}
                  </td>
                ))}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
