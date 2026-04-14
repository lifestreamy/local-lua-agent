import { cn } from "@/lib/utils";

export function Input({ className, ...props }) {
  return (
    <input
      className={cn(
        "flex h-10 w-full rounded-xl border border-fuchsia-200 bg-white px-3 py-2 text-sm text-fuchsia-950 outline-none transition focus:border-red-400 focus:ring-2 focus:ring-red-200",
        className
      )}
      {...props}
    />
  );
}
