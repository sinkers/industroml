import yaml from 'js-yaml';
import { IndustroMLDocument, Catalog } from '@/types/industroml';

// Parse YAML content into IndustroML document
export function parseYAMLDocument(yamlContent: string): IndustroMLDocument {
  try {
    const parsed = yaml.load(yamlContent) as any;
    
    // Validate basic structure
    if (!parsed || typeof parsed !== 'object') {
      throw new Error('Invalid YAML structure');
    }
    
    // Ensure required fields exist with defaults
    const document: IndustroMLDocument = {
      meta: {
        format: 'IndustroML',
        version: '0.1',
        site_name: parsed.meta?.site_name || 'Unnamed Site',
        ...parsed.meta
      },
      containers: parsed.containers || [],
      assets: parsed.assets || [],
      interfaces: parsed.interfaces || [],
      connections: parsed.connections || []
    };
    
    return document;
  } catch (error) {
    console.error('Failed to parse YAML:', error);
    throw new Error('Invalid YAML file format');
  }
}

// Export document to YAML string
export function exportToYAML(document: IndustroMLDocument): string {
  try {
    return yaml.dump(document, {
      indent: 2,
      lineWidth: -1,
      noRefs: true,
      sortKeys: false
    });
  } catch (error) {
    console.error('Failed to export to YAML:', error);
    throw new Error('Failed to export document');
  }
}

// Export document to JSON string
export function exportToJSON(document: IndustroMLDocument): string {
  try {
    return JSON.stringify(document, null, 2);
  } catch (error) {
    console.error('Failed to export to JSON:', error);
    throw new Error('Failed to export document');
  }
}

// Parse JSON content into IndustroML document
export function parseJSONDocument(jsonContent: string): IndustroMLDocument {
  try {
    const parsed = JSON.parse(jsonContent) as any;
    
    // Validate basic structure
    if (!parsed || typeof parsed !== 'object') {
      throw new Error('Invalid JSON structure');
    }
    
    // Ensure required fields exist with defaults
    const document: IndustroMLDocument = {
      meta: {
        format: 'IndustroML',
        version: '0.1',
        site_name: parsed.meta?.site_name || 'Unnamed Site',
        ...parsed.meta
      },
      containers: parsed.containers || [],
      assets: parsed.assets || [],
      interfaces: parsed.interfaces || [],
      connections: parsed.connections || []
    };
    
    return document;
  } catch (error) {
    console.error('Failed to parse JSON:', error);
    throw new Error('Invalid JSON file format');
  }
}

// Load document from file (supports both JSON and YAML)
export function loadFromFile(file: File): Promise<IndustroMLDocument> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    
    reader.onload = (e) => {
      try {
        const content = e.target?.result as string;
        
        // Determine file type and parse accordingly
        if (file.name.endsWith('.json')) {
          const document = parseJSONDocument(content);
          resolve(document);
        } else if (file.name.endsWith('.yml') || file.name.endsWith('.yaml')) {
          const document = parseYAMLDocument(content);
          resolve(document);
        } else {
          throw new Error('Unsupported file format. Please use .json, .yml, or .yaml files');
        }
      } catch (error) {
        reject(error);
      }
    };
    
    reader.onerror = () => {
      reject(new Error('Failed to read file'));
    };
    
    reader.readAsText(file);
  });
}

// Load sample data from the parent directory
export async function loadSampleData(): Promise<IndustroMLDocument> {
  try {
    // In a real app, this would be loaded from an API or file upload
    // For now, we'll return a simplified version of the example data
    const sampleDocument: IndustroMLDocument = {
      meta: {
        format: 'IndustroML',
        version: '0.1',
        site_name: 'George Town Data Center',
        units: {
          length: 'm',
          diameter: 'mm',
          pressure: 'bar',
          voltage: 'V',
          current: 'A',
          power: 'kW'
        }
      },
      containers: [
        {
          id: 'SITE',
          name: 'GT Site',
          type: 'site'
        },
        {
          id: 'SR',
          name: 'Server Room',
          type: 'room',
          parent: 'SITE'
        },
        {
          id: 'P1HALL',
          name: 'Data Hall 1',
          type: 'building',
          parent: 'SITE'
        },
        {
          id: 'MSB',
          name: 'Master Switchboard',
          type: 'cabinet',
          parent: 'P1HALL'
        },
        {
          id: 'YARD',
          name: 'Yard Area',
          type: 'area',
          parent: 'SITE'
        }
      ],
      assets: [
        {
          id: 'TX1',
          name: 'Transformer 22kV/415V 2500kVA',
          domain: 'electrical',
          kind: 'transformer',
          container: 'YARD',
          attributes: {
            primary_voltage_v: 22000,
            secondary_voltage_v: 415,
            power_kva: 1000
          }
        },
        {
          id: 'MSB1',
          name: 'Main Switchboard 4000A',
          domain: 'electrical',
          kind: 'switchboard',
          container: 'MSB',
          attributes: {
            voltage_v: 415,
            current_a: 4000,
            switching: ['isolation', 'load-break']
          }
        },
        {
          id: 'P1',
          name: 'Centrifugal Pump P1 (55kW)',
          domain: 'mechanical',
          kind: 'pump',
          container: 'P1HALL',
          attributes: {
            flow_m3h: 180,
            head_m: 45,
            material: 'SS316'
          }
        },
        {
          id: 'SW1',
          name: 'Core Switch SW1',
          domain: 'data',
          kind: 'ethernet_switch',
          container: 'SR',
          attributes: {
            ports: 24,
            speed_gbps: 1
          }
        },
        {
          id: 'PLC1',
          name: 'PLC CPU',
          domain: 'control',
          kind: 'plc',
          container: 'SR',
          attributes: {
            slots: 8
          }
        }
      ],
      interfaces: [
        {
          id: 'TX1.HV',
          asset: 'TX1',
          name: 'HV Primary',
          domain: 'electrical',
          medium: 'ac_lv_3ph'
        },
        {
          id: 'TX1.LV',
          asset: 'TX1',
          name: 'LV Secondary',
          domain: 'electrical',
          medium: 'ac_lv_3ph'
        },
        {
          id: 'MSB1.IN',
          asset: 'MSB1',
          name: 'Incomer',
          domain: 'electrical',
          medium: 'ac_lv_3ph'
        }
      ],
      connections: [
        {
          id: 'C-TX1-MSB1',
          type: 'cable',
          from: 'TX1.LV',
          to: 'MSB1.IN',
          attributes: {
            csa_mm2: 240,
            cores: 4,
            insulation: 'XLPE',
            length_m: 20,
            method: 'tray'
          }
        }
      ]
    };

    return sampleDocument;
  } catch (error) {
    console.error('Failed to load sample data:', error);
    throw error;
  }
}

export async function loadCatalog(): Promise<Catalog> {
  try {
    // Simplified catalog for demo
    const catalog: Catalog = {
      meta: {
        format: 'IndustrialML-Catalog',
        version: '0.1',
        notes: 'Simplified catalog for demo'
      },
      icons: {},
      mediums: {
        electrical: ['ac_lv_3ph', 'ac_lv_1ph', 'dc'],
        mechanical: ['pipe_flanged', 'pipe_welded'],
        data: ['ethernet_rj45', 'ethernet_fiber'],
        control: ['di_dry', 'do_relay', 'ai_4_20mA'],
        safety: ['di_dry']
      },
      connectors: [
        {
          type: 'low_voltage',
          label: 'Low-Voltage Electrical',
          color: '#111827',
          attributes: ['csa_mm2', 'cores', 'insulation', 'length_m']
        }
      ],
      elements: [
        // Electrical
        {
          domain: 'electrical',
          kind: 'transformer',
          label: 'Transformer',
          icon: 'sld:transformer'
        },
        {
          domain: 'electrical',
          kind: 'switchboard',
          label: 'Switchboard',
          icon: 'sld:switchboard'
        },
        {
          domain: 'electrical',
          kind: 'breaker',
          label: 'Circuit Breaker',
          icon: 'sld:breaker'
        },
        {
          domain: 'electrical',
          kind: 'motor',
          label: 'Electric Motor',
          icon: 'sld:motor'
        },
        {
          domain: 'electrical',
          kind: 'vfd',
          label: 'Variable Frequency Drive',
          icon: 'sld:vfd'
        },
        // Mechanical
        {
          domain: 'mechanical',
          kind: 'pump',
          label: 'Pump (Centrifugal)',
          icon: 'pid:pump'
        },
        {
          domain: 'mechanical',
          kind: 'tank',
          label: 'Tank (Vertical)',
          icon: 'pid:tank'
        },
        {
          domain: 'mechanical',
          kind: 'valve',
          label: 'Valve (Generic)',
          icon: 'pid:valve'
        },
        // Data
        {
          domain: 'data',
          kind: 'ethernet_switch',
          label: 'Ethernet Switch',
          icon: 'net:switch'
        },
        {
          domain: 'data',
          kind: 'router',
          label: 'Router',
          icon: 'net:router'
        },
        {
          domain: 'data',
          kind: 'firewall',
          label: 'Firewall',
          icon: 'net:firewall'
        },
        // Control
        {
          domain: 'control',
          kind: 'plc',
          label: 'PLC CPU',
          icon: 'ctrl:plc'
        },
        {
          domain: 'control',
          kind: 'sensor',
          label: 'Sensor (Generic)',
          icon: 'ctrl:sensor'
        },
        {
          domain: 'control',
          kind: 'adc',
          label: 'Analog Input (AI)',
          icon: 'ctrl:adc'
        },
        // Safety
        {
          domain: 'safety',
          kind: 'estop',
          label: 'Emergency Stop',
          icon: 'safe:estop'
        }
      ]
    };

    return catalog;
  } catch (error) {
    console.error('Failed to load catalog:', error);
    throw error;
  }
}