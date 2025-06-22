import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from "intellio-common/components/ui/card";
import { cn } from "intellio-common/lib/utils"; // 올바른 경로로 수정

interface StatCardItemProps {
  title: string;
  value: string;
  description: string;
  // icon?: React.ReactNode; // 필요시 아이콘 추가
  className?: string;
}

export function StatCard({ title, value, description, className }: StatCardItemProps) {
  return (
    <Card className={cn("rounded-[6px]", className)}>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-sm font-medium">{title}</CardTitle>
        {/* {icon && <Icon className="h-4 w-4 text-muted-foreground" />} */}
      </CardHeader>
      <CardContent>
        <div className="text-2xl font-bold">{value}</div>
        <p className="text-xs text-muted-foreground">{description}</p>
      </CardContent>
    </Card>
  );
}

interface SummaryStatCardsProps {
  stats: Array<Omit<StatCardItemProps, 'className'> & { id: string }>; // id는 key로 사용
}

export function SummaryStatCards({ stats }: SummaryStatCardsProps) {
  return (
    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4 mb-6">
      {stats.map((stat) => (
        <StatCard
          key={stat.id}
          title={stat.title}
          value={stat.value}
          description={stat.description}
          className="bg-white"
        />
      ))}
    </div>
  );
}
