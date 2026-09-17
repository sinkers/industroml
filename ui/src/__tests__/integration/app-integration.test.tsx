import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import Home from '@/app/page';

jest.mock('@/lib/data-loader', () => ({
  loadSampleData: jest.fn(),
  loadCatalog: jest.fn(),
}));

import { loadSampleData, loadCatalog } from '@/lib/data-loader';
const mockLoadSampleData = loadSampleData as jest.MockedFunction<typeof loadSampleData>;
const mockLoadCatalog = loadCatalog as jest.MockedFunction<typeof loadCatalog>;

describe('App Integration Tests', () => {
  const mockDocument = {
    meta: { format: 'IndustroML' as const, version: '0.1', site_name: 'Integration Test Site' },
    containers: [
      { id: 'SITE', name: 'Main Site', type: 'site' as const },
      { id: 'BLDG1', name: 'Building 1', type: 'building' as const, parent: 'SITE' },
      { id: 'ROOM1', name: 'Control Room', type: 'room' as const, parent: 'BLDG1' },
    ],
    assets: [
      { id: 'TX1', name: 'Main Transformer', domain: 'electrical' as const, kind: 'transformer' as const, container: 'SITE' },
      { id: 'P1', name: 'Water Pump', domain: 'mechanical' as const, kind: 'pump' as const, container: 'ROOM1' },
      { id: 'SW1', name: 'Network Switch', domain: 'data' as const, kind: 'ethernet_switch' as const, container: 'ROOM1' },
      { id: 'PLC1', name: 'Main PLC', domain: 'control' as const, kind: 'plc' as const, container: 'ROOM1' },
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

  it('should complete full app flow: load → display → filter', async () => {
    const user = userEvent.setup();
    render(<Home />);

    // 1. Loading state
    expect(screen.getByText('Loading IndustroML data...')).toBeInTheDocument();

    // 2. Wait for data to load
    await waitFor(() => {
      expect(screen.getByText('IndustroML UI - Integration Test Site')).toBeInTheDocument();
    }, { timeout: 3000 });

    // 3. Verify all data is displayed (now expanded by default to level 3)
    expect(screen.getByText('3 containers, 4 assets')).toBeInTheDocument();
    expect(screen.getByText('Main Site')).toBeInTheDocument();
    expect(screen.getByText('Building 1')).toBeInTheDocument();
    expect(screen.getByText('Control Room')).toBeInTheDocument();
    expect(screen.getByText('Main Transformer')).toBeInTheDocument();
    expect(screen.getByText('Water Pump')).toBeInTheDocument();
    expect(screen.getByText('Network Switch')).toBeInTheDocument();
    expect(screen.getByText('Main PLC')).toBeInTheDocument();

    // 4. Test domain filtering - click electrical filter
    const electricalButton = screen.getByText('electrical').closest('button');
    expect(electricalButton).toBeInTheDocument();
    await user.click(electricalButton!);

    // Should still show containers with electrical assets
    expect(screen.getByText('Main Site')).toBeInTheDocument();
    expect(screen.getByText('Main Transformer')).toBeInTheDocument();
    
    // Should not show mechanical, data, or control assets
    expect(screen.queryByText('Water Pump')).not.toBeInTheDocument();
    expect(screen.queryByText('Network Switch')).not.toBeInTheDocument();
    expect(screen.queryByText('Main PLC')).not.toBeInTheDocument();

    // 5. Test clicking "All Domains" to show everything again
    const allDomainsButton = screen.getByText('All Domains').closest('button');
    await user.click(allDomainsButton!);

    // All assets should be visible again
    expect(screen.getByText('Main Transformer')).toBeInTheDocument();
    expect(screen.getByText('Water Pump')).toBeInTheDocument();
    expect(screen.getByText('Network Switch')).toBeInTheDocument();
    expect(screen.getByText('Main PLC')).toBeInTheDocument();
  });

  it('should show correct domain counts in filter buttons', async () => {
    render(<Home />);

    await waitFor(() => {
      expect(screen.getByText('IndustroML UI - Integration Test Site')).toBeInTheDocument();
    });

    // Check domain counts are displayed correctly
    const electricalButton = screen.getByText('electrical').closest('button');
    const mechanicalButton = screen.getByText('mechanical').closest('button');
    const dataButton = screen.getByText('data').closest('button');
    const controlButton = screen.getByText('control').closest('button');

    expect(electricalButton).toHaveTextContent('1'); // 1 transformer
    expect(mechanicalButton).toHaveTextContent('1'); // 1 pump
    expect(dataButton).toHaveTextContent('1'); // 1 switch
    expect(controlButton).toHaveTextContent('1'); // 1 plc
  });

  it('should handle tree node expansion/collapse', async () => {
    const user = userEvent.setup();
    render(<Home />);

    await waitFor(() => {
      expect(screen.getByText('Main Site')).toBeInTheDocument();
    });

    // Initially, Building 1 should be visible (auto-expanded for first 2 levels)
    expect(screen.getByText('Building 1')).toBeInTheDocument();
    expect(screen.getByText('Control Room')).toBeInTheDocument();

    // Find and click the collapse button for Main Site
    const siteNode = screen.getByText('Main Site').closest('div');
    const collapseButton = siteNode?.querySelector('[role="button"]');
    
    if (collapseButton) {
      await user.click(collapseButton);
      // Building 1 should be hidden after collapse
      expect(screen.queryByText('Building 1')).not.toBeInTheDocument();
    }
  });

  it('should gracefully handle error states', async () => {
    mockLoadSampleData.mockRejectedValue(new Error('Network error'));

    render(<Home />);

    await waitFor(() => {
      expect(screen.getByText('Error')).toBeInTheDocument();
    });

    expect(screen.getByText('Network error')).toBeInTheDocument();
  });

  it('should display empty state when no assets match filter', async () => {
    const user = userEvent.setup();
    const emptyDocument = {
      ...mockDocument,
      containers: [], // No containers
      assets: [] // No assets
    };
    mockLoadSampleData.mockResolvedValue(emptyDocument);

    render(<Home />);

    await waitFor(() => {
      expect(screen.getByText('IndustroML UI - Integration Test Site')).toBeInTheDocument();
    });

    // With no containers and no assets, should show empty message
    expect(screen.getByText('No items match the current filter')).toBeInTheDocument();
  });
});