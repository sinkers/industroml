'use client';

import React from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { X } from 'lucide-react';
import { ContainerFormData, ContainerType, Container } from '@/types/industroml';
import { cn } from '@/lib/utils';

const containerSchema = z.object({
  id: z.string().min(1, 'ID is required').regex(/^[A-Za-z0-9]+(?:[._-][A-Za-z0-9]+)*$/, 'Invalid ID format'),
  name: z.string().min(1, 'Name is required'),
  type: z.enum(['site', 'building', 'room', 'area', 'skid', 'cabinet', 'rack', 'tray', 'pipe_rack', 'conduit']),
  parent: z.string().optional(),
});

interface ContainerFormProps {
  container?: ContainerFormData;
  containers: Container[];
  onSave: (data: ContainerFormData) => void;
  onCancel: () => void;
  existingIds: Set<string>;
  parentId?: string; // Pre-selected parent when adding child
}

export function ContainerForm({ 
  container, 
  containers, 
  onSave, 
  onCancel,
  existingIds,
  parentId
}: ContainerFormProps) {
  const isEditing = !!container;

  const {
    register,
    handleSubmit,
    formState: { errors, isValid }
  } = useForm<ContainerFormData>({
    resolver: zodResolver(containerSchema),
    defaultValues: container || {
      id: '',
      name: '',
      type: 'room',
      parent: parentId || ''
    }
  });

  // Available parent containers (exclude self and descendants to prevent cycles)
  const availableParents = containers.filter(c => {
    if (isEditing && c.id === container?.id) return false;
    // In a real app, we'd also exclude descendants to prevent cycles
    return true;
  });

  const onSubmit = (data: ContainerFormData) => {
    // Validate ID uniqueness if creating new or changing ID
    if (!isEditing || data.id !== container?.id) {
      if (existingIds.has(data.id)) {
        alert('ID already exists. Please choose a different ID.');
        return;
      }
    }

    // Clean up empty parent
    if (data.parent === '') {
      data.parent = undefined;
    }

    onSave(data);
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg p-6 w-full max-w-md max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold">
            {isEditing ? 'Edit Container' : 'Add Container'}
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
              placeholder="e.g. SITE, ROOM-01, MSB"
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
              placeholder="e.g. Main Site, Control Room, Switchboard"
            />
            {errors.name && (
              <p className="text-red-500 text-xs mt-1">{errors.name.message}</p>
            )}
          </div>

          {/* Type */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Type *
            </label>
            <select
              {...register('type')}
              className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
            >
              <option value="site">Site</option>
              <option value="building">Building</option>
              <option value="room">Room</option>
              <option value="area">Area</option>
              <option value="skid">Skid</option>
              <option value="cabinet">Cabinet</option>
              <option value="rack">Rack</option>
              <option value="tray">Tray</option>
              <option value="pipe_rack">Pipe Rack</option>
              <option value="conduit">Conduit</option>
            </select>
          </div>

          {/* Parent Container */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Parent Container
            </label>
            <select
              {...register('parent')}
              className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
            >
              <option value="">None (Root level)</option>
              {availableParents.map((parent) => (
                <option key={parent.id} value={parent.id}>
                  {parent.name} ({parent.type})
                </option>
              ))}
            </select>
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
              {isEditing ? 'Save Changes' : 'Add Container'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}