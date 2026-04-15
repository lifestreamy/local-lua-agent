import { cn } from "@/lib/utils";

export function Input({ className, ...props }) {
  return (
    <input
      className={cn(
        "flex h-11 w-full rounded-xl border border-red-200 bg-white px-3 py-2 text-base text-red-950 outline-none transition focus:border-red-500 focus:ring-2 focus:ring-red-200",
        className
      )}
      {...props}
    />
  );
}
