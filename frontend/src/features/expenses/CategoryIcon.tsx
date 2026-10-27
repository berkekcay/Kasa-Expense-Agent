import {
  Bus,
  Clapperboard,
  GraduationCap,
  HeartPulse,
  House,
  type LucideIcon,
  Plane,
  Receipt,
  Repeat,
  ShoppingBag,
  ShoppingBasket,
  Tag,
  UtensilsCrossed,
  Zap,
} from "lucide-react";
import { categoryVar } from "@/components/charts";

const ICONS: Record<string, LucideIcon> = {
  groceries: ShoppingBasket,
  food: UtensilsCrossed,
  transport: Bus,
  rent: House,
  utilities: Zap,
  subscriptions: Repeat,
  shopping: ShoppingBag,
  health: HeartPulse,
  education: GraduationCap,
  entertainment: Clapperboard,
  travel: Plane,
  other: Tag,
};

/** A small rounded square with the category's icon, tinted with the category's chart colour. */
export function CategoryIcon({ category, size = "md" }: { category: string | null; size?: "md" | "lg" }) {
  const Icon = (category && ICONS[category]) || Receipt;
  const colour = category ? categoryVar(category) : "var(--muted)";
  const box = size === "lg" ? "size-11 rounded-xl [&>svg]:size-5" : "size-9 rounded-lg [&>svg]:size-4";
  return (
    <span
      aria-hidden
      className={`flex shrink-0 items-center justify-center ${box}`}
      style={{ background: `color-mix(in oklab, ${colour} 15%, transparent)`, color: colour }}
    >
      <Icon />
    </span>
  );
}
