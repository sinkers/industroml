'use client';

import React, { useState } from 'react';
import { ChevronRight, ChevronDown } from 'lucide-react';
import { TreeNode as TreeNodeType } from '@/types/industroml';

interface SimpleTreeNodeProps {
  node: TreeNodeType;
  level?: number;
}

export function SimpleTreeNode({ node, level = 0 }: SimpleTreeNodeProps) {
  const [isExpanded, setIsExpanded] = useState(level < 3);
  const hasChildren = node.children && node.children.length > 0;

  const handleToggle = () => {
    if (hasChildren) {
      setIsExpanded(!isExpanded);
    }
  };

  return (
    <div className="select-none">
      <div 
        className="flex items-center gap-2 py-1 px-2 rounded-md cursor-pointer hover:bg-gray-100"
        style={{ paddingLeft: `${level * 16 + 8}px` }}
      >
        {/* Expand/Collapse icon */}
        <div 
          className="flex-shrink-0 w-4 h-4 flex items-center justify-center"
          onClick={handleToggle}
        >
          {hasChildren && (
            isExpanded ? (
              <ChevronDown className="w-3 h-3 text-gray-500" />
            ) : (
              <ChevronRight className="w-3 h-3 text-gray-500" />
            )
          )}
        </div>

        {/* Node name */}
        <div className="flex-1 min-w-0">
          <div className="font-medium text-sm truncate text-black">{node.name}</div>
          <div className="text-xs text-black">
            {node.type} {node.domain && `• ${node.domain}`}
          </div>
        </div>
      </div>

      {/* Children */}
      {hasChildren && isExpanded && (
        <div>
          {node.children!.map((child) => (
            <SimpleTreeNode
              key={child.id}
              node={child}
              level={level + 1}
            />
          ))}
        </div>
      )}
    </div>
  );
}