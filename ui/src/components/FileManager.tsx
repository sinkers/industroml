'use client';

import React, { useRef } from 'react';
import { Upload, Download, FileText } from 'lucide-react';
import { IndustroMLDocument } from '@/types/industroml';
import { loadFromFile, exportToYAML, exportToJSON } from '@/lib/data-loader';

interface FileManagerProps {
  document: IndustroMLDocument | null;
  onDocumentLoad: (document: IndustroMLDocument) => void;
  onError: (error: string) => void;
}

export function FileManager({ document, onDocumentLoad, onError }: FileManagerProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    // Validate file type
    if (!file.name.endsWith('.yml') && !file.name.endsWith('.yaml') && !file.name.endsWith('.json')) {
      onError('Please select a JSON (.json) or YAML (.yml/.yaml) file');
      return;
    }

    try {
      const loadedDocument = await loadFromFile(file);
      onDocumentLoad(loadedDocument);
    } catch (error) {
      onError(error instanceof Error ? error.message : 'Failed to load file');
    }

    // Clear the input
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const handleExportYAML = () => {
    if (!document) {
      onError('No document to export');
      return;
    }

    try {
      const yamlContent = exportToYAML(document);
      const blob = new Blob([yamlContent], { type: 'text/yaml' });
      const url = URL.createObjectURL(blob);
      
      const link = document.createElement('a');
      link.href = url;
      link.download = `${document.meta.site_name.replace(/[^a-zA-Z0-9]/g, '_').toLowerCase()}_config.yml`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      
      URL.revokeObjectURL(url);
    } catch (error) {
      onError(error instanceof Error ? error.message : 'Failed to export file');
    }
  };

  const handleExportJSON = () => {
    if (!document) {
      onError('No document to export');
      return;
    }

    try {
      const jsonContent = exportToJSON(document);
      const blob = new Blob([jsonContent], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      
      const link = document.createElement('a');
      link.href = url;
      link.download = `${document.meta.site_name.replace(/[^a-zA-Z0-9]/g, '_').toLowerCase()}_config.json`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      
      URL.revokeObjectURL(url);
    } catch (error) {
      onError(error instanceof Error ? error.message : 'Failed to export file');
    }
  };

  const triggerFileUpload = () => {
    fileInputRef.current?.click();
  };

  return (
    <div className="flex items-center gap-3">
      {/* Hidden file input */}
      <input
        type="file"
        ref={fileInputRef}
        onChange={handleFileUpload}
        accept=".yml,.yaml,.json"
        className="hidden"
      />

      {/* Load Configuration Button */}
      <button
        onClick={triggerFileUpload}
        className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors text-sm font-medium"
        title="Load JSON or YAML configuration file"
      >
        <Upload className="w-4 h-4" />
        Load Config
      </button>

      {/* Export Configuration Buttons */}
      <button
        onClick={handleExportJSON}
        disabled={!document}
        className="flex items-center gap-2 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors text-sm font-medium"
        title="Export current configuration to JSON"
      >
        <Download className="w-4 h-4" />
        Export JSON
      </button>
      
      <button
        onClick={handleExportYAML}
        disabled={!document}
        className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors text-sm font-medium"
        title="Export current configuration to YAML"
      >
        <Download className="w-4 h-4" />
        Export YAML
      </button>

      {/* Current file indicator */}
      {document && (
        <div className="flex items-center gap-2 px-3 py-2 bg-gray-100 rounded-lg text-sm text-black">
          <FileText className="w-4 h-4" />
          <span>{document.meta.site_name}</span>
        </div>
      )}
    </div>
  );
}