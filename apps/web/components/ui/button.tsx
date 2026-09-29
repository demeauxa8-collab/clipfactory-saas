import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-full text-sm font-medium transition-all duration-300 hover:-translate-y-0.5 active:translate-y-0 active:scale-[0.98] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-ring)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--color-background)] disabled:pointer-events-none disabled:opacity-50 disabled:hover:translate-y-0",
  {
    variants: {
      variant: {
        primary:
          "bg-[var(--color-brand)] text-[var(--color-brand-foreground)] shadow-[0_10px_24px_-12px_rgba(194,97,61,0.55)] hover:bg-[#b3562f]",
        secondary:
          "bg-[var(--color-muted)] text-[var(--color-foreground)] border border-[var(--color-border)] hover:border-[var(--color-brand)] hover:text-[var(--color-brand)]",
        ghost:
          "text-[var(--color-foreground)] hover:bg-[var(--color-muted)]",
        link:
          "text-[var(--color-brand)] underline-offset-4 hover:underline",
      },
      size: {
        sm: "h-8 px-4 text-xs",
        md: "h-10 px-5",
        lg: "h-12 px-7 text-base",
      },
    },
    defaultVariants: {
      variant: "primary",
      size: "md",
    },
  }
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, ...props }, ref) => {
    return (
      <button
        ref={ref}
        className={cn(buttonVariants({ variant, size }), className)}
        {...props}
      />
    );
  }
);
Button.displayName = "Button";

export { buttonVariants };
