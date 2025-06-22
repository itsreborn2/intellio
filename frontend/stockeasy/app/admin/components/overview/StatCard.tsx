import React from "react";
import { 
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "intellio-common/components/ui/card"; 
import { cn } from "intellio-common/lib/utils"; 

interface StatCardProps {
  title: string;
  value: string | number;
  description?: string;
  cardClassName?: string;
}

const StatCard: React.FC<StatCardProps> = ({
  title,
  value,
  description,
  cardClassName,
}) => {
  return (
    <Card className={cn("rounded-[6px]", cardClassName)}>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-sm font-medium">{title}</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="text-2xl font-bold">{value}</div>
        {description && (
          <CardDescription className="text-xs">{description}</CardDescription>
        )}
      </CardContent>
    </Card>
  );
};

export default StatCard;
