import React, { useState, useEffect } from 'react';
import {
  XMarkIcon,
  WrenchScrewdriverIcon,
  CpuChipIcon,
  DocumentTextIcon,
  CubeIcon,
  ArrowPathIcon,
  ChevronDownIcon,
  ChevronRightIcon
} from '@heroicons/react/24/outline';

/**
 * ToolsSidebar - Pull-out drawer showing available tools and agents
 *
 * Features:
 * - Lists all orchestrator tools
 * - Shows specialized agents with capabilities
 * - Displays custom MCP tools from user settings
 * - Slide-in drawer animation
 */
export default function ToolsSidebar({ isOpen, onClose, authToken }) {
  const [tools, setTools] = useState([]);
  const [agents, setAgents] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [expandedCategories, setExpandedCategories] = useState({
    agents: true, // Agents expanded by default
    core: false,
    file: false,
    cache: false,
    docs: false,
    vision: false,
    mcp: true, // MCP expanded by default to show user's custom servers
    user: false,
  });

  // Fetch tools and agents when sidebar opens
  useEffect(() => {
    if (isOpen && authToken) {
      loadTools();
    }
  }, [isOpen, authToken]);

  const loadTools = async () => {
    setIsLoading(true);
    setError(null);

    try {
      const response = await fetch('/api/tools/', {
        headers: {
          Authorization: `Bearer ${authToken}`,
        },
      });

      if (response.ok) {
        const data = await response.json();
        setTools(data.tools || []);
        setAgents(data.agents || []);
      } else {
        throw new Error('Failed to load tools');
      }
    } catch (err) {
      console.error('Error loading tools:', err);
      setError('Failed to load tools and agents');
    } finally {
      setIsLoading(false);
    }
  };

  // Group tools by category
  const toolsByCategory = tools.reduce((acc, tool) => {
    if (!acc[tool.category]) {
      acc[tool.category] = [];
    }
    acc[tool.category].push(tool);
    return acc;
  }, {});

  const categoryIcons = {
    core: WrenchScrewdriverIcon,
    agent: CpuChipIcon,
    file: DocumentTextIcon,
    cache: ArrowPathIcon,
    docs: DocumentTextIcon,
    vision: CubeIcon,
    mcp: CubeIcon,
    user: CpuChipIcon,
  };

  const categoryLabels = {
    core: 'Core Tools',
    agent: 'Agent Management',
    file: 'File Operations',
    cache: 'Cache Management',
    docs: 'Documentation',
    vision: 'Vision & Analysis',
    mcp: 'MCP Servers',
    user: 'User Management',
  };

  const toggleCategory = (category) => {
    setExpandedCategories(prev => ({
      ...prev,
      [category]: !prev[category]
    }));
  };

  return (
    <>
      {/* Backdrop */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-40 lg:hidden"
          onClick={onClose}
        />
      )}

      {/* Drawer */}
      <div
        className={`fixed right-0 top-0 h-full w-80 bg-white dark:bg-zinc-900 border-l border-zinc-200 dark:border-zinc-800 shadow-2xl z-50 transform transition-transform duration-300 ease-in-out ${
          isOpen ? 'translate-x-0' : 'translate-x-full'
        }`}
      >
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-zinc-200 dark:border-zinc-800">
          <h2 className="text-lg font-semibold text-zinc-900 dark:text-zinc-100 flex items-center gap-2">
            <WrenchScrewdriverIcon className="h-5 w-5" />
            Available Tools
          </h2>
          <button
            onClick={onClose}
            className="p-1.5 text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-100 rounded-lg hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-colors"
          >
            <XMarkIcon className="h-5 w-5" />
          </button>
        </div>

        {/* Content */}
        <div className="overflow-y-auto h-[calc(100%-64px)] p-4">
          {isLoading && (
            <div className="flex items-center justify-center py-8">
              <ArrowPathIcon className="h-6 w-6 animate-spin text-zinc-400" />
              <span className="ml-2 text-sm text-zinc-500">Loading...</span>
            </div>
          )}

          {error && (
            <div className="text-sm text-red-600 dark:text-red-400 p-4 bg-red-50 dark:bg-red-900/20 rounded-lg">
              {error}
            </div>
          )}

          {!isLoading && !error && (
            <div className="space-y-6">
              {/* Agents Section */}
              {agents.length > 0 && (
                <div>
                  <button
                    onClick={() => toggleCategory('agents')}
                    className="w-full text-sm font-semibold text-zinc-900 dark:text-zinc-100 mb-3 flex items-center justify-between hover:text-amber-800 dark:hover:text-amber-200 transition-colors"
                  >
                    <div className="flex items-center gap-2">
                      <CpuChipIcon className="h-4 w-4" />
                      Specialized Agents
                      <span className="text-xs text-zinc-500 dark:text-zinc-400 font-normal">
                        ({agents.length})
                      </span>
                    </div>
                    {expandedCategories.agents ? (
                      <ChevronDownIcon className="h-4 w-4" />
                    ) : (
                      <ChevronRightIcon className="h-4 w-4" />
                    )}
                  </button>
                  {expandedCategories.agents && (
                    <div className="space-y-2 mb-6">
                      {agents.map((agent) => (
                        <div
                          key={agent.name}
                          className="p-3 bg-zinc-50 dark:bg-zinc-800/50 rounded-lg border border-zinc-200 dark:border-zinc-700"
                        >
                          <div className="font-medium text-sm text-zinc-900 dark:text-zinc-100">
                            {agent.name}
                          </div>
                          <div className="text-xs text-zinc-600 dark:text-zinc-400 mt-1">
                            {agent.description}
                          </div>
                          <div className="flex flex-wrap gap-1 mt-2">
                            {agent.capabilities.map((cap) => (
                              <span
                                key={cap}
                                className="text-xs px-2 py-0.5 bg-amber-100 dark:bg-amber-900/30 text-amber-800 dark:text-amber-300 rounded"
                              >
                                {cap}
                              </span>
                            ))}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {/* Tools by Category */}
              {Object.entries(toolsByCategory).map(([category, categoryTools]) => {
                const Icon = categoryIcons[category] || WrenchScrewdriverIcon;
                const label = categoryLabels[category] || category;
                const isExpanded = expandedCategories[category];

                return (
                  <div key={category}>
                    <button
                      onClick={() => toggleCategory(category)}
                      className="w-full text-sm font-semibold text-zinc-900 dark:text-zinc-100 mb-3 flex items-center justify-between hover:text-amber-800 dark:hover:text-amber-200 transition-colors"
                    >
                      <div className="flex items-center gap-2">
                        <Icon className="h-4 w-4" />
                        {label}
                        <span className="text-xs text-zinc-500 dark:text-zinc-400 font-normal">
                          ({categoryTools.length})
                        </span>
                      </div>
                      {isExpanded ? (
                        <ChevronDownIcon className="h-4 w-4" />
                      ) : (
                        <ChevronRightIcon className="h-4 w-4" />
                      )}
                    </button>
                    {isExpanded && (
                      <div className="space-y-1.5 mb-6">
                        {categoryTools.map((tool) => (
                          <div
                            key={tool.name}
                            className="p-2.5 bg-zinc-50 dark:bg-zinc-800/50 rounded-lg hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-colors"
                          >
                            <div className="font-mono text-xs text-zinc-900 dark:text-zinc-100">
                              {tool.name}
                            </div>
                            <div className="text-xs text-zinc-600 dark:text-zinc-400 mt-0.5">
                              {tool.description}
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </>
  );
}
