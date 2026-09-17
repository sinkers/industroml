import { render, screen, fireEvent } from '@testing-library/react';
import { SimpleTreeNode } from '@/components/SimpleTreeNode';
import { TreeNode } from '@/types/industroml';

describe('SimpleTreeNode', () => {
  const mockNode: TreeNode = {
    id: 'TEST1',
    name: 'Test Node',
    type: 'container',
    children: [
      {
        id: 'CHILD1',
        name: 'Child Node',
        type: 'asset',
        domain: 'electrical',
        kind: 'transformer',
        children: []
      }
    ]
  };

  it('should render node name and type', () => {
    render(<SimpleTreeNode node={mockNode} />);
    
    expect(screen.getByText('Test Node')).toBeInTheDocument();
    expect(screen.getByText(/container/)).toBeInTheDocument();
  });

  it('should show expand icon when node has children', () => {
    render(<SimpleTreeNode node={mockNode} />);
    
    // Check that the chevron icon is rendered
    const chevronIcon = document.querySelector('svg.lucide-chevron-down');
    expect(chevronIcon).toBeInTheDocument();
  });

  it('should expand/collapse when clicked', () => {
    render(<SimpleTreeNode node={mockNode} />);
    
    // Initially expanded (level < 3)
    expect(screen.getByText('Child Node')).toBeInTheDocument();
    
    // Click to collapse - find the clickable div
    const clickableDiv = document.querySelector('.flex-shrink-0.w-4.h-4');
    expect(clickableDiv).toBeInTheDocument();
    
    if (clickableDiv) {
      fireEvent.click(clickableDiv);
      // Child should be hidden after collapse
      expect(screen.queryByText('Child Node')).not.toBeInTheDocument();
    }
  });

  it('should render child nodes when expanded', () => {
    render(<SimpleTreeNode node={mockNode} />);
    
    expect(screen.getByText('Child Node')).toBeInTheDocument();
    expect(screen.getByText(/electrical/)).toBeInTheDocument();
  });

  it('should handle nodes without children', () => {
    const leafNode: TreeNode = {
      id: 'LEAF',
      name: 'Leaf Node',
      type: 'asset',
      domain: 'mechanical',
      kind: 'pump',
      children: []
    };

    render(<SimpleTreeNode node={leafNode} />);
    
    expect(screen.getByText('Leaf Node')).toBeInTheDocument();
    expect(screen.getByText(/mechanical/)).toBeInTheDocument();
    
    // Should not show chevron icon for leaf nodes
    const chevronIcon = document.querySelector('svg.lucide-chevron-down');
    expect(chevronIcon).not.toBeInTheDocument();
  });

  it('should apply correct indentation based on level', () => {
    const { container } = render(<SimpleTreeNode node={mockNode} level={2} />);
    
    const nodeDiv = container.querySelector('div[style*="padding-left"]');
    expect(nodeDiv).toBeInTheDocument();
    expect(nodeDiv).toHaveStyle('padding-left: 40px'); // 2 * 16 + 8
  });
});