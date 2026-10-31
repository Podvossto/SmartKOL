/** What the Search page offers to do by itself once the search is done: read the latest videos of the top matches, then score them. */
export const AUTO_READ = { creators: 10, videos: 5 } as const;

// clockworks/tiktok-scraper prices, as in backend/app/enrichment.py: per video read, and a start fee per run.
const VIDEO_USD = 0.0037;
const RUN_USD = 0.001;

/** The most the read can cost; fewer creators than that pass the filters, or a saved copy, make it cheaper or free. */
export const AUTO_READ_MAX_USD = AUTO_READ.creators * AUTO_READ.videos * VIDEO_USD + RUN_USD;
