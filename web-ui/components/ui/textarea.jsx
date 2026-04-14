import { cn } from "@/lib/utils";

export function Textarea({ className, ...props }) {
  return (
    <textarea
      className={cn(
        "min-h-[96px] w-full rounded-xl border border-fuchsia-200 bg-white px-3 py-2 text-sm text-fuchsia-950 placeholder:text-fuchsia-500/80 outline-none transition focus:border-red-400 focus:ring-2 focus:ring-red-200",
        className
      )}
      {...props}
    />
  );
}
