import { ArrowUpRight, Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

/** Primary call to action: the arrow sits in its own circle inside the pill and drifts on hover. */
export function PillButton({
  children,
  loading,
  className,
  ...props
}: React.ComponentProps<typeof Button> & { loading?: boolean }) {
  return (
    <Button size="lg" className={cn("group h-12 gap-3 pl-6 pr-2 hover:-translate-y-0.5 hover:shadow-[inset_0_1px_0_rgba(255,255,255,0.3),0_14px_30px_-10px_oklch(0.49_0.25_264/0.85)] active:translate-y-0", className)} disabled={props.disabled || loading} {...props}>
      {children}
      <span className="relative grid size-8 place-items-center overflow-hidden rounded-full bg-white/20 transition-all duration-500 ease-[cubic-bezier(0.32,0.72,0,1)] group-hover:scale-110 group-hover:bg-white/30">
        {loading ? (
          <Loader2 className="size-4 animate-spin" strokeWidth={1.5} />
        ) : (
          <>
            {/* the arrow leaves toward the corner while a second one slides in behind it */}
            <ArrowUpRight className="size-4 transition-transform duration-500 ease-[cubic-bezier(0.32,0.72,0,1)] group-hover:translate-x-6 group-hover:-translate-y-6" strokeWidth={1.5} />
            <ArrowUpRight className="absolute size-4 -translate-x-6 translate-y-6 transition-transform duration-500 ease-[cubic-bezier(0.32,0.72,0,1)] group-hover:translate-x-0 group-hover:translate-y-0" strokeWidth={1.5} />
          </>
        )}
      </span>
    </Button>
  );
}
