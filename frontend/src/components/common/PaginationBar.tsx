import { Button } from "../ui/button";

interface PaginationBarProps {
  page: number;
  totalPages: number;
  total?: number;
  hasPrevious: boolean;
  hasNext: boolean;
  onPrevious: () => void;
  onNext: () => void;
}

export function PaginationBar({
  page,
  totalPages,
  total,
  hasPrevious,
  hasNext,
  onPrevious,
  onNext,
}: PaginationBarProps) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-4 rounded-md border border-border bg-card px-4 py-3">
      <Button type="button" variant="outline" size="sm" disabled={!hasPrevious} onClick={onPrevious}>
        Previous
      </Button>
      <span className="text-sm font-medium text-muted-foreground">
        Page {page}/{totalPages}
        {typeof total === "number" ? ` (total ${total})` : ""}
      </span>
      <Button type="button" variant="outline" size="sm" disabled={!hasNext} onClick={onNext}>
        Next
      </Button>
    </div>
  );
}

