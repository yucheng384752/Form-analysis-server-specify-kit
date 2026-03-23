import {
  ResponsiveContainer,
  ComposedChart,
  CartesianGrid,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  Bar,
  Line,
} from 'recharts'

type ParetoDatum = {
  name: string
  value: number
  cumPct: number
}

type ParetoChartProps = {
  title: string
  data: ParetoDatum[]
  height?: number
  valueLabel?: string
  cumLabel?: string
}

export function ParetoChart({
  title,
  data,
  height = 260,
  valueLabel = 'Value',
  cumLabel = '累積%'
}: ParetoChartProps) {
  if (!data || data.length === 0) return null

  return (
    <div style={{ border: '1px solid #e5e7eb', borderRadius: 8, padding: 10 }}>
      <div style={{ fontWeight: 700, marginBottom: 6 }}>{title}</div>
      <div style={{ width: '100%', height }}>
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={data} margin={{ top: 10, right: 36, left: 0, bottom: 60 }}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="name" interval={0} angle={-20} height={60} textAnchor="end" />
            <YAxis yAxisId="left" allowDecimals={false} />
            <YAxis yAxisId="right" orientation="right" domain={[0, 100]} tickFormatter={(v: number) => `${v}%`} />
            <Tooltip
              formatter={(value: any, name: any) => {
                if (name === cumLabel) return [`${Number(value).toFixed(1)}%`, cumLabel]
                return [value ?? 0, valueLabel]
              }}
            />
            <Legend />
            <Bar yAxisId="left" dataKey="value" name={valueLabel} fill="#2563eb" radius={[6, 6, 0, 0]} />
            <Line yAxisId="right" dataKey="cumPct" name={cumLabel} type="monotone" stroke="#ef4444" strokeWidth={2} dot={{ r: 2 }} />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
