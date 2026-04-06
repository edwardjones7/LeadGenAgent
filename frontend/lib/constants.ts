export const NICHE_CATEGORIES = [
  "restaurants",
  "bars",
  "cafes",
  "hair salons",
  "nail salons",
  "barbershops",
  "plumbers",
  "electricians",
  "hvac",
  "roofers",
  "landscapers",
  "auto repair",
  "dentists",
  "chiropractors",
  "gyms",
  "yoga studios",
  "pet grooming",
  "cleaning services",
  "painters",
  "contractors",
];

export const LEAD_STATUSES = ["New", "Contacted", "Closed"] as const;

export const OUTREACH_STATUS_LABELS: Record<string, string> = {
  idle:       "Not contacted",
  analyzing:  "Analyzing…",
  queued:     "Queued",
  emailed_1:  "Emailed",
  emailed_2:  "Follow-up 1 sent",
  emailed_3:  "Follow-up 2 sent",
  bounced:    "Bounced",
  opted_out:  "Opted out",
};
