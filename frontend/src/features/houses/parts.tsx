// Small pieces shared by the house views: member avatars and the due date chip.
import type { House } from "@/lib/api";
import { formatDate } from "@/lib/format";
import { translate } from "@/lib/i18n";
import { houseMessages } from "./messages";

/** A member keeps the same colour everywhere: their position in the house, one series slot each. */
function memberColor(house: House, userId: string): string {
  const i = house.members.findIndex((m) => m.user_id === userId);
  return i < 0 ? "var(--series-other)" : `var(--series-${(i % 8) + 1})`;
}

function initial(name: string): string {
  const first = Array.from(name.trim())[0] ?? "?";
  return first.toLocaleUpperCase("tr-TR");
}

/** Initial in a tinted circle. Decorative: the name is always written next to it. */
export function MemberAvatar({
  house,
  userId,
  name,
  size = "md",
  className = "",
}: {
  house: House;
  userId: string;
  name: string;
  size?: "sm" | "md" | "lg";
  className?: string;
}) {
  const sizing = { sm: "size-6 text-[11px]", md: "size-8 text-xs", lg: "size-9 text-sm" }[size];
  return (
    <span
      aria-hidden
      className={`flex shrink-0 items-center justify-center rounded-full font-semibold text-foreground ${sizing} ${className}`}
      style={{ background: `color-mix(in srgb, ${memberColor(house, userId)} 24%, var(--card))` }}
    >
      {initial(name)}
    </span>
  );
}

/** Overlapping avatars for the house header. */
export function AvatarStack({ house, max = 5 }: { house: House; max?: number }) {
  const shown = house.members.slice(0, max);
  const rest = house.members.length - shown.length;
  return (
    <span aria-hidden className="flex items-center">
      {shown.map((m, i) => (
        <MemberAvatar
          key={m.user_id}
          house={house}
          userId={m.user_id}
          name={m.display_name}
          className={`ring-2 ring-[var(--background)] ${i > 0 ? "-ml-2" : ""}`}
        />
      ))}
      {rest > 0 && (
        <span className="-ml-2 flex size-8 items-center justify-center rounded-full bg-card text-xs font-medium text-muted ring-2 ring-[var(--background)]">
          +{rest}
        </span>
      )}
    </span>
  );
}

/** "2026-10-27" as a small calendar chip: OCT / 27. The date is also written in text nearby. */
export function DateChip({ iso, tone = "neutral" }: { iso: string; tone?: "neutral" | "accent" | "muted" }) {
  const [day, mon] = formatDate(iso).split(" ");
  const head = {
    neutral: "bg-foreground/[0.05] text-muted",
    accent: "bg-accent-soft text-accent",
    muted: "bg-foreground/[0.03] text-muted",
  }[tone];
  return (
    <span
      aria-hidden
      className={`flex w-10 shrink-0 flex-col items-center overflow-hidden rounded-lg border border-border text-center ${tone === "muted" ? "opacity-60" : ""}`}
    >
      <span className={`w-full text-[10px] leading-4 font-semibold uppercase ${head}`}>{mon}</span>
      <span className="text-sm leading-6 font-semibold tabular-nums">{day}</span>
    </span>
  );
}

/** "Deniz, Ali and Ayşe" / "Deniz, Ali ve Ayşe". */
export function joinNames(names: string[]): string {
  if (names.length <= 1) return names.join("");
  return `${names.slice(0, -1).join(", ")} ${translate(houseMessages, "and")} ${names[names.length - 1]}`;
}
