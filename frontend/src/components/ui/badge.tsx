import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "../../lib/utils";

const badgeVariants = cva(
  "inline-flex items-center rounded-md border px-2.5 py-1 text-xs font-semibold leading-none transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-0",
  {
    variants: {
      variant: {
        default: "border-primary/30 bg-primary/10 text-primary",
        secondary: "border-border bg-muted text-muted-foreground",
        destructive: "border-destructive/35 bg-destructive/10 text-destructive",
        outline: "border-border bg-background text-foreground",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  },
);

export interface BadgeProps extends React.HTMLAttributes<HTMLDivElement>, VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return <div className={cn(badgeVariants({ variant }), className)} {...props} />;
}

export { Badge };

