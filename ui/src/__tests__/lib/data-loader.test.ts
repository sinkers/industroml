import { parseYAMLDocument, exportToYAML } from '@/lib/data-loader';
import { IndustroMLDocument } from '@/types/industroml';

describe('YAML Data Loader', () => {
  const sampleYAML = `
meta:
  format: IndustroML
  version: "0.1"
  site_name: Test YAML Site

containers:
  - id: SITE
    name: Test Site
    type: site
  - id: ROOM1
    name: Test Room
    type: room
    parent: SITE

assets:
  - id: TX1
    name: Test Transformer
    domain: electrical
    kind: transformer
    container: SITE
    attributes:
      voltage: 415
  - id: P1
    name: Test Pump
    domain: mechanical
    kind: pump
    container: ROOM1

interfaces: []
connections: []
`;

  const expectedDocument: IndustroMLDocument = {
    meta: {
      format: 'IndustroML',
      version: '0.1',
      site_name: 'Test YAML Site'
    },
    containers: [
      { id: 'SITE', name: 'Test Site', type: 'site' },
      { id: 'ROOM1', name: 'Test Room', type: 'room', parent: 'SITE' }
    ],
    assets: [
      { 
        id: 'TX1', 
        name: 'Test Transformer', 
        domain: 'electrical', 
        kind: 'transformer', 
        container: 'SITE',
        attributes: { voltage: 415 }
      },
      { 
        id: 'P1', 
        name: 'Test Pump', 
        domain: 'mechanical', 
        kind: 'pump', 
        container: 'ROOM1'
      }
    ],
    interfaces: [],
    connections: []
  };

  describe('parseYAMLDocument', () => {
    it('should parse valid YAML into IndustroML document', () => {
      const result = parseYAMLDocument(sampleYAML);
      
      expect(result.meta.site_name).toBe('Test YAML Site');
      expect(result.containers).toHaveLength(2);
      expect(result.assets).toHaveLength(2);
      expect(result.interfaces).toHaveLength(0);
      expect(result.connections).toHaveLength(0);
    });

    it('should handle missing optional sections', () => {
      const minimalYAML = `
meta:
  format: IndustroML
  version: "0.1"
  site_name: Minimal Site

containers:
  - id: SITE
    name: Site
    type: site
`;

      const result = parseYAMLDocument(minimalYAML);
      
      expect(result.meta.site_name).toBe('Minimal Site');
      expect(result.containers).toHaveLength(1);
      expect(result.assets).toHaveLength(0);
      expect(result.interfaces).toHaveLength(0);
      expect(result.connections).toHaveLength(0);
    });

    it('should throw error for invalid YAML', () => {
      const invalidYAML = 'invalid: yaml: structure: [}';
      
      expect(() => parseYAMLDocument(invalidYAML)).toThrow('Invalid YAML file format');
    });

    it('should handle missing meta section', () => {
      const noMetaYAML = `
containers:
  - id: SITE
    name: Site
    type: site
`;

      const result = parseYAMLDocument(noMetaYAML);
      
      expect(result.meta.site_name).toBe('Unnamed Site');
      expect(result.meta.format).toBe('IndustroML');
      expect(result.meta.version).toBe('0.1');
    });
  });

  describe('exportToYAML', () => {
    it('should export document to valid YAML string', () => {
      const yamlString = exportToYAML(expectedDocument);
      
      expect(yamlString).toContain('meta:');
      expect(yamlString).toContain('site_name: Test YAML Site');
      expect(yamlString).toContain('containers:');
      expect(yamlString).toContain('assets:');
      expect(yamlString).toContain('- id: SITE');
      expect(yamlString).toContain('- id: TX1');
    });

    it('should create YAML that can be parsed back', () => {
      const exported = exportToYAML(expectedDocument);
      const parsed = parseYAMLDocument(exported);
      
      expect(parsed.meta.site_name).toBe(expectedDocument.meta.site_name);
      expect(parsed.containers).toHaveLength(expectedDocument.containers.length);
      expect(parsed.assets).toHaveLength(expectedDocument.assets.length);
    });
  });
});