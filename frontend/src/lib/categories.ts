// Same fixed list as backend/app/services/categories.py (GET /categories returns it too).
export const CATEGORIES = [
  "groceries",
  "food",
  "transport",
  "rent",
  "utilities",
  "subscriptions",
  "shopping",
  "health",
  "education",
  "entertainment",
  "travel",
  "other",
] as const;

export type Category = (typeof CATEGORIES)[number];
