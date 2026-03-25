/**
 * StationManager — CRUD for stations and their schemas.
 * Used as a tab inside AdminPage.
 */

import { useEffect, useState } from 'react';
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
      showToast('error', err.message || 'Failed to load stations');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { refresh(); }, []);

  const handleCreate = async () => {
    if (!newCode.trim() || !newName.trim()) {
      showToast('error', 'Code and Name are required');
      return;
    }
    setCreating(true);
    try {
      await createStation({ code: newCode.trim(), name: newName.trim(), sort_order: newSort, has_items: newHasItems });
      showToast('success', `Station ${newCode} created`);
      setNewCode(''); setNewName(''); setNewSort(0); setNewHasItems(false);
      await refresh();
    } catch (err: any) {
      showToast('error', err.message);
    } finally {
      setCreating(false);
    }
  };

  const handleDelete = async (code: string) => {
    if (!confirm(`Delete station ${code}? This will also delete its schema, records, and links.`)) return;
    try {
      await deleteStation(code);
      showToast('success', `Station ${code} deleted`);
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
      showToast('success', `Station ${station.code} updated`);
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
      showToast('success', `Schema for ${editingSchemaCode} saved`);
      setEditingSchemaCode(null);
    } catch (err: any) {
      showToast('error', err.message || 'Invalid JSON');
    }
  };

  return (
    <section className="register-card">
      <div className="admin-header-row">
        <div>
          <h2 className="register-title">Station Management</h2>
          <p className="register-hint">Manage workstations and their schema definitions.</p>
        </div>
        <button className="btn" onClick={refresh} disabled={loading}>
          {loading ? 'Loading...' : 'Refresh'}
        </button>
      </div>

      <details className="register-details">
        <summary className="register-summary">Add Station</summary>
        <div className="admin-form-grid">
          <label className="register-label">
            Code
            <input className="register-input" value={newCode} onChange={e => setNewCode(e.target.value)} placeholder="e.g. P4" />
          </label>
          <label className="register-label">
            Name
            <input className="register-input" value={newName} onChange={e => setNewName(e.target.value)} placeholder="e.g. Assembly" />
          </label>
          <label className="register-label">
            Sort Order
            <input className="register-input" type="number" value={newSort} onChange={e => setNewSort(Number(e.target.value))} />
          </label>
          <label className="register-label" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <input type="checkbox" checked={newHasItems} onChange={e => setNewHasItems(e.target.checked)} />
            Has Items
          </label>
        </div>
        <div className="register-actions">
          <button className="btn btn-primary" onClick={handleCreate} disabled={creating}>
            {creating ? 'Creating...' : 'Create Station'}
          </button>
        </div>
      </details>

      <div className="admin-table-wrap">
        <table className="admin-table">
          <thead>
            <tr>
              <th>Code</th>
              <th>Name</th>
              <th>Sort</th>
              <th>Has Items</th>
              <th>Actions</th>
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
                    Schema
                  </button>
                  <button className="btn btn-small" onClick={() => handleDelete(s.code)} style={{ marginLeft: 8 }}>
                    Delete
                  </button>
                </td>
              </tr>
            ))}
            {!stations.length && (
              <tr><td colSpan={5} className="admin-empty">No stations</td></tr>
            )}
          </tbody>
        </table>
      </div>

      {editingSchemaCode && (
        <div style={{ marginTop: 16, padding: 16, border: '1px solid #e5e7eb', borderRadius: 12, background: '#fafafa' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
            <h3 style={{ margin: 0 }}>Schema: {editingSchemaCode}</h3>
            <div style={{ display: 'flex', gap: 8 }}>
              <button className="btn btn-primary" onClick={handleSaveSchema}>Save</button>
              <button className="btn" onClick={() => setEditingSchemaCode(null)}>Cancel</button>
            </div>
          </div>
          {schemaLoading ? (
            <p>Loading schema...</p>
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
