/**
 * GenericTraceabilityFlow — dynamic N-level traceability visualization.
 *
 * Replaces the hardcoded P1→P2→P3 TraceabilityFlow with a schema-driven
 * chain that renders any number of stations from the station_links API.
 */

import React, { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import type { TraceNode } from '../types/api';
import { fetchTraceabilityChain } from '../services/stationApi';

interface GenericTraceabilityFlowProps {
  lotNoNorm: number;
  startStation?: string;
  onClose: () => void;
}

export const GenericTraceabilityFlow: React.FC<GenericTraceabilityFlowProps> = ({
  lotNoNorm,
  startStation,
  onClose,
}) => {
  const { t } = useTranslation();
  const [chain, setChain] = useState<TraceNode[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    fetchTraceabilityChain(lotNoNorm, startStation)
      .then((data) => {
        if (!cancelled) setChain(data);
      })
      .catch((err) => {
        if (!cancelled) setError(err.message ?? 'Failed to fetch traceability');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => { cancelled = true; };
  }, [lotNoNorm, startStation]);

  if (loading) return <div style={{ padding: 24 }}>{t('traceability.loading', 'Loading...')}</div>;
  if (error) return <div style={{ padding: 24, color: 'red' }}>{error}</div>;
  if (chain.length === 0) return <div style={{ padding: 24 }}>{t('traceability.noData', 'No trace data')}</div>;

  return (
    <div style={{ padding: 16 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <h3 style={{ margin: 0 }}>{t('traceability.title', 'Traceability')}</h3>
        <button onClick={onClose} style={{ cursor: 'pointer' }}>✕</button>
      </div>

      <div style={{ display: 'flex', gap: 16, overflowX: 'auto', paddingBottom: 8 }}>
        {chain.map((node, idx) => (
          <React.Fragment key={node.station_code}>
            <StationCard node={node} />
            {idx < chain.length - 1 && (
              <div style={{ display: 'flex', alignItems: 'center', fontSize: 24, color: '#999' }}>→</div>
            )}
          </React.Fragment>
        ))}
      </div>
    </div>
  );
};

// ------------------------------------------------------------------

interface StationCardProps {
  node: TraceNode;
}

const StationCard: React.FC<StationCardProps> = ({ node }) => {
  const hasRecord = !!node.record;

  return (
    <div
      style={{
        border: '1px solid #ddd',
        borderRadius: 8,
        padding: 12,
        minWidth: 220,
        maxWidth: 320,
        background: hasRecord ? '#f8fdf8' : '#fafafa',
        opacity: hasRecord ? 1 : 0.6,
      }}
    >
      <div style={{ fontWeight: 600, marginBottom: 8, fontSize: '1rem' }}>
        {node.station_code} — {node.station_name}
      </div>

      {hasRecord ? (
        <>
          <div style={{ fontSize: '0.85rem', marginBottom: 4 }}>
            <strong>Lot:</strong> {node.record!.lot_no_raw}
          </div>
          <DataFields data={node.record!.data} />
          {node.items.length > 0 && (
            <details style={{ marginTop: 8 }}>
              <summary style={{ cursor: 'pointer', fontSize: '0.85rem' }}>
                {node.items.length} item(s)
              </summary>
              <div style={{ maxHeight: 200, overflowY: 'auto', marginTop: 4 }}>
                {node.items.map((item) => (
                  <div
                    key={item.id}
                    style={{
                      borderTop: '1px solid #eee',
                      paddingTop: 4,
                      marginTop: 4,
                      fontSize: '0.8rem',
                    }}
                  >
                    <div><strong>#{item.row_no}</strong></div>
                    <DataFields data={item.data} />
                  </div>
                ))}
              </div>
            </details>
          )}
        </>
      ) : (
        <div style={{ fontSize: '0.85rem', color: '#999' }}>No data</div>
      )}
    </div>
  );
};

// ------------------------------------------------------------------

const DataFields: React.FC<{ data: Record<string, any> }> = ({ data }) => {
  const entries = Object.entries(data).filter(([, v]) => v != null);
  if (entries.length === 0) return null;

  return (
    <div style={{ fontSize: '0.8rem', lineHeight: 1.5 }}>
      {entries.slice(0, 8).map(([k, v]) => (
        <div key={k}>
          <span style={{ color: '#666' }}>{k}:</span> {String(v)}
        </div>
      ))}
      {entries.length > 8 && (
        <div style={{ color: '#aaa' }}>+{entries.length - 8} more...</div>
      )}
    </div>
  );
};
