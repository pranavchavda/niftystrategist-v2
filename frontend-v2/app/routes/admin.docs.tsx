import { useState, useEffect, useCallback } from 'react';
import { useOutletContext } from 'react-router';
import type { Route } from './+types/admin.docs';
import TextareaWithAutocomplete from '../components/TextareaWithAutocomplete';
import { requireAnyPermission } from '../utils/route-permissions';

export function clientLoader({ request }: Route.ClientLoaderArgs) {
  // Require either admin.manage_users or admin.manage_roles
  requireAnyPermission(['admin.manage_users', 'admin.manage_roles']);
  return null;
}

interface FileNode {
  name: string;
  path: string;
  type: 'file' | 'folder';
  children?: FileNode[];
  size?: number;
  modified?: number;
}

export default function AdminDocs() {
  const { authToken } = useOutletContext<{ authToken: string }>();
  const [fileTree, setFileTree] = useState<FileNode | null>(null);
  const [selectedFile, setSelectedFile] = useState<string | null>(null);
  const [fileContent, setFileContent] = useState<string>('');
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [hasChanges, setHasChanges] = useState(false);
  const [showPreview, setShowPreview] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expandedFolders, setExpandedFolders] = useState<Set<string>>(new Set([]));
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [createType, setCreateType] = useState<'file' | 'folder'>('file');
  const [createPath, setCreatePath] = useState('');
  const [isReindexing, setIsReindexing] = useState(false);
  const [reindexResult, setReindexResult] = useState<{ success: boolean; message: string; total_docs?: number } | null>(null);
  const [isExporting, setIsExporting] = useState(false);
  const [isImporting, setIsImporting] = useState(false);
  const [syncStatus, setSyncStatus] = useState<{
    total_docs: number;
    total_chunks: number;
    by_category: Record<string, number>;
    by_source: Record<string, number>;
    disk_files: number;
    disk_path: string;
  } | null>(null);
  const [exportImportResult, setExportImportResult] = useState<{
    type: 'export' | 'import';
    success: boolean;
    message: string;
  } | null>(null);

  // Load file tree and sync status on mount
  useEffect(() => {
    loadFileTree();
    loadSyncStatus();
  }, []);

  const loadSyncStatus = async () => {
    try {
      const response = await fetch('/api/admin/docs/sync-status', {
        headers: { 'Authorization': `Bearer ${authToken}` }
      });
      if (response.ok) {
        const status = await response.json();
        setSyncStatus(status);
      }
    } catch (error) {
      console.error('Failed to load sync status:', error);
    }
  };

  const exportDocs = async () => {
    setIsExporting(true);
    setExportImportResult(null);

    try {
      const response = await fetch('/api/admin/docs/export', {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${authToken}` }
      });

      const result = await response.json();
      setExportImportResult({
        type: 'export',
        success: result.success,
        message: result.success
          ? `Exported ${result.exported_count} documents to disk`
          : `Export failed: ${result.errors?.join(', ') || 'Unknown error'}`
      });
      loadSyncStatus();
    } catch (error) {
      console.error('Failed to export:', error);
      setExportImportResult({
        type: 'export',
        success: false,
        message: 'Failed to export documentation'
      });
    } finally {
      setIsExporting(false);
    }
  };

  const importDocs = async (force: boolean = false) => {
    setIsImporting(true);
    setExportImportResult(null);

    try {
      const response = await fetch(`/api/admin/docs/import?force=${force}`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${authToken}` }
      });

      const result = await response.json();
      setExportImportResult({
        type: 'import',
        success: result.success,
        message: result.success
          ? `Imported ${result.imported_count} new, updated ${result.updated_count}, skipped ${result.skipped_count}`
          : `Import failed: ${result.errors?.join(', ') || 'Unknown error'}`
      });
      loadFileTree();
      loadSyncStatus();
    } catch (error) {
      console.error('Failed to import:', error);
      setExportImportResult({
        type: 'import',
        success: false,
        message: 'Failed to import documentation'
      });
    } finally {
      setIsImporting(false);
    }
  };

  const loadFileTree = async () => {
    try {
      const response = await fetch('/api/admin/docs/tree', {
        headers: { 'Authorization': `Bearer ${authToken}` }
      });
      if (response.ok) {
        const tree = await response.json();
        setFileTree(tree);
      }
    } catch (error) {
      console.error('Failed to load file tree:', error);
      setError('Failed to load file tree');
    }
  };

  const loadFile = async (path: string) => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await fetch(`/api/admin/docs/read?path=${encodeURIComponent(path)}`, {
        headers: { 'Authorization': `Bearer ${authToken}` }
      });
      if (response.ok) {
        const data = await response.json();
        setFileContent(data.content);
        setSelectedFile(path);
        setHasChanges(false);
      } else {
        throw new Error('Failed to load file');
      }
    } catch (error) {
      console.error('Failed to load file:', error);
      setError('Failed to load file');
    } finally {
      setIsLoading(false);
    }
  };

  const saveFile = async () => {
    if (!selectedFile) return;

    setIsSaving(true);
    setError(null);
    try {
      const response = await fetch('/api/admin/docs/write', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${authToken}`
        },
        body: JSON.stringify({
          path: selectedFile,
          content: fileContent
        })
      });

      if (response.ok) {
        setHasChanges(false);
        // Optionally show success message
      } else {
        throw new Error('Failed to save file');
      }
    } catch (error) {
      console.error('Failed to save file:', error);
      setError('Failed to save file');
    } finally {
      setIsSaving(false);
    }
  };

  const handleContentChange = (newContent: string) => {
    setFileContent(newContent);
    setHasChanges(true);
  };

  const toggleFolder = (path: string) => {
    setExpandedFolders(prev => {
      const next = new Set(prev);
      if (next.has(path)) {
        next.delete(path);
      } else {
        next.add(path);
      }
      return next;
    });
  };

  const createItem = async () => {
    if (!createPath.trim()) {
      setError('Path is required');
      return;
    }

    try {
      const response = await fetch('/api/admin/docs/create', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${authToken}`
        },
        body: JSON.stringify({
          path: createPath,
          type: createType,
          content: createType === 'file' ? '# New Document\n\nAdd your content here...' : ''
        })
      });

      if (response.ok) {
        setShowCreateDialog(false);
        setCreatePath('');
        loadFileTree();
      } else {
        const data = await response.json();
        setError(data.detail || 'Failed to create item');
      }
    } catch (error) {
      console.error('Failed to create item:', error);
      setError('Failed to create item');
    }
  };

  const deleteItem = async (path: string) => {
    if (!confirm(`Are you sure you want to delete ${path}?`)) {
      return;
    }

    try {
      const response = await fetch('/api/admin/docs/delete', {
        method: 'DELETE',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${authToken}`
        },
        body: JSON.stringify({ path })
      });

      if (response.ok) {
        if (selectedFile === path) {
          setSelectedFile(null);
          setFileContent('');
        }
        loadFileTree();
      } else {
        const data = await response.json();
        setError(data.detail || 'Failed to delete item');
      }
    } catch (error) {
      console.error('Failed to delete item:', error);
      setError('Failed to delete item');
    }
  };

  const reindexDocs = async () => {
    setIsReindexing(true);
    setReindexResult(null);
    setError(null);

    try {
      const response = await fetch('/api/admin/docs/reindex', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${authToken}`
        }
      });

      if (response.ok) {
        const result = await response.json();
        setReindexResult(result);
      } else {
        throw new Error('Failed to reindex documentation');
      }
    } catch (error) {
      console.error('Failed to reindex:', error);
      setError('Failed to reindex documentation');
      setReindexResult({ success: false, message: 'Failed to reindex documentation' });
    } finally {
      setIsReindexing(false);
    }
  };

  const renderFileTree = (node: FileNode, depth: number = 0) => {
    const isSelected = selectedFile === node.path;
    const isExpanded = expandedFolders.has(node.path);
    const isFolder = node.type === 'folder';

    return (
      <div key={node.path}>
        <div
          className={`
            flex items-center gap-2 px-3 py-1.5 rounded-md cursor-pointer
            ${isSelected ? 'bg-blue-100 dark:bg-blue-900/30 text-blue-900 dark:text-blue-100' : 'hover:bg-zinc-100 dark:hover:bg-zinc-800'}
          `}
          style={{ paddingLeft: `${depth * 16 + 12}px` }}
          onClick={() => {
            if (isFolder) {
              toggleFolder(node.path);
            } else {
              loadFile(node.path);
            }
          }}
        >
          {isFolder && (
            <span className="text-xs text-zinc-500">
              {isExpanded ? '▼' : '▶'}
            </span>
          )}
          <span className="text-sm">
            {node.type === 'folder' ? '📁' : '📄'}
          </span>
          <span className="text-sm font-medium">{node.name}</span>
          {node.type === 'file' && node.size && (
            <span className="text-xs text-zinc-500 ml-auto">
              {(node.size / 1024).toFixed(1)}KB
            </span>
          )}
        </div>
        {isFolder && isExpanded && node.children && node.children.map(child => renderFileTree(child, depth + 1))}
      </div>
    );
  };

  return (
    <div className="flex h-screen bg-white dark:bg-zinc-950">
      {/* Sidebar - File Browser */}
      <div className="w-80 border-r border-zinc-200 dark:border-zinc-800 overflow-y-auto">
        <div className="p-4 border-b border-zinc-200 dark:border-zinc-800">
          <div className="flex items-center justify-between mb-2">
            <h2 className="text-lg font-semibold text-zinc-900 dark:text-zinc-100">
              Documentation Files
            </h2>
            <button
              onClick={() => setShowCreateDialog(true)}
              className="px-2 py-1 text-xs bg-blue-600 text-white rounded hover:bg-blue-700"
              title="Create new file or folder"
            >
              + New
            </button>
          </div>
          <p className="text-xs text-zinc-500 dark:text-zinc-400">
            Click to edit
          </p>

          {/* Reindex Documentation */}
          <div className="mt-3 p-3 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-md">
            <div className="flex flex-col gap-2">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs font-medium text-blue-900 dark:text-blue-100 mb-0.5">
                    Documentation Indexing
                  </p>
                  <p className="text-xs text-blue-600 dark:text-blue-400">
                    Updates semantic search after editing
                  </p>
                </div>
              </div>

              <button
                onClick={reindexDocs}
                disabled={isReindexing}
                className="w-full px-3 py-2 text-xs font-medium rounded-md transition-colors disabled:opacity-50 disabled:cursor-not-allowed bg-blue-600 hover:bg-blue-700 text-white"
              >
                {isReindexing ? (
                  <span className="flex items-center justify-center gap-2">
                    <svg className="animate-spin h-3 w-3" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                    Reindexing...
                  </span>
                ) : '🔄 Reindex Documentation'}
              </button>

              {reindexResult && (
                <div className={`p-2 rounded-md text-xs ${
                  reindexResult.success
                    ? 'bg-green-50 dark:bg-green-900/20 text-green-900 dark:text-green-100 border border-green-200 dark:border-green-800'
                    : 'bg-red-50 dark:bg-red-900/20 text-red-900 dark:text-red-100 border border-red-200 dark:border-red-800'
                }`}>
                  {reindexResult.success ? '✓' : '✗'} {reindexResult.message}
                  {reindexResult.total_docs && (
                    <div className="mt-1 text-green-700 dark:text-green-300">
                      Total indexed: {reindexResult.total_docs} documents
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>

          {/* Export/Import Section */}
          <div className="mt-3 p-3 bg-purple-50 dark:bg-purple-900/20 border border-purple-200 dark:border-purple-800 rounded-md">
            <div className="flex flex-col gap-2">
              <div>
                <p className="text-xs font-medium text-purple-900 dark:text-purple-100 mb-0.5">
                  Sync with Disk
                </p>
                <p className="text-xs text-purple-600 dark:text-purple-400">
                  Export DB to disk or import from disk
                </p>
              </div>

              {/* Sync Status */}
              {syncStatus && (
                <div className="p-2 bg-white dark:bg-zinc-800 rounded text-xs">
                  <div className="flex justify-between mb-1">
                    <span className="text-zinc-600 dark:text-zinc-400">DB Docs:</span>
                    <span className="font-medium text-zinc-900 dark:text-zinc-100">{syncStatus.total_docs}</span>
                  </div>
                  <div className="flex justify-between mb-1">
                    <span className="text-zinc-600 dark:text-zinc-400">Search Chunks:</span>
                    <span className="font-medium text-zinc-900 dark:text-zinc-100">{syncStatus.total_chunks}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-zinc-600 dark:text-zinc-400">Disk Files:</span>
                    <span className="font-medium text-zinc-900 dark:text-zinc-100">{syncStatus.disk_files}</span>
                  </div>
                </div>
              )}

              {/* Export/Import Buttons */}
              <div className="flex gap-2">
                <button
                  onClick={exportDocs}
                  disabled={isExporting || isImporting}
                  className="flex-1 px-2 py-1.5 text-xs font-medium rounded-md transition-colors disabled:opacity-50 disabled:cursor-not-allowed bg-purple-600 hover:bg-purple-700 text-white"
                >
                  {isExporting ? (
                    <span className="flex items-center justify-center gap-1">
                      <svg className="animate-spin h-3 w-3" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                      </svg>
                      Exporting...
                    </span>
                  ) : '📤 Export'}
                </button>
                <button
                  onClick={() => importDocs(false)}
                  disabled={isExporting || isImporting}
                  className="flex-1 px-2 py-1.5 text-xs font-medium rounded-md transition-colors disabled:opacity-50 disabled:cursor-not-allowed bg-purple-600 hover:bg-purple-700 text-white"
                >
                  {isImporting ? (
                    <span className="flex items-center justify-center gap-1">
                      <svg className="animate-spin h-3 w-3" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                      </svg>
                      Importing...
                    </span>
                  ) : '📥 Import'}
                </button>
              </div>

              {/* Force Import Option */}
              <button
                onClick={() => {
                  if (confirm('Force import will overwrite all existing documents in DB. Continue?')) {
                    importDocs(true);
                  }
                }}
                disabled={isExporting || isImporting}
                className="w-full px-2 py-1 text-xs text-purple-700 dark:text-purple-300 hover:bg-purple-100 dark:hover:bg-purple-900/30 rounded disabled:opacity-50"
              >
                Force Import (overwrite all)
              </button>

              {/* Export/Import Result */}
              {exportImportResult && (
                <div className={`p-2 rounded-md text-xs ${
                  exportImportResult.success
                    ? 'bg-green-50 dark:bg-green-900/20 text-green-900 dark:text-green-100 border border-green-200 dark:border-green-800'
                    : 'bg-red-50 dark:bg-red-900/20 text-red-900 dark:text-red-100 border border-red-200 dark:border-red-800'
                }`}>
                  {exportImportResult.success ? '✓' : '✗'} {exportImportResult.message}
                </div>
              )}
            </div>
          </div>
        </div>

        <div className="p-2">
          {fileTree ? (
            renderFileTree(fileTree)
          ) : (
            <div className="text-center py-8 text-zinc-500">
              Loading...
            </div>
          )}
        </div>
      </div>

      {/* Main Editor Area */}
      <div className="flex-1 flex flex-col">
        {/* Toolbar */}
        <div className="flex items-center justify-between px-6 py-3 border-b border-zinc-200 dark:border-zinc-800">
          <div className="flex items-center gap-4">
            {selectedFile ? (
              <>
                <h3 className="text-sm font-medium text-zinc-900 dark:text-zinc-100">
                  {selectedFile}
                </h3>
                {hasChanges && (
                  <span className="text-xs text-amber-600 dark:text-amber-400">
                    • Unsaved changes
                  </span>
                )}
              </>
            ) : (
              <h3 className="text-sm text-zinc-500 dark:text-zinc-400">
                Select a file to edit
              </h3>
            )}
          </div>

          <div className="flex items-center gap-2">
            {selectedFile && (
              <>
                <button
                  onClick={() => deleteItem(selectedFile)}
                  className="px-3 py-1.5 text-sm bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300 rounded-md hover:bg-red-200 dark:hover:bg-red-900/50"
                >
                  Delete
                </button>
                <button
                  onClick={() => setShowPreview(!showPreview)}
                  className="px-3 py-1.5 text-sm bg-zinc-100 dark:bg-zinc-800 text-zinc-700 dark:text-zinc-300 rounded-md hover:bg-zinc-200 dark:hover:bg-zinc-700"
                >
                  {showPreview ? 'Hide Preview' : 'Show Preview'}
                </button>
                <button
                  onClick={saveFile}
                  disabled={!hasChanges || isSaving}
                  className={`
                    px-3 py-1.5 text-sm rounded-md
                    ${hasChanges && !isSaving
                      ? 'bg-blue-600 text-white hover:bg-blue-700'
                      : 'bg-zinc-200 dark:bg-zinc-800 text-zinc-400 cursor-not-allowed'
                    }
                  `}
                >
                  {isSaving ? 'Saving...' : 'Save'}
                </button>
              </>
            )}
          </div>
        </div>

        {error && (
          <div className="mx-6 mt-4 p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-md">
            <p className="text-sm text-red-700 dark:text-red-300">{error}</p>
          </div>
        )}

        {/* Editor/Preview Area */}
        <div className="flex-1 overflow-hidden">
          {selectedFile ? (
            <div className={`flex h-full ${showPreview ? 'divide-x divide-zinc-200 dark:divide-zinc-800' : ''}`}>
              {/* Editor */}
              <div className={showPreview ? 'w-1/2' : 'w-full'}>
                <TextareaWithAutocomplete
                  value={fileContent}
                  onChange={(e) => handleContentChange(e.target.value)}
                  authToken={authToken}
                  mode="docs"
                  className="w-full h-full p-6 bg-white dark:bg-zinc-950 text-zinc-900 dark:text-zinc-100 font-mono text-sm leading-relaxed resize-none focus:outline-none"
                  placeholder="Start typing..."
                  spellCheck={false}
                  style={{ tabSize: 2 }}
                />
              </div>

              {/* Preview */}
              {showPreview && (
                <div className="w-1/2 overflow-y-auto p-6 bg-zinc-50 dark:bg-zinc-900">
                  <div
                    className="prose dark:prose-invert max-w-none"
                    dangerouslySetInnerHTML={{ __html: renderMarkdown(fileContent) }}
                  />
                </div>
              )}
            </div>
          ) : (
            <div className="flex items-center justify-center h-full text-zinc-500">
              <div className="text-center">
                <svg className="mx-auto w-16 h-16 text-zinc-300 dark:text-zinc-700 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
                <p className="text-sm">Select a file from the sidebar to begin editing</p>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Create Dialog */}
      {showCreateDialog && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white dark:bg-zinc-900 rounded-lg p-6 w-96 shadow-xl">
            <h3 className="text-lg font-semibold text-zinc-900 dark:text-zinc-100 mb-4">
              Create New {createType === 'file' ? 'File' : 'Folder'}
            </h3>

            <div className="mb-4">
              <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-2">
                Type
              </label>
              <div className="flex gap-2">
                <button
                  onClick={() => setCreateType('file')}
                  className={`flex-1 px-3 py-2 text-sm rounded ${
                    createType === 'file'
                      ? 'bg-blue-600 text-white'
                      : 'bg-zinc-100 dark:bg-zinc-800 text-zinc-700 dark:text-zinc-300'
                  }`}
                >
                  📄 File
                </button>
                <button
                  onClick={() => setCreateType('folder')}
                  className={`flex-1 px-3 py-2 text-sm rounded ${
                    createType === 'folder'
                      ? 'bg-blue-600 text-white'
                      : 'bg-zinc-100 dark:bg-zinc-800 text-zinc-700 dark:text-zinc-300'
                  }`}
                >
                  📁 Folder
                </button>
              </div>
            </div>

            <div className="mb-4">
              <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-2">
                Path (relative to docs/)
              </label>
              <input
                type="text"
                value={createPath}
                onChange={(e) => setCreatePath(e.target.value)}
                placeholder={createType === 'file' ? 'example.md' : 'folder-name'}
                className="w-full px-3 py-2 bg-white dark:bg-zinc-800 border border-zinc-300 dark:border-zinc-700 rounded text-zinc-900 dark:text-zinc-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            <div className="flex justify-end gap-2">
              <button
                onClick={() => {
                  setShowCreateDialog(false);
                  setCreatePath('');
                }}
                className="px-4 py-2 text-sm bg-zinc-100 dark:bg-zinc-800 text-zinc-700 dark:text-zinc-300 rounded hover:bg-zinc-200 dark:hover:bg-zinc-700"
              >
                Cancel
              </button>
              <button
                onClick={createItem}
                className="px-4 py-2 text-sm bg-blue-600 text-white rounded hover:bg-blue-700"
              >
                Create
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// Enhanced markdown renderer
function renderMarkdown(markdown: string): string {
  let html = markdown;

  // Escape HTML entities first
  html = html.replace(/&/g, '&amp;')
             .replace(/</g, '&lt;')
             .replace(/>/g, '&gt;');

  // Code blocks with language (triple backticks)
  html = html.replace(/```(\w+)?\n([\s\S]*?)```/g, (match, lang, code) => {
    return `<pre class="bg-zinc-800 text-zinc-100 p-4 rounded overflow-x-auto"><code class="language-${lang || 'text'}">${code.trim()}</code></pre>`;
  });

  // Headers (with proper line breaks)
  html = html.replace(/^#### (.*$)/gim, '<h4 class="text-base font-semibold mt-4 mb-2">$1</h4>');
  html = html.replace(/^### (.*$)/gim, '<h3 class="text-lg font-semibold mt-6 mb-3">$1</h3>');
  html = html.replace(/^## (.*$)/gim, '<h2 class="text-xl font-bold mt-8 mb-4">$1</h2>');
  html = html.replace(/^# (.*$)/gim, '<h1 class="text-2xl font-bold mt-8 mb-4">$1</h1>');

  // Horizontal rules
  html = html.replace(/^---$/gm, '<hr class="my-6 border-zinc-300 dark:border-zinc-700">');

  // Blockquotes
  html = html.replace(/^> (.*)$/gm, '<blockquote class="border-l-4 border-zinc-300 dark:border-zinc-700 pl-4 italic my-4">$1</blockquote>');

  // Bold
  html = html.replace(/\*\*(.*?)\*\*/g, '<strong class="font-semibold">$1</strong>');

  // Italic
  html = html.replace(/\*(.*?)\*/g, '<em class="italic">$1</em>');

  // Inline code
  html = html.replace(/`([^`]+)`/g, '<code class="bg-zinc-200 dark:bg-zinc-800 px-1.5 py-0.5 rounded text-sm font-mono">$1</code>');

  // Links
  html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" class="text-blue-600 dark:text-blue-400 hover:underline">$1</a>');

  // Unordered lists
  html = html.replace(/^\* (.*)$/gm, '<li class="ml-6 list-disc">$1</li>');
  html = html.replace(/^- (.*)$/gm, '<li class="ml-6 list-disc">$1</li>');

  // Ordered lists
  html = html.replace(/^\d+\. (.*)$/gm, '<li class="ml-6 list-decimal">$1</li>');

  // Wrap consecutive list items in ul/ol
  html = html.replace(/(<li[^>]*>.*<\/li>\n?)+/g, (match) => {
    if (match.includes('list-decimal')) {
      return `<ol class="my-4">${match}</ol>`;
    }
    return `<ul class="my-4">${match}</ul>`;
  });

  // Paragraphs (double line breaks)
  html = html.replace(/\n\n/g, '</p><p class="mb-4">');
  html = `<p class="mb-4">${html}</p>`;

  // Single line breaks
  html = html.replace(/\n/g, '<br>');

  return html;
}
