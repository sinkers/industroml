'use client';

import React, { useState, useMemo } from 'react';
import { SimpleTreeNode } from './SimpleTreeNode';
import { DomainFilter } from './DomainFilter';
import { TreeNode as TreeNodeType, Domain, IndustroMLDocument } from '@/types/industroml';
import { buildTreeStructure, filterTreeByDomain } from '@/lib/industroml';

interface TreeViewProps {
  document: IndustroMLDocument;
  onAddChild?: (parentId: string, type: 'container' | 'asset') => void;
  onEdit?: (id: string) => void;
  onClone?: (id: string) => void;
  onDelete?: (id: string) => void;
  selectedId?: string;
  onSelect?: (id: string) => void;
}

export function TreeView({
  document,
  onAddChild,
  onEdit,
  onClone,
  onDelete,
  selectedId,
  onSelect
}: TreeViewProps) {
  const [selectedDomain, setSelectedDomain] = useState<Domain | undefined>();

  // Build and filter tree structure
  const treeData = useMemo(() => {
    console.log('Building tree with containers:', document.containers);
    console.log('Building tree with assets:', document.assets);
    const tree = buildTreeStructure(document.containers, document.assets);
    console.log('Built tree:', tree);
    const result = selectedDomain ? filterTreeByDomain(tree, selectedDomain) : tree;
    console.log('Final tree after filtering:', result);
    return result;
  }, [document.containers, document.assets, selectedDomain]);

  // Count assets by domain
  const domainCounts = useMemo(() => {
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
  }, [document.assets]);

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex-shrink-0 p-4 border-b bg-white">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h1 className="text-xl font-bold text-black">
              {document.meta.site_name || 'IndustroML Site'}
            </h1>
            <p className="text-sm text-black">
              {document.containers.length} containers, {document.assets.length} assets
            </p>
          </div>
        </div>

        {/* Domain filter */}
        <DomainFilter
          selectedDomain={selectedDomain}
          onDomainChange={setSelectedDomain}
          domainCounts={domainCounts}
        />
      </div>

      {/* Tree content */}
      <div className="flex-1 overflow-y-auto p-4">
        {treeData.length === 0 ? (
          <div className="text-center text-black py-8">
            <p>No items match the current filter</p>
          </div>
        ) : (
          <div className="space-y-1">
            {treeData.map((node) => (
              <SimpleTreeNode
                key={node.id}
                node={node}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}