import { useMemo } from 'react'
import { useTranslation } from 'react-i18next'
import { DayPicker, type DateRange } from 'react-day-picker'
import { enUS, zhTW } from 'date-fns/locale'
import type { RangeMode } from './types'
import { getIsoWeekYear, getIsoWeekNumber, isoWeekStartDate } from './utils'

interface DateRangeSectionProps {
  rangeMode: RangeMode
  anchorDate: Date | undefined
  customRange: DateRange | undefined
  startDate: string
  endDate: string
  isCompactCalendar: boolean
  onRangeModeChange: (mode: RangeMode) => void
  onSelectCustomRange: (range: DateRange | undefined) => void
  onApplyAnchorForMode: (mode: Exclude<RangeMode, 'custom'>, date: Date | undefined) => void
  onClearDateFilter: () => void
}

export function DateRangeSection({
  rangeMode,
  anchorDate,
  customRange,
  startDate,
  endDate,
  isCompactCalendar,
  onRangeModeChange,
  onSelectCustomRange,
  onApplyAnchorForMode,
  onClearDateFilter,
}: DateRangeSectionProps) {
  const { t, i18n } = useTranslation()

  const pickerLocale = useMemo(() => {
    return i18n.language === 'en' ? enUS : zhTW
  }, [i18n.language])

  return (
    <div className="analytics-filter-block analytics-date-block">
      <div className="analytics-date-block-top">
        <div>
          <div className="analytics-filter-title">{t('analytics.dateRangeMode')}</div>
          <div className="analytics-date-mode">
            <select
              className="register-input analytics-date-select"
              value={rangeMode}
              onChange={(e) => onRangeModeChange(e.target.value as RangeMode)}
            >
              <option value="week">{t('analytics.modeWeek')}</option>
              <option value="month">{t('analytics.modeMonth')}</option>
              <option value="quarter">{t('analytics.modeQuarter')}</option>
              <option value="halfYear">{t('analytics.modeHalfYear')}</option>
              <option value="custom">{t('analytics.modeCustom')}</option>
            </select>
          </div>
          <div className="analytics-date-preview">{t('analytics.rangePreview', { start: startDate || '-', end: endDate || '-' })}</div>
        </div>
        <div className="analytics-date-actions">
          <button type="button" className="btn-secondary" onClick={onClearDateFilter}>
            {t('common.clear')}
          </button>
        </div>
      </div>

      <div className="analytics-date-picker">
        <div className="analytics-filter-title">{rangeMode === 'custom' ? t('analytics.pickRange') : t('analytics.pickPreset')}</div>
        {rangeMode === 'custom' ? (
          <DayPicker
            mode="range"
            selected={customRange}
            onSelect={onSelectCustomRange}
            showOutsideDays
            numberOfMonths={isCompactCalendar ? 1 : 2}
            locale={pickerLocale}
            weekStartsOn={1}
          />
        ) : (
          <PresetPicker
            rangeMode={rangeMode as Exclude<RangeMode, 'custom'>}
            anchorDate={anchorDate}
            onApplyAnchorForMode={onApplyAnchorForMode}
          />
        )}
      </div>
    </div>
  )
}

function PresetPicker({
  rangeMode,
  anchorDate,
  onApplyAnchorForMode,
}: {
  rangeMode: Exclude<RangeMode, 'custom'>
  anchorDate: Date | undefined
  onApplyAnchorForMode: (mode: Exclude<RangeMode, 'custom'>, date: Date | undefined) => void
}) {
  const { t } = useTranslation()

  const today = new Date()
  const hasAnchor = Boolean(anchorDate)
  const anchor = anchorDate ?? today

  const baseYear = anchor.getFullYear()
  const years = Array.from({ length: 9 }, (_, i) => baseYear - 4 + i)

  const month = anchor.getMonth() + 1
  const quarter = Math.floor(anchor.getMonth() / 3) + 1
  const half = anchor.getMonth() < 6 ? 1 : 2

  const isoWeekYear = getIsoWeekYear(anchor)
  const isoWeek = getIsoWeekNumber(anchor)

  if (rangeMode === 'month') {
    const yearValue = hasAnchor ? String(baseYear) : ''
    const monthValue = hasAnchor ? String(month) : ''
    return (
      <div className="analytics-date-presets">
        <label className="analytics-date-label">
          {t('analytics.yearLabel')}
          <select
            className="register-input analytics-date-select"
            value={yearValue}
            onChange={(e) => {
              if (!e.target.value) {
                onApplyAnchorForMode('month', undefined)
                return
              }
              const y = Number(e.target.value)
              if (!Number.isFinite(y)) return
              onApplyAnchorForMode('month', new Date(y, month - 1, 1))
            }}
          >
            {!hasAnchor ? <option value="">-</option> : null}
            {years.map((y) => (
              <option key={y} value={String(y)}>
                {y}
              </option>
            ))}
          </select>
        </label>
        <label className="analytics-date-label">
          {t('analytics.monthLabel')}
          <select
            className="register-input analytics-date-select"
            value={monthValue}
            onChange={(e) => {
              if (!e.target.value) {
                onApplyAnchorForMode('month', undefined)
                return
              }
              const m = Number(e.target.value)
              if (!Number.isFinite(m)) return
              onApplyAnchorForMode('month', new Date(baseYear, Math.max(1, Math.min(12, m)) - 1, 1))
            }}
          >
            {!hasAnchor ? <option value="">-</option> : null}
            {Array.from({ length: 12 }, (_, i) => i + 1).map((m) => (
              <option key={m} value={String(m)}>
                {m}
              </option>
            ))}
          </select>
        </label>
      </div>
    )
  }

  if (rangeMode === 'quarter') {
    const yearValue = hasAnchor ? String(baseYear) : ''
    const quarterValue = hasAnchor ? String(quarter) : ''
    return (
      <div className="analytics-date-presets">
        <label className="analytics-date-label">
          {t('analytics.yearLabel')}
          <select
            className="register-input analytics-date-select"
            value={yearValue}
            onChange={(e) => {
              if (!e.target.value) {
                onApplyAnchorForMode('quarter', undefined)
                return
              }
              const y = Number(e.target.value)
              if (!Number.isFinite(y)) return
              onApplyAnchorForMode('quarter', new Date(y, (quarter - 1) * 3, 1))
            }}
          >
            {!hasAnchor ? <option value="">-</option> : null}
            {years.map((y) => (
              <option key={y} value={String(y)}>
                {y}
              </option>
            ))}
          </select>
        </label>
        <label className="analytics-date-label">
          {t('analytics.quarterLabel')}
          <select
            className="register-input analytics-date-select"
            value={quarterValue}
            onChange={(e) => {
              if (!e.target.value) {
                onApplyAnchorForMode('quarter', undefined)
                return
              }
              const q = Number(e.target.value)
              if (!Number.isFinite(q)) return
              const qq = Math.max(1, Math.min(4, q))
              onApplyAnchorForMode('quarter', new Date(baseYear, (qq - 1) * 3, 1))
            }}
          >
            {!hasAnchor ? <option value="">-</option> : null}
            {[1, 2, 3, 4].map((q) => (
              <option key={q} value={String(q)}>
                Q{q}
              </option>
            ))}
          </select>
        </label>
      </div>
    )
  }

  if (rangeMode === 'halfYear') {
    const yearValue = hasAnchor ? String(baseYear) : ''
    const halfValue = hasAnchor ? String(half) : ''
    return (
      <div className="analytics-date-presets">
        <label className="analytics-date-label">
          {t('analytics.yearLabel')}
          <select
            className="register-input analytics-date-select"
            value={yearValue}
            onChange={(e) => {
              if (!e.target.value) {
                onApplyAnchorForMode('halfYear', undefined)
                return
              }
              const y = Number(e.target.value)
              if (!Number.isFinite(y)) return
              onApplyAnchorForMode('halfYear', new Date(y, half === 1 ? 0 : 6, 1))
            }}
          >
            {!hasAnchor ? <option value="">-</option> : null}
            {years.map((y) => (
              <option key={y} value={String(y)}>
                {y}
              </option>
            ))}
          </select>
        </label>
        <label className="analytics-date-label">
          {t('analytics.halfYearLabel')}
          <select
            className="register-input analytics-date-select"
            value={halfValue}
            onChange={(e) => {
              if (!e.target.value) {
                onApplyAnchorForMode('halfYear', undefined)
                return
              }
              const h = Number(e.target.value)
              if (!Number.isFinite(h)) return
              const hh = Math.max(1, Math.min(2, h))
              onApplyAnchorForMode('halfYear', new Date(baseYear, hh === 1 ? 0 : 6, 1))
            }}
          >
            {!hasAnchor ? <option value="">-</option> : null}
            <option value="1">{t('analytics.halfYearH1')}</option>
            <option value="2">{t('analytics.halfYearH2')}</option>
          </select>
        </label>
      </div>
    )
  }

  // week
  const yearValue = hasAnchor ? String(isoWeekYear) : ''
  const weekValue = hasAnchor ? String(isoWeek) : ''
  return (
    <div className="analytics-date-presets">
      <label className="analytics-date-label">
        {t('analytics.yearLabel')}
        <select
          className="register-input analytics-date-select"
          value={yearValue}
          onChange={(e) => {
            if (!e.target.value) {
              onApplyAnchorForMode('week', undefined)
              return
            }
            const y = Number(e.target.value)
            if (!Number.isFinite(y)) return
            onApplyAnchorForMode('week', isoWeekStartDate(y, isoWeek))
          }}
        >
          {!hasAnchor ? <option value="">-</option> : null}
          {Array.from({ length: 9 }, (_, i) => isoWeekYear - 4 + i).map((y) => (
            <option key={y} value={String(y)}>
              {y}
            </option>
          ))}
        </select>
      </label>
      <label className="analytics-date-label">
        {t('analytics.weekNumberLabel')}
        <input
          className="register-input analytics-date-input"
          type="number"
          min={1}
          max={53}
          value={weekValue}
          onChange={(e) => {
            if (!e.target.value) {
              onApplyAnchorForMode('week', undefined)
              return
            }
            const w = Number(e.target.value)
            if (!Number.isFinite(w)) return
            onApplyAnchorForMode('week', isoWeekStartDate(isoWeekYear, w))
          }}
        />
      </label>
    </div>
  )
}
