/**
 * StationManager — CRUD for stations and their schemas.
 * Used as a tab inside AdminPage.
 */

import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import type { StationInfo } from '../../types/api';
import {
  fetchStations,
  fetchStationSchema,
  createStation,
  updateStation,
  deleteStation,
  upsertStationSchema,
} from '../../services/stationApi';

interface Props {
  showToast: (type: 'success' | 'error' | 'info', msg: string) => void;
}

export function StationManager({ showToast }: Props) {
  const { t } = useTranslation();
  const [stations, setStations] = useState<StationInfo[]>([]);
  const [loading, setLoading] = useState(false);

  // create form
  const [newCode, setNewCode] = useState('');
  const [newName, setNewName] = useState('');
  const [newSort, setNewSort] = useState(0);
  const [newHasItems, setNewHasItems] = useState(false);
  const [creating, setCreating] = useState(false);

  // schema editor
  const [editingSchemaCode, setEditingSchemaCode] = useState<string | null>(null);
  const [schemaJson, setSchemaJson] = useState('');
  const [schemaLoading, setSchemaLoading] = useState(false);

  const refresh = async () => {
    setLoading(true);
    try {
      const data = await fetchStations();
      setStations(data);
    } catch (err: any) {
      showToast('error', err.message || t('admin.stations.toast.failedLoad'));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { refresh(); }, []);

  const handleCreate = async () => {
    if (!newCode.trim() || !newName.trim()) {
      showToast('error', t('admin.stations.toast.requiredFields'));
      return;
    }
    setCreating(true);
    try {
      await createStation({ code: newCode.trim(), name: newName.trim(), sort_order: newSort, has_items: newHasItems });
      showToast('success', t('admin.stations.toast.created', { code: newCode }));
      setNewCode(''); setNewName(''); setNewSort(0); setNewHasItems(false);
      await refresh();
    } catch (err: any) {
      showToast('error', err.message);
    } finally {
      setCreating(false);
    }
  };

  const handleDelete = async (code: string) => {
    if (!confirm(t('admin.stations.confirm.delete', { code }))) return;
    try {
      await deleteStation(code);
      showToast('success', t('admin.stations.toast.deleted', { code }));
      await refresh();
    } catch (err: any) {
      showToast('error', err.message);
    }
  };

  const handleNameBlur = async (station: StationInfo, newVal: string) => {
    const v = newVal.trim();
    if (!v || v === station.name) return;
    try {
      await updateStation(station.code, { name: v });
      showToast('success', t('admin.stations.toast.updated', { code: station.code }));
      await refresh();
    } catch (err: any) {
      showToast('error', err.message);
    }
  };

  const handleSortBlur = async (station: StationInfo, newVal: string) => {
    const n = parseInt(newVal, 10);
    if (isNaN(n) || n === station.sort_order) return;
    try {
      await updateStation(station.code, { sort_order: n });
      await refresh();
    } catch (err: any) {
      showToast('error', err.message);
    }
  };

  const handleToggleItems = async (station: StationInfo) => {
    try {
      await updateStation(station.code, { has_items: !station.has_items });
      await refresh();
    } catch (err: any) {
      showToast('error', err.message);
    }
  };

  const openSchemaEditor = async (code: string) => {
    setEditingSchemaCode(code);
    setSchemaLoading(true);
    try {
      const schema = await fetchStationSchema(code);
      setSchemaJson(JSON.stringify({
        record_fields: schema.record_fields,
        item_fields: schema.item_fields,
        unique_key_fields: schema.unique_key_fields,
      }, null, 2));
    } catch {
      setSchemaJson('{\n  "record_fields": [],\n  "item_fields": null,\n  "unique_key_fields": []\n}');
    } finally {
      setSchemaLoading(false);
    }
  };

  const handleSaveSchema = async () => {
    if (!editingSchemaCode) return;
    try {
      const parsed = JSON.parse(schemaJson);
      await upsertStationSchema(editingSchemaCode, parsed);
      showToast('success', t('admin.stations.schema.saved', { code: editingSchemaCode }));
      setEditingSchemaCode(null);
    } catch (err: any) {
      showToast('error', err.message || t('admin.stations.toast.invalidJson'));
    }
  };

  return (
    <section className="register-card">
      <div className="admin-header-row">
        <div>
          <h2 className="register-title">{t('admin.stations.title')}</h2>
          <p className="register-hint">{t('admin.stations.subtitle')}</p>
        </div>
        <button className="btn" onClick={refresh} disabled={loading}>
          {t('admin.stations.btn.refresh')}
        </button>
      </div>

      <details className="register-details">
        <summary className="register-summary">{t('admin.stations.form.title')}</summary>
        <div className="admin-form-grid">
          <label className="register-label">
            {t('admin.stations.form.code')}
            <input className="register-input" value={newCode} onChange={e => setNewCode(e.target.value)} placeholder={t('admin.stations.form.codePlaceholder')} />
          </label>
          <label className="register-label">
            {t('admin.stations.form.name')}
            <input className="register-input" value={newName} onChange={e => setNewName(e.target.value)} placeholder={t('admin.stations.form.namePlaceholder')} />
          </label>
          <label className="register-label">
            {t('admin.stations.form.sortOrder')}
            <input className="register-input" type="number" value={newSort} onChange={e => setNewSort(Number(e.target.value))} />
          </label>
          <label className="register-label" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <input type="checkbox" checked={newHasItems} onChange={e => setNewHasItems(e.target.checked)} />
            {t('admin.stations.form.hasItems')}
          </label>
        </div>
        <div className="register-actions">
          <button className="btn btn-primary" onClick={handleCreate} disabled={creating}>
            {creating ? t('admin.stations.btn.creating') : t('admin.stations.btn.create')}
          </button>
        </div>
      </details>

      <div className="admin-table-wrap">
        <table className="admin-table">
          <thead>
            <tr>
              <th>{t('admin.stations.table.colCode')}</th>
              <th>{t('admin.stations.table.colName')}</th>
              <th>{t('admin.stations.table.colSort')}</th>
              <th>{t('admin.stations.table.colHasItems')}</th>
              <th>{t('admin.stations.table.colActions')}</th>
            </tr>
          </thead>
          <tbody>
            {stations.map(s => (
              <tr key={s.id}>
                <td className="admin-mono">{s.code}</td>
                <td>
                  <input
                    className="admin-inline-input"
                    defaultValue={s.name}
                    onBlur={e => handleNameBlur(s, e.target.value)}
                  />
                </td>
                <td>
                  <input
                    className="admin-inline-input"
                    type="number"
                    defaultValue={s.sort_order}
                    style={{ width: 60 }}
                    onBlur={e => handleSortBlur(s, e.target.value)}
                  />
                </td>
                <td>
                  <input type="checkbox" checked={s.has_items} onChange={() => handleToggleItems(s)} />
                </td>
                <td>
                  <button className="btn btn-small" onClick={() => openSchemaEditor(s.code)}>
                    {t('admin.stations.btn.schema')}
                  </button>
                  <button className="btn btn-small" onClick={() => handleDelete(s.code)} style={{ marginLeft: 8 }}>
                    {t('admin.stations.btn.delete')}
                  </button>
                </td>
              </tr>
            ))}
            {!stations.length && (
              <tr><td colSpan={5} className="admin-empty">{t('admin.stations.table.empty')}</td></tr>
            )}
          </tbody>
        </table>
      </div>

      {editingSchemaCode && (
        <div style={{ marginTop: 16, padding: 16, border: '1px solid #e5e7eb', borderRadius: 12, background: '#fafafa' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
            <h3 style={{ margin: 0 }}>{t('admin.stations.schema.title', { code: editingSchemaCode })}</h3>
            <div style={{ display: 'flex', gap: 8 }}>
              <button className="btn btn-primary" onClick={handleSaveSchema}>{t('admin.stations.btn.save')}</button>
              <button className="btn" onClick={() => setEditingSchemaCode(null)}>{t('admin.stations.btn.cancel')}</button>
            </div>
          </div>
          {schemaLoading ? (
            <p>{t('admin.stations.schema.loading')}</p>
          ) : (
            <textarea
              value={schemaJson}
              onChange={e => setSchemaJson(e.target.value)}
              style={{ width: '100%', minHeight: 300, fontFamily: 'monospace', fontSize: '0.85rem', padding: 8, border: '1px solid #d1d5db', borderRadius: 8 }}
            />
          )}
        </div>
      )}
    </section>
  );
}
