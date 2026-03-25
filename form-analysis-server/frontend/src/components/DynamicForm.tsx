/**
 * DynamicForm — renders form fields from a FieldDef[] array.
 *
 * Replaces hardcoded P1/P2/P3 field layouts with a schema-driven approach.
 */

import React from 'react';
import { useTranslation } from 'react-i18next';
import type { FieldDef } from '../types/api';

interface DynamicFormProps {
  fields: FieldDef[];
  values: Record<string, any>;
  onChange: (name: string, value: any) => void;
  readOnly?: boolean;
}

export const DynamicForm: React.FC<DynamicFormProps> = ({
  fields,
  values,
  onChange,
  readOnly = false,
}) => {
  const { i18n } = useTranslation();
  const lang = i18n.resolvedLanguage ?? i18n.language ?? 'zh-TW';

  return (
    <div className="dynamic-form" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: '12px' }}>
      {fields.map((field) => {
        const label = field.label[lang] ?? field.label['en'] ?? field.name;
        const value = values[field.name] ?? '';

        return (
          <div key={field.name} className="dynamic-form-field">
            <label style={{ display: 'block', fontSize: '0.85rem', marginBottom: '4px', fontWeight: 500 }}>
              {label}
              {field.required && <span style={{ color: 'red', marginLeft: 2 }}>*</span>}
              {field.unit && <span style={{ color: '#888', marginLeft: 4 }}>({field.unit})</span>}
            </label>
            {renderInput(field, value, onChange, readOnly)}
          </div>
        );
      })}
    </div>
  );
};

function renderInput(
  field: FieldDef,
  value: any,
  onChange: (name: string, value: any) => void,
  readOnly: boolean,
) {
  const common = {
    disabled: readOnly,
    style: {
      width: '100%',
      padding: '6px 8px',
      border: '1px solid #ccc',
      borderRadius: 4,
      fontSize: '0.9rem',
    } as React.CSSProperties,
  };

  switch (field.type) {
    case 'integer':
    case 'float':
      return (
        <input
          type="number"
          value={value}
          step={field.type === 'float' ? 'any' : '1'}
          min={field.min}
          max={field.max}
          onChange={(e) => onChange(field.name, e.target.value === '' ? null : Number(e.target.value))}
          {...common}
        />
      );

    case 'date':
      return (
        <input
          type="date"
          value={value}
          onChange={(e) => onChange(field.name, e.target.value || null)}
          {...common}
        />
      );

    case 'boolean':
      return (
        <input
          type="checkbox"
          checked={Boolean(value)}
          onChange={(e) => onChange(field.name, e.target.checked)}
          disabled={readOnly}
          style={{ width: 18, height: 18 }}
        />
      );

    case 'enum':
      return (
        <select
          value={value}
          onChange={(e) => onChange(field.name, e.target.value || null)}
          {...common}
        >
          <option value="">--</option>
          {(field.enum_values ?? []).map((ev) => (
            <option key={String(ev.value)} value={ev.value}>
              {ev.label?.['zh-TW'] ?? ev.label?.['en'] ?? String(ev.value)}
            </option>
          ))}
        </select>
      );

    default: // string
      return (
        <input
          type="text"
          value={value}
          onChange={(e) => onChange(field.name, e.target.value || null)}
          {...common}
        />
      );
  }
}
