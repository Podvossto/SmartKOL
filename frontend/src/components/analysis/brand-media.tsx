import { Play } from "lucide-react";

import { PlatformIcon } from "@/components/platform-icon";
import { type Analysis, mediaUrl } from "@/lib/analysis-api";

import { Origin } from "./origin";
import { Eyebrow } from "./panel";

type Item = Analysis["media"][number];

/** The brand's cover picture, as it is on its Facebook page (or its website's share image when there's no cover). */
export function BrandBanner({ analysisId, item }: { analysisId: string; item: Item }) {
  return (
    <figure className="relative aspect-[21/8] max-h-72 w-full overflow-hidden rounded-3xl bg-muted ring-1 ring-black/[0.06]">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={mediaUrl(analysisId, item.key)} alt="Brand cover" className="size-full object-cover" />
      <figcaption className="absolute bottom-3 left-3 flex items-center gap-1.5 rounded-full bg-white/85 px-2.5 py-1 text-[11px] font-medium text-foreground/80 backdrop-blur">
        <PlatformIcon platform={item.source} className="size-3" /> Cover
      </figcaption>
    </figure>
  );
}

/** A few of the brand's own pictures and videos (shown as their cover), each linking back to where it was found. */
export function BrandGallery({ analysisId, items }: { analysisId: string; items: Item[] }) {
  if (!items.length) return null;
  return (
    <section aria-label="Brand media" className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2">
        <Eyebrow>Brand media</Eyebrow>
        <Origin kind="data" />
      </div>
      <ul className="grid grid-cols-3 gap-2 sm:grid-cols-6">
        {items.map((item) => {
          const tile = (
            <>
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={mediaUrl(analysisId, item.key)} alt={item.caption || "Brand picture"} loading="lazy" className="size-full object-cover transition-transform duration-700 ease-[cubic-bezier(0.32,0.72,0,1)] group-hover:scale-105" />
              <span className="absolute left-1.5 top-1.5 grid size-5 place-items-center rounded-full bg-white/90">
                <PlatformIcon platform={item.source} className="size-3" />
              </span>
              {item.video && (
                <span className="absolute inset-0 grid place-items-center">
                  <span className="grid size-9 place-items-center rounded-full bg-black/55 text-white backdrop-blur-sm">
                    <Play className="size-4 fill-current" strokeWidth={0} />
                  </span>
                </span>
              )}
            </>
          );
          const frame = "group relative block aspect-square overflow-hidden rounded-2xl bg-muted ring-1 ring-black/[0.06]";
          return (
            <li key={item.key}>
              {item.link ? (
                <a href={item.link} target="_blank" rel="noreferrer" title={item.caption || undefined} className={frame}>
                  {tile}
                </a>
              ) : (
                <div className={frame}>{tile}</div>
              )}
            </li>
          );
        })}
      </ul>
    </section>
  );
}
