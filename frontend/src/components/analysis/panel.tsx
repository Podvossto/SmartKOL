import { cn } from "@/lib/utils";

/** Staggered entrance: `index` delays each block a little so a screen assembles instead of popping in. */
export function Rise({ index = 0, className, children }: { index?: number; className?: string; children: React.ReactNode }) {
  return (
    <div className={cn("animate-rise", className)} style={{ "--d": `${index * 70}ms` } as React.CSSProperties}>
      {children}
    </div>
  );
}

export function Eyebrow({ children }: { children: React.ReactNode }) {
  return <h3 className="text-[11px] font-medium uppercase tracking-[0.18em] text-muted-foreground">{children}</h3>;
}

/** One labelled line of a key-facts list: the label on the left, plain readable text on the right. */
export function FactRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="grid gap-1 px-6 py-4 sm:grid-cols-[9rem_1fr] sm:gap-6">
      <dt className="pt-0.5 text-sm text-muted-foreground">{label}</dt>
      <dd className="flex flex-col gap-1 text-[15px] leading-relaxed">{children}</dd>
    </div>
  );
}

/** A small labelled tile — lighter than a full card, so several can sit side by side without shouting. */
export function Fact({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-2.5 rounded-3xl bg-white/70 p-5 ring-1 ring-black/[0.05]">
      <Eyebrow>{title}</Eyebrow>
      {children}
    </div>
  );
}

/** Chips, capped: the first `max` and a "+N more" when there are more (the rest live in the full profile). */
export function ChipList({ items, max }: { items: string[]; max?: number }) {
  const shown = max ? items.slice(0, max) : items;
  return (
    <ul className="flex flex-wrap gap-1.5">
      {shown.map((item) => (
        <li key={item} className="rounded-xl bg-muted px-2.5 py-1 text-sm">
          {item}
        </li>
      ))}
      {max && items.length > max && <li className="px-1 py-1 text-sm text-muted-foreground">+{items.length - max} more</li>}
    </ul>
  );
}

export function Bullets({ items }: { items: string[] }) {
  return (
    <ul className="flex flex-col gap-1.5 text-sm">
      {items.map((item) => (
        <li key={item} className="flex gap-2.5">
          <span aria-hidden className="mt-2 size-1.5 shrink-0 rounded-full bg-primary/60" />
          <span>{item}</span>
        </li>
      ))}
    </ul>
  );
}

export function EmptyState({ title, text, children }: { title: string; text: string; children?: React.ReactNode }) {
  return (
    <div className="animate-rise flex flex-col items-center gap-3 rounded-3xl bg-white/60 px-6 py-16 text-center ring-1 ring-black/[0.05]">
      <h2 className="font-heading text-xl font-semibold tracking-tight">{title}</h2>
      <p className="max-w-md text-sm text-muted-foreground">{text}</p>
      {children}
    </div>
  );
}
