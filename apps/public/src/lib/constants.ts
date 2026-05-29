export const SITE_NAME = 'DataMktMx';
export const SITE_DESCRIPTION = 'Inteligencia de datos del mercado inmobiliario en México';

export const OPERATION_LABELS: Record<string, string> = {
  venta: 'Venta',
  renta: 'Renta',
  'renta vacacional': 'Renta Vacacional',
  sale: 'Venta',
  rent: 'Renta',
};

export const PROPERTY_TYPE_LABELS: Record<string, string> = {
  casa: 'Casa',
  departamento: 'Departamento',
  terreno: 'Terreno',
  oficina: 'Oficina',
  local: 'Local Comercial',
  bodega: 'Bodega',
  'casa en condominio': 'Casa en Condominio',
};

export function getOperationLabel(op: string): string {
  return OPERATION_LABELS[op.toLowerCase()] || op;
}

export function getPropertyTypeLabel(pt: string): string {
  return PROPERTY_TYPE_LABELS[pt.toLowerCase()] || pt;
}
