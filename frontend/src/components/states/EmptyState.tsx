import { Card, CardContent, CardHeader, CardTitle } from "../ui/card";

interface EmptyStateProps {
  title?: string;
  message: string;
}

export function EmptyState({ title = "No data", message }: EmptyStateProps) {
  return (
    <Card className="border-border/70 bg-card/70">
      <CardHeader>
        <CardTitle className="text-base">{title}</CardTitle>
      </CardHeader>
      <CardContent className="pt-0 text-sm text-muted-foreground">{message}</CardContent>
    </Card>
  );
}

