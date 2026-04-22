import { Card, CardContent } from "../ui/card";
import { Skeleton } from "../ui/skeleton";

interface LoadingStateProps {
  message?: string;
}

export function LoadingState({ message = "Loading..." }: LoadingStateProps) {
  return (
    <Card role="status" aria-live="polite" className="border-border/75 bg-card/75">
      <CardContent className="flex items-center gap-3 pt-6">
        <Skeleton className="h-5 w-5 rounded-full bg-primary/40" />
        <p className="text-sm text-muted-foreground">{message}</p>
      </CardContent>
    </Card>
  );
}

