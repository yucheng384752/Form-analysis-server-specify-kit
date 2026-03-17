import React from 'react'
import { useTranslation } from 'react-i18next'
import type { QueryRecord } from './types'
import {
  formatFieldValue,
  formatCell,
  generateRowProductId,
  getFlattenedAdditionalData,
  getValueByKeyRegex,
  getRowFieldValue,
  isNgLike,
} from './utils'

// ── Detail renderers used in traceability panel & detail modal ──

interface RecordDetailContentProps {
  record: QueryRecord
  collapsedSections: { [key: string]: boolean }
  onToggleSection: (recordId: string, sectionKey: string) => void
}

export function RecordDetailContent({ record, collapsedSections, onToggleSection }: RecordDetailContentProps) {
  switch (record.data_type) {
    case 'P1':
      return <P1Details record={record} collapsedSections={collapsedSections} onToggleSection={onToggleSection} />
    case 'P2':
      return <P2Details record={record} />
    case 'P3':
      return <P3Details record={record} />
    default:
      return null
  }
}

// ── P1 Details ──

function P1Details({
  record,
  collapsedSections,
  onToggleSection,
}: RecordDetailContentProps) {
  return (
    <div className="detail-grid" style={{ gridColumn: '1 / -1' }}>
      <P1PaperLayoutDetail record={record} collapsedSections={collapsedSections} onToggleSection={onToggleSection} />
    </div>
  )
}

function CollapsibleSection({
  recordId,
  title,
  sectionKey,
  children,
  icon = '',
  collapsedSections,
  onToggleSection,
}: {
  recordId: string
  title: string
  sectionKey: string
  children: React.ReactNode
  icon?: string
  collapsedSections: { [key: string]: boolean }
  onToggleSection: (recordId: string, sectionKey: string) => void
}) {
  const { t } = useTranslation()
  const isCollapsed = collapsedSections[`${recordId}-${sectionKey}`] || false

  return (
    <div className="data-section" key={sectionKey}>
      <div className="section-header">
        <div className="section-title-wrapper">
          {icon ? <span className="section-icon">{icon}</span> : <span className="section-icon"></span>}
          <h5>{title}</h5>
        </div>
        <button className="btn-collapse" onClick={() => onToggleSection(recordId, sectionKey)}>
          {isCollapsed ? t('common.expand') : t('common.collapse')}
        </button>
      </div>
      {!isCollapsed && <div className="section-content">{children}</div>}
    </div>
  )
}

function P1CheckboxGroup({ title, options, selectedRaw }: { title: string; options: string[]; selectedRaw: any }) {
  const { t } = useTranslation()
  const selected = selectedRaw === null || selectedRaw === undefined ? '' : String(selectedRaw).trim()
  const normalizedSelected = selected.replace(/\s+/g, '').toLowerCase()
  const matched = options.find((o) => o.replace(/\s+/g, '').toLowerCase() === normalizedSelected)
  const otherValue = matched ? '' : selected

  return (
    <div className="p1-paper-checkbox-group">
      <div className="p1-paper-checkbox-title">{title}</div>
      <div className="p1-paper-checkbox-options">
        {options.map((o) => {
          const isChecked = !!matched && o === matched
          return (
            <div key={o} className={`p1-paper-checkbox ${isChecked ? 'is-checked' : ''}`}>
              <span className="p1-paper-box" aria-hidden="true"></span>
              <span className="p1-paper-checkbox-label">{o}</span>
            </div>
          )
        })}
        <div className={`p1-paper-checkbox ${otherValue ? 'is-checked' : ''}`}>
          <span className="p1-paper-box" aria-hidden="true"></span>
          <span className="p1-paper-checkbox-label">{t('common.other')}</span>
          <span className="p1-paper-checkbox-other">{otherValue || ''}</span>
        </div>
      </div>
    </div>
  )
}

function P1PaperLayoutDetail({
  record,
  collapsedSections,
  onToggleSection,
}: RecordDetailContentProps) {
  const { t } = useTranslation()
  const data = getFlattenedAdditionalData(record.additional_data)

  const specValue = getValueByKeyRegex(data, [/^specification$/i, /specification/i]) ?? record.product_name
  const materialValue = getValueByKeyRegex(data, [/^material$/i, /material/i])
  const startTime = getValueByKeyRegex(data, [/production\s*time.*start/i, /start\s*time/i, /\bstart\b.*time/i])
  const endTime = getValueByKeyRegex(data, [/production\s*time.*end/i, /end\s*time/i, /\bend\b.*time/i])

  const cCols = Array.from({ length: 16 }, (_, i) => i + 1)
  const extrusionActual = cCols.map((i) =>
    getValueByKeyRegex(data, [new RegExp(`^actual\\s*temp.*c${i}\\b`, 'i'), new RegExp(`^actual[_\\s]*temp.*c${i}\\b`, 'i')])
  )
  const extrusionSet = cCols.map((i) =>
    getValueByKeyRegex(data, [new RegExp(`^set\\s*temp.*c${i}\\b`, 'i'), new RegExp(`^set[_\\s]*temp.*c${i}\\b`, 'i')])
  )

  const dryerCols = ['A', 'B', 'C'] as const
  const dryerActual = dryerCols.map((b) =>
    getValueByKeyRegex(data, [new RegExp(`^actual\\s*temp.*${b}.*bucket`, 'i'), new RegExp(`^actual[_\\s]*temp.*${b}.*bucket`, 'i')])
  )
  const dryerSet = dryerCols.map((b) =>
    getValueByKeyRegex(data, [new RegExp(`^set\\s*temp.*${b}.*bucket`, 'i'), new RegExp(`^set[_\\s]*temp.*${b}.*bucket`, 'i')])
  )

  const extCols = [
    { key: 'Top', label: t('query.p1.paper.extWheel.top') },
    { key: 'Mid', label: t('query.p1.paper.extWheel.mid') },
    { key: 'Bottom', label: t('query.p1.paper.extWheel.bottom') },
  ] as const
  const extActual = extCols.map((c) =>
    getValueByKeyRegex(data, [new RegExp(`^actual\\s*temp.*${c.key}`, 'i'), new RegExp(`^actual[_\\s]*temp.*${c.key}`, 'i')])
  )
  const extSet = extCols.map((c) =>
    getValueByKeyRegex(data, [new RegExp(`^set\\s*temp.*${c.key}`, 'i'), new RegExp(`^set[_\\s]*temp.*${c.key}`, 'i')])
  )

  const params = [
    { label: t('query.p1.paper.params.lineSpeed'), value: getValueByKeyRegex(data, [/^line\s*speed/i, /^line_speed/i]), unit: 'M/min' },
    { label: t('query.p1.paper.params.screwPressure'), value: getValueByKeyRegex(data, [/^screw\s*pressure/i, /^screw_pressure/i]), unit: 'psi' },
    { label: t('query.p1.paper.params.screwOutput'), value: getValueByKeyRegex(data, [/^screw\s*output/i, /^screw_output/i]), unit: '%' },
    { label: t('query.p1.paper.params.leftPadThickness'), value: getValueByKeyRegex(data, [/^left\s*pad\s*thickness/i, /^left_pad_thickness/i]), unit: 'mm' },
    { label: t('query.p1.paper.params.rightPadThickness'), value: getValueByKeyRegex(data, [/^right\s*pad\s*thickness/i, /^right_pad_thickness/i]), unit: 'mm' },
    { label: t('query.p1.paper.params.current'), value: getValueByKeyRegex(data, [/^current\s*\(a\)/i, /^current\(a\)/i, /^current$/i]), unit: 'A' },
    { label: t('query.p1.paper.params.extruderSpeed'), value: getValueByKeyRegex(data, [/^extruder\s*speed/i, /^extruder_speed/i]), unit: 'rpm' },
    { label: t('query.p1.paper.params.quantitativePressure'), value: getValueByKeyRegex(data, [/^quantitative\s*pressure/i, /^quantitative_pressure/i]), unit: 'psi' },
    { label: t('query.p1.paper.params.quantitativeOutput'), value: getValueByKeyRegex(data, [/^quantitative\s*output/i, /^quantitative_output/i]), unit: '%' },
    { label: t('query.p1.paper.params.frame'), value: getValueByKeyRegex(data, [/^frame/i, /^carriage/i]), unit: 'cm' },
    { label: t('query.p1.paper.params.filterPressure'), value: getValueByKeyRegex(data, [/^filter\s*pressure/i, /^filter_pressure/i]), unit: 'psi' },
  ]

  return (
    <div className="p1-paper">
      <div className="p1-paper-header">
        <div className="p1-paper-header-item">
          <div className="p1-paper-header-label">{t('query.fields.productionDate')}</div>
          <div className="p1-paper-header-value">{record.production_date ? formatFieldValue('production_date', record.production_date) : '-'}</div>
        </div>
        <div className="p1-paper-header-item">
          <div className="p1-paper-header-label">{t('query.fields.lotNo')}</div>
          <div className="p1-paper-header-value">{record.lot_no}</div>
        </div>
        <div className="p1-paper-header-item">
          <div className="p1-paper-header-label">{t('query.p1.paper.productionTimeStart')}</div>
          <div className="p1-paper-header-value">{formatCell(startTime)}</div>
        </div>
        <div className="p1-paper-header-item">
          <div className="p1-paper-header-label">{t('query.p1.paper.productionTimeEnd')}</div>
          <div className="p1-paper-header-value">{formatCell(endTime)}</div>
        </div>
      </div>

      <div className="p1-paper-header">
        <P1CheckboxGroup title={t('query.p1.paper.specification')} options={['0.30mm','0.32mm','0.33mm','0.35mm','0.40mm','0.44mm','0.45mm','0.50mm','0.60mm']} selectedRaw={specValue} />
        <P1CheckboxGroup title={t('query.p1.paper.material')} options={['H2','H8','H5']} selectedRaw={materialValue} />
      </div>

      <CollapsibleSection recordId={record.id} title={t('query.sections.extrusionConditions')} sectionKey="p1_extrusion_detail" collapsedSections={collapsedSections} onToggleSection={onToggleSection}>
        <div className="table-container">
          <table className="p1-paper-table">
            <thead><tr><th></th>{cCols.map((i) => <th key={i}>C{i}</th>)}</tr></thead>
            <tbody>
              <tr><th>{t('query.p1.paper.actualTemp')}</th>{extrusionActual.map((v, idx) => <td key={idx}>{formatCell(v)}</td>)}</tr>
              <tr><th>{t('query.p1.paper.setTemp')}</th>{extrusionSet.map((v, idx) => <td key={idx}>{formatCell(v)}</td>)}</tr>
            </tbody>
          </table>
        </div>
      </CollapsibleSection>

      <CollapsibleSection recordId={record.id} title={t('query.p1.paper.sections.dryerTemps')} sectionKey="p1_dryer_detail" collapsedSections={collapsedSections} onToggleSection={onToggleSection}>
        <div className="table-container">
          <table className="p1-paper-table">
            <thead><tr><th></th><th>A</th><th>B</th><th>C</th></tr></thead>
            <tbody>
              <tr><th>{t('query.p1.paper.actualTemp')}</th>{dryerActual.map((v, idx) => <td key={idx}>{formatCell(v)}</td>)}</tr>
              <tr><th>{t('query.p1.paper.setTemp')}</th>{dryerSet.map((v, idx) => <td key={idx}>{formatCell(v)}</td>)}</tr>
            </tbody>
          </table>
        </div>
      </CollapsibleSection>

      <CollapsibleSection recordId={record.id} title={t('query.p1.paper.sections.extWheelTemps')} sectionKey="p1_extwheel_detail" collapsedSections={collapsedSections} onToggleSection={onToggleSection}>
        <div className="table-container">
          <table className="p1-paper-table">
            <thead><tr><th></th>{extCols.map((c) => <th key={c.key}>{c.label}</th>)}</tr></thead>
            <tbody>
              <tr><th>{t('query.p1.paper.actualTemp')}</th>{extActual.map((v, idx) => <td key={idx}>{formatCell(v)}</td>)}</tr>
              <tr><th>{t('query.p1.paper.setTemp')}</th>{extSet.map((v, idx) => <td key={idx}>{formatCell(v)}</td>)}</tr>
            </tbody>
          </table>
        </div>
      </CollapsibleSection>

      <CollapsibleSection recordId={record.id} title={t('query.p1.paper.sections.productionParams')} sectionKey="p1_params_detail" collapsedSections={collapsedSections} onToggleSection={onToggleSection}>
        <div className="table-container">
          <table className="p1-paper-table p1-paper-table-params">
            <thead><tr><th>{t('query.p1.paper.param')}</th><th>{t('query.p1.paper.value')}</th><th>{t('query.p1.paper.unit')}</th></tr></thead>
            <tbody>
              {params.map((p) => (
                <tr key={p.label}><td>{p.label}</td><td>{formatCell(p.value)}</td><td>{p.unit}</td></tr>
              ))}
            </tbody>
          </table>
        </div>
      </CollapsibleSection>
    </div>
  )
}

// ── P2 Details ──

function sortRowsNgFirstLocal(rows: any[], fieldKeys: string[]): any[] {
  if (!Array.isArray(rows) || rows.length <= 1) return rows
  return rows
    .map((row, idx) => ({ row, idx }))
    .sort((a, b) => {
      const aKey = fieldKeys.find(k => a.row && Object.prototype.hasOwnProperty.call(a.row, k)) || fieldKeys[0]
      const bKey = fieldKeys.find(k => b.row && Object.prototype.hasOwnProperty.call(b.row, k)) || fieldKeys[0]
      const aRaw = getRowFieldValue(a.row, fieldKeys)
      const bRaw = getRowFieldValue(b.row, fieldKeys)
      const aFmt = formatFieldValue(aKey, aRaw)
      const bFmt = formatFieldValue(bKey, bRaw)
      const aNg = isNgLike(aFmt)
      const bNg = isNgLike(bFmt)
      if (aNg !== bNg) return aNg ? -1 : 1
      return a.idx - b.idx
    })
    .map(x => x.row)
}

function P2Details({ record }: { record: QueryRecord }) {
  const { t } = useTranslation()

  console.log('[Traceability Debug] Rendering P2 details for record:', record)

  let displayData: { [key: string]: any } = {}

  const standardFields: Array<{ label: string; value: any }> = [
    { label: t('query.p2.fields.slittingMachine'), value: record.slitting_machine_number },
    { label: t('query.p2.fields.winderMachine'), value: record.winder_number },
    { label: t('query.p2.fields.sheetWidth'), value: record.sheet_width },
    { label: t('query.p2.fields.thickness1'), value: record.thickness1 },
    { label: t('query.p2.fields.thickness2'), value: record.thickness2 },
    { label: t('query.p2.fields.thickness3'), value: record.thickness3 },
    { label: t('query.p2.fields.thickness4'), value: record.thickness4 },
    { label: t('query.p2.fields.thickness5'), value: record.thickness5 },
    { label: t('query.p2.fields.thickness6'), value: record.thickness6 },
    { label: t('query.p2.fields.thickness7'), value: record.thickness7 },
    { label: t('query.p2.fields.appearance'), value: record.appearance },
    { label: t('query.p2.fields.roughEdge'), value: record.rough_edge },
    { label: t('query.p2.fields.slittingResult'), value: record.slitting_result },
  ]

  for (const f of standardFields) {
    if (f.value !== undefined && f.value !== null) {
      displayData[f.label] = f.value
    }
  }

  const additional = (record.additional_data || {}) as any
  const rows = Array.isArray(additional.rows) ? (additional.rows as any[]) : []
  const { rows: _rowsIgnored, ...additionalWithoutRows } = additional || {}

  if (rows.length === 1 && rows[0] && typeof rows[0] === 'object' && !Array.isArray(rows[0])) {
    displayData = { ...displayData, ...additionalWithoutRows, ...rows[0] }
  } else {
    displayData = { ...displayData, ...additionalWithoutRows }
  }

  const hasItemRows = rows.length > 1
  const sortedRows = hasItemRows ? sortRowsNgFirstLocal(rows, ['striped results', 'Striped results', '分條結果']) : rows
  const rowHeaders = hasItemRows && rows[0] && typeof rows[0] === 'object' && !Array.isArray(rows[0])
    ? Object.keys(rows[0])
    : []

  return (
    <div className="detail-grid">
      <div className="detail-row">
        <strong>{t('query.fields.lotNo')}:</strong>
        <span>{record.lot_no}</span>
      </div>
      {Array.isArray((record as any).winder_numbers) && (record as any).winder_numbers.length > 0 && (
        <div className="detail-row">
          <strong>符合的收卷機（Winder）：</strong>
          <span>{(record as any).winder_numbers.join(', ')}</span>
        </div>
      )}
      <div className="detail-row">
        <strong>{t('query.fields.createdAt')}:</strong>
        <span>{new Date(record.created_at).toLocaleString()}</span>
      </div>

      {Object.entries(displayData).map(([key, value]) => (
        <div key={key} className="detail-row">
          <strong>{key}：</strong>
          <span>{formatFieldValue(key, value)}</span>
        </div>
      ))}

      {hasItemRows && (
        <div className="additional-data-section" style={{ gridColumn: '1 / -1' }}>
          <div className="section-title">{t('query.sections.checkItemsDetail')}</div>
          <div className="table-container">
            <table className="data-table">
              <thead>
                <tr>
                  <th>#</th>
                  {rowHeaders.map((h) => (
                    <th key={h}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {sortedRows.map((row: any, idx: number) => (
                  <tr key={idx}>
                    <td>{idx + 1}</td>
                    {rowHeaders.map((header: string, vidx: number) => {
                      const rawValue = row?.[header]

                      if (
                        (header === '分條時間' || header === 'slitting time') &&
                        record.production_date &&
                        typeof rawValue === 'string'
                      ) {
                        const v = rawValue.trim()
                        const timeOnly = /^\d{1,2}:\d{2}(:\d{2})?$/.test(v)
                        const hasLeadingDate = /^\d{3}[\/-]\d{1,2}[\/-]\d{1,2}/.test(v) || /^\d{4}-\d{2}-\d{2}/.test(v)
                        if (timeOnly && !hasLeadingDate) {
                          return (
                            <td key={vidx}>
                              {`${formatFieldValue('production_date', record.production_date)} ${v}`}
                            </td>
                          )
                        }
                      }

                      return (
                        <td key={vidx}>{formatFieldValue(header, rawValue)}</td>
                      )
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}

// ── P3 Details ──

function P3Details({ record }: { record: QueryRecord }) {
  const { t } = useTranslation()

  let displayData = record.additional_data || {}

  if (displayData.rows &&
    Array.isArray(displayData.rows) &&
    displayData.rows.length === 1) {
    const { rows, ...rest } = displayData
    displayData = { ...rest, ...rows[0] }
  }

  return (
    <div className="detail-grid">
      <div className="detail-row">
        <strong>{t('query.fields.lotNo')}:</strong>
        <span>{record.lot_no}</span>
      </div>
      <div className="detail-row">
        <strong>{t('query.p3.fields.p3No')}:</strong>
        <span>{record.p3_no}</span>
      </div>
      <div className="detail-row">
        <strong>{t('query.fields.productId')}:</strong>
        <span>{record.product_id || '-'}</span>
      </div>
      <div className="detail-row">
        <strong>{t('query.fields.machineNo')}:</strong>
        <span>{record.machine_no || '-'}</span>
      </div>
      <div className="detail-row">
        <strong>{t('query.fields.moldNo')}:</strong>
        <span>{record.mold_no || '-'}</span>
      </div>
      <div className="detail-row">
        <strong>{t('query.fields.specification')}:</strong>
        <span>{record.specification || '-'}</span>
      </div>
      <div className="detail-row">
        <strong>{t('query.fields.bottomTapeLot')}:</strong>
        <span>{record.bottom_tape_lot || '-'}</span>
      </div>
      {record.notes && (
        <div className="detail-row">
          <strong>{t('query.fields.notes')}:</strong>
          <span>{record.notes}</span>
        </div>
      )}
      <div className="detail-row">
        <strong>{t('query.fields.createdAt')}:</strong>
        <span>{new Date(record.created_at).toLocaleString()}</span>
      </div>
      {displayData.rows && Array.isArray(displayData.rows) && displayData.rows.length > 0 ? (
        <div className="additional-data-section">
          <div className="section-title">{t('query.sections.checkItemsDetail')}</div>
          <div className="text-display-container">
            {displayData.rows.map((row: any, idx: number) => {
              const rowProductId = generateRowProductId(record, row)
              return (
                <div key={idx} className="text-item-row" style={{ marginBottom: '15px', padding: '15px', borderBottom: '1px solid #eee', backgroundColor: '#f9f9f9', borderRadius: '4px' }}>
                  <div style={{ fontWeight: 'bold', marginBottom: '8px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span>{t('query.p3.rowHeader', { index: idx + 1, productId: rowProductId })}</span>
                  </div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '15px' }}>
                    {Object.keys(row).map(header => (
                      <div key={header} style={{ fontSize: '14px', display: 'flex', flexDirection: 'column' }}>
                        <span style={{ color: '#666', fontSize: '12px', marginBottom: '2px' }}>{header}</span>
                        <span style={{ fontWeight: '500' }}>{formatFieldValue(header, row[header])}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      ) : null}
    </div>
  )
}
