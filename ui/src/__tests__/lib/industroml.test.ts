import { 
  buildTreeStructure, 
  filterTreeByDomain, 
  generateId, 
  getDomainColor,
  validateDocument 
} from '@/lib/industroml';
import { Container, Asset, IndustroMLDocument } from '@/types/industroml';

describe('industroml utility functions', () => {
  const mockContainers: Container[] = [
    { id: 'SITE', name: 'Test Site', type: 'site' },
    { id: 'ROOM', name: 'Test Room', type: 'room', parent: 'SITE' },
  ];

  const mockAssets: Asset[] = [
    { id: 'TX1', name: 'Transformer', domain: 'electrical', kind: 'transformer', container: 'SITE' },
    { id: 'P1', name: 'Pump', domain: 'mechanical', kind: 'pump', container: 'ROOM' },
    { id: 'SW1', name: 'Switch', domain: 'data', kind: 'ethernet_switch', container: 'ROOM' },
  ];

  describe('buildTreeStructure', () => {
    it('should build correct tree hierarchy', () => {
      const tree = buildTreeStructure(mockContainers, mockAssets);
      
      expect(tree).toHaveLength(1); // Only SITE as root
      expect(tree[0].id).toBe('SITE');
      expect(tree[0].children).toHaveLength(2); // ROOM and TX1
      
      const room = tree[0].children?.find(child => child.id === 'ROOM');
      expect(room).toBeDefined();
      expect(room?.children).toHaveLength(2); // P1 and SW1
    });

    it('should handle empty inputs', () => {
      const tree = buildTreeStructure([], []);
      expect(tree).toEqual([]);
    });
  });

  describe('filterTreeByDomain', () => {
    it('should filter assets by domain', () => {
      const tree = buildTreeStructure(mockContainers, mockAssets);
      const filtered = filterTreeByDomain(tree, 'electrical');
      
      expect(filtered).toHaveLength(1);
      expect(filtered[0].id).toBe('SITE');
      expect(filtered[0].children).toHaveLength(1); // Only TX1
    });

    it('should return all nodes when no domain specified', () => {
      const tree = buildTreeStructure(mockContainers, mockAssets);
      const filtered = filterTreeByDomain(tree);
      
      expect(filtered).toEqual(tree);
    });
  });

  describe('generateId', () => {
    it('should generate unique IDs', () => {
      const existingIds = new Set(['TX1', 'TX2']);
      const newId = generateId('TX', existingIds);
      
      expect(newId).toBe('TX3');
      expect(existingIds.has(newId)).toBe(false);
    });

    it('should handle empty prefix', () => {
      const existingIds = new Set(['1']);
      const newId = generateId('', existingIds);
      
      expect(newId).toBe('2');
    });
  });

  describe('getDomainColor', () => {
    it('should return correct colors for domains', () => {
      expect(getDomainColor('electrical')).toBe('#dc2626');
      expect(getDomainColor('mechanical')).toBe('#2563eb');
      expect(getDomainColor('data')).toBe('#059669');
      expect(getDomainColor('control')).toBe('#ca8a04');
      expect(getDomainColor('safety')).toBe('#dc2626');
    });
  });

  describe('validateDocument', () => {
    const validDocument: IndustroMLDocument = {
      meta: { format: 'IndustroML', version: '0.1' },
      containers: mockContainers,
      assets: mockAssets,
      interfaces: [
        { id: 'TX1.HV', asset: 'TX1', domain: 'electrical', medium: 'ac_lv_3ph' }
      ],
      connections: []
    };

    it('should validate correct document', () => {
      const errors = validateDocument(validDocument);
      expect(errors).toHaveLength(0);
    });

    it('should detect duplicate IDs', () => {
      const invalidDoc = {
        ...validDocument,
        assets: [
          ...mockAssets,
          { id: 'TX1', name: 'Duplicate', domain: 'electrical', kind: 'transformer', container: 'SITE' }
        ]
      } as IndustroMLDocument;

      const errors = validateDocument(invalidDoc);
      expect(errors.length).toBeGreaterThan(0);
      expect(errors[0]).toContain('Duplicate ID "TX1"');
    });

    it('should detect invalid container references', () => {
      const invalidDoc = {
        ...validDocument,
        assets: [
          { id: 'INVALID', name: 'Invalid Asset', domain: 'electrical', kind: 'transformer', container: 'NONEXISTENT' }
        ]
      } as IndustroMLDocument;

      const errors = validateDocument(invalidDoc);
      expect(errors.length).toBeGreaterThan(0);
      expect(errors[0]).toContain('references non-existent container');
    });
  });
});