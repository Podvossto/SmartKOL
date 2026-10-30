"use client";

import { useState } from "react";

import { logoUrl } from "@/lib/analysis-api";
import { cn } from "@/lib/utils";

/** True for a mostly transparent logo whose visible part is light (e.g. white lettering): it vanishes on a white tile. */
function needsDarkBackdrop(img: HTMLImageElement): boolean {
  try {
    const size = 24;
    const canvas = document.createElement("canvas");
    canvas.width = canvas.height = size;
    const ctx = canvas.getContext("2d");
    if (!ctx) return false;
    ctx.drawImage(img, 0, 0, size, size);
    const { data } = ctx.getImageData(0, 0, size, size);
    let opaque = 0;
    let light = 0;
    for (let i = 0; i < data.length; i += 4) {
      if (data[i + 3] > 128) {
        opaque += 1;
        light += (0.2126 * data[i] + 0.7152 * data[i + 1] + 0.0722 * data[i + 2]) / 255;
      }
    }
    const transparent = 1 - opaque / (size * size);
    return opaque > 0 && transparent > 0.2 && light / opaque > 0.8;
  } catch {
    return false; // a canvas we may not read (e.g. a tainted image): keep the default backdrop
  }
}

/** The brand's logo from our own server, or its initial on a gradient tile when there isn't one. */
export function BrandLogo({ id, hasLogo, name, className }: { id: string; hasLogo: boolean; name: string; className?: string }) {
  const [failed, setFailed] = useState(false);
  const [dark, setDark] = useState(false);
  const tile = "grid shrink-0 place-items-center overflow-hidden rounded-2xl";
  if (hasLogo && !failed) {
    return (
      <span className={cn(tile, "p-1.5 shadow-[0_6px_16px_-8px_rgba(20,40,120,0.35)] ring-1 transition-colors", dark ? "bg-[oklch(0.27_0.05_264)] ring-black/10" : "bg-white ring-black/[0.06]", className)}>
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={logoUrl(id)} alt={`${name} logo`} className="size-full object-contain" onLoad={(e) => setDark(needsDarkBackdrop(e.currentTarget))} onError={() => setFailed(true)} />
      </span>
    );
  }
  return (
    <span aria-hidden className={cn(tile, "bg-gradient-to-br from-primary to-[oklch(0.62_0.18_235)] font-heading font-semibold text-primary-foreground", className)}>
      {name.trim().charAt(0).toUpperCase() || "?"}
    </span>
  );
}
