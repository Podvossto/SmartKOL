/** Where a pasted link points. A Facebook link is told apart from a website by its host. */
export const kindOf = (link: string) => (/(^|[/.@])(facebook\.com|fb\.com|fb\.me)\b/i.test(link) ? "facebook" : "website");

const HOST = /^(?:[a-z0-9\u0E00-\u0E7F](?:[a-z0-9\u0E00-\u0E7F-]{0,61}[a-z0-9\u0E00-\u0E7F])?\.)+(?:[a-z]{2,}|xn--[a-z0-9-]+)$/i;

/** Quick checks on what was typed, before anything is sent. Returns a plain-language problem, or null when it looks fine. */
export function linkProblem(raw: string): string | null {
  const text = raw.trim();
  if (!text) return null;
  if (/\s/.test(text)) return "A link can't contain spaces.";
  if (/^\d+$/.test(text)) return "That's only numbers. Paste a link like https://example.com.";
  const scheme = text.match(/^([a-z][a-z0-9+.-]*):\/\//i);
  if (scheme && !/^https?$/i.test(scheme[1])) return "Use a link that starts with http:// or https://.";
  const rest = scheme ? text.slice(scheme[0].length) : text;
  const host = rest.split(/[/?#]/)[0].replace(/^[^@]*@/, "").replace(/:\d+$/, "");
  if (!host) return "The link is cut off. Paste the full address.";
  if (!HOST.test(host)) return host.includes(".") ? "That address doesn't look complete. Check the ending (like .com or .co.th)." : "That doesn't look like a web address. Paste a link like https://example.com.";
  if (kindOf(text) === "facebook" && !/^(?:www\.|m\.|web\.)?(?:facebook\.com|fb\.com|fb\.me)\/[^/?#]+/i.test(rest)) return "Add the page name after facebook.com/, e.g. facebook.com/yourbrand.";
  return null;
}

/** What identifies the brand in a link, to recognise one that was analysed before: the site's host, or the Facebook page name. */
export function linkKey(raw: string): { kind: "website" | "facebook"; key: string } | null {
  const text = raw.trim().replace(/^[a-z]+:\/\//i, "");
  if (!text) return null;
  const [host, ...path] = text.split(/[?#]/)[0].split("/");
  const clean = host.toLowerCase().replace(/^(www|m|web)\./, "");
  if (kindOf(text) === "facebook") {
    const name = path.filter(Boolean)[0];
    return name ? { kind: "facebook", key: decodeURIComponent(name).toLowerCase() } : null;
  }
  return { kind: "website", key: clean };
}
