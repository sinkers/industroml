import { 
  IndustroMLDocument, 
  Container, 
  Asset, 
  TreeNode, 
  Domain,
  Catalog,
  CatalogElement 
} from '@/types/industroml';

// Domain colors for UI consistency
export const DOMAIN_COLORS = {
  electrical: '#dc2626', // red-600
  mechanical: '#2563eb', // blue-600
  data: '#059669', // green-600
  control: '#ca8a04', // yellow-600
  safety: '#dc2626', // red-600
} as const;

// Build tree structure from containers and assets
export function buildTreeStructure(
  containers: Container[], 
  assets: Asset[]
): TreeNode[] {
  const containerMap = new Map<string, Container>();
  const assetMap = new Map<string, Asset>();
  
  // Create maps for quick lookup
  containers.forEach(c => containerMap.set(c.id, c));
  assets.forEach(a => assetMap.set(a.id, a));

  // Build tree nodes
  const nodeMap = new Map<string, TreeNode>();
  
  // Create container nodes
  containers.forEach(container => {
    nodeMap.set(container.id, {
      id: container.id,
      name: container.name,
      type: 'container',
      children: [],
      parent: container.parent
    });
  });

  // Create asset nodes
  assets.forEach(asset => {
    nodeMap.set(asset.id, {
      id: asset.id,
      name: asset.name,
      type: 'asset',
      domain: asset.domain,
      kind: asset.kind,
      children: [],
      parent: asset.container
    });
  });

  // Build parent-child relationships
  const rootNodes: TreeNode[] = [];
  
  nodeMap.forEach(node => {
    if (node.parent && nodeMap.has(node.parent)) {
      const parent = nodeMap.get(node.parent)!;
      parent.children = parent.children || [];
      parent.children.push(node);
    } else {
      rootNodes.push(node);
    }
  });

  // Sort children by name
  const sortNodes = (nodes: TreeNode[]) => {
    nodes.sort((a, b) => a.name.localeCompare(b.name));
    nodes.forEach(node => {
      if (node.children) {
        sortNodes(node.children);
      }
    });
  };

  sortNodes(rootNodes);
  return rootNodes;
}

// Filter tree nodes by domain
export function filterTreeByDomain(nodes: TreeNode[], domain?: Domain): TreeNode[] {
  if (!domain) return nodes;

  return nodes.map(node => {
    const filteredChildren = node.children 
      ? filterTreeByDomain(node.children, domain)
      : [];

    // Include container if it has children or if it's an asset of the correct domain
    if (node.type === 'container') {
      return filteredChildren.length > 0 
        ? { ...node, children: filteredChildren }
        : null;
    } else {
      return node.domain === domain 
        ? { ...node, children: filteredChildren }
        : null;
    }
  }).filter(Boolean) as TreeNode[];
}

// Generate unique ID for new assets/containers
export function generateId(prefix: string, existingIds: Set<string>): string {
  let counter = 1;
  let newId = `${prefix}${counter}`;
  
  while (existingIds.has(newId)) {
    counter++;
    newId = `${prefix}${counter}`;
  }
  
  return newId;
}

// Get domain color
export function getDomainColor(domain: Domain): string {
  return DOMAIN_COLORS[domain];
}

// Clone asset with new ID
export function cloneAsset(
  asset: Asset, 
  newId: string,
  nameSuffix: string = ' (Copy)'
): Asset {
  return {
    ...asset,
    id: newId,
    name: asset.name + nameSuffix,
    // Deep clone attributes
    attributes: asset.attributes ? JSON.parse(JSON.stringify(asset.attributes)) : undefined,
    labels: asset.labels ? [...asset.labels] : undefined
  };
}

// Clone container with new ID  
export function cloneContainer(
  container: Container,
  newId: string,
  nameSuffix: string = ' (Copy)'
): Container {
  return {
    ...container,
    id: newId,
    name: container.name + nameSuffix,
    // Deep clone attributes
    attributes: container.attributes ? JSON.parse(JSON.stringify(container.attributes)) : undefined
  };
}

// Get catalog elements by domain
export function getCatalogElementsByDomain(
  catalog: Catalog, 
  domain: Domain
): CatalogElement[] {
  return catalog.elements.filter(element => element.domain === domain);
}

// Validate IndustroML document structure
export function validateDocument(doc: IndustroMLDocument): string[] {
  const errors: string[] = [];
  
  // Check for duplicate IDs
  const allIds = new Set<string>();
  const checkDuplicateId = (id: string, type: string) => {
    if (allIds.has(id)) {
      errors.push(`Duplicate ID "${id}" found in ${type}`);
    } else {
      allIds.add(id);
    }
  };

  // Check containers
  doc.containers.forEach(container => {
    checkDuplicateId(container.id, 'containers');
  });

  // Check assets
  doc.assets.forEach(asset => {
    checkDuplicateId(asset.id, 'assets');
    
    // Verify container exists
    const containerExists = doc.containers.some(c => c.id === asset.container);
    if (!containerExists) {
      errors.push(`Asset "${asset.id}" references non-existent container "${asset.container}"`);
    }
  });

  // Check interfaces
  doc.interfaces.forEach(iface => {
    checkDuplicateId(iface.id, 'interfaces');
    
    // Verify asset exists
    const assetExists = doc.assets.some(a => a.id === iface.asset);
    if (!assetExists) {
      errors.push(`Interface "${iface.id}" references non-existent asset "${iface.asset}"`);
    }
  });

  // Check connections
  doc.connections.forEach(conn => {
    checkDuplicateId(conn.id, 'connections');
    
    // Verify from/to interfaces exist
    const fromExists = doc.interfaces.some(i => i.id === conn.from);
    const toExists = doc.interfaces.some(i => i.id === conn.to);
    
    if (!fromExists) {
      errors.push(`Connection "${conn.id}" references non-existent 'from' interface "${conn.from}"`);
    }
    if (!toExists) {
      errors.push(`Connection "${conn.id}" references non-existent 'to' interface "${conn.to}"`);
    }
  });

  return errors;
}

// Get all existing IDs in a document
export function getExistingIds(doc: IndustroMLDocument): Set<string> {
  const ids = new Set<string>();
  
  doc.containers.forEach(c => ids.add(c.id));
  doc.assets.forEach(a => ids.add(a.id));
  doc.interfaces.forEach(i => ids.add(i.id));
  doc.connections.forEach(c => ids.add(c.id));
  
  return ids;
}