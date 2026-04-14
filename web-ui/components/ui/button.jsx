import { cva } from "class-variance-authority";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center rounded-xl text-sm font-medium transition-colors disabled:pointer-events-none disabled:opacity-50",
  {
    variants: {
      variant: {
        default:
          "bg-gradient-to-r from-red-600 to-fuchsia-700 text-white hover:from-red-700 hover:to-fuchsia-800",
        secondary:
          "bg-fuchsia-100 text-fuchsia-900 hover:bg-fuchsia-200",
        ghost: "text-fuchsia-900 hover:bg-fuchsia-100",
        destructive: "bg-red-600 text-white hover:bg-red-700",
        outline: "border border-red-500 text-red-600 hover:bg-red-50",
      },
      size: {
        default: "h-10 px-4 py-2",
        sm: "h-8 px-3 text-xs",
        icon: "h-9 w-9",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
);

export function Button({ className, variant, size, ...props }) {
  return (
    <button
      className={cn(buttonVariants({ variant, size }), className)}
      {...props}
    />
  );
}
