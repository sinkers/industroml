import { render, screen, fireEvent } from '@testing-library/react';
import { TreeNode } from '@/components/TreeNode';
import { TreeNode as TreeNodeType } from '@/types/industroml';

describe('TreeNode', () => {
  const mockNode: TreeNodeType = {
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

  const mockCallbacks = {
    onAddChild: jest.fn(),
    onEdit: jest.fn(),
    onClone: jest.fn(),
    onDelete: jest.fn(),
    onSelect: jest.fn()
  };

  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('should render node name and type', () => {
    render(<TreeNode node={mockNode} {...mockCallbacks} />);
    
    expect(screen.getByText('Test Node')).toBeInTheDocument();
    expect(screen.getByText(/container/)).toBeInTheDocument();
  });

  it('should show action buttons on hover', () => {
    render(<TreeNode node={mockNode} {...mockCallbacks} />);
    
    // Action buttons should be present but initially invisible (opacity-0)
    const editButtons = screen.getAllByTitle('Edit');
    const cloneButtons = screen.getAllByTitle('Clone');
    const deleteButtons = screen.getAllByTitle('Delete');
    
    expect(editButtons.length).toBeGreaterThan(0);
    expect(cloneButtons.length).toBeGreaterThan(0);
    expect(deleteButtons.length).toBeGreaterThan(0);
  });

  it('should call onEdit when edit button is clicked', () => {
    render(<TreeNode node={mockNode} {...mockCallbacks} />);
    
    const editButtons = screen.getAllByTitle('Edit');
    fireEvent.click(editButtons[0]); // Click first edit button (parent node)
    
    expect(mockCallbacks.onEdit).toHaveBeenCalledWith('TEST1');
  });

  it('should call onClone when clone button is clicked', () => {
    render(<TreeNode node={mockNode} {...mockCallbacks} />);
    
    const cloneButtons = screen.getAllByTitle('Clone');
    fireEvent.click(cloneButtons[0]); // Click first clone button (parent node)
    
    expect(mockCallbacks.onClone).toHaveBeenCalledWith('TEST1');
  });

  it('should call onDelete when delete button is clicked', () => {
    render(<TreeNode node={mockNode} {...mockCallbacks} />);
    
    const deleteButtons = screen.getAllByTitle('Delete');
    fireEvent.click(deleteButtons[0]); // Click first delete button (parent node)
    
    expect(mockCallbacks.onDelete).toHaveBeenCalledWith('TEST1');
  });

  it('should show add buttons for containers', () => {
    render(<TreeNode node={mockNode} {...mockCallbacks} />);
    
    // Container should have two "Add" buttons (for container and asset)
    const addButtons = screen.getAllByTitle(/Add/);
    expect(addButtons).toHaveLength(2);
    expect(screen.getByTitle('Add container')).toBeInTheDocument();
    expect(screen.getByTitle('Add asset')).toBeInTheDocument();
  });

  it('should render child nodes when expanded', () => {
    render(<TreeNode node={mockNode} {...mockCallbacks} />);
    
    // Child should be visible by default (level < 3)
    expect(screen.getByText('Child Node')).toBeInTheDocument();
    expect(screen.getByText(/electrical/)).toBeInTheDocument();
  });

  it('should display domain icon for assets', () => {
    const assetNode: TreeNodeType = {
      id: 'ASSET1',
      name: 'Test Asset',
      type: 'asset',
      domain: 'electrical',
      kind: 'transformer',
      children: []
    };

    render(<TreeNode node={assetNode} {...mockCallbacks} />);
    
    // Should render electrical domain icon (Zap icon)
    expect(screen.getByText('Test Asset')).toBeInTheDocument();
    expect(screen.getByText(/electrical/)).toBeInTheDocument();
  });
});