import React, { useState, useRef } from 'react';
import {
  PhotoIcon,
  SparklesIcon,
  ArrowUpTrayIcon,
  RectangleStackIcon,
  ChevronDownIcon,
  ChevronUpIcon,
} from '@heroicons/react/20/solid';
import { Loader2 } from 'lucide-react';

export default function HeroSectionEditor({
  heroImageUrl,
  heroTitle,
  heroDescription,
  onHeroTitleChange,
  onHeroDescriptionChange,
  onRegenerateImage,
  onUploadImage,
  onBrowseImages,
  saving,
  uploadingFile,
}) {
  const [expanded, setExpanded] = useState(true);
  const [selectedModel, setSelectedModel] = useState('gpt5-image-mini');
  const [promptMode, setPromptMode] = useState('contextual');
  const [selectedTemplate, setSelectedTemplate] = useState('home_barista');
  const [customPrompt, setCustomPrompt] = useState('');
  const fileInputRef = useRef(null);

  const handleRegenerate = () => {
    onRegenerateImage(
      selectedTemplate,
      selectedModel,
      promptMode === 'contextual' ? heroTitle : null,
      promptMode === 'contextual' ? heroDescription : null,
      promptMode === 'custom' ? customPrompt : null
    );
  };

  const handleFileUpload = (event) => {
    const file = event.target.files?.[0];
    if (file) {
      onUploadImage(file);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">
            Hero Section
          </h3>
          <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-0.5">
            Configure hero image, title, and description
          </p>
        </div>
        <button
          onClick={() => setExpanded(!expanded)}
          className="p-1 hover:bg-zinc-100 dark:hover:bg-zinc-800 rounded transition-colors"
          aria-label={expanded ? 'Collapse section' : 'Expand section'}
        >
          {expanded ? (
            <ChevronUpIcon className="h-5 w-5 text-zinc-500" />
          ) : (
            <ChevronDownIcon className="h-5 w-5 text-zinc-500" />
          )}
        </button>
      </div>

      {/* Content */}
      {expanded && (
        <div className="space-y-4 pl-4 border-l-2 border-zinc-200 dark:border-zinc-800">
          {/* Hero Image Preview */}
          <div>
            <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-2">
              Hero Image
            </label>
            <div className="relative h-48 bg-zinc-100 dark:bg-zinc-800 rounded-lg overflow-hidden mb-3">
              {heroImageUrl ? (
                <img
                  src={heroImageUrl}
                  alt="Hero preview"
                  className="w-full h-full object-cover"
                />
              ) : (
                <div className="w-full h-full flex items-center justify-center">
                  <PhotoIcon className="h-16 w-16 text-zinc-300 dark:text-zinc-600" />
                </div>
              )}
            </div>

            {/* AI Generation Controls */}
            <div className="space-y-3 mb-3">
              {/* Model Selector */}
              <div>
                <label className="block text-xs font-medium text-zinc-600 dark:text-zinc-400 mb-1">
                  AI Model
                </label>
                <select
                  value={selectedModel}
                  onChange={(e) => setSelectedModel(e.target.value)}
                  className="w-full px-3 py-2 bg-white dark:bg-zinc-800 border border-zinc-300 dark:border-zinc-700 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-purple-500"
                >
                  <option value="gpt5-image-mini">GPT-5-image-mini (OpenAI)</option>
                  <option value="gemini">Gemini 2.5 Flash Image (Google)</option>
                </select>
              </div>

              {/* Prompt Mode Selector */}
              <div>
                <label className="block text-xs font-medium text-zinc-600 dark:text-zinc-400 mb-1">
                  Prompt Mode
                </label>
                <select
                  value={promptMode}
                  onChange={(e) => setPromptMode(e.target.value)}
                  className="w-full px-3 py-2 bg-white dark:bg-zinc-800 border border-zinc-300 dark:border-zinc-700 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-purple-500"
                >
                  <option value="contextual">Contextual (from hero text)</option>
                  <option value="template">Template</option>
                  <option value="custom">Custom Prompt</option>
                </select>
              </div>

              {/* Template Selector */}
              {promptMode === 'template' && (
                <div>
                  <label className="block text-xs font-medium text-zinc-600 dark:text-zinc-400 mb-1">
                    Template
                  </label>
                  <select
                    value={selectedTemplate}
                    onChange={(e) => setSelectedTemplate(e.target.value)}
                    className="w-full px-3 py-2 bg-white dark:bg-zinc-800 border border-zinc-300 dark:border-zinc-700 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-purple-500"
                  >
                    <option value="home_barista">Home Barista</option>
                    <option value="espresso_machines">Espresso Machines</option>
                    <option value="grinders">Grinders</option>
                    <option value="single_dose">Single Dose</option>
                    <option value="commercial">Commercial</option>
                    <option value="la_marzocco">La Marzocco</option>
                    <option value="accessories">Accessories</option>
                  </select>
                </div>
              )}

              {/* Custom Prompt Input */}
              {promptMode === 'custom' && (
                <div>
                  <label className="block text-xs font-medium text-zinc-600 dark:text-zinc-400 mb-1">
                    Custom Prompt
                  </label>
                  <textarea
                    value={customPrompt}
                    onChange={(e) => setCustomPrompt(e.target.value)}
                    rows={3}
                    className="w-full px-3 py-2 bg-white dark:bg-zinc-800 border border-zinc-300 dark:border-zinc-700 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-purple-500 resize-none"
                    placeholder="Enter custom prompt for image generation..."
                  />
                </div>
              )}
            </div>

            {/* Regenerate Button */}
            <button
              onClick={handleRegenerate}
              disabled={saving || uploadingFile || (promptMode === 'custom' && !customPrompt.trim())}
              className="w-full py-2 px-4 bg-purple-600 hover:bg-purple-700 disabled:bg-purple-400 text-white rounded-lg font-medium text-sm transition-colors flex items-center justify-center gap-2"
            >
              {saving && !uploadingFile ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Generating...
                </>
              ) : (
                <>
                  <SparklesIcon className="h-4 w-4" />
                  Regenerate with AI
                </>
              )}
            </button>

            {/* Help Text */}
            <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-2 mb-4">
              {promptMode === 'contextual' ? (
                <>
                  {selectedModel === 'gpt5-image-mini'
                    ? 'Uses OpenAI GPT-5-image-mini to generate contextually relevant hero images based on your title and description'
                    : 'Uses Google Gemini 2.5 Flash Image to generate contextually relevant hero images based on your title and description'
                  }
                </>
              ) : promptMode === 'template' ? (
                <>Generates hero image using the <strong>{selectedTemplate.replace(/_/g, ' ')}</strong> template</>
              ) : (
                <>Generates hero image using your custom prompt</>
              )}
            </p>

            {/* Upload and Browse Buttons */}
            <div className="grid grid-cols-2 gap-3">
              <input
                ref={fileInputRef}
                type="file"
                accept="image/*"
                onChange={handleFileUpload}
                className="hidden"
              />

              <button
                onClick={() => fileInputRef.current?.click()}
                disabled={saving || uploadingFile}
                className="py-2 px-4 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-400 text-white rounded-lg font-medium text-sm transition-colors flex items-center justify-center gap-2"
              >
                {uploadingFile ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Uploading...
                  </>
                ) : (
                  <>
                    <ArrowUpTrayIcon className="h-4 w-4" />
                    Upload Image
                  </>
                )}
              </button>

              <button
                onClick={onBrowseImages}
                disabled={saving || uploadingFile}
                className="py-2 px-4 bg-emerald-600 hover:bg-emerald-700 disabled:bg-emerald-400 text-white rounded-lg font-medium text-sm transition-colors flex items-center justify-center gap-2"
              >
                <RectangleStackIcon className="h-4 w-4" />
                Browse CDN
              </button>
            </div>
          </div>

          {/* Hero Title */}
          <div>
            <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-2">
              Hero Title
            </label>
            <input
              type="text"
              value={heroTitle}
              onChange={(e) => onHeroTitleChange(e.target.value)}
              className="w-full px-4 py-2 bg-white dark:bg-zinc-800 border border-zinc-300 dark:border-zinc-700 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-amber-500"
              placeholder="Enter hero title..."
            />
          </div>

          {/* Hero Description */}
          <div>
            <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-2">
              Hero Description
            </label>
            <textarea
              value={heroDescription}
              onChange={(e) => onHeroDescriptionChange(e.target.value)}
              rows={4}
              className="w-full px-4 py-2 bg-white dark:bg-zinc-800 border border-zinc-300 dark:border-zinc-700 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-amber-500 resize-none"
              placeholder="Enter hero description..."
            />
          </div>
        </div>
      )}
    </div>
  );
}
