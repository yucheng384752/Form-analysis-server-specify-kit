/**
 * DynamicFilterField — a single filter input rendered from a FieldDef.
 *
 * Used by a schema-driven AdvancedSearch to replace hardcoded filter fields.
 */

import React from 'react';
import { useTranslation } from 'react-i18next';
import type { FieldDef } from '../types/api';

interface DynamicFilterFieldProps {
  field: FieldDef;
  value: any;
  onChange: (value: any) => void;
}

export const DynamicFilterField: React.FC<DynamicFilterFieldProps> = ({
  field,
  value,
  onChange,
}) => {
  const { i18n } = useTranslation();
  const lang = i18n.resolvedLanguage ?? i18n.language ?? 'zh-TW';
  const label = field.label[lang] ?? field.label['en'] ?? field.name;

  const inputStyle: React.CSSProperties = {
    width: '100%',
    padding: '6px 8px',
    border: '1px solid #ccc',
    borderRadius: 4,
    fontSize: '0.85rem',
  };

  const renderControl = () => {
    switch (field.type) {
      case 'integer':
      case 'float':
        return (
          <input
            type="number"
            value={value ?? ''}
            step={field.type === 'float' ? 'any' : '1'}
            min={field.min}
            max={field.max}
            placeholder={label}
            onChange={(e) => onChange(e.target.value === '' ? undefined : Number(e.target.value))}
            style={inputStyle}
          />
        );

      case 'date':
        return (
          <input
            type="date"
            value={value ?? ''}
            onChange={(e) => onChange(e.target.value || undefined)}
            style={inputStyle}
          />
        );

      case 'boolean':
        return (
          <select
            value={value === undefined ? '' : String(value)}
            onChange={(e) => {
              if (e.target.value === '') onChange(undefined);
              else onChange(e.target.value === 'true');
            }}
            style={inputStyle}
          >
            <option value="">--</option>
            <option value="true">Yes</option>
            <option value="false">No</option>
          </select>
        );

      case 'enum':
        return (
          <select
            value={value ?? ''}
            onChange={(e) => onChange(e.target.value || undefined)}
            style={inputStyle}
          >
            <option value="">--</option>
            {(field.enum_values ?? []).map((ev) => (
              <option key={String(ev.value)} value={ev.value}>
                {ev.label?.[lang] ?? ev.label?.['en'] ?? String(ev.value)}
              </option>
            ))}
          </select>
        );

      default: // string
        return (
          <input
            type="text"
            value={value ?? ''}
            placeholder={label}
            onChange={(e) => onChange(e.target.value || undefined)}
            style={inputStyle}
          />
        );
    }
  };

  return (
    <div style={{ minWidth: 160 }}>
      <label style={{ display: 'block', fontSize: '0.8rem', marginBottom: 2, fontWeight: 500 }}>
        {label}
        {field.unit && <span style={{ color: '#888', marginLeft: 4 }}>({field.unit})</span>}
      </label>
      {renderControl()}
    </div>
  );
};
