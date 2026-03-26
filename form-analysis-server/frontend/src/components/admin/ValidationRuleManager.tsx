/**
 * ValidationRuleManager — CRUD for validation rules.
 * Used as a tab inside AdminPage.
 */

import { useEffect, useState } from 'react';
import type { StationInfo, ValidationRuleInfo } from '../../types/api';
import {
  fetchStations,
  fetchValidationRules,
  createValidationRule,
  updateValidationRule,
  deleteValidationRule,
} from '../../services/stationApi';

interface Props {
  showToast: (type: 'success' | 'error' | 'info', msg: string) => void;
}

export function ValidationRuleManager({ showToast }: Props) {
  const [stations, setStations] = useState<StationInfo[]>([]);
  const [selectedCode, setSelectedCode] = useState('');
  const [rules, setRules] = useState<ValidationRuleInfo[]>([]);
  const [loading, setLoading] = useState(false);

  // create form
  const [newField, setNewField] = useState('');
  const [newType, setNewType] = useState('enum');
  const [newConfigJson, setNewConfigJson] = useState('{}');
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    fetchStations().then(setStations).catch(() => {});
  }, []);

  const loadRules = async () => {
    if (!selectedCode) return;
    setLoading(true);
    try {
      const data = await fetchValidationRules(selectedCode);
      setRules(data);
    } catch (err: any) {
      showToast('error', err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleCreate = async () => {
    if (!newField.trim()) {
      showToast('error', 'Field name is required');
      return;
    }
    let config: Record<string, unknown>;
    try {
      config = JSON.parse(newConfigJson);
    } catch {
      showToast('error', 'Invalid JSON in rule config');
      return;
    }
    setCreating(true);
    try {
      await createValidationRule({
        field_name: newField.trim(),
        rule_type: newType,
        rule_config: config,
        station_code: selectedCode || null,
      });
      showToast('success', 'Validation rule created');
      setNewField(''); setNewConfigJson('{}');
      await loadRules();
    } catch (err: any) {
      showToast('error', err.message);
    } finally {
      setCreating(false);
    }
  };

  const handleToggleActive = async (rule: ValidationRuleInfo) => {
    try {
      await updateValidationRule(rule.id, { is_active: !(rule as any).is_active });
      await loadRules();
    } catch (err: any) {
      showToast('error', err.message);
    }
  };

  const handleDelete = async (rule: ValidationRuleInfo) => {
    if (!confirm(`Delete validation rule for field "${rule.field_name}"?`)) return;
    try {
      await deleteValidationRule(rule.id);
      showToast('success', 'Rule deleted');
      await loadRules();
    } catch (err: any) {
      showToast('error', err.message);
    }
  };

  return (
    <section className="register-card">
      <div className="admin-header-row">
        <div>
          <h2 className="register-title">Validation Rules</h2>
          <p className="register-hint">Manage enum, range, regex, and required validation rules per station.</p>
        </div>
        <div className="admin-header-actions">
          <select
            className="register-input admin-select"
            value={selectedCode}
            onChange={e => setSelectedCode(e.target.value)}
          >
            <option value="">Select station...</option>
            {stations.map(s => (
              <option key={s.id} value={s.code}>{s.code} ({s.name})</option>
            ))}
          </select>
          <button className="btn" onClick={loadRules} disabled={loading || !selectedCode}>
            {loading ? 'Loading...' : 'Load Rules'}
          </button>
        </div>
      </div>

      {selectedCode && (
        <details className="register-details">
          <summary className="register-summary">Add Rule</summary>
          <div className="admin-form-grid">
            <label className="register-label">
              Field Name
              <input className="register-input" value={newField} onChange={e => setNewField(e.target.value)} placeholder="e.g. material_grade" />
            </label>
            <label className="register-label">
              Rule Type
              <select className="register-input" value={newType} onChange={e => setNewType(e.target.value)}>
                <option value="enum">enum</option>
                <option value="range">range</option>
                <option value="regex">regex</option>
                <option value="required">required</option>
              </select>
            </label>
            <label className="register-label">
              Config (JSON)
              <textarea
                className="register-input"
                value={newConfigJson}
                onChange={e => setNewConfigJson(e.target.value)}
                rows={3}
                style={{ fontFamily: 'monospace', fontSize: '0.85rem' }}
                placeholder='{"values": ["H2","H5","H8"]}'
              />
            </label>
          </div>
          <div className="register-actions">
            <button className="btn btn-primary" onClick={handleCreate} disabled={creating}>
              {creating ? 'Creating...' : 'Create Rule'}
            </button>
          </div>
        </details>
      )}

      <div className="admin-table-wrap">
        <table className="admin-table">
          <thead>
            <tr>
              <th>Field</th>
              <th>Type</th>
              <th>Config</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {rules.map(r => (
              <tr key={r.id}>
                <td className="admin-mono">{r.field_name}</td>
                <td><span className="pill pill-ok">{r.rule_type}</span></td>
                <td style={{ maxWidth: 300, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontSize: '0.82rem', fontFamily: 'monospace' }}>
                  {JSON.stringify(r.rule_config)}
                </td>
                <td>
                  <button className="btn btn-small" onClick={() => handleToggleActive(r)}>
                    Toggle
                  </button>
                  <button className="btn btn-small" onClick={() => handleDelete(r)} style={{ marginLeft: 8 }}>
                    Delete
                  </button>
                </td>
              </tr>
            ))}
            {!rules.length && (
              <tr><td colSpan={4} className="admin-empty">{selectedCode ? 'No rules' : 'Select a station first'}</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}
