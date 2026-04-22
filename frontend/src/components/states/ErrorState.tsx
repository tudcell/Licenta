import { Alert, AlertDescription, AlertTitle } from "../ui/alert";
import { Button } from "../ui/button";

interface ErrorStateProps {
  title?: string;
  message: string;
  onRetry?: () => void;
}

export function ErrorState({ title = "Something went wrong", message, onRetry }: ErrorStateProps) {
  return (
    <Alert variant="destructive" className="space-y-1.5">
      <AlertTitle>{title}</AlertTitle>
      <AlertDescription>{message}</AlertDescription>
      {onRetry ? (
        <Button type="button" variant="outline" className="mt-3" onClick={onRetry}>
          Retry
        </Button>
      ) : null}
    </Alert>
  );
}

