import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import '../styles/traceability-flow.css';
import { Drawer, DrawerClose, DrawerContent, DrawerFooter, DrawerHeader, DrawerTitle, DrawerTrigger } from './ui/drawer';

interface TraceabilityData {
  product_id: string;
  p3: any;
  p2: any;
  p1: any;
  trace_complete: boolean;
  missing_links: string[];
}

interface TraceabilityFlowProps {
  productId?: string;
  preloadedData?: TraceabilityData;
  onClose: () => void;
  onRecordClick?: (record: any, type: 'P1' | 'P2' | 'P3') => void;
  tenantId?: string;
}

export const TraceabilityFlow: React.FC<TraceabilityFlowProps> = ({ productId, preloadedData, onClose, onRecordClick, tenantId }) => {
  const { t } = useTranslation();
  const [data, setData] = useState<TraceabilityData | null>(preloadedData || null);
  const [loading, setLoading] = useState(!preloadedData);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (preloadedData) {
      setData(preloadedData);
      setLoading(false);
      return;
    }

    const fetchData = async () => {
      if (!productId) return;
      
      try {
        setLoading(true);
        const headers: HeadersInit = tenantId ? { 'X-Tenant-Id': tenantId } : {};
        const response = await fetch(`/api/traceability/product/${productId}`, { headers });
        if (!response.ok) {
          throw new Error(t('traceability.errors.fetchFailed'));
        }
        const result = await response.json();
        setData(result);
      } catch (err: any) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [productId, preloadedData, tenantId]);

  if (loading) return <div className="trace-loading">{t('traceability.loading')}</div>;
  if (error) return <div className="trace-error">{t('traceability.errorWithDetail', { error })}</div>;
  if (!data) return null;

  const renderCard = (title: string, record: any, type: 'P1' | 'P2' | 'P3') => {
    if (!record) {
      return (
        <div className={`trace-card trace-card-${type.toLowerCase()} missing`}>
          <div className="trace-card-header">
            <h4>{title}</h4>
          </div>
          <div className="trace-card-body">
            <p>{t('traceability.noData')}</p>
          </div>
        </div>
      );
    }

    // 檢查是否有資料內容，避免顯示空卡片
    const hasContent = type === 'P3' ? (record.product_id || record.lot_no) : record.lot_no;
    if (!hasContent) {
      console.warn(`[TraceabilityFlow] ${type} record exists but has no content:`, record);
    }

    return (
      <div 
        className={`trace-card trace-card-${type.toLowerCase()} ${onRecordClick ? 'clickable' : ''}`}
        onClick={() => onRecordClick && onRecordClick(record, type)}
        title={t('traceability.clickToViewDetails')}
      >
        <div className="trace-card-header">
          <h4>{title}</h4>
        </div>
        <div className="trace-card-body">
          {type === 'P1' && (
            <>
              <div className="trace-row"><label>{t('traceability.fields.lotNo')}:</label> <span>{record.lot_no || <span style={{color: 'red'}}>{t('traceability.missingData')}</span>}</span></div>
              <div className="trace-row"><label>{t('traceability.fields.material')}:</label> <span>{record.material_code || record.Material || record.material || '-'}</span></div>
            </>
          )}
          {type === 'P2' && (
            <>
              <div className="trace-row">
                <label>{t('traceability.fields.winderNumber')}:</label>
                <Drawer>
                  <DrawerTrigger
                    type="button"
                    onClick={(e) => e.stopPropagation()}
                    style={{
                      background: 'transparent',
                      border: '1px solid #d1d5db',
                      borderRadius: 8,
                      padding: '2px 10px',
                      cursor: 'pointer',
                    }}
                  >
                    {t('traceability.actions.clickToExpand')}
                  </DrawerTrigger>
                  <DrawerContent onClick={(e) => e.stopPropagation()}>
                    <DrawerHeader>
                      <DrawerTitle>{t('traceability.fields.winderNumber')}</DrawerTitle>
                    </DrawerHeader>
                    <div style={{ padding: '0 16px 16px 16px', fontSize: 18 }}>
                      {record.winder_number ?? '-'}
                    </div>
                    <DrawerFooter>
                      <DrawerClose asChild>
                        <button type="button" style={{
                          borderRadius: 8,
                          padding: '8px 12px',
                          border: '1px solid #d1d5db',
                          background: 'white',
                          cursor: 'pointer',
                        }}>{t('common.close')}</button>
                      </DrawerClose>
                    </DrawerFooter>
                  </DrawerContent>
                </Drawer>
              </div>
              <div className="trace-row"><label>{t('traceability.fields.semiProductNo')}:</label> <span>{record.lot_no}</span></div>
            </>
          )}
          {type === 'P3' && (
            <>
              <div className="trace-row"><label>ID:</label> <span title={record.product_id}>{record.product_id}</span></div>
              <div className="trace-row"><label>{t('traceability.fields.lotNo')}:</label> <span>{record.lot_no}</span></div>
              <div className="trace-row"><label>{t('traceability.fields.moldNo')}:</label> <span>{record.mold_no}</span></div>
              <div className="trace-row"><label>{t('traceability.fields.productionSerial')}:</label> <span>{record.production_lot}</span></div>
            </>
          )}
        </div>
      </div>
    );
  };

  return (
    <div className="traceability-container">
      <div className="traceability-header">
        <h3>{t('traceability.title')}</h3>
        <button className="close-btn" onClick={onClose}>&times;</button>
      </div>
      
      <div className="trace-flow">
        {renderCard(t('traceability.cards.p1'), data.p1, 'P1')}
        <div className={`trace-arrow ${!data.p1 || !data.p2 ? 'broken' : ''}`}>➜</div>
        {renderCard(t('traceability.cards.p2'), data.p2, 'P2')}
        <div className={`trace-arrow ${!data.p2 || !data.p3 ? 'broken' : ''}`}>➜</div>
        {renderCard(t('traceability.cards.p3'), data.p3, 'P3')}
      </div>

      {!data.trace_complete && (
        <div className="trace-warning">
          {t('traceability.chainIncomplete', { links: data.missing_links.join(', ') })}
        </div>
      )}
    </div>
  );
};
