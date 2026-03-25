/**
 * StationLinkManager — CRUD for station traceability links.
 * Used as a tab inside AdminPage.
 */

import { useEffect, useState } from 'react';
import type { StationInfo, StationLinkInfo } from '../../types/api';
import {
  fetchStations,
  fetchStationLinks,
  createStationLink,
  updateStationLink,
  deleteStationLink,
} from '../../services/stationApi';

interface Props {
  showToast: (type: 'success' | 'error' | 'info', msg: string) => void;
}

export function StationLinkManager({ showToast }: Props) {
  const [stations, setStations] = useState<StationInfo[]>([]);
  const [links, setLinks] = useState<StationLinkInfo[]>([]);
  const [loading, setLoading] = useState(false);

  // create form
  const [fromCode, setFromCode] = useState('');
  const [toCode, setToCode] = useState('');
  const [linkType, setLinkType] = useState('lot_no');
  const [sortOrder, setSortOrder] = useState(0);
  const [creating, setCreating] = useState(false);

  const refresh = async () => {
    setLoading(true);
    try {
      const [stationData, linkData] = await Promise.all([
        fetchStations(),
        fetchStationLinks(),
      ]);
      setStations(stationData);
      setLinks(linkData);
    } catch (err: any) {
      showToast('error', err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { refresh(); }, []);

  const handleCreate = async () => {
    if (!fromCode || !toCode) {
      showToast('error', 'Select both From and To stations');
      return;
    }
    if (fromCode === toCode) {
      showToast('error', 'From and To cannot be the same station');
      return;
    }
    setCreating(true);
    try {
      await createStationLink({
        from_station_code: fromCode,
        to_station_code: toCode,
        link_type: linkType,
        sort_order: sortOrder,
      });
      showToast('success', `Link ${fromCode} -> ${toCode} created`);
      setFromCode(''); setToCode(''); setSortOrder(0);
      await refresh();
    } catch (err: any) {
      showToast('error', err.message);
    } finally {
      setCreating(false);
    }
  };

  const handleSortBlur = async (link: StationLinkInfo, newVal: string) => {
    const n = parseInt(newVal, 10);
    if (isNaN(n)) return;
    try {
      await updateStationLink(link.id, { sort_order: n });
      await refresh();
    } catch (err: any) {
      showToast('error', err.message);
    }
  };

  const handleDelete = async (link: StationLinkInfo) => {
    if (!confirm(`Delete link ${link.from_station_code} -> ${link.to_station_code}?`)) return;
    try {
      await deleteStationLink(link.id);
      showToast('success', 'Link deleted');
      await refresh();
    } catch (err: any) {
      showToast('error', err.message);
    }
  };

  return (
    <section className="register-card">
      <div className="admin-header-row">
        <div>
          <h2 className="register-title">Station Links (Traceability)</h2>
          <p className="register-hint">Define traceability relationships between stations.</p>
        </div>
        <button className="btn" onClick={refresh} disabled={loading}>
          {loading ? 'Loading...' : 'Refresh'}
        </button>
      </div>

      <details className="register-details">
        <summary className="register-summary">Add Link</summary>
        <div className="admin-form-grid">
          <label className="register-label">
            From Station
            <select className="register-input" value={fromCode} onChange={e => setFromCode(e.target.value)}>
              <option value="">Select...</option>
              {stations.map(s => (
                <option key={s.id} value={s.code}>{s.code} ({s.name})</option>
              ))}
            </select>
          </label>
          <label className="register-label">
            To Station
            <select className="register-input" value={toCode} onChange={e => setToCode(e.target.value)}>
              <option value="">Select...</option>
              {stations.map(s => (
                <option key={s.id} value={s.code}>{s.code} ({s.name})</option>
              ))}
            </select>
          </label>
          <label className="register-label">
            Link Type
            <select className="register-input" value={linkType} onChange={e => setLinkType(e.target.value)}>
              <option value="lot_no">lot_no</option>
              <option value="custom">custom</option>
            </select>
          </label>
          <label className="register-label">
            Sort Order
            <input className="register-input" type="number" value={sortOrder} onChange={e => setSortOrder(Number(e.target.value))} />
          </label>
        </div>
        <div className="register-actions">
          <button className="btn btn-primary" onClick={handleCreate} disabled={creating}>
            {creating ? 'Creating...' : 'Create Link'}
          </button>
        </div>
      </details>

      <div className="admin-table-wrap">
        <table className="admin-table">
          <thead>
            <tr>
              <th>From</th>
              <th>To</th>
              <th>Type</th>
              <th>Sort</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {links.map(l => (
              <tr key={l.id}>
                <td className="admin-mono">{l.from_station_code}</td>
                <td className="admin-mono">{l.to_station_code}</td>
                <td><span className="pill pill-ok">{l.link_type}</span></td>
                <td>
                  <input
                    className="admin-inline-input"
                    type="number"
                    defaultValue={0}
                    style={{ width: 60 }}
                    onBlur={e => handleSortBlur(l, e.target.value)}
                  />
                </td>
                <td>
                  <button className="btn btn-small" onClick={() => handleDelete(l)}>Delete</button>
                </td>
              </tr>
            ))}
            {!links.length && (
              <tr><td colSpan={5} className="admin-empty">No links</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}
