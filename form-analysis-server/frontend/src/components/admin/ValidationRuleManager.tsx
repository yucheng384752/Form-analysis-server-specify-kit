/**
 * ValidationRuleManager — CRUD for validation rules.
 * Used as a tab inside AdminPage.
 */

import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
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
  const { t } = useTranslation();
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
      showToast('error', t('admin.validation.toast.fieldRequired'));
      return;
    }
    let config: Record<string, unknown>;
    try {
      config = JSON.parse(newConfigJson);
    } catch {
      showToast('error', t('admin.validation.toast.invalidJson'));
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
      showToast('success', t('admin.validation.toast.created'));
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
    if (!confirm(t('admin.validation.confirm.delete', { field: rule.field_name }))) return;
    try {
      await deleteValidationRule(rule.id);
      showToast('success', t('admin.validation.toast.deleted'));
      await loadRules();
    } catch (err: any) {
      showToast('error', err.message);
    }
  };

  return (
    <section className="register-card">
      <div className="admin-header-row">
        <div>
          <h2 className="register-title">{t('admin.validation.title')}</h2>
          <p className="register-hint">{t('admin.validation.subtitle')}</p>
        </div>
        <div className="admin-header-actions">
          <select
            className="register-input admin-select"
            value={selectedCode}
            onChange={e => setSelectedCode(e.target.value)}
          >
            <option value="">{t('admin.validation.selectStation')}</option>
            {stations.map(s => (
              <option key={s.id} value={s.code}>{s.code} ({s.name})</option>
            ))}
          </select>
          <button className="btn" onClick={loadRules} disabled={loading || !selectedCode}>
            {loading ? t('common.loading') : t('admin.validation.btn.load')}
          </button>
        </div>
      </div>

      {selectedCode && (
        <details className="register-details">
          <summary className="register-summary">{t('admin.validation.form.title')}</summary>
          <div className="admin-form-grid">
            <label className="register-label">
              {t('admin.validation.form.fieldName')}
              <input className="register-input" value={newField} onChange={e => setNewField(e.target.value)} placeholder={t('admin.validation.form.fieldNamePlaceholder')} />
            </label>
            <label className="register-label">
              {t('admin.validation.form.ruleType')}
              <select className="register-input" value={newType} onChange={e => setNewType(e.target.value)}>
                <option value="enum">enum</option>
                <option value="range">range</option>
                <option value="regex">regex</option>
                <option value="required">required</option>
              </select>
            </label>
            <label className="register-label">
              {t('admin.validation.form.config')}
              <textarea
                className="register-input"
                value={newConfigJson}
                onChange={e => setNewConfigJson(e.target.value)}
                rows={3}
                style={{ fontFamily: 'monospace', fontSize: '0.85rem' }}
                placeholder={t('admin.validation.form.configPlaceholder')}
              />
            </label>
          </div>
          <div className="register-actions">
            <button className="btn btn-primary" onClick={handleCreate} disabled={creating}>
              {creating ? t('admin.validation.btn.creating') : t('admin.validation.btn.create')}
            </button>
          </div>
        </details>
      )}

      <div className="admin-table-wrap">
        <table className="admin-table">
          <thead>
            <tr>
              <th>{t('admin.validation.table.colField')}</th>
              <th>{t('admin.validation.table.colType')}</th>
              <th>{t('admin.validation.table.colConfig')}</th>
              <th>{t('admin.validation.table.colActions')}</th>
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
                    {t('admin.validation.btn.toggle')}
                  </button>
                  <button className="btn btn-small" onClick={() => handleDelete(r)} style={{ marginLeft: 8 }}>
                    {t('admin.validation.btn.delete')}
                  </button>
                </td>
              </tr>
            ))}
            {!rules.length && (
              <tr><td colSpan={4} className="admin-empty">{selectedCode ? t('admin.validation.table.emptyNoRules') : t('admin.validation.table.emptySelectFirst')}</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}
