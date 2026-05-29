'use client';

import {
  PieChart,
  Pie,
  Cell,
  ResponsiveContainer,
  Tooltip,
  Legend,
} from 'recharts';

const COLORS = [
  'hsl(217, 91%, 60%)',
  'hsl(262, 83%, 58%)',
  'hsl(142, 71%, 45%)',
  'hsl(38, 92%, 50%)',
  'hsl(0, 84%, 60%)',
  'hsl(199, 89%, 48%)',
  'hsl(326, 100%, 74%)',
  'hsl(45, 93%, 47%)',
];

interface DistributionChartProps {
  data: { name: string; value: number }[];
}

export function DistributionChart({ data }: DistributionChartProps) {
  return (
    <ResponsiveContainer width="100%" height={300}>
      <PieChart>
        <Pie
          data={data}
          cx="50%"
          cy="50%"
          innerRadius={60}
          outerRadius={100}
          paddingAngle={2}
          dataKey="value"
        >
          {data.map((_, index) => (
            <Cell key={index} fill={COLORS[index % COLORS.length]} />
          ))}
        </Pie>
        <Tooltip
          contentStyle={{
            backgroundColor: 'hsl(224, 71%, 4%)',
            border: '1px solid hsl(216, 34%, 17%)',
            borderRadius: '0.5rem',
            fontSize: '0.875rem',
          }}
          formatter={(value: number) => [value.toLocaleString('es-MX'), '']}
        />
        <Legend
          wrapperStyle={{ fontSize: '0.75rem' }}
        />
      </PieChart>
    </ResponsiveContainer>
  );
}
