/**
 * AnalyticsMappingManager — CRUD for analytics field mappings.
 * Used as a tab inside AdminPage.
 */

import { useEffect, useState } from 'react';
import type { StationInfo } from '../../types/api';
import {
  fetchStations,
  fetchAnalyticsMapping,
  createAnalyticsMapping,
  updateAnalyticsMapping,
  deleteAnalyticsMapping,
} from '../../services/stationApi';

interface MappingRow {
  id: string;
  source_path: string;
  output_column: string;
  output_order: number;
  data_type: string;
  null_if_missing: boolean;
}

interface Props {
  showToast: (type: 'success' | 'error' | 'info', msg: string) => void;
}

export function AnalyticsMappingManager({ showToast }: Props) {
  const [stations, setStations] = useState<StationInfo[]>([]);
  const [selectedCode, setSelectedCode] = useState('');
  const [mappings, setMappings] = useState<MappingRow[]>([]);
  const [loading, setLoading] = useState(false);

  // create form
  const [newSource, setNewSource] = useState('');
  const [newColumn, setNewColumn] = useState('');
  const [newOrder, setNewOrder] = useState(0);
  const [newDataType, setNewDataType] = useState('string');
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    fetchStations().then(setStations).catch(() => {});
  }, []);

  const loadMappings = async () => {
    if (!selectedCode) return;
    setLoading(true);
    try {
      const data = await fetchAnalyticsMapping(selectedCode);
      setMappings(data);
    } catch (err: any) {
      showToast('error', err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleCreate = async () => {
    if (!newSource.trim() || !newColumn.trim()) {
      showToast('error', 'Source path and output column are required');
      return;
    }
    setCreating(true);
    try {
      await createAnalyticsMapping({
        station_code: selectedCode,
        source_path: newSource.trim(),
        output_column: newColumn.trim(),
        output_order: newOrder,
        data_type: newDataType,
      });
      showToast('success', 'Mapping created');
      setNewSource(''); setNewColumn(''); setNewOrder(0);
      await loadMappings();
    } catch (err: any) {
      showToast('error', err.message);
    } finally {
      setCreating(false);
    }
  };

  const handleOrderBlur = async (m: MappingRow, newVal: string) => {
    const n = parseInt(newVal, 10);
    if (isNaN(n) || n === m.output_order) return;
    try {
      await updateAnalyticsMapping(m.id, { output_order: n });
      await loadMappings();
    } catch (err: any) {
      showToast('error', err.message);
    }
  };

  const handleDelete = async (m: MappingRow) => {
    if (!confirm(`Delete mapping "${m.output_column}"?`)) return;
    try {
      await deleteAnalyticsMapping(m.id);
      showToast('success', 'Mapping deleted');
      await loadMappings();
    } catch (err: any) {
      showToast('error', err.message);
    }
  };

  return (
    <section className="register-card">
      <div className="admin-header-row">
        <div>
          <h2 className="register-title">Analytics Mappings</h2>
          <p className="register-hint">Map JSONB data paths to named analytics output columns.</p>
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
          <button className="btn" onClick={loadMappings} disabled={loading || !selectedCode}>
            {loading ? 'Loading...' : 'Load Mappings'}
          </button>
        </div>
      </div>

      {selectedCode && (
        <details className="register-details">
          <summary className="register-summary">Add Mapping</summary>
          <div className="admin-form-grid">
            <label className="register-label">
              Source Path
              <input className="register-input" value={newSource} onChange={e => setNewSource(e.target.value)} placeholder="e.g. record.data.thickness" />
            </label>
            <label className="register-label">
              Output Column
              <input className="register-input" value={newColumn} onChange={e => setNewColumn(e.target.value)} placeholder="e.g. thickness_mm" />
            </label>
            <label className="register-label">
              Order
              <input className="register-input" type="number" value={newOrder} onChange={e => setNewOrder(Number(e.target.value))} />
            </label>
            <label className="register-label">
              Data Type
              <select className="register-input" value={newDataType} onChange={e => setNewDataType(e.target.value)}>
                <option value="string">string</option>
                <option value="integer">integer</option>
                <option value="float">float</option>
                <option value="date">date</option>
                <option value="boolean">boolean</option>
              </select>
            </label>
          </div>
          <div className="register-actions">
            <button className="btn btn-primary" onClick={handleCreate} disabled={creating}>
              {creating ? 'Creating...' : 'Create Mapping'}
            </button>
          </div>
        </details>
      )}

      <div className="admin-table-wrap">
        <table className="admin-table">
          <thead>
            <tr>
              <th>Order</th>
              <th>Source Path</th>
              <th>Output Column</th>
              <th>Type</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {mappings.map(m => (
              <tr key={m.id}>
                <td>
                  <input
                    className="admin-inline-input"
                    type="number"
                    defaultValue={m.output_order}
                    style={{ width: 60 }}
                    onBlur={e => handleOrderBlur(m, e.target.value)}
                  />
                </td>
                <td className="admin-mono">{m.source_path}</td>
                <td className="admin-mono">{m.output_column}</td>
                <td><span className="pill pill-ok">{m.data_type}</span></td>
                <td>
                  <button className="btn btn-small" onClick={() => handleDelete(m)}>Delete</button>
                </td>
              </tr>
            ))}
            {!mappings.length && (
              <tr><td colSpan={5} className="admin-empty">{selectedCode ? 'No mappings' : 'Select a station first'}</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}
