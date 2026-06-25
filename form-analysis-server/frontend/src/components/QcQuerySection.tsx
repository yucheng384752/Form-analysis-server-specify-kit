// QC 日報表查詢與顯示（表格格式與 PDF 打孔帶生產日報表一致）
import React, { useState, useCallback } from 'react'
import { useTranslation } from 'react-i18next'
import { useToast } from './common/ToastContext'

// ── Types ──────────────────────────────────────────────────────────────────

export interface QcRoll {
  roll_no: number
  judgment: string | null
  thickness_H: number | null
  thickness_L: number | null
}

export interface QcRecord {
  id: string
  production_date: string
  machine_no: string
  source_file: string | null
  qc_A_H: number | null
  qc_A_L: number | null
  qc_B_H: number | null
  qc_B_L: number | null
  qc_E_prime_H: number | null
  qc_E_prime_L: number | null
  qc_10P0_H: number | null
  qc_10P0_L: number | null
  qc_bending: number | null
  qc_result: string | null
  ng_count: number
  bad_reason: string | null
  rolls_data: QcRoll[] | null
}

// ── Helpers ────────────────────────────────────────────────────────────────

const fmt = (v: number | null | undefined, dp = 4) =>
  v == null ? '' : v.toFixed(dp)

const JudgmentMark = ({ j }: { j: string | null }) => {
  if (j === 'OK') return <span className="qc-mark-ok">✓</span>
  if (j === 'NG') return <span className="qc-mark-ng">✗</span>
  return null
}

// ── QC Table (PDF layout) ──────────────────────────────────────────────────
// 格式對應 PDF 打孔帶生產日報表：
// 機台 | sub | 1 2 ... 9 | 不良原因 | A値 | B値 | E'値 | 10P0 | 彎曲 | 備註
// 每機台 3 列：判定 / H（厚度+QC H值）/ L（厚度+QC L值）

export function QcDailyTable({ records }: { records: QcRecord[] }) {
  const { t } = useTranslation()

  const maxRollNo = records.reduce((acc, r) => {
    const mx = Math.max(0, ...(r.rolls_data?.map(ro => ro.roll_no) ?? []))
    return Math.max(acc, mx)
  }, 9)

  const rollNos = Array.from({ length: maxRollNo }, (_, i) => i + 1)
  // 欄位總數：機台(1) + sub(1) + 捲數(N) + 不良原因(1) + A,B,E',10P0(4) + 彎曲(1) + 備註(1)
  const totalCols = 2 + maxRollNo + 7

  const isNg = (r: QcRecord) =>
    r.ng_count > 0 || (r.qc_result != null && r.qc_result !== 'No NG')

  return (
    <div className="qc-table-wrapper">
      <table className="qc-daily-table">
        <thead>
          {/* 第一列：大分組標題 */}
          <tr className="qc-thead-group">
            <th rowSpan={2} className="qc-th-machine">
              {t('qc.table.machine', '機台 machine')}
            </th>
            <th rowSpan={2} className="qc-th-sub" />
            <th colSpan={maxRollNo} className="qc-th-section">
              {t('qc.table.productionRolls', '生產捲數 Number of production rolls')}
            </th>
            <th rowSpan={2} className="qc-th-bad">
              {t('qc.table.badReason', '不良原因說明')}
            </th>
            <th colSpan={6} className="qc-th-section qc-th-section-qc">
              {t('qc.table.qcInspection', 'QC 檢驗 QC inspection')}
            </th>
          </tr>
          {/* 第二列：捲號 + QC 子欄 */}
          <tr className="qc-thead-sub">
            {rollNos.map(n => (
              <th key={n} className="qc-th-roll-no">{n}</th>
            ))}
            <th className="qc-th-val">A值</th>
            <th className="qc-th-val">B值</th>
            <th className="qc-th-val">E'值</th>
            <th className="qc-th-val">10P0</th>
            <th className="qc-th-val">彎曲</th>
            <th className="qc-th-val">備註</th>
          </tr>
        </thead>

        <tbody>
          {records.length === 0 ? (
            <tr>
              <td colSpan={totalCols} className="qc-empty-row">
                {t('common.noData')}
              </td>
            </tr>
          ) : records.map((rec, recIdx) => {
            const rolls = rec.rolls_data ?? []
            const rollMap = new Map(rolls.map(r => [r.roll_no, r]))
            const ng = isNg(rec)
            const rowCls = ng ? 'qc-row-ng' : ''
            const lastMachine = recIdx === records.length - 1

            return (
              <React.Fragment key={rec.id}>

                {/* ── 判定行 ─────────────────────────────────── */}
                <tr className={rowCls}>
                  {/* 機台：跨 3 列 */}
                  <td rowSpan={3} className={`qc-td-machine ${ng ? 'qc-machine-ng' : ''}`}>
                    {rec.machine_no}
                  </td>
                  <td className="qc-td-sub">判定</td>
                  {rollNos.map(n => {
                    const roll = rollMap.get(n)
                    return (
                      <td key={n} className="qc-td-roll">
                        {roll ? <JudgmentMark j={roll.judgment} /> : null}
                      </td>
                    )
                  })}
                  {/* 不良原因：跨 3 列 */}
                  <td rowSpan={3} className="qc-td-bad">
                    {rec.bad_reason
                      ? <span className="qc-mark-ng">{rec.bad_reason}</span>
                      : null}
                  </td>
                  {/* QC 判定行：空白（值在 H/L 行） */}
                  <td colSpan={4} className="qc-td-empty" />
                  {/* 彎曲：跨 H+L 兩列，從 H 行開始 → 判定行這裡佔位用空白 */}
                  <td className="qc-td-empty" />
                  <td className="qc-td-empty" />
                </tr>

                {/* ── H 行（厚度 + QC H 值）───────────────────── */}
                <tr className={rowCls}>
                  <td className="qc-td-sub">H</td>
                  {rollNos.map(n => {
                    const roll = rollMap.get(n)
                    return (
                      <td key={n} className="qc-td-roll qc-td-num">
                        {roll?.thickness_H ?? ''}
                      </td>
                    )
                  })}
                  {/* QC H 值 */}
                  <td className="qc-td-val">{fmt(rec.qc_A_H)}</td>
                  <td className="qc-td-val">{fmt(rec.qc_B_H)}</td>
                  <td className="qc-td-val">{fmt(rec.qc_E_prime_H, 3)}</td>
                  <td className="qc-td-val">{fmt(rec.qc_10P0_H, 4)}</td>
                  {/* 彎曲：跨 H+L 兩列 */}
                  <td rowSpan={2} className="qc-td-bending">
                    {rec.qc_bending ?? ''}
                  </td>
                  {/* 備註：跨 H+L 兩列 */}
                  <td rowSpan={2} className={`qc-td-remark ${ng ? 'qc-remark-ng' : ''}`}>
                    {rec.qc_result ?? ''}
                  </td>
                </tr>

                {/* ── L 行（厚度 + QC L 值）───────────────────── */}
                <tr className={`${rowCls} ${!lastMachine ? 'qc-row-last' : ''}`}>
                  <td className="qc-td-sub">L</td>
                  {rollNos.map(n => {
                    const roll = rollMap.get(n)
                    return (
                      <td key={n} className="qc-td-roll qc-td-num">
                        {roll?.thickness_L ?? ''}
                      </td>
                    )
                  })}
                  {/* QC L 值 */}
                  <td className="qc-td-val">{fmt(rec.qc_A_L)}</td>
                  <td className="qc-td-val">{fmt(rec.qc_B_L)}</td>
                  <td className="qc-td-val">{fmt(rec.qc_E_prime_L, 3)}</td>
                  <td className="qc-td-val">{fmt(rec.qc_10P0_L, 4)}</td>
                  {/* 彎曲 / 備註 由上方 rowSpan 覆蓋，不需再放 */}
                </tr>

              </React.Fragment>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

// ── Main Section ───────────────────────────────────────────────────────────

export function QcQuerySection() {
  const { t } = useTranslation()
  const { showToast } = useToast()

  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [machineNo, setMachineNo] = useState('')
  const [ngOnly, setNgOnly] = useState(false)

  const [records, setRecords] = useState<QcRecord[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)

  const [uploadFile, setUploadFile] = useState<File | null>(null)
  const [uploading, setUploading] = useState(false)

  // ── Query ──────────────────────────────────────────────────────────────
  const handleQuery = useCallback(async () => {
    setLoading(true)
    try {
      const params = new URLSearchParams()
      if (dateFrom) params.append('date_from', dateFrom)
      if (dateTo) params.append('date_to', dateTo)
      if (machineNo.trim()) params.append('machine_no', machineNo.trim())
      if (ngOnly) params.append('ng_only', 'true')
      params.append('page_size', '200')

      const res = await fetch(`/api/qc/records?${params}`)
      if (!res.ok) throw new Error(await res.text())
      const data = await res.json() as { records: QcRecord[]; total: number }
      setRecords(data.records ?? [])
      setTotal(data.total ?? 0)
    } catch (e) {
      showToast('error', String(e))
    } finally {
      setLoading(false)
    }
  }, [dateFrom, dateTo, machineNo, ngOnly, showToast])

  // ── Upload ─────────────────────────────────────────────────────────────
  const handleUpload = useCallback(async () => {
    if (!uploadFile) return
    setUploading(true)
    try {
      const form = new FormData()
      form.append('file', uploadFile)
      const res = await fetch('/api/qc/upload', { method: 'POST', body: form })
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText })) as { detail?: string }
        throw new Error(err.detail || res.statusText)
      }
      const data = await res.json() as { message?: string }
      showToast('success', data.message || t('qc.uploadSuccess', '上傳成功'))
      setUploadFile(null)
      await handleQuery()
    } catch (e) {
      showToast('error', String(e))
    } finally {
      setUploading(false)
    }
  }, [uploadFile, showToast, handleQuery, t])

  const ngMachineCount = records.filter(r => r.ng_count > 0).length

  return (
    <div className="qc-query-section">

      {/* 上傳 QC PDF */}
      <div className="qc-upload-bar">
        <span className="qc-upload-label">
          {t('qc.upload.label', '上傳 QC 日報 PDF：')}
        </span>
        <input
          type="file"
          accept=".pdf"
          onChange={e => setUploadFile(e.target.files?.[0] ?? null)}
        />
        <button
          className="btn-secondary"
          onClick={handleUpload}
          disabled={!uploadFile || uploading}
        >
          {uploading ? t('common.loading') : t('qc.upload.submit', '辨識並匯入')}
        </button>
      </div>

      {/* 篩選列 */}
      <div className="qc-filter-bar">
        <div className="qc-filter-group">
          <label>{t('qc.filter.dateFrom', '起始日期')}</label>
          <input
            type="date"
            className="qc-input"
            value={dateFrom}
            onChange={e => setDateFrom(e.target.value)}
          />
        </div>
        <div className="qc-filter-group">
          <label>{t('qc.filter.dateTo', '結束日期')}</label>
          <input
            type="date"
            className="qc-input"
            value={dateTo}
            onChange={e => setDateTo(e.target.value)}
          />
        </div>
        <div className="qc-filter-group">
          <label>{t('qc.filter.machine', '機台')}</label>
          <input
            type="text"
            className="qc-input"
            placeholder="P41..."
            value={machineNo}
            onChange={e => setMachineNo(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleQuery()}
          />
        </div>
        <div className="qc-filter-group qc-filter-check">
          <label>
            <input
              type="checkbox"
              checked={ngOnly}
              onChange={e => setNgOnly(e.target.checked)}
            />
            {' '}{t('qc.filter.ngOnly', '僅顯示 NG')}
          </label>
        </div>
        <button
          className="btn-primary"
          onClick={handleQuery}
          disabled={loading}
        >
          {loading ? t('common.loading') : t('qc.filter.query', '查詢')}
        </button>
      </div>

      {/* 統計 */}
      {records.length > 0 && (
        <div className="qc-result-summary">
          <span>{t('qc.result.total', '共 {{n}} 筆機台記錄', { n: total })}</span>
          {ngMachineCount > 0 && (
            <span className="qc-ng-badge">
              {t('qc.result.ngCount', 'NG 機台：{{n}} 台', { n: ngMachineCount })}
            </span>
          )}
        </div>
      )}

      {/* 日報表格 */}
      <QcDailyTable records={records} />
    </div>
  )
}
