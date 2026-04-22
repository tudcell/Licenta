import type { ReactNode } from "react";

import { Card, CardDescription, CardHeader, CardTitle } from "../ui/card";

interface PageShellProps {
  title: string;
  description?: string;
  children: ReactNode;
  actions?: ReactNode;
}

export function PageShell({ title, description, children, actions }: PageShellProps) {
  return (
    <div className="space-y-5">
      <Card className="border-border/70 bg-card/70 backdrop-blur-sm">
        <CardHeader className="gap-3 p-5 md:p-6">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="space-y-1">
              <CardTitle className="text-2xl tracking-tight">{title}</CardTitle>
              {description ? <CardDescription className="max-w-3xl text-sm">{description}</CardDescription> : null}
            </div>
            {actions ? <div className="flex flex-wrap items-center gap-2">{actions}</div> : null}
          </div>
        </CardHeader>
      </Card>
      <div className="space-y-5">
        {children}
      </div>
    </div>
  );
}

