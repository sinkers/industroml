'use client';

import React, { useState } from 'react';
import { 
  ChevronRight, 
  ChevronDown, 
  Package, 
  Cpu, 
  Zap, 
  Wrench, 
  Network, 
  Shield,
  Plus,
  Copy,
  Edit,
  Trash2
} from 'lucide-react';
import { TreeNode as TreeNodeType, Domain } from '@/types/industroml';
import { getDomainColor } from '@/lib/industroml';
import { cn } from '@/lib/utils';

// Domain icons mapping
const DOMAIN_ICONS = {
  electrical: Zap,
  mechanical: Wrench,
  data: Network,
  control: Cpu,
  safety: Shield,
} as const;

interface TreeNodeProps {
  node: TreeNodeType;
  level?: number;
  onAddChild?: (parentId: string, type: 'container' | 'asset') => void;
  onEdit?: (id: string) => void;
  onClone?: (id: string) => void;
  onDelete?: (id: string) => void;
  selectedId?: string;
  onSelect?: (id: string) => void;
}

export function TreeNode({ 
  node, 
  level = 0, 
  onAddChild,
  onEdit,
  onClone,
  onDelete,
  selectedId,
  onSelect
}: TreeNodeProps) {
  const [isExpanded, setIsExpanded] = useState(level < 3); // Auto-expand first three levels
  const hasChildren = node.children && node.children.length > 0;
  
  const isSelected = selectedId === node.id;
  
  const handleToggle = () => {
    if (hasChildren) {
      setIsExpanded(!isExpanded);
    }
  };

  const handleSelect = () => {
    if (onSelect) {
      onSelect(node.id);
    }
  };

  // Get the appropriate icon component
  const DomainIcon = node.domain ? DOMAIN_ICONS[node.domain] : null;
  const NodeIcon = node.type === 'container' ? Package : DomainIcon;

  return (
    <div className="select-none">
      <div 
        className={cn(
          "flex items-center gap-2 py-1 px-2 rounded-md cursor-pointer group hover:bg-gray-100",
          isSelected && "bg-blue-50 border border-blue-200",
          level > 0 && "ml-4"
        )}
        style={{ paddingLeft: `${level * 16 + 8}px` }}
        onClick={handleSelect}
      >
        {/* Expand/Collapse icon */}
        <div 
          className="flex-shrink-0 w-4 h-4 flex items-center justify-center"
          onClick={(e) => {
            e.stopPropagation();
            handleToggle();
          }}
        >
          {hasChildren && (
            isExpanded ? (
              <ChevronDown className="w-3 h-3 text-gray-500" />
            ) : (
              <ChevronRight className="w-3 h-3 text-gray-500" />
            )
          )}
        </div>

        {/* Node icon */}
        <div className="flex-shrink-0">
          {NodeIcon && (
            <NodeIcon 
              className="w-4 h-4" 
              style={{ 
                color: node.domain ? getDomainColor(node.domain) : '#6b7280' 
              }} 
            />
          )}
        </div>

        {/* Node name and info */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="font-medium text-sm truncate text-black">{node.name}</span>
            {node.kind && (
              <span className="text-xs text-gray-500 bg-gray-100 px-2 py-0.5 rounded">
                {node.kind}
              </span>
            )}
          </div>
          <div className="text-xs text-black">
            {node.type} {node.domain && `• ${node.domain}`}
          </div>
        </div>

        {/* Action buttons - show on hover */}
        <div className="flex-shrink-0 flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
          {node.type === 'container' && (
            <>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  onAddChild?.(node.id, 'container');
                }}
                className="p-1 hover:bg-gray-200 rounded text-gray-500 hover:text-gray-700"
                title="Add container"
              >
                <Plus className="w-3 h-3" />
              </button>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  onAddChild?.(node.id, 'asset');
                }}
                className="p-1 hover:bg-gray-200 rounded text-gray-500 hover:text-gray-700"
                title="Add asset"
              >
                <Plus className="w-3 h-3" />
              </button>
            </>
          )}
          <button
            onClick={(e) => {
              e.stopPropagation();
              onEdit?.(node.id);
            }}
            className="p-1 hover:bg-gray-200 rounded text-gray-500 hover:text-gray-700"
            title="Edit"
          >
            <Edit className="w-3 h-3" />
          </button>
          <button
            onClick={(e) => {
              e.stopPropagation();
              onClone?.(node.id);
            }}
            className="p-1 hover:bg-gray-200 rounded text-gray-500 hover:text-gray-700"
            title="Clone"
          >
            <Copy className="w-3 h-3" />
          </button>
          <button
            onClick={(e) => {
              e.stopPropagation();
              onDelete?.(node.id);
            }}
            className="p-1 hover:bg-gray-200 rounded text-red-500 hover:text-red-700"
            title="Delete"
          >
            <Trash2 className="w-3 h-3" />
          </button>
        </div>
      </div>

      {/* Children */}
      {hasChildren && isExpanded && (
        <div>
          {node.children!.map((child) => (
            <TreeNode
              key={child.id}
              node={child}
              level={level + 1}
              onAddChild={onAddChild}
              onEdit={onEdit}
              onClone={onClone}
              onDelete={onDelete}
              selectedId={selectedId}
              onSelect={onSelect}
            />
          ))}
        </div>
      )}
    </div>
  );
}