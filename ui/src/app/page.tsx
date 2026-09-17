'use client';

import React, { useState, useEffect, useMemo } from 'react';
import { IndustroMLDocument, Catalog, Domain, Container, Asset, ContainerFormData, AssetFormData } from '@/types/industroml';
import { loadSampleData, loadCatalog } from '@/lib/data-loader';
import { buildTreeStructure, filterTreeByDomain, generateId, cloneAsset, cloneContainer, getExistingIds } from '@/lib/industroml';
import { TreeNode } from '@/components/TreeNode';
import { DomainFilter } from '@/components/DomainFilter';
import { ContainerForm } from '@/components/ContainerForm';
import { AssetForm } from '@/components/AssetForm';
import { FileManager } from '@/components/FileManager';

export default function Home() {
  const [document, setDocument] = useState<IndustroMLDocument | null>(null);
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedDomain, setSelectedDomain] = useState<Domain | undefined>();
  const [selectedNodeId, setSelectedNodeId] = useState<string | undefined>();
  
  // Modal states
  const [showContainerForm, setShowContainerForm] = useState(false);
  const [showAssetForm, setShowAssetForm] = useState(false);
  const [editingContainer, setEditingContainer] = useState<Container | null>(null);
  const [editingAsset, setEditingAsset] = useState<Asset | null>(null);
  const [addToParentId, setAddToParentId] = useState<string | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);

  useEffect(() => {
    const loadData = async () => {
      try {
        setLoading(true);
        const [docData, catalogData] = await Promise.all([
          loadSampleData(),
          loadCatalog()
        ]);
        setDocument(docData);
        setCatalog(catalogData);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load data');
      } finally {
        setLoading(false);
      }
    };

    loadData();
  }, []);

  const treeData = useMemo(() => {
    if (!document) return [];
    const tree = buildTreeStructure(document.containers, document.assets);
    return selectedDomain ? filterTreeByDomain(tree, selectedDomain) : tree;
  }, [document, selectedDomain]);

  const domainCounts = useMemo(() => {
    if (!document) {
      return {
        electrical: 0,
        mechanical: 0,
        data: 0,
        control: 0,
        safety: 0,
      };
    }
    
    const counts = {
      electrical: 0,
      mechanical: 0,
      data: 0,
      control: 0,
      safety: 0,
    };
    
    document.assets.forEach(asset => {
      counts[asset.domain]++;
    });
    
    return counts;
  }, [document]);

  // Handler functions
  const handleAddChild = (parentId: string, type: 'container' | 'asset') => {
    setAddToParentId(parentId);
    if (type === 'container') {
      setEditingContainer(null);
      setShowContainerForm(true);
    } else {
      setEditingAsset(null);
      setShowAssetForm(true);
    }
  };

  const handleEdit = (id: string) => {
    if (!document) return;
    
    // Find if it's a container or asset
    const container = document.containers.find(c => c.id === id);
    if (container) {
      setEditingContainer(container);
      setAddToParentId(null);
      setShowContainerForm(true);
    } else {
      const asset = document.assets.find(a => a.id === id);
      if (asset) {
        setEditingAsset(asset);
        setAddToParentId(null);
        setShowAssetForm(true);
      }
    }
  };

  const handleClone = (id: string) => {
    if (!document) return;
    
    const existingIds = getExistingIds(document);
    
    // Find if it's a container or asset and clone it
    const container = document.containers.find(c => c.id === id);
    if (container) {
      const newId = generateId('C', existingIds);
      const clonedContainer = cloneContainer(container, newId);
      
      setDocument(prev => prev ? {
        ...prev,
        containers: [...prev.containers, clonedContainer]
      } : null);
    } else {
      const asset = document.assets.find(a => a.id === id);
      if (asset) {
        const newId = generateId('A', existingIds);
        const clonedAsset = cloneAsset(asset, newId);
        
        setDocument(prev => prev ? {
          ...prev,
          assets: [...prev.assets, clonedAsset]
        } : null);
      }
    }
  };

  const handleDelete = (id: string) => {
    if (!document) return;
    
    // Remove from containers or assets
    const isContainer = document.containers.some(c => c.id === id);
    
    if (isContainer) {
      setDocument(prev => prev ? {
        ...prev,
        containers: prev.containers.filter(c => c.id !== id),
        // Also remove any assets that were in this container
        assets: prev.assets.filter(a => a.container !== id)
      } : null);
    } else {
      setDocument(prev => prev ? {
        ...prev,
        assets: prev.assets.filter(a => a.id !== id)
      } : null);
    }
  };

  const handleSaveContainer = (containerData: ContainerFormData) => {
    if (!document) return;
    
    if (editingContainer) {
      // Update existing container
      setDocument(prev => prev ? {
        ...prev,
        containers: prev.containers.map(c => 
          c.id === editingContainer.id 
            ? { ...containerData }
            : c
        )
      } : null);
    } else {
      // Add new container - form includes id from user input
      const newContainer: Container = {
        ...containerData,
        parent: addToParentId || containerData.parent
      };
      
      setDocument(prev => prev ? {
        ...prev,
        containers: [...prev.containers, newContainer]
      } : null);
    }
    
    setShowContainerForm(false);
    setEditingContainer(null);
    setAddToParentId(null);
  };

  const handleSaveAsset = (assetData: AssetFormData) => {
    if (!document) return;
    
    if (editingAsset) {
      // Update existing asset
      setDocument(prev => prev ? {
        ...prev,
        assets: prev.assets.map(a => 
          a.id === editingAsset.id 
            ? { ...assetData }
            : a
        )
      } : null);
    } else {
      // Add new asset - form includes id from user input
      const newAsset: Asset = {
        ...assetData,
        container: addToParentId || assetData.container
      };
      
      setDocument(prev => prev ? {
        ...prev,
        assets: [...prev.assets, newAsset]
      } : null);
    }
    
    setShowAssetForm(false);
    setEditingAsset(null);
    setAddToParentId(null);
  };

  // File management handlers
  const handleDocumentLoad = (newDocument: IndustroMLDocument) => {
    setDocument(newDocument);
    setFileError(null);
    // Clear any open modals
    setShowContainerForm(false);
    setShowAssetForm(false);
    setSelectedNodeId(undefined);
  };

  const handleFileError = (errorMessage: string) => {
    setFileError(errorMessage);
    // Clear error after 5 seconds
    setTimeout(() => setFileError(null), 5000);
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-black">Loading IndustroML data...</p>
        </div>
      </div>
    );
  }

  if (error || !document || !catalog) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center text-red-600">
          <h1 className="text-xl font-bold mb-2">Error</h1>
          <p>{error || 'Failed to load application data'}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="p-4 bg-white border-b">
        <div className="flex justify-between items-start mb-4">
          <div>
            <h1 className="text-2xl font-bold text-black">IndustroML UI - {document.meta.site_name}</h1>
            <p className="text-black mb-4">
              {document.containers.length} containers, {document.assets.length} assets
            </p>
          </div>
          <FileManager
            document={document}
            onDocumentLoad={handleDocumentLoad}
            onError={handleFileError}
          />
        </div>

        {/* File error message */}
        {fileError && (
          <div className="mb-4 p-3 bg-red-100 border border-red-300 text-red-700 rounded-lg text-sm">
            {fileError}
          </div>
        )}

        <DomainFilter
          selectedDomain={selectedDomain}
          onDomainChange={setSelectedDomain}
          domainCounts={domainCounts}
        />
      </div>
      
      <div className="p-4">
        <div className="bg-white rounded-lg shadow p-4">
          <h2 className="text-lg font-semibold mb-4 text-black">Asset Hierarchy</h2>
          {treeData.length === 0 ? (
            <div className="text-center text-black py-8">
              <p>No items match the current filter</p>
            </div>
          ) : (
            <div className="space-y-1">
              {treeData.map(node => (
                <TreeNode 
                  key={node.id} 
                  node={node}
                  onAddChild={handleAddChild}
                  onEdit={handleEdit}
                  onClone={handleClone}
                  onDelete={handleDelete}
                  selectedId={selectedNodeId}
                  onSelect={setSelectedNodeId}
                />
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Info Panel */}
      {selectedNodeId && (
        <div className="fixed top-4 right-4 w-80 bg-white rounded-lg shadow-lg p-4 border z-40">
          <h3 className="text-lg font-semibold mb-3 text-black">Object Properties</h3>
          {(() => {
            const container = document?.containers.find(c => c.id === selectedNodeId);
            const asset = document?.assets.find(a => a.id === selectedNodeId);
            const item = container || asset;
            
            if (!item) return null;
            
            return (
              <div className="space-y-2 text-sm">
                <div><strong className="text-black">ID:</strong> <span className="text-black">{item.id}</span></div>
                <div><strong className="text-black">Name:</strong> <span className="text-black">{item.name}</span></div>
                <div><strong className="text-black">Type:</strong> <span className="text-black">{container ? 'Container' : 'Asset'}</span></div>
                
                {container && (
                  <>
                    <div><strong className="text-black">Container Type:</strong> <span className="text-black">{container.type}</span></div>
                    {container.parent && (
                      <div><strong className="text-black">Parent:</strong> <span className="text-black">{container.parent}</span></div>
                    )}
                  </>
                )}
                
                {asset && (
                  <>
                    <div><strong className="text-black">Domain:</strong> <span className="text-black">{asset.domain}</span></div>
                    <div><strong className="text-black">Kind:</strong> <span className="text-black">{asset.kind}</span></div>
                    <div><strong className="text-black">Container:</strong> <span className="text-black">{asset.container}</span></div>
                    {asset.labels && asset.labels.length > 0 && (
                      <div><strong className="text-black">Labels:</strong> <span className="text-black">{asset.labels.join(', ')}</span></div>
                    )}
                  </>
                )}
                
                {item.attributes && Object.keys(item.attributes).length > 0 && (
                  <>
                    <div className="mt-3 pt-3 border-t">
                      <strong className="text-black">Attributes:</strong>
                    </div>
                    {Object.entries(item.attributes).map(([key, value]) => (
                      <div key={key} className="ml-2">
                        <span className="text-black">{key}:</span> <span className="text-black">{String(value)}</span>
                      </div>
                    ))}
                  </>
                )}
                
                <button
                  onClick={() => setSelectedNodeId(undefined)}
                  className="mt-3 px-3 py-1 bg-gray-100 text-black rounded hover:bg-gray-200 text-xs"
                >
                  Close
                </button>
              </div>
            );
          })()}
        </div>
      )}

      {/* Container Form Modal */}
      {showContainerForm && catalog && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 w-full max-w-md max-h-[90vh] overflow-y-auto">
            <h2 className="text-lg font-semibold mb-4 text-black">
              {editingContainer ? 'Edit Container' : 'Add Container'}
            </h2>
            <ContainerForm
              container={editingContainer}
              containers={document.containers}
              onSave={handleSaveContainer}
              onCancel={() => {
                setShowContainerForm(false);
                setEditingContainer(null);
                setAddToParentId(null);
              }}
              existingIds={getExistingIds(document)}
              parentId={addToParentId || undefined}
            />
          </div>
        </div>
      )}

      {/* Asset Form Modal */}
      {showAssetForm && catalog && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 w-full max-w-md max-h-[90vh] overflow-y-auto">
            <h2 className="text-lg font-semibold mb-4 text-black">
              {editingAsset ? 'Edit Asset' : 'Add Asset'}
            </h2>
            <AssetForm
              asset={editingAsset}
              containers={document.containers}
              catalog={catalog}
              onSave={handleSaveAsset}
              onCancel={() => {
                setShowAssetForm(false);
                setEditingAsset(null);
                setAddToParentId(null);
              }}
              existingIds={getExistingIds(document)}
            />
          </div>
        </div>
      )}
    </div>
  );
}
