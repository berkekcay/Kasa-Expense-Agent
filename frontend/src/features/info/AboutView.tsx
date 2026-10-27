"use client";

import {
  Bot,
  Calculator,
  CheckCheck,
  Coins,
  ExternalLink,
  FileUp,
  Home,
  Mail,
  MessageSquareText,
  PiggyBank,
  Repeat,
  ScanLine,
  ShieldCheck,
  type LucideIcon,
} from "lucide-react";
import Link from "next/link";
import { Logo } from "@/components/Logo";
import { Alert, Card, cardLinkClass } from "@/components/ui";
import { type Locale, useLocale } from "@/lib/i18n";
import { ISSUES_URL, REPO_URL } from "./site";

type Item = { icon: LucideIcon; title: string; text: string };

type Content = {
  title: string;
  subtitle: string;
  whatTitle: string;
  what: string[];
  status: { title: string; text: string };
  featuresTitle: string;
  features: Item[];
  aiTitle: string;
  aiDescription: string;
  ai: Item[];
  teamTitle: string;
  teamText: string;
  team: { name: string; role: string }[];
  stackTitle: string;
  stack: { label: string; value: string }[];
  codeTitle: string;
  codeText: string;
  repoLink: string;
  issuesLink: string;
  helpLink: string;
};


const CONTENT: Record<Locale, Content> = {
  en: {
    title: "About Kasa",
    subtitle: "A money assistant for students and the people they share a flat with.",
    whatTitle: "What Kasa is",
    what: [
      "Kasa keeps track of what you spend and what you share. You add an expense by typing it, by taking a photo of the receipt, by uploading a bank statement or, if you choose, from your Gmail. For a shared flat, Kasa splits the bills, keeps the balances and tells you who should pay whom.",
      "You can ask about your money in Turkish or English and get the answer as a chart. Kasa is made for student life: small daily spending, a monthly allowance and bills shared with flatmates.",
      "Kasa is not a bank and does not move money. It does not give financial advice.",
    ],
    status: {
      title: "Kasa is a student project",
      text: "It runs as a demo today. Google sign-in, the Gmail connection with real Google accounts and the production database are still being set up.",
    },
    featuresTitle: "What you can do",
    features: [
      { icon: ScanLine, title: "Scan receipts", text: "Take a photo of a receipt. Kasa reads the shop, date, items and total and saves the expense." },
      { icon: FileUp, title: "Import statements", text: "Upload a CSV, Excel or PDF statement from your bank. Each line waits in your inbox until you approve it." },
      { icon: Mail, title: "Gmail import", text: "Optional and read-only. Order and card emails become inbox items. Nothing is saved until you approve it." },
      { icon: Home, title: "Shared flat", text: "Split a bill equally, by percent, by amount or item by item. See balances and the fewest payments to settle up." },
      { icon: PiggyBank, title: "Budgets", text: "Set a monthly limit per category. Kasa warns you at 80 percent and again when you go over." },
      { icon: Repeat, title: "Subscriptions", text: "Kasa finds monthly charges such as Netflix or Spotify and shows when the next one is due." },
      { icon: MessageSquareText, title: "Ask Kasa", text: "Ask about your spending in plain words. Answers come with a chart or a table." },
      { icon: Coins, title: "Other currencies", text: "Paid in euros or dollars? Kasa converts with the Central Bank of Türkiye (TCMB) rates." },
    ],
    aiTitle: "How the AI works",
    aiDescription: "Plain words, no magic.",
    ai: [
      {
        icon: Bot,
        title: "A coordinator and specialists",
        text: "A coordinator agent reads your message and hands it to a specialist for receipts, the house, reports, budgets or the inbox. Each specialist has a short list of tools it may call.",
      },
      {
        icon: Calculator,
        title: "Tools do the math",
        text: "The model never adds, splits or converts amounts. Plain code does, and money is stored exactly in kuruş, so the shares of a bill always add up to the total.",
      },
      {
        icon: ShieldCheck,
        title: "It only sees your data",
        text: "For a question, the report agent writes one read-only query that can only reach your own rows. A second agent checks the query against your question before it runs.",
      },
      {
        icon: CheckCheck,
        title: "You approve imports",
        text: "Emails and statements only create inbox items, and you decide on each one. Text inside a receipt or email is treated as data, never as an instruction.",
      },
    ],
    teamTitle: "Who made it",
    teamText:
      "Kasa is a team project for the AI-Augmented Software Engineering course at Istinye University, 2026.",
    team: [
      { name: "Berke Eren Akçay", role: "Product owner, architecture, backend and frontend" },
      { name: "Mustafa", role: "Database, backend and Google integration" },
      { name: "Yusuf", role: "Agents for receipts, budgets and reports" },
      { name: "Ömer", role: "House agent, splits and settling up" },
      { name: "Zehra", role: "Frontend" },
    ],
    stackTitle: "Built with",
    stack: [
      { label: "Web app", value: "Next.js, React, Tailwind CSS, ECharts" },
      { label: "Backend", value: "Python, FastAPI, SQLAlchemy, Alembic" },
      { label: "Agents", value: "Google Agent Development Kit (ADK)" },
      { label: "AI models", value: "Google Gemini; Ollama during development" },
      { label: "Database", value: "SQLite today; Azure SQL Database planned" },
      { label: "Sign in and hosting", value: "Firebase Authentication, Google Cloud Run (planned)" },
    ],
    codeTitle: "Source code",
    codeText: "Kasa is developed in the open. You can read the code, the architecture notes and the user stories on GitHub.",
    repoLink: "Kasa on GitHub",
    issuesLink: "Report a problem",
    helpLink: "Read the help pages",
  },
  tr: {
    title: "Kasa hakkında",
    subtitle: "Öğrenciler ve ev arkadaşları için bir para asistanı.",
    whatTitle: "Kasa nedir",
    what: [
      "Kasa neye para harcadığını ve neyi paylaştığını takip eder. Harcamayı yazarak, fişin fotoğrafını çekerek, banka ekstresi yükleyerek ya da istersen Gmail'den eklersin. Ortak evde faturaları böler, bakiyeleri tutar ve kimin kime ne ödemesi gerektiğini söyler.",
      "Paranla ilgili soruları Türkçe ya da İngilizce sorabilir, cevabı grafik olarak alabilirsin. Kasa öğrenci hayatı için yapıldı: günlük küçük harcamalar, aylık harçlık ve ev arkadaşlarıyla bölünen faturalar.",
      "Kasa bir banka değil ve para transferi yapmaz. Finansal tavsiye de vermez.",
    ],
    status: {
      title: "Kasa bir öğrenci projesi",
      text: "Bugün demo olarak çalışıyor. Google ile giriş, gerçek Google hesaplarıyla Gmail bağlantısı ve production veritabanı hâlâ kuruluyor.",
    },
    featuresTitle: "Neler yapabilirsin",
    features: [
      { icon: ScanLine, title: "Fiş tara", text: "Fişin fotoğrafını çek. Kasa mağazayı, tarihi, kalemleri ve toplamı okur, harcamayı kaydeder." },
      { icon: FileUp, title: "Ekstre yükle", text: "Bankandan aldığın CSV, Excel ya da PDF ekstreyi yükle. Her satır, sen onaylayana kadar gelen kutusunda bekler." },
      { icon: Mail, title: "Gmail'den al", text: "İsteğe bağlı ve salt okunur. Sipariş ve kart e-postaları gelen kutusuna düşer, sen onaylamadan hiçbir şey kaydedilmez." },
      { icon: Home, title: "Ortak ev", text: "Faturayı eşit, yüzdeyle, tutarla ya da kalem kalem böl. Bakiyeleri ve hesaplaşmak için en az ödemeyi gör." },
      { icon: PiggyBank, title: "Bütçeler", text: "Her kategori için aylık bir sınır koy. Kasa yüzde 80'e gelince ve sınırı aşınca seni uyarır." },
      { icon: Repeat, title: "Abonelikler", text: "Kasa Netflix ya da Spotify gibi aylık ödemeleri bulur ve bir sonrakinin ne zaman çekileceğini gösterir." },
      { icon: MessageSquareText, title: "Kasa'ya sor", text: "Harcamalarını kendi cümlelerinle sor. Cevaplar bir grafik ya da tabloyla gelir." },
      { icon: Coins, title: "Döviz", text: "Euro ya da dolarla mı ödedin? Kasa, Türkiye Cumhuriyet Merkez Bankası (TCMB) kurlarıyla çevirir." },
    ],
    aiTitle: "Yapay zeka nasıl çalışıyor",
    aiDescription: "Sihir yok, sade bir anlatım.",
    ai: [
      {
        icon: Bot,
        title: "Bir koordinatör ve uzmanlar",
        text: "Koordinatör ajan mesajını okur ve onu fiş, ev, rapor, bütçe ya da gelen kutusu uzmanına verir. Her uzmanın kullanabileceği kısa bir araç listesi var.",
      },
      {
        icon: Calculator,
        title: "Hesabı araçlar yapar",
        text: "Model tutarları hiçbir zaman kendisi toplamaz, bölmez ya da çevirmez. Bunu düz kod yapar. Para kuruşu kuruşuna saklandığı için bir faturanın payları her zaman toplamı verir.",
      },
      {
        icon: ShieldCheck,
        title: "Sadece senin verini görür",
        text: "Bir soru sorduğunda rapor ajanı, sadece senin satırlarına ulaşabilen tek bir salt okunur sorgu yazar. İkinci bir ajan sorguyu çalışmadan önce sorunla karşılaştırır.",
      },
      {
        icon: CheckCheck,
        title: "İçe aktarmayı sen onaylarsın",
        text: "E-postalar ve ekstreler sadece gelen kutusu kaydı oluşturur, her birine sen karar verirsin. Fişteki ya da e-postadaki metin veri olarak ele alınır, asla talimat olarak değil.",
      },
    ],
    teamTitle: "Kim yaptı",
    teamText: "Kasa, İstinye Üniversitesi'nde 2026 yılında verilen AI-Augmented Software Engineering dersinin ekip projesi.",
    team: [
      { name: "Berke Eren Akçay", role: "Product owner, mimari, backend ve frontend" },
      { name: "Mustafa", role: "Veritabanı, backend ve Google bağlantısı" },
      { name: "Yusuf", role: "Fiş, bütçe ve rapor ajanları" },
      { name: "Ömer", role: "Ev ajanı, bölüşümler ve hesaplaşma" },
      { name: "Zehra", role: "Frontend" },
    ],
    stackTitle: "Neyle yapıldı",
    stack: [
      { label: "Web uygulaması", value: "Next.js, React, Tailwind CSS, ECharts" },
      { label: "Backend", value: "Python, FastAPI, SQLAlchemy, Alembic" },
      { label: "Ajanlar", value: "Google Agent Development Kit (ADK)" },
      { label: "Yapay zeka modelleri", value: "Google Gemini, geliştirme sırasında Ollama" },
      { label: "Veritabanı", value: "Bugün SQLite, planlanan Azure SQL Database" },
      { label: "Giriş ve barındırma", value: "Firebase Authentication, Google Cloud Run (planlı)" },
    ],
    codeTitle: "Kaynak kodu",
    codeText: "Kasa açık olarak geliştiriliyor. Kodu, mimari notlarını ve kullanıcı hikayelerini GitHub'da okuyabilirsin.",
    repoLink: "Kasa'nın GitHub sayfası",
    issuesLink: "Bir sorun bildir",
    helpLink: "Yardım sayfalarını oku",
  },
};

function IconTile({ icon: Icon }: { icon: LucideIcon }) {
  return (
    <span aria-hidden className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-accent-soft text-accent">
      <Icon className="size-[18px]" />
    </span>
  );
}

export function AboutView() {
  const c = CONTENT[useLocale()];
  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-wrap items-center gap-4">
        <Logo className="size-12 shrink-0" />
        <div className="min-w-0">
          <h1 className="text-[26px] leading-tight font-semibold tracking-tight sm:text-3xl">{c.title}</h1>
          <p className="mt-1.5 max-w-2xl text-sm text-muted">{c.subtitle}</p>
        </div>
      </header>

      <div className="grid gap-6 lg:grid-cols-3">
        <Card title={c.whatTitle} className="lg:col-span-2">
          <div className="flex flex-col gap-3 text-[15px] leading-relaxed text-foreground/90">
            {c.what.map((p) => (
              <p key={p}>{p}</p>
            ))}
          </div>
        </Card>
        <div className="flex flex-col gap-4">
          <Alert title={c.status.title}>{c.status.text}</Alert>
          <Card title={c.codeTitle}>
            <p className="text-sm text-muted">{c.codeText}</p>
            <ul className="mt-4 flex flex-col items-start gap-1">
              <li>
                <a href={REPO_URL} className={cardLinkClass}>
                  {c.repoLink} <ExternalLink aria-hidden className="size-3.5" />
                </a>
              </li>
              <li>
                <a href={ISSUES_URL} className={cardLinkClass}>
                  {c.issuesLink} <ExternalLink aria-hidden className="size-3.5" />
                </a>
              </li>
              <li>
                <Link href="/help" className={cardLinkClass}>
                  {c.helpLink}
                </Link>
              </li>
            </ul>
          </Card>
        </div>
      </div>

      <section aria-labelledby="features-title">
        <h2 id="features-title" className="mb-3 text-lg font-semibold tracking-tight">
          {c.featuresTitle}
        </h2>
        <ul className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {c.features.map((f) => (
            <li key={f.title} className="flex flex-col gap-3 rounded-2xl border border-border bg-card p-5 shadow-card">
              <IconTile icon={f.icon} />
              <div>
                <h3 className="text-[15px] font-semibold tracking-tight">{f.title}</h3>
                <p className="mt-1 text-sm text-muted">{f.text}</p>
              </div>
            </li>
          ))}
        </ul>
      </section>

      <Card title={c.aiTitle} description={c.aiDescription}>
        <ul className="grid gap-5 md:grid-cols-2">
          {c.ai.map((a) => (
            <li key={a.title} className="flex gap-3">
              <IconTile icon={a.icon} />
              <div className="min-w-0">
                <h3 className="text-[15px] font-semibold tracking-tight">{a.title}</h3>
                <p className="mt-1 text-sm leading-relaxed text-muted">{a.text}</p>
              </div>
            </li>
          ))}
        </ul>
      </Card>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card title={c.teamTitle} description={c.teamText}>
          <ul className="flex flex-col divide-y divide-border">
            {c.team.map((m) => (
              <li key={m.name} className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-0.5 py-2.5 first:pt-0 last:pb-0">
                <span className="font-medium">{m.name}</span>
                <span className="text-sm text-muted">{m.role}</span>
              </li>
            ))}
          </ul>
        </Card>
        <Card title={c.stackTitle}>
          <dl className="grid gap-x-6 gap-y-3 text-sm sm:grid-cols-[auto_1fr]">
            {c.stack.map((s) => (
              <div key={s.label} className="contents">
                <dt className="text-muted">{s.label}</dt>
                <dd className="font-medium">{s.value}</dd>
              </div>
            ))}
          </dl>
        </Card>
      </div>
    </div>
  );
}
