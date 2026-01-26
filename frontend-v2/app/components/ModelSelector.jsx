import React, { useState, useEffect } from 'react';
import { Cpu, Check } from 'lucide-react';
import { Dropdown, DropdownButton, DropdownItem, DropdownMenu } from "./catalyst/dropdown";

export default function ModelSelector({ authToken, compact = false }) {
  const [models, setModels] = useState([]);
  const [selectedModel, setSelectedModel] = useState('claude-haiku-4.5');
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const fetchModels = async () => {
      try {
        const modelsRes = await fetch('/api/models');
        const modelsData = await modelsRes.json();
        setModels(modelsData.models || []);

        if (authToken) {
          const prefRes = await fetch('/api/user/model-preference', {
            headers: { Authorization: `Bearer ${authToken}` }
          });
          const prefData = await prefRes.json();
          setSelectedModel(prefData.preferred_model || 'claude-haiku-4.5');
        }
      } catch (err) {
        console.error('Failed to fetch models:', err);
      } finally {
        setIsLoading(false);
      }
    };

    fetchModels();
  }, [authToken]);

  const handleModelChange = async (modelId) => {
    try {
      const res = await fetch('/api/user/model-preference', {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${authToken}`
        },
        body: JSON.stringify({ preferred_model: modelId })
      });

      if (res.ok) {
        setSelectedModel(modelId);
      }
    } catch (err) {
      console.error('Failed to update model:', err);
    }
  };

  const selectedModelData = models.find(m => m.id === selectedModel);

  if (isLoading) {
    return (
      <div className="text-xs text-zinc-500 dark:text-zinc-400">
        Loading...
      </div>
    );
  }

  if (compact) {
    // Compact dropdown for chat interface using Catalyst
    return (
      <Dropdown>
        <DropdownButton
          variant="plain"
          className="flex items-center gap-2 text-xs hover:bg-zinc-100 dark:hover:bg-zinc-800 px-3 py-1.5 rounded-lg transition-colors"
        >
          <Cpu className="w-3.5 h-3.5 text-zinc-500 dark:text-zinc-400" />
          <span className="text-zinc-700 dark:text-zinc-300 font-medium">
            {selectedModelData?.name || 'Select Model'}
          </span>
        </DropdownButton>
        <DropdownMenu className="w-80 max-h-1/2 overflow-y-auto" anchor="bottom end">
          <div className="px-3 py-2 text-xs font-semibold text-zinc-500 dark:text-zinc-400 uppercase tracking-wide border border-zinc-200 dark:border-zinc-700 p-2 mb-2 bg-zinc-100 dark:bg-zinc-900">
            Select Model
          </div>
          {models.map((model) => {
            const isSelected = selectedModel === model.id;
            return (
              <DropdownItem
                outline
                variant="outline"
                key={model.id}
                onClick={() => handleModelChange(model.id)}
              >
                <div className="flex items-start justify-between w-full max-w-64
                bg-zinc-50 dark:bg-zinc-800 hover:bg-zinc-100 dark:hover:bg-zinc-700 backdrop-blur-sm border-b border-zinc-200 dark:border-zinc-700 px-2 hover:text-zinc-600 dark:hover:text-zinc-400
                " title={model.description}>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className={`text-sm font-medium truncate ${isSelected
                        ? 'text-blue-900 dark:text-blue-100'
                        : 'text-zinc-900 dark:text-zinc-100'
                        }`}>
                        {model.name}
                      </span>
                      {isSelected && (
                        <Check className="w-4 h-4 text-blue-600 dark:text-blue-400 flex-shrink-0" />
                      )}
                    </div>
                    <div className="flex items-center gap-2 mt-1 text-xs text-zinc-500 dark:text-zinc-500">
                      <span>{model.cost_input}/{model.cost_output}</span>
                      <span>•</span>
                      <span>{(model.context_window / 1000).toFixed(0)}K ctx</span>
                      <span>•</span>
                      <span className="capitalize">{model.speed}</span>
                    </div>
                  </div>
                </div>
              </DropdownItem>
            );
          })}
        </DropdownMenu>
      </Dropdown>
    );
  }

  // Full version (not used in compact mode)
  return null;
}
