'use client';

import React from 'react';
import { Zap, Wrench, Network, Cpu, Shield } from 'lucide-react';
import { Domain } from '@/types/industroml';
import { getDomainColor } from '@/lib/industroml';
import { cn } from '@/lib/utils';

const DOMAIN_ICONS = {
  electrical: Zap,
  mechanical: Wrench,
  data: Network,
  control: Cpu,
  safety: Shield,
} as const;

interface DomainFilterProps {
  selectedDomain?: Domain;
  onDomainChange: (domain?: Domain) => void;
  domainCounts: Record<Domain, number>;
}

export function DomainFilter({ 
  selectedDomain, 
  onDomainChange, 
  domainCounts 
}: DomainFilterProps) {
  const domains: Domain[] = ['electrical', 'mechanical', 'data', 'control', 'safety'];

  return (
    <div className="flex flex-wrap gap-2">
      {/* All domains button */}
      <button
        onClick={() => onDomainChange(undefined)}
        className={cn(
          "flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-colors",
          !selectedDomain 
            ? "bg-gray-900 text-white" 
            : "bg-gray-100 text-black hover:bg-gray-200"
        )}
      >
        All Domains
        <span className="bg-white bg-opacity-20 text-xs px-2 py-0.5 rounded-full">
          {Object.values(domainCounts).reduce((sum, count) => sum + count, 0)}
        </span>
      </button>

      {/* Individual domain buttons */}
      {domains.map((domain) => {
        const Icon = DOMAIN_ICONS[domain];
        const count = domainCounts[domain];
        const isSelected = selectedDomain === domain;

        return (
          <button
            key={domain}
            onClick={() => onDomainChange(isSelected ? undefined : domain)}
            className={cn(
              "flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-colors",
              isSelected 
                ? "text-white shadow-md" 
                : "bg-gray-100 text-black hover:bg-gray-200"
            )}
            style={isSelected ? { backgroundColor: getDomainColor(domain) } : {}}
            disabled={count === 0}
          >
            <Icon className="w-4 h-4" />
            <span className="capitalize">{domain}</span>
            <span 
              className={cn(
                "text-xs px-2 py-0.5 rounded-full",
                isSelected 
                  ? "bg-white bg-opacity-20" 
                  : count === 0 
                    ? "bg-gray-200 text-gray-400"
                    : "bg-gray-200 text-black"
              )}
            >
              {count}
            </span>
          </button>
        );
      })}
    </div>
  );
}