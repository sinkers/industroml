# IndustroML UI

A modern Next.js web application for viewing and editing IndustroML industrial site models.

## Features

- **Tree View**: Hierarchical display of containers and assets
- **Domain Filtering**: Filter view by electrical, mechanical, data, control, or safety domains
- **Asset Management**: Add, edit, clone, and delete assets and containers
- **Modern UI**: Built with React, Next.js, and Tailwind CSS
- **Type Safety**: Full TypeScript integration with IndustroML schema

## Getting Started

### Prerequisites

- Node.js 18+ 
- npm or yarn

### Installation

```bash
npm install
```

### Development

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

### Building for Production

```bash
npm run build
npm start
```

## Architecture

### Components

- **TreeView**: Main container for the asset hierarchy
- **TreeNode**: Individual tree node with expand/collapse and actions
- **DomainFilter**: Filter buttons for different engineering domains
- **AssetForm**: Modal form for adding/editing assets
- **ContainerForm**: Modal form for adding/editing containers

### Data Model

The application uses TypeScript interfaces that mirror the IndustroML schema:

- `IndustroMLDocument`: Root document structure
- `Container`: Physical or logical groupings (buildings, rooms, cabinets)
- `Asset`: Functional equipment (pumps, switches, sensors)
- `Interface`: Connection points on assets
- `Connection`: Relationships between interfaces

### Key Features

#### Tree Navigation
- Expand/collapse nodes to explore hierarchy
- Color-coded icons by domain (electrical=red, mechanical=blue, data=green, control=yellow, safety=red)
- Asset type badges and metadata display

#### Domain Filtering
- Filter entire tree by engineering domain
- Show asset counts per domain
- Maintain hierarchy structure in filtered view

#### Asset Operations
- **Add**: Create new assets or containers at any level
- **Edit**: Modify existing items with form validation
- **Clone**: Duplicate items with auto-generated unique IDs
- **Delete**: Remove items with cascade cleanup

#### Form Validation
- ID format validation (alphanumeric with dots, dashes, underscores)
- Unique ID enforcement
- Required field validation
- Domain-specific asset type selection

## File Structure

```
src/
├── app/
│   ├── globals.css          # Global styles
│   ├── layout.tsx          # App layout
│   └── page.tsx            # Main application page
├── components/
│   ├── AssetForm.tsx       # Asset add/edit form
│   ├── ContainerForm.tsx   # Container add/edit form  
│   ├── DomainFilter.tsx    # Domain filter buttons
│   ├── TreeNode.tsx        # Individual tree node
│   └── TreeView.tsx        # Main tree container
├── lib/
│   ├── data-loader.ts      # Sample data loading
│   ├── industroml.ts       # Business logic utilities
│   └── utils.ts            # General utilities
└── types/
    └── industroml.ts       # TypeScript type definitions
```

## Sample Data

The application loads sample data representing a data center site with:

- Site-level containers (buildings, rooms, areas)
- Electrical assets (transformers, switchboards, motors)  
- Mechanical assets (pumps, tanks, valves)
- Data network assets (switches, firewalls)
- Control system assets (PLCs, sensors)

## Integration

To integrate with real IndustroML files:

1. Replace the `loadSampleData()` function in `src/lib/data-loader.ts`
2. Add file upload/download capabilities  
3. Connect to a backend API for persistence
4. Add validation against the full IndustroML schema

## Technologies

- **Next.js 15**: React framework with app router
- **TypeScript**: Type-safe development
- **Tailwind CSS**: Utility-first styling
- **React Hook Form**: Form management
- **Zod**: Schema validation
- **Lucide React**: Icon library
- **js-yaml**: YAML parsing support
