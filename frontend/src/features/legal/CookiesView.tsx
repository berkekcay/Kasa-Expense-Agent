"use client";

// Cookie and browser storage notice. The keys listed here must match the code:
// lib/theme.ts (kasa.theme), lib/i18n.ts (kasa.locale), lib/auth.ts (kasa.userId),
// features/chat/chatStore.ts (kasa.chat.<user>), and Firebase Auth's own storage.

import { useLocale } from "@/lib/i18n";
import { LEGAL_UPDATED } from "@/features/info/site";
import { A, Code, InfoTable, P, Section, TextPage } from "./parts";

export function CookiesView() {
  return useLocale() === "tr" ? <CookiesTr /> : <CookiesEn />;
}

export function CookiesEn() {
  return (
    <TextPage
      title="Cookies and browser storage"
      subtitle="What Kasa keeps in your browser, and why."
      updated={`Last updated: ${LEGAL_UPDATED.en}`}
    >
      <Section id="short" title="In short">
        <P>
          Kasa has no ads, no analytics and no tracking cookies. It keeps a few small settings in your browser so the
          app remembers your choices, and the sign-in service keeps you signed in.
        </P>
      </Section>

      <Section id="what" title="What is stored">
        <InfoTable
          caption="Browser storage used by Kasa"
          head={["Name", "Where", "What for", "How long"]}
          rows={[
            [<Code key="k">kasa.theme</Code>, "localStorage", "Your light or dark theme choice", "Until you change it or clear site data"],
            [<Code key="k">kasa.locale</Code>, "localStorage", "Your language, Turkish or English", "Until you change it or clear site data"],
            [
              <Code key="k">kasa.userId</Code>,
              "localStorage",
              "The demo user name, only when Google sign-in is not set up (local development)",
              "Until you change it or clear site data",
            ],
            [
              <Code key="k">kasa.chat.&lt;user&gt;</Code>,
              "sessionStorage",
              "The Ask Kasa conversation in this tab, so it survives a reload",
              "Until you close the tab",
            ],
            [
              "Firebase Auth",
              "IndexedDB or localStorage",
              "Keeps you signed in with Google",
              "Until you sign out",
            ],
          ]}
        />
        <P>
          When you sign in, Google&apos;s sign-in window opens on Google&apos;s own pages, where Google may set its own
          cookies. Google&apos;s privacy policy applies to those.
        </P>
      </Section>

      <Section id="consent" title="Why there is no cookie banner">
        <P>
          Everything above is needed for a feature you use, and none of it is used to track you or show ads. That is why
          Kasa does not ask for cookie consent. If this changes, we will ask first and update this page.
        </P>
      </Section>

      <Section id="clear" title="How to remove it">
        <P>
          Sign out to end your Google session. To remove everything else, clear the site data for Kasa in your
          browser&apos;s settings. Your expenses are not stored in the browser, so clearing it does not delete them. See
          the <A href="/privacy">privacy policy</A> for how to delete your data.
        </P>
      </Section>
    </TextPage>
  );
}

export function CookiesTr() {
  return (
    <TextPage
      title="Çerezler ve tarayıcı depolama"
      subtitle="Kasa'nın tarayıcında ne sakladığı ve neden."
      updated={`Son güncelleme: ${LEGAL_UPDATED.tr}`}
    >
      <Section id="short" title="Kısaca">
        <P>
          Kasa&apos;da reklam, analitik ya da takip çerezi yok. Seçimlerini hatırlamak için tarayıcında birkaç küçük ayar
          tutar, giriş servisi de oturumunu açık tutar.
        </P>
      </Section>

      <Section id="what" title="Neler saklanıyor">
        <InfoTable
          caption="Kasa'nın kullandığı tarayıcı depolama alanları"
          head={["Ad", "Nerede", "Ne için", "Ne kadar süre"]}
          rows={[
            [<Code key="k">kasa.theme</Code>, "localStorage", "Açık ya da koyu tema seçimin", "Değiştirene ya da site verilerini silene kadar"],
            [<Code key="k">kasa.locale</Code>, "localStorage", "Dil seçimin, Türkçe ya da İngilizce", "Değiştirene ya da site verilerini silene kadar"],
            [
              <Code key="k">kasa.userId</Code>,
              "localStorage",
              "Demo kullanıcı adı, sadece Google ile giriş kurulu değilken (yerel geliştirme)",
              "Değiştirene ya da site verilerini silene kadar",
            ],
            [
              <Code key="k">kasa.chat.&lt;kullanıcı&gt;</Code>,
              "sessionStorage",
              "Bu sekmedeki Kasa'ya sor sohbeti, sayfa yenilenince kaybolmasın diye",
              "Sekmeyi kapatana kadar",
            ],
            ["Firebase Auth", "IndexedDB ya da localStorage", "Google ile girişini açık tutar", "Çıkış yapana kadar"],
          ]}
        />
        <P>
          Giriş yaparken Google&apos;ın giriş penceresi Google&apos;ın kendi sayfalarında açılır, Google orada kendi
          çerezlerini kullanabilir. Bunlar için Google&apos;ın gizlilik politikası geçerli.
        </P>
      </Section>

      <Section id="consent" title="Neden çerez uyarısı yok">
        <P>
          Yukarıdakilerin hepsi kullandığın bir özellik için gerekli ve hiçbiri seni takip etmek ya da reklam göstermek
          için kullanılmıyor. Bu yüzden Kasa çerez onayı istemiyor. Bu değişirse önce sana soracağız ve bu sayfayı
          güncelleyeceğiz.
        </P>
      </Section>

      <Section id="clear" title="Nasıl silersin">
        <P>
          Google oturumunu kapatmak için çıkış yap. Geri kalan her şeyi silmek için tarayıcı ayarlarından Kasa&apos;nın
          site verilerini temizle. Harcamaların tarayıcıda saklanmadığı için bu onları silmez. Verilerini nasıl
          sileceğin <A href="/privacy">gizlilik politikasında</A> anlatılıyor.
        </P>
      </Section>
    </TextPage>
  );
}
