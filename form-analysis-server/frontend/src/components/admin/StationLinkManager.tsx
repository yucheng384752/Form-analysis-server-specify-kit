/**
 * StationLinkManager — CRUD for station traceability links.
 * Used as a tab inside AdminPage.
 */

import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
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
  const { t } = useTranslation();
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
      showToast('error', t('admin.links.toast.requiredStations'));
      return;
    }
    if (fromCode === toCode) {
      showToast('error', t('admin.links.toast.sameStation'));
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
      showToast('success', t('admin.links.toast.created', { from: fromCode, to: toCode }));
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
    if (!confirm(t('admin.links.confirm.delete', { from: link.from_station_code, to: link.to_station_code }))) return;
    try {
      await deleteStationLink(link.id);
      showToast('success', t('admin.links.toast.deleted'));
      await refresh();
    } catch (err: any) {
      showToast('error', err.message);
    }
  };

  return (
    <section className="register-card">
      <div className="admin-header-row">
        <div>
          <h2 className="register-title">{t('admin.links.title')}</h2>
          <p className="register-hint">{t('admin.links.subtitle')}</p>
        </div>
        <button className="btn" onClick={refresh} disabled={loading}>
          {loading ? t('common.loading') : t('admin.links.btn.refresh')}
        </button>
      </div>

      <details className="register-details">
        <summary className="register-summary">{t('admin.links.form.title')}</summary>
        <div className="admin-form-grid">
          <label className="register-label">
            {t('admin.links.form.fromStation')}
            <select className="register-input" value={fromCode} onChange={e => setFromCode(e.target.value)}>
              <option value="">{t('admin.links.form.stationPlaceholder')}</option>
              {stations.map(s => (
                <option key={s.id} value={s.code}>{s.code} ({s.name})</option>
              ))}
            </select>
          </label>
          <label className="register-label">
            {t('admin.links.form.toStation')}
            <select className="register-input" value={toCode} onChange={e => setToCode(e.target.value)}>
              <option value="">{t('admin.links.form.stationPlaceholder')}</option>
              {stations.map(s => (
                <option key={s.id} value={s.code}>{s.code} ({s.name})</option>
              ))}
            </select>
          </label>
          <label className="register-label">
            {t('admin.links.form.linkType')}
            <select className="register-input" value={linkType} onChange={e => setLinkType(e.target.value)}>
              <option value="lot_no">lot_no</option>
              <option value="custom">custom</option>
            </select>
          </label>
          <label className="register-label">
            {t('admin.links.form.sortOrder')}
            <input className="register-input" type="number" value={sortOrder} onChange={e => setSortOrder(Number(e.target.value))} />
          </label>
        </div>
        <div className="register-actions">
          <button className="btn btn-primary" onClick={handleCreate} disabled={creating}>
            {creating ? t('admin.links.btn.creating') : t('admin.links.btn.create')}
          </button>
        </div>
      </details>

      <div className="admin-table-wrap">
        <table className="admin-table">
          <thead>
            <tr>
              <th>{t('admin.links.table.colFrom')}</th>
              <th>{t('admin.links.table.colTo')}</th>
              <th>{t('admin.links.table.colType')}</th>
              <th>{t('admin.links.table.colSort')}</th>
              <th>{t('admin.links.table.colActions')}</th>
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
                  <button className="btn btn-small" onClick={() => handleDelete(l)}>{t('admin.links.btn.delete')}</button>
                </td>
              </tr>
            ))}
            {!links.length && (
              <tr><td colSpan={5} className="admin-empty">{t('admin.links.table.empty')}</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}
