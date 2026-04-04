interface EmptyStateProps {
  title?: string;
  message: string;
}

export function EmptyState({ title = "No data", message }: EmptyStateProps) {
  return (
    <div className="state-card">
      <h3>{title}</h3>
      <p>{message}</p>
    </div>
  );
}

