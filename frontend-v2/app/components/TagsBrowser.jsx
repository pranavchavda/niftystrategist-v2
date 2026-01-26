import React, { useMemo, useState } from 'react';
import { Hash, ChevronRight, ChevronDown, Folder, Tag as TagIcon } from 'lucide-react';

/**
 * Build hierarchical tag tree from flat tag list
 * Example: ['projects/espressobot', 'work', 'projects/cms']
 * becomes:
 * - projects (2)
 *   - espressobot
 *   - cms
 * - work
 */
function buildTagHierarchy(tags) {
  const root = {};

  tags.forEach(tag => {
    const parts = tag.split('/');
    let current = root;
    let path = '';

    parts.forEach((part, idx) => {
      path = path ? `${path}/${part}` : part;

      if (!current[part]) {
        current[part] = {
          name: part,
          fullPath: path,
          count: 0,
          children: {},
          isLeaf: idx === parts.length - 1
        };
      }

      current[part].count++;

      if (idx < parts.length - 1) {
        // Navigate deeper
        current = current[part].children;
      }
    });
  });

  // Convert object tree to array tree
  const convertToArray = (node) => {
    return Object.values(node).map(item => ({
      ...item,
      children: Object.keys(item.children).length > 0
        ? convertToArray(item.children)
        : []
    }));
  };

  return convertToArray(root);
}

/**
 * Recursive tag node renderer with expand/collapse
 */
function TagNode({ node, depth, selectedTag, onSelectTag, expandedTags, toggleExpanded }) {
  const hasChildren = node.children && node.children.length > 0;
  const isExpanded = expandedTags.has(node.fullPath);
  const isSelected = selectedTag === node.fullPath;

  return (
    <div>
      <button
        onClick={() => {
          if (hasChildren) {
            toggleExpanded(node.fullPath);
          }
          onSelectTag(isSelected ? null : node.fullPath);
        }}
        className={`w-full flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm transition-colors ${
          isSelected
            ? 'bg-blue-500 text-white'
            : 'text-zinc-700 dark:text-zinc-300 hover:bg-zinc-100 dark:hover:bg-zinc-800'
        }`}
        style={{ paddingLeft: `${depth * 12 + 12}px` }}
      >
        {hasChildren ? (
          <button
            onClick={(e) => {
              e.stopPropagation();
              toggleExpanded(node.fullPath);
            }}
            className="p-0.5 hover:bg-zinc-200 dark:hover:bg-zinc-700 rounded"
          >
            {isExpanded ? (
              <ChevronDown className="w-3 h-3" />
            ) : (
              <ChevronRight className="w-3 h-3" />
            )}
          </button>
        ) : (
          <span className="w-4" />
        )}

        {hasChildren ? (
          <Folder className="w-3 h-3 flex-shrink-0" />
        ) : (
          <TagIcon className="w-3 h-3 flex-shrink-0" />
        )}

        <span className="truncate flex-1 text-left">{node.name}</span>

        <span className={`text-xs flex-shrink-0 ${
          isSelected ? 'text-white' : 'text-zinc-500 dark:text-zinc-400'
        }`}>
          {node.count}
        </span>
      </button>

      {/* Render children if expanded */}
      {hasChildren && isExpanded && (
        <div>
          {node.children.map(child => (
            <TagNode
              key={child.fullPath}
              node={child}
              depth={depth + 1}
              selectedTag={selectedTag}
              onSelectTag={onSelectTag}
              expandedTags={expandedTags}
              toggleExpanded={toggleExpanded}
            />
          ))}
        </div>
      )}
    </div>
  );
}

/**
 * Hierarchical tags browser with nested tag support
 *
 * Features:
 * - Nested tags like #projects/espressobot/backend
 * - Expand/collapse folders
 * - Tag counts at each level
 * - Visual distinction between folders and leaf tags
 */
export default function TagsBrowser({ allTags, selectedTag, onSelectTag }) {
  const [expandedTags, setExpandedTags] = useState(new Set());

  // Build hierarchical tree
  const tagTree = useMemo(() => {
    return buildTagHierarchy(allTags);
  }, [allTags]);

  const toggleExpanded = (tagPath) => {
    setExpandedTags(prev => {
      const next = new Set(prev);
      if (next.has(tagPath)) {
        next.delete(tagPath);
      } else {
        next.add(tagPath);
      }
      return next;
    });
  };

  // Expand all/collapse all
  const expandAll = () => {
    const allPaths = new Set();
    const collectPaths = (nodes) => {
      nodes.forEach(node => {
        if (node.children && node.children.length > 0) {
          allPaths.add(node.fullPath);
          collectPaths(node.children);
        }
      });
    };
    collectPaths(tagTree);
    setExpandedTags(allPaths);
  };

  const collapseAll = () => {
    setExpandedTags(new Set());
  };

  if (allTags.length === 0) {
    return null;
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-xs font-semibold text-zinc-500 dark:text-zinc-400 uppercase tracking-wide">
          Tags
        </h3>
        <div className="flex gap-1">
          <button
            onClick={expandAll}
            className="text-xs text-zinc-500 dark:text-zinc-400 hover:text-zinc-700 dark:hover:text-zinc-200 px-2 py-0.5 rounded"
            title="Expand all"
          >
            ▼
          </button>
          <button
            onClick={collapseAll}
            className="text-xs text-zinc-500 dark:text-zinc-400 hover:text-zinc-700 dark:hover:text-zinc-200 px-2 py-0.5 rounded"
            title="Collapse all"
          >
            ▶
          </button>
        </div>
      </div>

      <div className="space-y-0.5">
        {tagTree.map(node => (
          <TagNode
            key={node.fullPath}
            node={node}
            depth={0}
            selectedTag={selectedTag}
            onSelectTag={onSelectTag}
            expandedTags={expandedTags}
            toggleExpanded={toggleExpanded}
          />
        ))}
      </div>
    </div>
  );
}
