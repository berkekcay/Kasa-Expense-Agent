// Building blocks for long, readable text pages (privacy, terms, cookies). The Tailwind setup
// has no typography plugin, so headings, paragraphs and lists get their styles here.

import type { AnchorHTMLAttributes, ReactNode } from "react";
import { PageHeader } from "@/components/ui";

export function TextPage({
  title,
  subtitle,
  updated,
  notice,
  toc,
  tocLabel,
  children,
}: {
  title: string;
  subtitle?: string;
  /** "Last updated: 27 October 2026", already translated. */
  updated?: string;
  /** The student project notice, shown above the text. */
  notice?: ReactNode;
  /** Section ids and titles for the "On this page" list. */
  toc?: { id: string; title: string }[];
  tocLabel?: string;
  children: ReactNode;
}) {
  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-6">
      <div>
        <PageHeader title={title} subtitle={subtitle} />
        {updated && <p className="-mt-3 text-sm text-muted sm:-mt-5">{updated}</p>}
      </div>
      {notice}
      {toc && toc.length > 0 && (
        <nav aria-label={tocLabel} className="rounded-2xl border border-border bg-card p-5 shadow-card">
          <h2 className="text-[15px] font-semibold tracking-tight">{tocLabel}</h2>
          <ol className="mt-3 grid list-decimal gap-x-8 gap-y-1.5 pl-5 text-sm marker:text-muted sm:grid-cols-2">
            {toc.map((s) => (
              <li key={s.id}>
                <a href={`#${s.id}`} className="text-accent underline-offset-2 hover:underline">
                  {s.title}
                </a>
              </li>
            ))}
          </ol>
        </nav>
      )}
      <article className="flex flex-col gap-8 rounded-2xl border border-border bg-card p-5 shadow-card sm:p-8">
        {children}
      </article>
    </div>
  );
}

export function Section({ id, title, children }: { id?: string; title: string; children: ReactNode }) {
  return (
    <section id={id} aria-labelledby={id ? `${id}-title` : undefined} className="scroll-mt-24">
      <h2 id={id ? `${id}-title` : undefined} className="text-lg font-semibold tracking-tight">
        {title}
      </h2>
      <div className="mt-3 flex flex-col gap-3 text-[15px] leading-relaxed text-foreground/90">{children}</div>
    </section>
  );
}

export function SubHeading({ children }: { children: ReactNode }) {
  return <h3 className="mt-2 text-[15px] font-semibold">{children}</h3>;
}

export function P({ children }: { children: ReactNode }) {
  return <p>{children}</p>;
}

export function List({ children, ordered = false }: { children: ReactNode; ordered?: boolean }) {
  const cls = "flex flex-col gap-1.5 pl-5 marker:text-muted";
  return ordered ? (
    <ol className={`list-decimal ${cls}`}>{children}</ol>
  ) : (
    <ul className={`list-disc ${cls}`}>{children}</ul>
  );
}

/** An inline link. External links open in the same tab, like the rest of the app. */
export function A({ href, children, ...props }: AnchorHTMLAttributes<HTMLAnchorElement> & { href: string }) {
  return (
    <a href={href} className="font-medium text-accent underline underline-offset-2 hover:no-underline" {...props}>
      {children}
    </a>
  );
}

/** A two column definition table that stays readable on phones. */
export function InfoTable({
  head,
  rows,
  caption,
}: {
  head: string[];
  rows: ReactNode[][];
  caption?: string;
}) {
  return (
    <div className="-mx-1 overflow-x-auto">
      <table className="w-full min-w-[34rem] border-collapse text-left text-sm">
        {caption && <caption className="sr-only">{caption}</caption>}
        <thead>
          <tr className="border-b border-border text-muted">
            {head.map((h) => (
              <th key={h} scope="col" className="px-2 py-2 font-medium">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i} className="border-b border-border last:border-0 align-top">
              {row.map((cell, j) =>
                j === 0 ? (
                  <th key={j} scope="row" className="px-2 py-2.5 font-medium">
                    {cell}
                  </th>
                ) : (
                  <td key={j} className="px-2 py-2.5 text-foreground/90">
                    {cell}
                  </td>
                ),
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function Code({ children }: { children: ReactNode }) {
  return <code className="rounded bg-foreground/[0.06] px-1 py-0.5 font-mono text-[0.85em]">{children}</code>;
}
