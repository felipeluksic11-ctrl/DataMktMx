'use client';

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from 'recharts';

function formatCurrency(value: number): string {
  return new Intl.NumberFormat('es-MX', {
    style: 'currency',
    currency: 'MXN',
    maximumFractionDigits: 0,
  }).format(value);
}

function formatNum(value: number): string {
  return new Intl.NumberFormat('es-MX').format(value);
}

interface PriceChartProps {
  data: { name: string; value: number }[];
  format?: 'currency' | 'number';
  color?: string;
}

export function PriceChart({ data, format = 'currency', color = 'hsl(217, 91%, 60%)' }: PriceChartProps) {
  const fmt = format === 'currency' ? formatCurrency : formatNum;

  return (
    <ResponsiveContainer width="100%" height={Math.max(data.length * 36, 200)}>
      <BarChart data={data} layout="vertical" margin={{ left: 0, right: 20, top: 0, bottom: 0 }}>
        <XAxis
          type="number"
          tickFormatter={fmt}
          tick={{ fontSize: 11, fill: 'hsl(215, 20%, 65%)' }}
          axisLine={false}
          tickLine={false}
        />
        <YAxis
          dataKey="name"
          type="category"
          width={140}
          tick={{ fontSize: 12, fill: 'hsl(213, 31%, 91%)' }}
          axisLine={false}
          tickLine={false}
        />
        <Tooltip
          formatter={(value: number) => [fmt(value), '']}
          contentStyle={{
            backgroundColor: 'hsl(224, 71%, 4%)',
            border: '1px solid hsl(216, 34%, 17%)',
            borderRadius: '0.5rem',
            fontSize: '0.875rem',
          }}
          labelStyle={{ color: 'hsl(213, 31%, 91%)' }}
        />
        <Bar dataKey="value" radius={[0, 4, 4, 0]}>
          {data.map((_, index) => (
            <Cell key={index} fill={color} fillOpacity={1 - index * 0.05} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
