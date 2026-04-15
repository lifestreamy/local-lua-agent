import { cva } from "class-variance-authority";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center rounded-xl text-base font-medium transition-colors disabled:pointer-events-none disabled:opacity-50",
  {
    variants: {
      variant: {
        default:
          "bg-gradient-to-r from-red-600 to-red-700 text-white hover:from-red-700 hover:to-red-800",
        secondary:
          "bg-red-100 text-red-900 hover:bg-red-200",
        ghost: "text-red-900 hover:bg-red-100",
        destructive: "bg-red-600 text-white hover:bg-red-700",
        outline: "border border-red-500 text-red-600 hover:bg-red-50",
      },
      size: {
        default: "h-11 px-5 py-2",
        sm: "h-9 px-3 text-sm",
        icon: "h-10 w-10",
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
