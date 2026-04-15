import { cn } from "@/lib/utils";

export function Textarea({ className, ...props }) {
  return (
    <textarea
      className={cn(
        "min-h-[108px] w-full rounded-xl border border-red-200 bg-white px-3 py-2.5 text-base text-red-950 placeholder:text-red-500/80 outline-none transition focus:border-red-500 focus:ring-2 focus:ring-red-200",
        className
      )}
      {...props}
    />
  );
}
