// The Kasa mark: a rounded "K" whose lower leg turns into a rising coin path, on the accent
// square. Kept as inline SVG so it follows the theme and stays sharp at any size. The same
// drawing is in public/kasa-logo.svg and app/icon.svg for the favicon.

export function Logo({ className = "size-8", title }: { className?: string; title?: string }) {
  return (
    <svg
      viewBox="0 0 32 32"
      className={className}
      role={title ? "img" : undefined}
      aria-label={title}
      aria-hidden={title ? undefined : true}
    >
      <rect width="32" height="32" rx="9" fill="var(--accent)" />
      <path d="M10.5 8.5v15" stroke="var(--accent-foreground)" strokeWidth="3" strokeLinecap="round" fill="none" />
      <path
        d="M21.5 8.5 13 16.2"
        stroke="var(--accent-foreground)"
        strokeWidth="3"
        strokeLinecap="round"
        strokeLinejoin="round"
        fill="none"
      />
      <path
        d="M13 16.2c2.4 0 3.6 1.2 4.8 3.4"
        stroke="var(--accent-foreground)"
        strokeWidth="3"
        strokeLinecap="round"
        fill="none"
      />
      <circle cx="22" cy="22" r="3.3" fill="var(--accent-foreground)" />
    </svg>
  );
}
