import React from 'react'
import { useTranslation } from 'react-i18next'
import type { QueryRecord } from './types'
import {
  getP2RowWinderNumber,
  formatFieldValue,
  generateRowProductId,
  getFlattenedAdditionalData,
  getValueByKeyRegex,
  formatCell,
  getRowFieldValue,
  isNgLike,
} from './utils'

interface RecordExpandedContentProps {
  record: QueryRecord
  collapsedSections: { [key: string]: boolean }
  tableSortState: { [key: string]: { column: string; direction: 'asc' | 'desc' } }
  onToggleSection: (recordId: string, sectionKey: string) => void
  onTableSort: (recordId: string, tableType: 'p2' | 'p3', column: string) => void
  onP3LinkSearch: (record: QueryRecord, row: any, rowProductId?: string) => void
}

export function RecordExpandedContent({
  record,
  collapsedSections,
  tableSortState,
  onToggleSection,
  onTableSort,
  onP3LinkSearch,
}: RecordExpandedContentProps) {
  switch (record.data_type) {
    case 'P1':
      return <P1ExpandedContent record={record} collapsedSections={collapsedSections} onToggleSection={onToggleSection} />
    case 'P2':
      return <P2ExpandedContent record={record} collapsedSections={collapsedSections} tableSortState={tableSortState} onToggleSection={onToggleSection} onTableSort={onTableSort} />
    case 'P3':
      return <P3ExpandedContent record={record} collapsedSections={collapsedSections} tableSortState={tableSortState} onToggleSection={onToggleSection} onTableSort={onTableSort} onP3LinkSearch={onP3LinkSearch} />
    default:
      return <NoDataContent />
  }
}

function NoDataContent() {
  const { t } = useTranslation()
  return <p className="no-data">{t('query.errors.unknownDataType')}</p>
}

// ── P1 ──

function P1ExpandedContent({
  record,
  collapsedSections,
  onToggleSection,
}: {
  record: QueryRecord
  collapsedSections: { [key: string]: boolean }
  onToggleSection: (recordId: string, sectionKey: string) => void
}) {
  const { t } = useTranslation()
  if (!record.additional_data) {
    return <p className="no-data">{t('query.noExtraCsvData')}</p>
  }
  return (
    <div className="grouped-data-container">
      <P1PaperLayout record={record} collapsedSections={collapsedSections} onToggleSection={onToggleSection} />
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

function P1CheckboxGroup({
  title,
  options,
  selectedRaw,
}: {
  title: string
  options: string[]
  selectedRaw: any
}) {
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

function P1PaperLayout({
  record,
  collapsedSections,
  onToggleSection,
}: {
  record: QueryRecord
  collapsedSections: { [key: string]: boolean }
  onToggleSection: (recordId: string, sectionKey: string) => void
}) {
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

      <CollapsibleSection recordId={record.id} title={t('query.sections.extrusionConditions')} sectionKey="p1_extrusion_paper" collapsedSections={collapsedSections} onToggleSection={onToggleSection}>
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

      <CollapsibleSection recordId={record.id} title={t('query.p1.paper.sections.dryerTemps')} sectionKey="p1_dryer_paper" collapsedSections={collapsedSections} onToggleSection={onToggleSection}>
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

      <CollapsibleSection recordId={record.id} title={t('query.p1.paper.sections.extWheelTemps')} sectionKey="p1_extwheel_paper" collapsedSections={collapsedSections} onToggleSection={onToggleSection}>
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

      <CollapsibleSection recordId={record.id} title={t('query.p1.paper.sections.productionParams')} sectionKey="p1_params_paper" collapsedSections={collapsedSections} onToggleSection={onToggleSection}>
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

// ── P2 ──

function P2ExpandedContent({
  record,
  collapsedSections,
  tableSortState,
  onToggleSection,
  onTableSort,
}: {
  record: QueryRecord
  collapsedSections: { [key: string]: boolean }
  tableSortState: { [key: string]: { column: string; direction: 'asc' | 'desc' } }
  onToggleSection: (recordId: string, sectionKey: string) => void
  onTableSort: (recordId: string, tableType: 'p2' | 'p3', column: string) => void
}) {
  const { t } = useTranslation()
  if (!record.additional_data) {
    return <p className="no-data">{t('query.noExtraCsvData')}</p>
  }

  const rows = record.additional_data.rows || []
  const sortedRows = sortRowsNgFirstLocal(rows, ['striped results', 'Striped results', '分條結果'])
  const displayRows = sortTableDataLocal(sortedRows, record.id, 'p2', tableSortState)
  const hasRows = Array.isArray(rows) && rows.length > 0
  const p2Headers = hasRows
    ? Object.keys(rows[0]).filter((k) => {
        const nk = k.toLowerCase().replace(/[\s_]/g, '')
        return nk !== 'windernumber'
      })
    : []

  const sortState = tableSortState[`${record.id}-p2`]

  return (
    <div className="grouped-data-container">
      {hasRows && (
        <div className="data-section">
          <div className="section-header">
            <div className="section-title-wrapper">
              <span className="section-icon"></span>
              <h5>{t('query.sections.inspectionData')}</h5>
              <span className="field-count-badge">{t('query.units.items', { count: rows.length })}</span>
            </div>
            <button className="btn-collapse" onClick={() => onToggleSection(record.id, 'rows_data')}>
              {collapsedSections[`${record.id}-rows_data`] ? t('common.expand') : t('common.collapse')}
            </button>
          </div>
          {!collapsedSections[`${record.id}-rows_data`] && (
            <div className="section-content">
              <table className="data-table">
                <thead>
                  <tr>
                    <th
                      onClick={() => onTableSort(record.id, 'p2', '__winder_number__')}
                      style={{ cursor: 'pointer', userSelect: 'none' }}
                      title={t('query.tableHeaders.clickToSort')}
                    >
                      {t('query.tableHeaders.winder')}
                      {sortState && sortState.column === '__winder_number__' && (
                        <span style={{ marginLeft: '4px' }}>{sortState.direction === 'asc' ? '▲' : '▼'}</span>
                      )}
                    </th>
                    {p2Headers.map(key => (
                      <th
                        key={key}
                        onClick={() => onTableSort(record.id, 'p2', key)}
                        style={{ cursor: 'pointer', userSelect: 'none' }}
                        title={t('query.tableHeaders.clickToSort')}
                      >
                        {key}
                        {sortState && sortState.column === key && (
                          <span style={{ marginLeft: '4px' }}>{sortState.direction === 'asc' ? '▲' : '▼'}</span>
                        )}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {displayRows.map((row: any, idx: number) => (
                    <tr key={idx}>
                      <td>{(() => { const w = getP2RowWinderNumber(row); return w == null ? '-' : String(w) })()}</td>
                      {p2Headers.map((header: string, vidx: number) => {
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
                            return <td key={vidx}>{`${formatFieldValue('production_date', record.production_date)} ${v}`}</td>
                          }
                        }
                        return <td key={vidx}>{formatFieldValue(header, rawValue)}</td>
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ── P3 ──

function P3ExpandedContent({
  record,
  collapsedSections,
  tableSortState,
  onToggleSection,
  onTableSort,
  onP3LinkSearch,
}: {
  record: QueryRecord
  collapsedSections: { [key: string]: boolean }
  tableSortState: { [key: string]: { column: string; direction: 'asc' | 'desc' } }
  onToggleSection: (recordId: string, sectionKey: string) => void
  onTableSort: (recordId: string, tableType: 'p2' | 'p3', column: string) => void
  onP3LinkSearch: (record: QueryRecord, row: any, rowProductId?: string) => void
}) {
  const { t } = useTranslation()
  if (!record.additional_data) {
    return <p className="no-data">{t('query.noExtraCsvData')}</p>
  }

  const rows = record.additional_data.rows || []
  const sortedRows = sortRowsNgFirstLocal(rows, ['Finish', 'finish'])
  const displayRows = sortTableDataLocal(sortedRows, record.id, 'p3', tableSortState)
  const rowCount = Array.isArray(rows) ? rows.length : 0
  const sortState = tableSortState[`${record.id}-p3`]

  return (
    <div className="grouped-data-container">
      <div className="p3-header">
        <div className="p3-badges">
          <span className="badge badge-primary">{t('query.fields.lotNo')}: {record.lot_no}</span>
          <span className="badge badge-success">{t('query.stats.checkCount')}: {t('query.units.items', { count: rowCount })}</span>
        </div>
        <div className="p3-stats">
          <div className="stat-item">
            <span className="stat-label">{t('query.stats.originalCount')}:</span>
            <span className="stat-value">{rowCount}</span>
          </div>
          <div className="stat-item">
            <span className="stat-label">{t('query.stats.validCount')}:</span>
            <span className="stat-value">{rowCount}</span>
          </div>
        </div>
      </div>

      {Array.isArray(rows) && rows.length > 0 && (
        <div className="data-section" key="check_items">
          <div className="section-header">
            <div className="section-title-wrapper">
              <span className="section-icon"></span>
              <h5>{t('query.sections.checkItemsDetail')}</h5>
              <span className="field-count-badge">{t('query.units.items', { count: rows.length })}</span>
            </div>
            <button className="btn-collapse" onClick={() => onToggleSection(record.id, 'check_items')}>
              {collapsedSections[`${record.id}-check_items`] ? '▼' : '▲'}
            </button>
          </div>
          {!collapsedSections[`${record.id}-check_items`] && (
            <div className="section-content">
              <div className="table-container">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th className="action-column">{t('query.tableHeaders.linkSearch')}</th>
                      <th
                        onClick={() => onTableSort(record.id, 'p3', 'product_id')}
                        style={{ cursor: 'pointer', userSelect: 'none' }}
                        title={t('query.tableHeaders.clickToSort')}
                      >
                        {t('query.fields.productId')}
                        {sortState && sortState.column === 'product_id' && (
                          <span style={{ marginLeft: '4px' }}>{sortState.direction === 'asc' ? '▲' : '▼'}</span>
                        )}
                      </th>
                      {Object.keys(rows[0]).filter(h => h !== 'product_id').map(header => (
                        <th
                          key={header}
                          onClick={() => onTableSort(record.id, 'p3', header)}
                          style={{ cursor: 'pointer', userSelect: 'none' }}
                          title={t('query.tableHeaders.clickToSort')}
                        >
                          {header}
                          {sortState && sortState.column === header && (
                            <span style={{ marginLeft: '4px' }}>{sortState.direction === 'asc' ? '▲' : '▼'}</span>
                          )}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {displayRows.map((row: any, idx: number) => {
                      const rowProductId = generateRowProductId(record, row)
                      return (
                        <tr key={idx}>
                          <td className="action-column">
                            <button className="btn-link-search" title={t('query.actions.searchLinkedDataHint')} onClick={() => onP3LinkSearch(record, row, rowProductId)}>
                              {t('query.actions.linkSearch')}
                            </button>
                          </td>
                          <td className="product-id-cell" title={rowProductId}>{rowProductId}</td>
                          {Object.keys(rows[0]).filter(h => h !== 'product_id').map(header => (
                            <td key={header}>{formatFieldValue(header, row[header])}</td>
                          ))}
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ── Local helpers (NG sort + table sort) ──

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

function sortTableDataLocal(
  rows: any[],
  recordId: string,
  tableType: 'p2' | 'p3',
  tableSortState: { [key: string]: { column: string; direction: 'asc' | 'desc' } }
): any[] {
  const key = `${recordId}-${tableType}`
  const sortState = tableSortState[key]
  if (!sortState || !rows || rows.length === 0) return rows

  const { column, direction } = sortState
  const multiplier = direction === 'asc' ? 1 : -1

  return [...rows].sort((a, b) => {
    const isP2WinderSort = tableType === 'p2' && column === '__winder_number__'
    const aVal = isP2WinderSort ? getP2RowWinderNumber(a) : a[column]
    const bVal = isP2WinderSort ? getP2RowWinderNumber(b) : b[column]

    if (aVal === null || aVal === undefined) return 1
    if (bVal === null || bVal === undefined) return -1

    if (typeof aVal === 'number' && typeof bVal === 'number') return (aVal - bVal) * multiplier

    const aStr = String(aVal).toLowerCase()
    const bStr = String(bVal).toLowerCase()
    return aStr.localeCompare(bStr) * multiplier
  })
}
