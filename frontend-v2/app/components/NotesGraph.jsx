import React, { useMemo, useState, useCallback, useEffect } from 'react';
import { X, Link2, Brain, SlidersHorizontal } from 'lucide-react';
import { Button } from './catalyst/button';

/**
 * Notes Graph Visualization
 *
 * Features:
 * - Force-directed graph of note connections
 * - Nodes: notes (colored by category)
 * - Edges: [[wikilinks]] (solid) + semantic connections (dashed)
 * - Similarity threshold slider for semantic connections
 * - Interactive: click nodes to navigate
 * - Zoom and pan controls
 *
 * Requirements:
 * - npm install react-force-graph-2d
 */
export default function NotesGraph({ notes, onSelectNote, onClose }) {
  const [ForceGraph, setForceGraph] = useState(null);
  const [graphError, setGraphError] = useState(null);
  const [semanticConnections, setSemanticConnections] = useState([]);
  const [similarityThreshold, setSimilarityThreshold] = useState(0.65);
  const [showSemanticLinks, setShowSemanticLinks] = useState(true);
  const [showWikilinks, setShowWikilinks] = useState(true);
  const [isLoadingConnections, setIsLoadingConnections] = useState(false);

  // Dynamic import of react-force-graph-2d
  useEffect(() => {
    const loadForceGraph = async () => {
      try {
        console.log('[NotesGraph] Starting dynamic import of react-force-graph-2d...');
        const module = await import('react-force-graph-2d');
        console.log('[NotesGraph] Module loaded:', module);

        // Try default export first, then named export
        const Component = module.default || module.ForceGraph2D;

        if (!Component) {
          throw new Error('ForceGraph2D component not found in module');
        }

        console.log('[NotesGraph] ForceGraph2D component loaded successfully');
        setForceGraph(() => Component);
      } catch (err) {
        console.error('[NotesGraph] Failed to load react-force-graph-2d:', err);
        setGraphError('Graph visualization library not installed. Run: pnpm install react-force-graph-2d');
      }
    };

    loadForceGraph();
  }, []);

  // Fetch semantic connections when threshold changes
  useEffect(() => {
    const fetchSemanticConnections = async () => {
      if (!showSemanticLinks) {
        setSemanticConnections([]);
        return;
      }

      setIsLoadingConnections(true);
      try {
        const response = await fetch(
          `/api/notes/graph-connections?similarity_threshold=${similarityThreshold}&limit_per_note=5`,
          {
            headers: {
              'Authorization': `Bearer ${localStorage.getItem('token')}`
            }
          }
        );

        if (response.ok) {
          const data = await response.json();
          console.log('[NotesGraph] Fetched semantic connections:', data.count);
          setSemanticConnections(data.connections || []);
        } else {
          console.error('[NotesGraph] Failed to fetch semantic connections:', response.status);
          setSemanticConnections([]);
        }
      } catch (err) {
        console.error('[NotesGraph] Error fetching semantic connections:', err);
        setSemanticConnections([]);
      } finally {
        setIsLoadingConnections(false);
      }
    };

    // Debounce the fetch to avoid too many requests while sliding
    const timeoutId = setTimeout(fetchSemanticConnections, 300);
    return () => clearTimeout(timeoutId);
  }, [similarityThreshold, showSemanticLinks]);

  // Build graph data from notes
  const graphData = useMemo(() => {
    console.log('[NotesGraph] Building graph data from', notes?.length || 0, 'notes');

    if (!notes || notes.length === 0) {
      console.log('[NotesGraph] No notes provided, returning empty graph');
      return { nodes: [], links: [] };
    }

    // Create a map for quick ID lookup
    const noteIdSet = new Set(notes.map(n => n.id));

    // Create nodes
    const nodes = notes.map(note => ({
      id: note.id,
      name: note.title,
      category: note.category,
      starred: note.is_starred,
      val: 5 + (note.tags?.length || 0) * 2, // Node size based on tag count
      color: getCategoryColor(note.category, note.is_starred)
    }));

    console.log('[NotesGraph] Created', nodes.length, 'nodes');

    // Create wikilink connections by parsing [[wikilinks]] in content
    const wikilinkConnections = [];
    if (showWikilinks) {
      const WIKILINK_REGEX = /\[\[([^\]|]+)(\|([^\]]+))?\]\]/g;

      notes.forEach(note => {
        if (!note.content) return;

        let match;
        WIKILINK_REGEX.lastIndex = 0;

        while ((match = WIKILINK_REGEX.exec(note.content)) !== null) {
          const linkedTitle = match[1].trim();

          // Find the linked note
          const linkedNote = notes.find(n =>
            n.title.toLowerCase() === linkedTitle.toLowerCase()
          );

          if (linkedNote) {
            wikilinkConnections.push({
              source: note.id,
              target: linkedNote.id,
              type: 'wikilink'
            });
          }
        }
      });
    }

    console.log('[NotesGraph] Created', wikilinkConnections.length, 'wikilink connections');

    // Add semantic connections (filtered to only include notes in current view)
    const semanticLinks = showSemanticLinks
      ? semanticConnections
          .filter(conn => noteIdSet.has(conn.source) && noteIdSet.has(conn.target))
          .map(conn => ({
            source: conn.source,
            target: conn.target,
            type: 'semantic',
            similarity: conn.similarity
          }))
      : [];

    console.log('[NotesGraph] Added', semanticLinks.length, 'semantic connections');

    // Combine all links
    const links = [...wikilinkConnections, ...semanticLinks];

    console.log('[NotesGraph] Total links:', links.length);

    return { nodes, links };
  }, [notes, semanticConnections, showWikilinks, showSemanticLinks]);

  const handleNodeClick = useCallback((node) => {
    if (onSelectNote) {
      onSelectNote(node.id);
    }
    if (onClose) {
      onClose();
    }
  }, [onSelectNote, onClose]);

  // Count links by type for stats
  const linkStats = useMemo(() => {
    const wikilinks = graphData.links.filter(l => l.type === 'wikilink').length;
    const semantic = graphData.links.filter(l => l.type === 'semantic').length;
    return { wikilinks, semantic };
  }, [graphData.links]);

  // Loading state
  if (!ForceGraph && !graphError) {
    return (
      <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm flex items-center justify-center">
        <div className="bg-white dark:bg-zinc-900 rounded-xl shadow-2xl p-6 text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500 mx-auto mb-4"></div>
          <p className="text-zinc-700 dark:text-zinc-300">Loading graph visualization...</p>
        </div>
      </div>
    );
  }

  // Error state
  if (graphError) {
    return (
      <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm flex items-center justify-center p-4">
        <div className="bg-white dark:bg-zinc-900 rounded-xl shadow-2xl p-6 max-w-md">
          <div className="flex items-start gap-3 mb-4">
            <div className="flex-shrink-0 w-10 h-10 bg-red-100 dark:bg-red-900/30 rounded-full flex items-center justify-center">
              <X className="w-6 h-6 text-red-600 dark:text-red-400" />
            </div>
            <div>
              <h3 className="text-lg font-semibold text-zinc-900 dark:text-zinc-100 mb-2">
                Graph Library Not Installed
              </h3>
              <p className="text-sm text-zinc-600 dark:text-zinc-400 mb-3">
                {graphError}
              </p>
              <pre className="text-xs bg-zinc-100 dark:bg-zinc-800 p-3 rounded-lg overflow-x-auto">
                pnpm install react-force-graph-2d
              </pre>
            </div>
          </div>
          <Button onClick={onClose} className="w-full">
            Close
          </Button>
        </div>
      </div>
    );
  }

  // Render graph
  return (
    <div className="fixed inset-0 z-50 bg-black/90 backdrop-blur-sm">
      {/* Header */}
      <div className="absolute top-0 left-0 right-0 bg-zinc-900/80 backdrop-blur-sm border-b border-zinc-700 px-6 py-4 z-10">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-xl font-bold text-white">Notes Graph</h2>
            <p className="text-sm text-zinc-400">
              {graphData.nodes.length} notes • {linkStats.wikilinks} wikilinks • {linkStats.semantic} semantic
              {isLoadingConnections && <span className="ml-2 text-purple-400">(loading...)</span>}
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-white transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>
      </div>

      {/* Graph Canvas */}
      <div className="w-full h-full pt-20">
        <ForceGraph
          graphData={graphData}
          nodeLabel="name"
          nodeColor="color"
          nodeVal="val"
          linkColor={link => {
            if (link.type === 'wikilink') {
              return '#6B7280'; // Gray for wikilinks
            }
            // Purple with opacity based on similarity for semantic links
            const opacity = 0.4 + (link.similarity * 0.6);
            return `rgba(139, 92, 246, ${opacity})`;
          }}
          linkWidth={link => {
            if (link.type === 'wikilink') return 2;
            // Semantic links: width based on similarity (1-3px)
            return 1 + (link.similarity * 2);
          }}
          linkLineDash={link => link.type === 'semantic' ? [4, 4] : null}
          linkDirectionalArrowLength={link => link.type === 'wikilink' ? 4 : 0}
          linkDirectionalArrowRelPos={1}
          onNodeClick={handleNodeClick}
          nodeCanvasObject={(node, ctx, globalScale) => {
            // Custom node rendering
            const label = node.name;
            const fontSize = 12 / globalScale;
            const nodeRadius = Math.sqrt(node.val || 5);

            // Draw node circle
            ctx.beginPath();
            ctx.arc(node.x, node.y, nodeRadius, 0, 2 * Math.PI);
            ctx.fillStyle = node.color;
            ctx.fill();

            // Add white border for starred notes
            if (node.starred) {
              ctx.strokeStyle = '#FFD700';
              ctx.lineWidth = 2 / globalScale;
              ctx.stroke();
            }

            // Draw label
            ctx.font = `${fontSize}px Sans-Serif`;
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillStyle = '#FFF';
            ctx.fillText(label, node.x, node.y + nodeRadius + fontSize);
          }}
          cooldownTicks={100}
          onEngineStop={() => {
            // Auto-zoom to fit all nodes after initial layout
          }}
        />
      </div>

      {/* Controls Panel */}
      <div className="absolute top-24 right-6 bg-zinc-900/90 backdrop-blur-sm border border-zinc-700 rounded-lg p-4 z-10 w-72">
        <div className="flex items-center gap-2 mb-3">
          <SlidersHorizontal className="w-4 h-4 text-zinc-400" />
          <h3 className="text-sm font-semibold text-zinc-300">Connection Settings</h3>
        </div>

        {/* Toggle switches */}
        <div className="space-y-3 mb-4">
          <label className="flex items-center justify-between cursor-pointer">
            <span className="flex items-center gap-2 text-sm text-zinc-300">
              <Link2 className="w-4 h-4 text-gray-400" />
              Wikilinks
            </span>
            <input
              type="checkbox"
              checked={showWikilinks}
              onChange={(e) => setShowWikilinks(e.target.checked)}
              className="w-4 h-4 rounded border-zinc-600 bg-zinc-800 text-blue-500 focus:ring-blue-500"
            />
          </label>

          <label className="flex items-center justify-between cursor-pointer">
            <span className="flex items-center gap-2 text-sm text-zinc-300">
              <Brain className="w-4 h-4 text-purple-400" />
              Semantic
            </span>
            <input
              type="checkbox"
              checked={showSemanticLinks}
              onChange={(e) => setShowSemanticLinks(e.target.checked)}
              className="w-4 h-4 rounded border-zinc-600 bg-zinc-800 text-purple-500 focus:ring-purple-500"
            />
          </label>
        </div>

        {/* Similarity threshold slider */}
        {showSemanticLinks && (
          <div className="pt-3 border-t border-zinc-700">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs text-zinc-400">Similarity Threshold</span>
              <span className="text-xs font-mono text-purple-400">
                {(similarityThreshold * 100).toFixed(0)}%
              </span>
            </div>
            <input
              type="range"
              min="0.5"
              max="0.9"
              step="0.05"
              value={similarityThreshold}
              onChange={(e) => setSimilarityThreshold(parseFloat(e.target.value))}
              className="w-full h-2 bg-zinc-700 rounded-lg appearance-none cursor-pointer accent-purple-500"
            />
            <div className="flex justify-between text-xs text-zinc-500 mt-1">
              <span>More links</span>
              <span>Fewer links</span>
            </div>
          </div>
        )}
      </div>

      {/* Legend */}
      <div className="absolute bottom-6 left-6 bg-zinc-900/80 backdrop-blur-sm border border-zinc-700 rounded-lg p-4 z-10">
        <h3 className="text-xs font-semibold text-zinc-400 uppercase tracking-wide mb-2">
          Categories
        </h3>
        <div className="space-y-1.5">
          <LegendItem color={getCategoryColor('personal')} label="Personal" />
          <LegendItem color={getCategoryColor('work')} label="Work" />
          <LegendItem color={getCategoryColor('ideas')} label="Ideas" />
          <LegendItem color={getCategoryColor('inbox')} label="Inbox" />
          <LegendItem color={getCategoryColor('reference')} label="Reference" />
        </div>

        <div className="mt-3 pt-3 border-t border-zinc-700">
          <h3 className="text-xs font-semibold text-zinc-400 uppercase tracking-wide mb-2">
            Connections
          </h3>
          <div className="space-y-1.5">
            <div className="flex items-center gap-2 text-xs text-zinc-300">
              <div className="w-6 h-0.5 bg-gray-500"></div>
              <span>[[Wikilink]]</span>
            </div>
            <div className="flex items-center gap-2 text-xs text-zinc-300">
              <div className="w-6 h-0.5 bg-purple-500" style={{ backgroundImage: 'repeating-linear-gradient(90deg, #8B5CF6 0, #8B5CF6 4px, transparent 4px, transparent 8px)' }}></div>
              <span>Semantic similarity</span>
            </div>
          </div>
        </div>

        <div className="mt-3 pt-3 border-t border-zinc-700">
          <div className="flex items-center gap-2 text-xs text-zinc-400">
            <div className="w-4 h-4 rounded-full bg-blue-500 border-2 border-amber-500"></div>
            <span>Starred note</span>
          </div>
        </div>
      </div>
    </div>
  );
}

function LegendItem({ color, label }) {
  return (
    <div className="flex items-center gap-2 text-sm text-zinc-300">
      <div className="w-3 h-3 rounded-full" style={{ backgroundColor: color }}></div>
      <span>{label}</span>
    </div>
  );
}

function getCategoryColor(category, starred = false) {
  const colors = {
    personal: '#3B82F6',  // Blue
    work: '#10B981',      // Green
    ideas: '#8B5CF6',     // Purple
    inbox: '#F59E0B',     // Amber
    reference: '#6B7280', // Gray
  };

  const color = colors[category] || colors.personal;
  return starred ? '#FFD700' : color; // Gold for starred
}
