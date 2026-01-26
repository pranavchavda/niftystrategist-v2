import React, { useState } from 'react';
import { Upload, X, CheckCircle, AlertCircle, Loader2 } from 'lucide-react';
import { Button } from './catalyst/button';

export default function NotesImportDialog({ authToken, onClose }) {
  const [vaultId, setVaultId] = useState('');
  const [selectedFile, setSelectedFile] = useState(null);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [uploadResult, setUploadResult] = useState(null);
  const [uploadError, setUploadError] = useState(null);

  const handleFileSelect = (event) => {
    const file = event.target.files[0];
    if (file) {
      // Validate file type
      if (!file.name.endsWith('.zip')) {
        alert('Please select a .zip file');
        event.target.value = '';
        return;
      }
      setSelectedFile(file);
      setUploadResult(null);
      setUploadError(null);
    }
  };

  const handleUpload = async () => {
    if (!selectedFile) {
      alert('Please select a file first');
      return;
    }

    if (!authToken) {
      alert('Not authenticated');
      return;
    }

    setIsUploading(true);
    setUploadProgress(0);
    setUploadResult(null);
    setUploadError(null);

    try {
      // Create FormData
      const formData = new FormData();
      formData.append('file', selectedFile);
      if (vaultId.trim()) {
        formData.append('vault_id', vaultId.trim());
      }

      // Upload with progress simulation
      const progressInterval = setInterval(() => {
        setUploadProgress((prev) => {
          if (prev >= 90) return prev;
          return prev + 10;
        });
      }, 200);

      const response = await fetch('/api/notes/import-obsidian', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${authToken}`
        },
        body: formData
      });

      clearInterval(progressInterval);
      setUploadProgress(100);

      if (response.ok) {
        const result = await response.json();
        setUploadResult(result);
        setUploadError(null);
      } else {
        const error = await response.json();
        setUploadError(error.detail || 'Upload failed');
        setUploadResult(null);
      }
    } catch (error) {
      console.error('Upload error:', error);
      setUploadError('Network error: ' + error.message);
      setUploadResult(null);
    } finally {
      setIsUploading(false);
      setUploadProgress(0);
    }
  };

  const handleClose = () => {
    if (isUploading) {
      if (!confirm('Upload is in progress. Are you sure you want to close?')) {
        return;
      }
    }
    onClose();
  };

  const handleReset = () => {
    setSelectedFile(null);
    setVaultId('');
    setUploadResult(null);
    setUploadError(null);
    setUploadProgress(0);
  };

  return (
    <div className="fixed inset-0 bg-black/50 dark:bg-black/70 flex items-center justify-center p-4 z-50">
      <div className="bg-white dark:bg-zinc-900 rounded-xl border border-zinc-200 dark:border-zinc-800 p-6 max-w-2xl w-full shadow-xl">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-2xl font-bold text-zinc-900 dark:text-zinc-100 flex items-center gap-2">
            <Upload className="w-6 h-6 text-zinc-600 dark:text-zinc-400" />
            Import Obsidian Vault
          </h2>
          <button
            onClick={handleClose}
            disabled={isUploading}
            className="p-2 rounded hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="space-y-4">
          {/* Instructions */}
          <div className="p-4 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg">
            <p className="text-sm text-blue-900 dark:text-blue-100 mb-2">
              <strong>How to import:</strong>
            </p>
            <ol className="text-sm text-blue-800 dark:text-blue-200 space-y-1 list-decimal list-inside">
              <li>Export your Obsidian vault as a .zip file</li>
              <li>Select the .zip file below</li>
              <li>Optionally provide a Vault ID (auto-generated if empty)</li>
              <li>Click "Upload & Import" to start the import</li>
            </ol>
          </div>

          {/* Vault ID Input */}
          <div>
            <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-2">
              Vault ID (optional)
            </label>
            <input
              type="text"
              value={vaultId}
              onChange={(e) => setVaultId(e.target.value)}
              placeholder="e.g., my-vault (auto-generated if empty)"
              disabled={isUploading || uploadResult !== null}
              className="w-full px-4 py-2 rounded-lg border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100 focus:outline-none focus:ring-2 focus:ring-zinc-400 disabled:opacity-50"
            />
            <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-1">
              Leave empty to auto-generate a unique ID based on the zip filename
            </p>
          </div>

          {/* File Input */}
          <div>
            <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-2">
              Select Obsidian Vault (.zip)
            </label>
            <div className="relative">
              <input
                type="file"
                accept=".zip"
                onChange={handleFileSelect}
                disabled={isUploading || uploadResult !== null}
                className="w-full px-4 py-2 rounded-lg border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100 focus:outline-none focus:ring-2 focus:ring-zinc-400 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-zinc-100 file:text-zinc-700 hover:file:bg-zinc-200 dark:file:bg-zinc-700 dark:file:text-zinc-300 dark:hover:file:bg-zinc-600 disabled:opacity-50 disabled:cursor-not-allowed"
              />
            </div>
            {selectedFile && (
              <p className="text-sm text-zinc-600 dark:text-zinc-400 mt-2">
                Selected: <span className="font-medium">{selectedFile.name}</span> (
                {(selectedFile.size / 1024 / 1024).toFixed(2)} MB)
              </p>
            )}
          </div>

          {/* Progress Bar */}
          {isUploading && (
            <div className="space-y-2">
              <div className="flex items-center justify-between text-sm">
                <span className="text-zinc-700 dark:text-zinc-300">Uploading and processing...</span>
                <span className="text-zinc-600 dark:text-zinc-400">{uploadProgress}%</span>
              </div>
              <div className="w-full bg-zinc-200 dark:bg-zinc-700 rounded-full h-2 overflow-hidden">
                <div
                  className="bg-blue-600 dark:bg-blue-500 h-full transition-all duration-300 ease-out"
                  style={{ width: `${uploadProgress}%` }}
                />
              </div>
            </div>
          )}

          {/* Upload Result - Success */}
          {uploadResult && (
            <div className="p-4 bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg">
              <div className="flex items-start gap-3">
                <CheckCircle className="w-5 h-5 text-green-600 dark:text-green-400 flex-shrink-0 mt-0.5" />
                <div className="flex-1">
                  <p className="font-semibold text-green-900 dark:text-green-100 mb-2">
                    Import Successful!
                  </p>
                  <div className="space-y-1 text-sm text-green-800 dark:text-green-200">
                    <p>
                      <span className="font-medium">Vault ID:</span> {uploadResult.vault_id}
                    </p>
                    <p>
                      <span className="font-medium">Notes Imported:</span> {uploadResult.imported_count} / {uploadResult.total_files}
                    </p>
                    {uploadResult.skipped_count > 0 && (
                      <p className="text-amber-700 dark:text-amber-300">
                        <span className="font-medium">Skipped:</span> {uploadResult.skipped_count} (already exist)
                      </p>
                    )}
                  </div>
                  {uploadResult.errors && uploadResult.errors.length > 0 && (
                    <div className="mt-3 p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded">
                      <p className="text-sm font-medium text-red-900 dark:text-red-100 mb-1">
                        Errors ({uploadResult.errors.length}):
                      </p>
                      <ul className="text-xs text-red-800 dark:text-red-200 space-y-1 list-disc list-inside max-h-32 overflow-y-auto">
                        {uploadResult.errors.map((error, idx) => (
                          <li key={idx}>{error}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* Upload Error */}
          {uploadError && (
            <div className="p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg">
              <div className="flex items-start gap-3">
                <AlertCircle className="w-5 h-5 text-red-600 dark:text-red-400 flex-shrink-0 mt-0.5" />
                <div className="flex-1">
                  <p className="font-semibold text-red-900 dark:text-red-100 mb-1">
                    Upload Failed
                  </p>
                  <p className="text-sm text-red-800 dark:text-red-200">
                    {uploadError}
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* Action Buttons */}
          <div className="flex items-center gap-2 pt-4">
            {!uploadResult && !uploadError ? (
              <>
                <Button
                  onClick={handleUpload}
                  disabled={!selectedFile || isUploading}
                  className="bg-zinc-900 dark:bg-zinc-100 text-white dark:text-zinc-900 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {isUploading ? (
                    <>
                      <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                      Uploading...
                    </>
                  ) : (
                    <>
                      <Upload className="w-4 h-4 mr-2" />
                      Upload & Import
                    </>
                  )}
                </Button>
                <Button
                  onClick={handleClose}
                  disabled={isUploading}
                  className="bg-zinc-200 dark:bg-zinc-700 text-zinc-900 dark:text-zinc-100 disabled:opacity-50"
                >
                  Cancel
                </Button>
              </>
            ) : (
              <>
                <Button
                  onClick={handleReset}
                  className="bg-zinc-900 dark:bg-zinc-100 text-white dark:text-zinc-900"
                >
                  Import Another Vault
                </Button>
                <Button
                  onClick={handleClose}
                  className="bg-zinc-200 dark:bg-zinc-700 text-zinc-900 dark:text-zinc-100"
                >
                  Close
                </Button>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
