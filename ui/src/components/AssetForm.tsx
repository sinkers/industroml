'use client';

import React from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { X } from 'lucide-react';
import { AssetFormData, Domain, AssetKind, Container, Catalog } from '@/types/industroml';
import { cn } from '@/lib/utils';

const assetSchema = z.object({
  id: z.string().min(1, 'ID is required').regex(/^[A-Za-z0-9]+(?:[._-][A-Za-z0-9]+)*$/, 'Invalid ID format'),
  name: z.string().min(1, 'Name is required'),
  domain: z.enum(['electrical', 'mechanical', 'data', 'control', 'safety']),
  kind: z.string().min(1, 'Kind is required'),
  container: z.string().min(1, 'Container is required'),
  labels: z.array(z.string()).optional(),
});

interface AssetFormProps {
  asset?: AssetFormData;
  containers: Container[];
  catalog: Catalog;
  onSave: (data: AssetFormData) => void;
  onCancel: () => void;
  existingIds: Set<string>;
}

export function AssetForm({ 
  asset, 
  containers, 
  catalog, 
  onSave, 
  onCancel,
  existingIds
}: AssetFormProps) {
  const isEditing = !!asset;

  const {
    register,
    handleSubmit,
    watch,
    formState: { errors, isValid },
    setValue
  } = useForm<AssetFormData>({
    resolver: zodResolver(assetSchema),
    defaultValues: asset || {
      id: '',
      name: '',
      domain: 'electrical',
      kind: 'transformer',
      container: containers[0]?.id || '',
      labels: []
    }
  });

  const watchedDomain = watch('domain');

  // Filter catalog elements by selected domain
  const availableKinds = catalog.elements
    .filter(element => element.domain === watchedDomain)
    .map(element => ({
      value: element.kind,
      label: element.label
    }));

  const onSubmit = (data: AssetFormData) => {
    // Validate ID uniqueness if creating new or changing ID
    if (!isEditing || data.id !== asset?.id) {
      if (existingIds.has(data.id)) {
        alert('ID already exists. Please choose a different ID.');
        return;
      }
    }

    onSave(data);
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg p-6 w-full max-w-md max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold">
            {isEditing ? 'Edit Asset' : 'Add Asset'}
          </h2>
          <button
            onClick={onCancel}
            className="text-gray-500 hover:text-gray-700"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          {/* ID */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              ID *
            </label>
            <input
              type="text"
              {...register('id')}
              className={cn(
                "w-full px-3 py-2 border rounded-md text-sm",
                errors.id ? "border-red-300" : "border-gray-300"
              )}
              placeholder="e.g. TX1, PUMP-001"
            />
            {errors.id && (
              <p className="text-red-500 text-xs mt-1">{errors.id.message}</p>
            )}
          </div>

          {/* Name */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Name *
            </label>
            <input
              type="text"
              {...register('name')}
              className={cn(
                "w-full px-3 py-2 border rounded-md text-sm",
                errors.name ? "border-red-300" : "border-gray-300"
              )}
              placeholder="e.g. Main Transformer, Feed Pump"
            />
            {errors.name && (
              <p className="text-red-500 text-xs mt-1">{errors.name.message}</p>
            )}
          </div>

          {/* Domain */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Domain *
            </label>
            <select
              {...register('domain')}
              className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
            >
              <option value="electrical">Electrical</option>
              <option value="mechanical">Mechanical</option>
              <option value="data">Data</option>
              <option value="control">Control</option>
              <option value="safety">Safety</option>
            </select>
          </div>

          {/* Kind */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Type *
            </label>
            <select
              {...register('kind')}
              className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
            >
              {availableKinds.length === 0 ? (
                <option value="">No types available for this domain</option>
              ) : (
                availableKinds.map((kind) => (
                  <option key={kind.value} value={kind.value}>
                    {kind.label}
                  </option>
                ))
              )}
            </select>
          </div>

          {/* Container */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Container *
            </label>
            <select
              {...register('container')}
              className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
            >
              {containers.map((container) => (
                <option key={container.id} value={container.id}>
                  {container.name} ({container.type})
                </option>
              ))}
            </select>
          </div>

          {/* Labels */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Labels
            </label>
            <input
              type="text"
              placeholder="Comma-separated labels"
              onChange={(e) => {
                const labels = e.target.value
                  .split(',')
                  .map(l => l.trim())
                  .filter(l => l.length > 0);
                setValue('labels', labels);
              }}
              defaultValue={asset?.labels?.join(', ') || ''}
              className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
            />
            <p className="text-xs text-gray-500 mt-1">
              Add labels separated by commas
            </p>
          </div>

          {/* Actions */}
          <div className="flex justify-end gap-2 pt-4">
            <button
              type="button"
              onClick={onCancel}
              className="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 rounded-md hover:bg-gray-200"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={!isValid}
              className={cn(
                "px-4 py-2 text-sm font-medium text-white rounded-md",
                isValid 
                  ? "bg-blue-600 hover:bg-blue-700" 
                  : "bg-gray-300 cursor-not-allowed"
              )}
            >
              {isEditing ? 'Save Changes' : 'Add Asset'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}