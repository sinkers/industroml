import { render, screen, waitFor } from '@testing-library/react';
import Home from '@/app/page';

// Mock the data loader
jest.mock('@/lib/data-loader', () => ({
  loadSampleData: jest.fn(),
  loadCatalog: jest.fn(),
}));

// Import the mocked functions
import { loadSampleData, loadCatalog } from '@/lib/data-loader';
const mockLoadSampleData = loadSampleData as jest.MockedFunction<typeof loadSampleData>;
const mockLoadCatalog = loadCatalog as jest.MockedFunction<typeof loadCatalog>;

describe('Home Page', () => {
  const mockDocument = {
    meta: { format: 'IndustroML' as const, version: '0.1', site_name: 'Test Site' },
    containers: [
      { id: 'SITE', name: 'Test Site', type: 'site' as const },
      { id: 'ROOM', name: 'Test Room', type: 'room' as const, parent: 'SITE' },
    ],
    assets: [
      { id: 'TX1', name: 'Test Transformer', domain: 'electrical' as const, kind: 'transformer' as const, container: 'SITE' },
      { id: 'P1', name: 'Test Pump', domain: 'mechanical' as const, kind: 'pump' as const, container: 'ROOM' },
    ],
    interfaces: [],
    connections: [],
  };

  const mockCatalog = {
    meta: { format: 'IndustrialML-Catalog', version: '0.1' },
    icons: {},
    mediums: {
      electrical: ['ac_lv_3ph'],
      mechanical: ['pipe_flanged'],
      data: ['ethernet_rj45'],
      control: ['di_dry'],
      safety: ['di_dry']
    },
    connectors: [],
    elements: []
  };

  beforeEach(() => {
    mockLoadSampleData.mockResolvedValue(mockDocument);
    mockLoadCatalog.mockResolvedValue(mockCatalog);
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  it('should show loading state initially', () => {
    render(<Home />);
    expect(screen.getByText('Loading IndustroML data...')).toBeInTheDocument();
  });

  it('should render site name and asset counts after loading', async () => {
    render(<Home />);

    await waitFor(() => {
      expect(screen.getByText('IndustroML UI - Test Site')).toBeInTheDocument();
    });

    expect(screen.getByText('2 containers, 2 assets')).toBeInTheDocument();
  });

  it('should render asset hierarchy', async () => {
    render(<Home />);

    await waitFor(() => {
      expect(screen.getByText('Asset Hierarchy')).toBeInTheDocument();
    });

    expect(screen.getAllByText('Test Site')).toHaveLength(2); // Title and tree node
    expect(screen.getByText('Test Transformer')).toBeInTheDocument();
    expect(screen.getByText('Test Pump')).toBeInTheDocument();
  });

  it('should render domain filter', async () => {
    render(<Home />);

    await waitFor(() => {
      expect(screen.getByText('All Domains')).toBeInTheDocument();
    });

    expect(screen.getByText('electrical')).toBeInTheDocument();
    expect(screen.getByText('mechanical')).toBeInTheDocument();
  });

  it('should show error state when data loading fails', async () => {
    mockLoadSampleData.mockRejectedValue(new Error('Failed to load'));

    render(<Home />);

    await waitFor(() => {
      expect(screen.getByText('Error')).toBeInTheDocument();
    });

    expect(screen.getByText('Failed to load')).toBeInTheDocument();
  });

  it('should show no items message when filtered tree is empty', async () => {
    const emptyDocument = {
      ...mockDocument,
      containers: [], // No containers
      assets: [] // No assets
    };
    mockLoadSampleData.mockResolvedValue(emptyDocument);

    render(<Home />);

    await waitFor(() => {
      expect(screen.getByText('Asset Hierarchy')).toBeInTheDocument();
    });

    // With no containers and no assets, should show empty message
    expect(screen.getByText('No items match the current filter')).toBeInTheDocument();
  });
});