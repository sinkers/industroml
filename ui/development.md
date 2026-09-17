# IndustroML UI - Development Guide

This document provides comprehensive guidance for developing the IndustroML UI application.

## Table of Contents
1. [Getting Started](#getting-started)
2. [Development Workflow](#development-workflow)
3. [Architecture Overview](#architecture-overview)
4. [Testing Strategy](#testing-strategy)
5. [Component Development](#component-development)
6. [Code Quality](#code-quality)
7. [Troubleshooting](#troubleshooting)

## Getting Started

### Prerequisites
- Node.js 18+
- npm or yarn
- TypeScript knowledge
- React 19+ experience

### Installation
```bash
# Clone and navigate to the project
cd ui

# Install dependencies
npm install

# Start development server
npm run dev

# Open browser to http://localhost:3000 or http://localhost:3001 if 3000 is occupied
```

### Environment Setup
The application runs on Next.js 15 with the following key technologies:
- **React 19** with hooks and functional components
- **TypeScript** for type safety
- **Tailwind CSS** for styling
- **Lucide React** for icons
- **React Hook Form** + **Zod** for forms

## Development Workflow

### 1. Feature Development Process
```bash
# 1. Create feature branch (if using git)
git checkout -b feature/my-new-feature

# 2. Start development server
npm run dev

# 3. Run tests in watch mode
npm run test:watch

# 4. Make changes and verify tests pass
# 5. Run full test suite
npm run test

# 6. Check types and linting
npm run lint
npx tsc --noEmit

# 7. Test build
npm run build
```

### 2. Test-Driven Development (TDD)
**ALWAYS** run tests after making changes:

```bash
# Quick test run
npm test

# Watch mode for active development
npm run test:watch

# Coverage report
npm run test:coverage

# CI mode (for production builds)
npm run test:ci
```

### 3. Code Quality Checklist
Before committing any changes, ensure:
- [ ] All tests pass (`npm test`)
- [ ] TypeScript compiles without errors (`npx tsc --noEmit`)
- [ ] ESLint passes (`npm run lint`)
- [ ] Application builds successfully (`npm run build`)
- [ ] Manual testing in browser works
- [ ] Code follows established patterns

## Architecture Overview

### Directory Structure
```
src/
├── app/                    # Next.js App Router
│   ├── globals.css        # Global styles
│   ├── layout.tsx         # Root layout
│   └── page.tsx           # Main application page
├── components/            # Reusable UI components
│   ├── AssetForm.tsx      # Asset creation/editing form
│   ├── ContainerForm.tsx  # Container creation/editing form
│   ├── DomainFilter.tsx   # Domain filtering buttons
│   ├── SimpleTreeNode.tsx # Basic tree node component
│   └── TreeView.tsx       # Main tree view container
├── lib/                   # Business logic and utilities
│   ├── data-loader.ts     # Sample data loading
│   ├── industroml.ts      # Core business logic
│   └── utils.ts           # General utilities
├── types/                 # TypeScript type definitions
│   └── industroml.ts      # IndustroML schema types
└── __tests__/             # Test files (mirrors src structure)
    ├── app/
    ├── components/
    ├── lib/
    └── integration/
```

### Data Flow
1. **Data Loading**: `loadSampleData()` and `loadCatalog()` in `lib/data-loader.ts`
2. **Tree Building**: `buildTreeStructure()` in `lib/industroml.ts`
3. **State Management**: React useState/useEffect in main page
4. **Component Props**: Data flows down via props
5. **User Actions**: Event handlers bubble up via callbacks

### Key Components

#### TreeView (Main Container)
- Manages tree data and filtering
- Handles domain filter state
- Provides callback handlers for child components

#### SimpleTreeNode (Tree Display)
- Renders individual tree nodes
- Handles expand/collapse state
- Displays icons, names, and metadata

#### DomainFilter (Filtering)
- Renders domain filter buttons
- Shows asset counts per domain
- Handles selection state and styling

## Testing Strategy

### Test Types

#### 1. Unit Tests (`src/__tests__/lib/`)
Test individual functions and utilities:
```typescript
// Example: Testing tree building logic
describe('buildTreeStructure', () => {
  it('should build correct hierarchy', () => {
    const tree = buildTreeStructure(containers, assets);
    expect(tree[0].children).toHaveLength(2);
  });
});
```

#### 2. Component Tests (`src/__tests__/components/`)
Test individual React components:
```typescript
// Example: Testing component rendering
describe('SimpleTreeNode', () => {
  it('should render node name', () => {
    render(<SimpleTreeNode node={mockNode} />);
    expect(screen.getByText('Test Node')).toBeInTheDocument();
  });
});
```

#### 3. Integration Tests (`src/__tests__/integration/`)
Test full application workflows:
```typescript
// Example: Testing complete user flow
it('should complete full app flow: load → display → filter', async () => {
  render(<Home />);
  await waitFor(() => {
    expect(screen.getByText('Asset Hierarchy')).toBeInTheDocument();
  });
  // Test filtering, tree expansion, etc.
});
```

#### 4. Page Tests (`src/__tests__/app/`)
Test Next.js pages and routing:
```typescript
// Example: Testing main page
describe('Home Page', () => {
  it('should show loading state initially', () => {
    render(<Home />);
    expect(screen.getByText('Loading...')).toBeInTheDocument();
  });
});
```

### Running Tests

```bash
# Run all tests
npm test

# Run specific test file
npm test SimpleTreeNode

# Run tests in watch mode
npm run test:watch

# Run with coverage
npm run test:coverage

# Run integration tests only
npm test integration
```

### Test Writing Guidelines

1. **Always test user interactions**, not implementation details
2. **Mock external dependencies** (data loaders, APIs)
3. **Use descriptive test names** that explain the behavior
4. **Test both happy paths and error cases**
5. **Verify accessibility** with proper ARIA labels

## Component Development

### Creating New Components

1. **Create the component file**:
```typescript
// src/components/MyNewComponent.tsx
'use client';

import React from 'react';

interface MyNewComponentProps {
  title: string;
  onAction: () => void;
}

export function MyNewComponent({ title, onAction }: MyNewComponentProps) {
  return (
    <div className="p-4">
      <h2>{title}</h2>
      <button onClick={onAction}>Action</button>
    </div>
  );
}
```

2. **Create the test file**:
```typescript
// src/__tests__/components/MyNewComponent.test.tsx
import { render, screen, fireEvent } from '@testing-library/react';
import { MyNewComponent } from '@/components/MyNewComponent';

describe('MyNewComponent', () => {
  it('should render title and handle clicks', () => {
    const mockAction = jest.fn();
    render(<MyNewComponent title="Test" onAction={mockAction} />);
    
    expect(screen.getByText('Test')).toBeInTheDocument();
    fireEvent.click(screen.getByText('Action'));
    expect(mockAction).toHaveBeenCalled();
  });
});
```

3. **Run tests immediately**:
```bash
npm test MyNewComponent
```

### Component Patterns

#### Props Interface Pattern
```typescript
interface ComponentProps {
  // Required props
  id: string;
  title: string;
  
  // Optional props
  className?: string;
  children?: React.ReactNode;
  
  // Event handlers
  onSave?: (data: FormData) => void;
  onCancel?: () => void;
}
```

#### Styling Pattern
```typescript
// Use cn() utility for conditional classes
import { cn } from '@/lib/utils';

<div className={cn(
  "base-classes",
  isActive && "active-classes",
  className // Allow prop overrides
)}>
```

#### State Management Pattern
```typescript
// Use React hooks for local state
const [isLoading, setIsLoading] = useState(false);
const [data, setData] = useState<DataType | null>(null);

// Use useEffect for data loading
useEffect(() => {
  const loadData = async () => {
    setIsLoading(true);
    try {
      const result = await fetchData();
      setData(result);
    } catch (error) {
      console.error('Failed to load data:', error);
    } finally {
      setIsLoading(false);
    }
  };
  loadData();
}, [dependency]);
```

## Code Quality

### TypeScript Guidelines

1. **Use strict typing** - avoid `any`
2. **Define interfaces** for all props and data structures
3. **Use type guards** for runtime type checking
4. **Export types** from appropriate modules

Example:
```typescript
// Good
interface Asset {
  id: string;
  name: string;
  domain: Domain;
}

// Bad
const asset: any = { /* ... */ };
```

### React Best Practices

1. **Use functional components** with hooks
2. **Memoize expensive calculations** with useMemo
3. **Extract custom hooks** for reusable logic
4. **Handle loading and error states**
5. **Use proper dependency arrays** in useEffect

### Styling Guidelines

1. **Use Tailwind CSS classes** consistently
2. **Create reusable utility functions** for complex styling
3. **Follow mobile-first responsive design**
4. **Maintain accessibility** standards

```typescript
// Good
<button className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500">

// Bad
<button style={{ backgroundColor: 'blue', padding: '8px 16px' }}>
```

## Troubleshooting

### Common Issues

#### 1. Tests Failing After Component Changes
```bash
# Check what tests are failing
npm test

# Run specific failing test with more detail
npm test -- --verbose ComponentName

# Update snapshots if needed (use cautiously)
npm test -- --updateSnapshot
```

#### 2. TypeScript Errors
```bash
# Check TypeScript compilation
npx tsc --noEmit

# Common fixes:
# - Add missing type definitions
# - Update interface definitions
# - Check import paths
```

#### 3. Runtime Errors in Development
```bash
# Check browser console
# Check Next.js terminal output
# Verify all imports are correct
# Check for missing dependencies
```

#### 4. Build Failures
```bash
# Test build locally
npm run build

# Common issues:
# - Unused imports
# - Missing environment variables
# - Type errors not caught in development
```

#### 5. Component Not Rendering
```bash
# Verify component is properly exported
export function MyComponent() { /* ... */ }

# Check import path
import { MyComponent } from '@/components/MyComponent';

# Verify JSX return
return <div>Content</div>; // Not just return content;
```

### Debugging Steps

1. **Check browser console** for JavaScript errors
2. **Verify component props** are being passed correctly
3. **Add console.log statements** to trace data flow
4. **Use React Developer Tools** browser extension
5. **Check TypeScript compilation** with `npx tsc --noEmit`
6. **Run tests** to identify broken functionality

### Getting Help

1. **Check test output** for specific error messages
2. **Review similar components** in the codebase
3. **Check TypeScript/React documentation**
4. **Verify IndustroML schema** compliance
5. **Test with simplified data** to isolate issues

## Best Practices Summary

### Development Cycle
1. **Write tests first** or immediately after implementation
2. **Run tests frequently** during development
3. **Check TypeScript** compilation regularly
4. **Test in browser** manually for user experience
5. **Run full build** before considering feature complete

### Code Organization
1. **Keep components focused** on single responsibilities
2. **Extract business logic** to lib/ directory
3. **Use TypeScript** for all data structures
4. **Write comprehensive tests** for all user interactions
5. **Document complex logic** with clear comments

### Quality Assurance
1. **All tests must pass** before deployment
2. **TypeScript must compile** without errors
3. **ESLint rules must pass** (when configured)
4. **Manual testing** should cover main user flows
5. **Code review** for adherence to patterns

Remember: **Always run tests after making changes!**