import React, { useState, useEffect } from 'react';
import '../styles/traceability-flow.css';

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
}

export const TraceabilityFlow: React.FC<TraceabilityFlowProps> = ({ productId, preloadedData, onClose, onRecordClick }) => {
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
        const response = await fetch(`/api/traceability/product/${productId}`);
        if (!response.ok) {
          throw new Error('無法獲取追溯資料');
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
  }, [productId, preloadedData]);

  if (loading) return <div className="trace-loading">載入追溯資料中...</div>;
  if (error) return <div className="trace-error">錯誤: {error}</div>;
  if (!data) return null;

  const renderCard = (title: string, record: any, type: 'P1' | 'P2' | 'P3') => {
    if (!record) {
      return (
        <div className={`trace-card trace-card-${type.toLowerCase()} missing`}>
          <div className="trace-card-header">
            <h4>{title}</h4>
          </div>
          <div className="trace-card-body">
            <p>無資料</p>
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
        title="點擊查看詳細資料"
      >
        <div className="trace-card-header">
          <h4>{title}</h4>
        </div>
        <div className="trace-card-body">
          {type === 'P1' && (
            <>
              <div className="trace-row"><label>批號:</label> <span>{record.lot_no || <span style={{color: 'red'}}>資料缺失</span>}</span></div>
              <div className="trace-row"><label>材料:</label> <span>{record.material_code || '-'}</span></div>
            </>
          )}
          {type === 'P2' && (
            <>
              <div className="trace-row"><label>捲收機號碼:</label> <span>{record.winder_number}</span></div>
              <div className="trace-row"><label>機台:</label> <span>{record.machine_no || '-'}</span></div>
              <div className="trace-row"><label>半成品:</label> <span>{record.lot_no}</span></div>
              {/* <div className="trace-row"><label>半成品:</label> <span>{record.material_code || '-'}</span></div> */}
            </>
          )}
          {type === 'P3' && (
            <>
              <div className="trace-row"><label>ID:</label> <span title={record.product_id}>{record.product_id}</span></div>
              <div className="trace-row"><label>批號:</label> <span>{record.lot_no}</span></div>
              <div className="trace-row"><label>模號:</label> <span>{record.mold_no}</span></div>
              <div className="trace-row"><label>生產序號:</label> <span>{record.production_lot}</span></div>
            </>
          )}
        </div>
      </div>
    );
  };

  return (
    <div className="traceability-container">
      <div className="traceability-header">
        <h3>生產追溯流程圖</h3>
        <button className="close-btn" onClick={onClose}>&times;</button>
      </div>
      
      <div className="trace-flow">
        {renderCard('P1 原料', data.p1, 'P1')}
        <div className={`trace-arrow ${!data.p1 || !data.p2 ? 'broken' : ''}`}>➜</div>
        {renderCard('P2 半成品', data.p2, 'P2')}
        <div className={`trace-arrow ${!data.p2 || !data.p3 ? 'broken' : ''}`}>➜</div>
        {renderCard('P3 成品', data.p3, 'P3')}
      </div>

      {!data.trace_complete && (
        <div className="trace-warning">
          追溯鏈不完整: {data.missing_links.join(', ')}
        </div>
      )}
    </div>
  );
};
