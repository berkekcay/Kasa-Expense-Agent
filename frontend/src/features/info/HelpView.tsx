"use client";

// Help and FAQ. Each question is a native <details> element, so it opens with the keyboard
// and works for screen readers without extra ARIA. Answers describe what the app does today;
// update them when a feature changes.

import { ChevronDown, ExternalLink, LifeBuoy } from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";
import { Card, PageHeader, cardLinkClass } from "@/components/ui";
import { type Locale, useLocale } from "@/lib/i18n";
import { DELETE_ISSUE_URL, ISSUES_URL, NEW_ISSUE_URL } from "./site";

type Faq = { id: string; q: string; a: ReactNode };

type Content = {
  title: string;
  subtitle: string;
  faqTitle: string;
  faq: Faq[];
  contactTitle: string;
  contactText: string;
  contactNote: string;
  newIssue: string;
  allIssues: string;
  about: string;
  privacy: string;
};

function L({ href, children }: { href: string; children: ReactNode }) {
  const cls = "font-medium text-accent underline underline-offset-2 hover:no-underline";
  return href.startsWith("/") ? (
    <Link href={href} className={cls}>
      {children}
    </Link>
  ) : (
    <a href={href} className={cls}>
      {children}
    </a>
  );
}

function Examples({ items }: { items: string[] }) {
  return (
    <ul className="mt-2 flex flex-col gap-1.5">
      {items.map((x) => (
        <li key={x} className="rounded-lg border border-border bg-background px-3 py-1.5 text-sm">
          {x}
        </li>
      ))}
    </ul>
  );
}

const ASK_EXAMPLES = [
  "Bu ay kategorilere göre ne kadar harcadım?",
  "Son 6 ayın harcamalarını çizgi grafik olarak göster",
  "Evde kim kime borçlu?",
  "How much did I spend on groceries this month?",
  "Which subscriptions do I pay for?",
  "Am I over any budget?",
];

const CONTENT: Record<Locale, Content> = {
  en: {
    title: "Help",
    subtitle: "Answers to common questions about using Kasa.",
    faqTitle: "Frequently asked questions",
    faq: [
      {
        id: "add-expense",
        q: "How do I add an expense?",
        a: (
          <>
            <p>
              Open <L href="/expenses#add">Expenses</L> and fill in the form: amount, currency, category, date and shop.
              You can also just tell Kasa in <L href="/chat">Ask Kasa</L>, for example &quot;Migros&apos;ta 245,50 TL
              market alışverişi yaptım&quot;.
            </p>
            <p>
              You can change the shop, category, date or note of an expense later. To change the amount, delete the
              expense and add it again.
            </p>
          </>
        ),
      },
      {
        id: "receipt",
        q: "How do I scan a receipt?",
        a: (
          <p>
            Go to <L href="/receipts">Scan receipt</L> and choose or drop a photo (JPEG, PNG, WebP or HEIC, up to 10 MB).
            Kasa reads the shop, date, items and total and saves the expense. A sharp, flat photo with the total visible
            works best. Check the result: if something is wrong, edit it or delete it on the Expenses page.
          </p>
        ),
      },
      {
        id: "statement",
        q: "How do I import a bank statement?",
        a: (
          <>
            <p>
              Download your statement from your bank as CSV, or as PDF if there is no CSV, and upload it on{" "}
              <L href="/import">Import statement</L>. Every spending line goes to your inbox. Income, card payments and
              refunds are skipped.
            </p>
            <p>
              A PDF needs a text layer: a scanned paper statement cannot be read. Uploading the same file twice does not
              add anything new.
            </p>
          </>
        ),
      },
      {
        id: "inbox",
        q: "What is the inbox?",
        a: (
          <p>
            The <L href="/inbox">inbox</L> holds expenses that Kasa found in a statement or in Gmail but that you have not
            accepted yet. Check each one, fix the category if needed, then approve or reject it. You can select several
            and approve them at once. Nothing becomes an expense until you approve it.
          </p>
        ),
      },
      {
        id: "gmail",
        q: "Can Kasa read my Gmail?",
        a: (
          <p>
            Only if you connect Google in <L href="/settings">Settings</L>. The access is read-only: Kasa looks at emails
            from the last 30 days that look like receipts, invoices or orders and puts them in your inbox. It never
            sends, deletes or changes email. You can disconnect at any time, and Kasa then deletes its Google token. In
            the demo this may not be available yet.
          </p>
        ),
      },
      {
        id: "house",
        q: "How does splitting in a shared house work?",
        a: (
          <>
            <p>
              Create a house on the <L href="/houses">House</L> page and add your flatmates by their Kasa user id (invite
              links are coming). When you add a bill, choose how to split it: equally, by percent, by amount or item by
              item.
            </p>
            <p>
              Kasa works in exact kuruş, so the shares always add up to the bill. If a total does not divide evenly, the
              leftover kuruş go to some people so nothing is lost. Your budgets only count your own share.
            </p>
          </>
        ),
      },
      {
        id: "settle",
        q: "How do I settle up with my flatmates?",
        a: (
          <p>
            On the House page, Balances shows who owes whom and the fewest payments that clear everything. When someone
            pays, record the payment so the balances go down. You can also create reminders with a due date; if you
            connected Google, they are added to Google Calendar too.
          </p>
        ),
      },
      {
        id: "budgets",
        q: "How do budgets and warnings work?",
        a: (
          <p>
            On <L href="/budgets">Budgets</L>, set a monthly limit for a category or for all spending. When a new expense
            takes a budget past 80 percent, Kasa warns you, and again when you go over. You are not warned twice for the
            same level. House bills count only with your share.
          </p>
        ),
      },
      {
        id: "subscriptions",
        q: "How does Kasa find my subscriptions?",
        a: (
          <p>
            On <L href="/subscriptions">Subscriptions</L>, run the detection. Kasa looks for charges from the same shop
            that repeat every month, such as Netflix or Spotify, and shows when the next one is expected. Everyday
            shopping like groceries does not count. If something is not a subscription, dismiss it and it will not come
            back.
          </p>
        ),
      },
      {
        id: "ask",
        q: "What can I ask Kasa?",
        a: (
          <>
            <p>
              <L href="/chat">Ask Kasa</L> answers from your expenses, budgets, subscriptions, house and inbox, in
              Turkish or English. It can also add an expense or a house bill for you. Some examples:
            </p>
            <Examples items={ASK_EXAMPLES} />
            <p>
              Kasa can only read your own data. If an answer looks wrong, check the numbers on the matching page.
            </p>
          </>
        ),
      },
      {
        id: "slow",
        q: "Why are answers sometimes slow?",
        a: (
          <>
            <p>
              On the development server the team runs open models on a shared Ollama machine, and one chat answer can
              take 30 to 120 seconds depending on what else is running. With Gemini, which the real product uses, answers
              are much faster.
            </p>
            <p>
              You can keep using other pages while you wait: the answer will be in the chat when you come back. The
              first request after a long quiet period can also take about a minute while the database wakes up.
            </p>
          </>
        ),
      },
      {
        id: "language-theme",
        q: "How do I change the language or the theme?",
        a: (
          <p>
            At the bottom of the side menu (on a phone, open the menu first) pick Language: Türkçe or English, and Theme:
            Light, System or Dark. Your browser remembers both.
          </p>
        ),
      },
      {
        id: "delete",
        q: "How do I delete my data?",
        a: (
          <>
            <p>
              Delete an expense from its row on the Expenses page. A house bill can be deleted by the person who paid it,
              and you can leave a house when your balance is zero. Disconnect Google in Settings to remove Kasa&apos;s
              access to Gmail and Calendar.
            </p>
            <p>
              A button that deletes your whole account and all its data is planned (<L href={DELETE_ISSUE_URL}>issue #13</L>
              ). Until then, open an issue and we will delete it for you. See the <L href="/privacy">privacy policy</L>{" "}
              for details.
            </p>
          </>
        ),
      },
    ],
    contactTitle: "Still stuck?",
    contactText:
      "Open an issue on GitHub and tell us what you tried and what happened. Screenshots help, but hide any personal data first.",
    contactNote: "GitHub issues are public. Do not post card numbers, statements or other personal data.",
    newIssue: "Open a new issue on GitHub",
    allIssues: "See existing issues",
    about: "About Kasa",
    privacy: "Privacy policy",
  },
  tr: {
    title: "Yardım",
    subtitle: "Kasa'yı kullanırken en çok sorulan soruların cevapları.",
    faqTitle: "Sık sorulan sorular",
    faq: [
      {
        id: "add-expense",
        q: "Nasıl harcama eklerim?",
        a: (
          <>
            <p>
              <L href="/expenses#add">Harcamalar</L> sayfasını aç ve formu doldur: tutar, para birimi, kategori, tarih ve
              mağaza. İstersen <L href="/chat">Kasa&apos;ya sor</L> sayfasında yazman da yeterli, örneğin &quot;Migros&apos;ta
              245,50 TL market alışverişi yaptım&quot;.
            </p>
            <p>
              Bir harcamanın mağazasını, kategorisini, tarihini ya da notunu sonradan değiştirebilirsin. Tutarı
              değiştirmek için harcamayı silip yeniden ekle.
            </p>
          </>
        ),
      },
      {
        id: "receipt",
        q: "Fişi nasıl taratırım?",
        a: (
          <p>
            <L href="/receipts">Fiş tara</L> sayfasına git ve bir fotoğraf seç ya da sürükle (JPEG, PNG, WebP ya da HEIC,
            en fazla 10 MB). Kasa mağazayı, tarihi, kalemleri ve toplamı okuyup harcamayı kaydeder. En iyi sonucu,
            toplamın göründüğü net ve düz bir fotoğraf verir. Sonucu kontrol et, yanlış bir şey varsa Harcamalar
            sayfasında düzelt ya da sil.
          </p>
        ),
      },
      {
        id: "statement",
        q: "Banka ekstresini nasıl yüklerim?",
        a: (
          <>
            <p>
              Ekstreni bankandan CSV olarak, CSV yoksa PDF olarak indir ve <L href="/import">Ekstre yükle</L> sayfasından
              yükle. Her harcama satırı gelen kutuna düşer. Gelirler, kart ödemeleri ve iadeler atlanır.
            </p>
            <p>
              PDF&apos;in bir metin katmanı olmalı, taranmış kağıt ekstre okunamaz. Aynı dosyayı iki kez yüklersen yeni
              bir şey eklenmez.
            </p>
          </>
        ),
      },
      {
        id: "inbox",
        q: "Gelen kutusu nedir?",
        a: (
          <p>
            <L href="/inbox">Gelen kutusu</L>, Kasa&apos;nın bir ekstrede ya da Gmail&apos;de bulduğu ama senin henüz
            kabul etmediğin harcamaları tutar. Her birine bak, gerekirse kategorisini düzelt, sonra onayla ya da reddet.
            Birkaçını seçip tek seferde onaylayabilirsin. Sen onaylamadan hiçbir şey harcamaya dönüşmez.
          </p>
        ),
      },
      {
        id: "gmail",
        q: "Kasa Gmail'imi okuyabilir mi?",
        a: (
          <p>
            Sadece <L href="/settings">Ayarlar</L> sayfasından Google&apos;ı bağlarsan. Erişim salt okunur: Kasa son 30
            günün fiş, fatura ya da sipariş gibi görünen e-postalarına bakar ve onları gelen kutuna koyar. Hiçbir zaman
            e-posta göndermez, silmez ya da değiştirmez. Bağlantıyı istediğin zaman kesebilirsin, Kasa o zaman Google
            anahtarını siler. Demoda bu özellik henüz açık olmayabilir.
          </p>
        ),
      },
      {
        id: "house",
        q: "Ortak evde bölüşme nasıl çalışıyor?",
        a: (
          <>
            <p>
              <L href="/houses">Ev</L> sayfasında bir ev oluştur ve ev arkadaşlarını Kasa kullanıcı kimlikleriyle ekle
              (davet linkleri yolda). Bir fatura eklerken nasıl bölüneceğini seç: eşit, yüzdeyle, tutarla ya da kalem
              kalem.
            </p>
            <p>
              Kasa kuruşu kuruşuna hesaplar, bu yüzden paylar her zaman faturanın toplamını verir. Toplam eşit
              bölünmüyorsa artan kuruşlar bazı kişilere dağıtılır, hiçbir şey kaybolmaz. Bütçelerine sadece kendi payın
              sayılır.
            </p>
          </>
        ),
      },
      {
        id: "settle",
        q: "Ev arkadaşlarımla nasıl hesaplaşırım?",
        a: (
          <p>
            Ev sayfasındaki Bakiyeler bölümü kimin kime borçlu olduğunu ve her şeyi kapatan en az ödemeyi gösterir. Biri
            ödeme yaptığında ödemeyi kaydet, bakiyeler düşsün. Son tarihli hatırlatmalar da oluşturabilirsin, Google&apos;ı
            bağladıysan bunlar Google Takvim&apos;e de eklenir.
          </p>
        ),
      },
      {
        id: "budgets",
        q: "Bütçeler ve uyarılar nasıl çalışıyor?",
        a: (
          <p>
            <L href="/budgets">Bütçeler</L> sayfasında bir kategori ya da bütün harcamalar için aylık bir sınır koy. Yeni
            bir harcama bütçeyi yüzde 80&apos;in üstüne çıkarınca Kasa seni uyarır, sınırı aşınca bir kez daha. Aynı
            seviye için iki kez uyarılmazsın. Ev faturalarında sadece senin payın sayılır.
          </p>
        ),
      },
      {
        id: "subscriptions",
        q: "Kasa aboneliklerimi nasıl buluyor?",
        a: (
          <p>
            <L href="/subscriptions">Abonelikler</L> sayfasında tespiti çalıştır. Kasa, Netflix ya da Spotify gibi her ay
            aynı mağazadan tekrarlanan ödemeleri arar ve bir sonrakinin ne zaman beklendiğini gösterir. Market gibi
            günlük alışverişler sayılmaz. Bir kayıt abonelik değilse kapat, bir daha gelmez.
          </p>
        ),
      },
      {
        id: "ask",
        q: "Kasa'ya neler sorabilirim?",
        a: (
          <>
            <p>
              <L href="/chat">Kasa&apos;ya sor</L>, harcamalarından, bütçelerinden, aboneliklerinden, evinden ve gelen
              kutundan Türkçe ya da İngilizce cevap verir. Senin için harcama ya da ev faturası da ekleyebilir. Birkaç
              örnek:
            </p>
            <Examples items={ASK_EXAMPLES} />
            <p>Kasa sadece senin verilerini okuyabilir. Bir cevap yanlış görünüyorsa rakamları ilgili sayfada kontrol et.</p>
          </>
        ),
      },
      {
        id: "slow",
        q: "Cevaplar neden bazen yavaş geliyor?",
        a: (
          <>
            <p>
              Geliştirme sunucusunda ekip açık modelleri ortak bir Ollama makinesinde çalıştırıyor. O an başka ne
              çalıştığına göre bir sohbet cevabı 30 ile 120 saniye sürebilir. Asıl üründe kullanılan Gemini ile cevaplar
              çok daha hızlı.
            </p>
            <p>
              Beklerken başka sayfalara geçebilirsin, döndüğünde cevap sohbette olur. Uzun süre kimse kullanmadıysa ilk
              istek, veritabanı uyanırken bir dakika kadar sürebilir.
            </p>
          </>
        ),
      },
      {
        id: "language-theme",
        q: "Dili ya da temayı nasıl değiştiririm?",
        a: (
          <p>
            Yan menünün en altından (telefonda önce menüyü aç) Dil olarak Türkçe ya da English, Tema olarak Açık, Sistem
            ya da Koyu seç. Tarayıcın ikisini de hatırlar.
          </p>
        ),
      },
      {
        id: "delete",
        q: "Verilerimi nasıl silerim?",
        a: (
          <>
            <p>
              Bir harcamayı Harcamalar sayfasındaki satırından sil. Bir ev faturasını onu ödeyen kişi silebilir, bakiyen
              sıfırken de evden ayrılabilirsin. Kasa&apos;nın Gmail ve Takvim erişimini kaldırmak için Ayarlar&apos;dan
              Google bağlantısını kes.
            </p>
            <p>
              Hesabının tamamını ve bütün verilerini silen bir düğme planlanıyor (<L href={DELETE_ISSUE_URL}>issue #13</L>
              ). O zamana kadar bir issue aç, senin için silelim. Ayrıntılar <L href="/privacy">gizlilik politikasında</L>.
            </p>
          </>
        ),
      },
    ],
    contactTitle: "Hâlâ takıldın mı?",
    contactText:
      "GitHub'da bir issue aç, neyi denediğini ve ne olduğunu anlat. Ekran görüntüsü işe yarar, ama önce kişisel bilgileri gizle.",
    contactNote: "GitHub issue'ları herkese açık. Kart numarası, ekstre ya da başka kişisel veri paylaşma.",
    newIssue: "GitHub'da yeni bir issue aç",
    allIssues: "Açılmış issue'lara bak",
    about: "Kasa hakkında",
    privacy: "Gizlilik politikası",
  },
};

export function HelpView() {
  const c = CONTENT[useLocale()];
  return (
    <div className="flex flex-col gap-6">
      <PageHeader title={c.title} subtitle={c.subtitle} />
      <div className="grid items-start gap-6 lg:grid-cols-3">
        <section aria-labelledby="faq-title" className="lg:col-span-2">
          <h2 id="faq-title" className="mb-3 text-lg font-semibold tracking-tight">
            {c.faqTitle}
          </h2>
          <div className="divide-y divide-border overflow-hidden rounded-2xl border border-border bg-card shadow-card">
            {c.faq.map((f) => (
              <details key={f.id} id={f.id} className="group scroll-mt-24">
                <summary className="flex cursor-pointer list-none items-center justify-between gap-4 px-5 py-4 text-[15px] font-medium transition hover:bg-card-hover focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-accent [&::-webkit-details-marker]:hidden">
                  <h3>{f.q}</h3>
                  <ChevronDown
                    aria-hidden
                    className="size-4 shrink-0 text-muted transition-transform group-open:rotate-180 motion-reduce:transition-none"
                  />
                </summary>
                <div className="flex flex-col gap-3 px-5 pb-5 text-sm leading-relaxed text-foreground/90">{f.a}</div>
              </details>
            ))}
          </div>
        </section>
        <Card title={c.contactTitle} className="lg:sticky lg:top-8">
          <div className="flex gap-3">
            <span aria-hidden className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-accent-soft text-accent">
              <LifeBuoy className="size-[18px]" />
            </span>
            <p className="text-sm text-muted">{c.contactText}</p>
          </div>
          <p className="mt-3 text-xs text-muted">{c.contactNote}</p>
          <ul className="mt-4 flex flex-col items-start gap-1">
            <li>
              <a href={NEW_ISSUE_URL} className={cardLinkClass}>
                {c.newIssue} <ExternalLink aria-hidden className="size-3.5" />
              </a>
            </li>
            <li>
              <a href={ISSUES_URL} className={cardLinkClass}>
                {c.allIssues} <ExternalLink aria-hidden className="size-3.5" />
              </a>
            </li>
            <li>
              <Link href="/about" className={cardLinkClass}>
                {c.about}
              </Link>
            </li>
            <li>
              <Link href="/privacy" className={cardLinkClass}>
                {c.privacy}
              </Link>
            </li>
          </ul>
        </Card>
      </div>
    </div>
  );
}
