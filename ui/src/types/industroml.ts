// IndustroML TypeScript interfaces based on the schema

export type Domain = 'electrical' | 'mechanical' | 'data' | 'control' | 'safety';

export type ContainerType = 
  | 'site' 
  | 'building' 
  | 'room' 
  | 'area' 
  | 'skid' 
  | 'cabinet' 
  | 'rack' 
  | 'tray' 
  | 'pipe_rack' 
  | 'conduit';

export type AssetKind = 
  | 'transformer' | 'switchboard' | 'mcc' | 'pdu' | 'vfd' | 'breaker' | 'motor' | 'ups' | 'generator' | 'switchgear'
  | 'pump' | 'tank' | 'heat_exchanger' | 'valve' | 'pipe_support' | 'filter' | 'vessel'
  | 'ethernet_switch' | 'router' | 'firewall' | 'server' | 'plc' | 'rtu' | 'adc' | 'sensor' | 'hmi' | 'gateway';

export type Medium = 
  | 'ac_lv_3ph' | 'ac_lv_1ph' | 'dc' | 'aux_contact'
  | 'pipe_flanged' | 'pipe_threaded' | 'hose' | 'nozzle'
  | 'ethernet_rj45' | 'ethernet_fiber' | 'rs485' | 'ai_4_20mA' | 'di_dry' | 'do_relay';

export type ConnectionType = 'cable' | 'pipe' | 'data_link' | 'io_link';

export interface IndustroMLMeta {
  format: 'IndustroML';
  version: string;
  units?: Record<string, string>;
  site_name?: string;
  tags?: string[];
}

export interface Container {
  id: string;
  name: string;
  type: ContainerType;
  parent?: string;
  attributes?: Record<string, any>;
}

export interface Asset {
  id: string;
  name: string;
  domain: Domain;
  kind: AssetKind;
  container: string;
  attributes?: Record<string, any>;
  labels?: string[];
}

export interface Interface {
  id: string;
  asset: string;
  name?: string;
  domain: Domain;
  medium: Medium;
  attributes?: Record<string, any>;
}

export interface Connection {
  id: string;
  type: ConnectionType;
  from: string;
  to: string;
  attributes?: Record<string, any>;
  route?: string[];
}

export interface IndustroMLDocument {
  meta: IndustroMLMeta;
  containers: Container[];
  assets: Asset[];
  interfaces: Interface[];
  connections: Connection[];
}

// Catalog interfaces
export interface CatalogElement {
  domain: Domain;
  kind: string;
  label: string;
  icon: string;
  default_attributes?: Record<string, any>;
  default_interfaces?: Array<{
    name: string;
    domain: Domain;
    medium: Medium;
  }>;
}

export interface Catalog {
  meta: {
    format: string;
    version: string;
    notes?: string;
  };
  icons: Record<string, any>;
  mediums: Record<Domain, string[]>;
  connectors: Array<{
    type: string;
    label: string;
    color: string;
    attributes: string[];
  }>;
  elements: CatalogElement[];
}

// Tree view interfaces
export interface TreeNode {
  id: string;
  name: string;
  type: 'container' | 'asset';
  domain?: Domain;
  kind?: string;
  children?: TreeNode[];
  parent?: string;
}

// Form interfaces
export interface AssetFormData {
  id: string;
  name: string;
  domain: Domain;
  kind: AssetKind;
  container: string;
  attributes?: Record<string, any>;
  labels?: string[];
}

export interface ContainerFormData {
  id: string;
  name: string;
  type: ContainerType;
  parent?: string;
  attributes?: Record<string, any>;
}