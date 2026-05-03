import { Badge } from "../ui/badge";

interface SeverityBadgeProps {
  severity: string;
}

const normalizeSeverity = (value: string): "critical" | "high" | "medium" | "low" | "unknown" => {
  const normalized = String(value || "").trim().toLowerCase();
  if (normalized === "critical") {
    return "critical";
  }
  if (normalized === "high") {
    return "high";
  }
  if (normalized === "medium") {
    return "medium";
  }
  if (normalized === "low") {
    return "low";
  }
  return "unknown";
};

const severityToVariant = (severity: ReturnType<typeof normalizeSeverity>): "destructive" | "outline" | "secondary" => {
  if (severity === "critical" || severity === "high") {
    return "destructive";
  }
  if (severity === "medium") {
    return "outline";
  }
  return "secondary";
};

export function SeverityBadge({ severity }: SeverityBadgeProps) {
  const normalized = normalizeSeverity(severity);
  const label = normalized === "unknown" ? String(severity || "unknown") : normalized;

  return (
    <Badge variant={severityToVariant(normalized)} className="capitalize">
      {label}
    </Badge>
  );
}

