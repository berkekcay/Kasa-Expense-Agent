"use client";

// Terms of use. English and Turkish are separate components; keep them in step.

import { Alert } from "@/components/ui";
import { useLocale } from "@/lib/i18n";
import { DELETE_ISSUE_URL, LEGAL_UPDATED, NEW_ISSUE_URL } from "@/features/info/site";
import { A, List, P, Section, TextPage } from "./parts";

export function TermsView() {
  return useLocale() === "tr" ? <TermsTr /> : <TermsEn />;
}

export function TermsEn() {
  return (
    <TextPage
      title="Terms of use"
      subtitle="The rules for using Kasa, in plain words."
      updated={`Last updated: ${LEGAL_UPDATED.en}`}
      notice={
        <Alert title="Kasa is a student project and a demo">
          It is free, it comes with no guarantees, and parts of it are still being built. Please use test data or only
          data you are comfortable sharing.
        </Alert>
      }
    >
      <Section id="what" title="What Kasa is">
        <P>
          Kasa is a money assistant made by a student team for the AI-Augmented Software Engineering course at Istinye
          University in 2026. It helps you track your own spending and the bills you share with flatmates. By using
          Kasa you accept these terms and our <A href="/privacy">privacy policy</A>.
        </P>
      </Section>

      <Section id="not-advice" title="Not a bank, not financial advice">
        <P>
          Kasa does not hold, move or pay money. It only records what you tell it. Budgets, warnings, charts and answers
          in the chat are there to help you see your spending. They are not financial, tax or legal advice. Decide for
          yourself, and ask a qualified person when it matters.
        </P>
      </Section>

      <Section id="ai" title="AI can make mistakes">
        <P>
          Kasa uses AI models to read receipts, statements and emails and to understand your questions. A model can
          misread a total, a date or a shop name, or pick the wrong category.
        </P>
        <List>
          <li>Check the amount, date and category before you approve an inbox item or keep a scanned receipt.</li>
          <li>
            The math itself (totals, splits, balances, currency conversion) is done by plain code, not by the model. It is
            only as right as the data you saved.
          </li>
          <li>Before you pay a flatmate, check the balance against your own records.</li>
        </List>
      </Section>

      <Section id="account" title="Your account">
        <List>
          <li>One account is for one person. Keep your Google account secure; anyone who can sign in as you can see your data.</li>
          <li>
            In the local demo there is no password: anyone who types the same user name sees the same data. Do not put
            real personal data into a demo user.
          </li>
          <li>You are responsible for what you add to Kasa and for having the right to add it.</li>
        </List>
      </Section>

      <Section id="acceptable-use" title="Acceptable use">
        <P>Please do not:</P>
        <List>
          <li>upload other people&apos;s documents or add people to a house without asking them;</li>
          <li>try to see or change other users&apos; data, or get around Kasa&apos;s security checks;</li>
          <li>
            try to make the AI do something outside its job, for example with instructions hidden in a receipt, email or
            chat message;
          </li>
          <li>overload Kasa with automated requests or very large uploads;</li>
          <li>use Kasa for anything illegal, including fraud or money laundering.</li>
        </List>
        <P>We may remove data or block access when these rules are broken.</P>
      </Section>

      <Section id="houses" title="Shared houses">
        <P>
          Members of a house see that house&apos;s bills, shares, payments and reminders. A bill can be deleted by the
          person who paid it, and you can leave a house when your balance is zero. Agree with your flatmates on how you
          use Kasa together.
        </P>
      </Section>

      <Section id="no-warranty" title="No warranty">
        <P>
          Kasa is provided as it is, without any warranty. It can be slow, unavailable, change without notice or be reset,
          and demo data can be lost. Keep your own records of anything important. As far as the law allows, the project
          team is not liable for losses that come from using Kasa or from relying on its numbers.
        </P>
      </Section>

      <Section id="deletion" title="Deleting your data and account">
        <List>
          <li>You can delete your own expenses on the Expenses page.</li>
          <li>You can disconnect Google at any time in <A href="/settings">Settings</A>. Kasa then deletes its Google token.</li>
          <li>
            A way to delete your whole account and all its data is planned (<A href={DELETE_ISSUE_URL}>issue #13</A>).
            Until then, ask us and we will delete it for you.
          </li>
        </List>
      </Section>

      <Section id="third-parties" title="Other services">
        <P>
          Kasa relies on Google (Gemini, Firebase Authentication, Gmail, Google Calendar, Cloud Run) and on Microsoft Azure
          for the planned database. Their own terms apply to what they provide.
        </P>
      </Section>

      <Section id="changes" title="Changes and contact">
        <P>
          We may update these terms as the project changes. The date at the top shows the latest version. For questions,
          open an issue on our <A href={NEW_ISSUE_URL}>GitHub repository</A>; do not write personal data in it.
        </P>
      </Section>
    </TextPage>
  );
}

export function TermsTr() {
  return (
    <TextPage
      title="Kullanım koşulları"
      subtitle="Kasa'yı kullanmanın kuralları, sade bir dille."
      updated={`Son güncelleme: ${LEGAL_UPDATED.tr}`}
      notice={
        <Alert title="Kasa bir öğrenci projesi ve demo">
          Ücretsiz, hiçbir garantisi yok ve bazı kısımları hâlâ yapım aşamasında. Lütfen deneme verisi ya da paylaşmakta
          sakınca görmediğin veriler kullan.
        </Alert>
      }
    >
      <Section id="what" title="Kasa nedir">
        <P>
          Kasa, İstinye Üniversitesi&apos;nde 2026 yılında verilen AI-Augmented Software Engineering dersi için bir
          öğrenci ekibinin yaptığı bir para asistanı. Kendi harcamalarını ve ev arkadaşlarınla paylaştığın faturaları
          takip etmene yardım eder. Kasa&apos;yı kullanarak bu koşulları ve <A href="/privacy">gizlilik politikamızı</A>{" "}
          kabul etmiş olursun.
        </P>
      </Section>

      <Section id="not-advice" title="Banka değil, finansal tavsiye değil">
        <P>
          Kasa para tutmaz, transfer etmez ya da ödeme yapmaz. Sadece ona söylediğin şeyi kaydeder. Bütçeler, uyarılar,
          grafikler ve sohbetteki cevaplar harcamalarını görmen için var. Finansal, vergi ya da hukuki tavsiye değiller.
          Kararı sen ver, önemli konularda bir uzmana danış.
        </P>
      </Section>

      <Section id="ai" title="Yapay zeka hata yapabilir">
        <P>
          Kasa fişleri, ekstreleri ve e-postaları okumak ve sorularını anlamak için yapay zeka modelleri kullanır. Model
          bir toplamı, tarihi ya da mağaza adını yanlış okuyabilir veya yanlış kategori seçebilir.
        </P>
        <List>
          <li>Bir gelen kutusu kaydını onaylamadan ya da taranan fişi bırakmadan önce tutarı, tarihi ve kategoriyi kontrol et.</li>
          <li>
            Hesabın kendisini (toplamlar, bölüşümler, bakiyeler, kur çevirme) model değil, düz kod yapar. Ama sonuç ancak
            kaydettiğin veri kadar doğrudur.
          </li>
          <li>Bir ev arkadaşına ödeme yapmadan önce bakiyeyi kendi kayıtlarınla karşılaştır.</li>
        </List>
      </Section>

      <Section id="account" title="Hesabın">
        <List>
          <li>
            Bir hesap bir kişi içindir. Google hesabını güvende tut, senin yerine giriş yapabilen herkes verilerini
            görebilir.
          </li>
          <li>
            Yerel demoda şifre yok: aynı kullanıcı adını yazan herkes aynı verileri görür. Demo kullanıcısına gerçek
            kişisel veri girme.
          </li>
          <li>Kasa&apos;ya eklediğin her şeyden ve onu ekleme hakkına sahip olmaktan sen sorumlusun.</li>
        </List>
      </Section>

      <Section id="acceptable-use" title="Kabul edilebilir kullanım">
        <P>Lütfen şunları yapma:</P>
        <List>
          <li>başkalarının belgelerini yüklemek ya da birini sormadan bir eve eklemek,</li>
          <li>başka kullanıcıların verilerini görmeye ya da değiştirmeye, Kasa&apos;nın güvenlik kontrollerini aşmaya çalışmak,</li>
          <li>
            yapay zekaya işi dışında bir şey yaptırmaya çalışmak, örneğin bir fişe, e-postaya ya da sohbet mesajına
            gizlenmiş talimatlarla,
          </li>
          <li>Kasa&apos;yı otomatik isteklerle ya da çok büyük yüklemelerle yormak,</li>
          <li>Kasa&apos;yı dolandırıcılık ya da kara para aklama dahil yasa dışı herhangi bir iş için kullanmak.</li>
        </List>
        <P>Bu kurallara uyulmadığında verileri kaldırabilir ya da erişimi engelleyebiliriz.</P>
      </Section>

      <Section id="houses" title="Ortak evler">
        <P>
          Bir evin üyeleri o evin faturalarını, paylarını, ödemelerini ve hatırlatmalarını görür. Bir faturayı onu ödeyen
          kişi silebilir, bakiyen sıfırken de evden ayrılabilirsin. Kasa&apos;yı birlikte nasıl kullanacağınızı ev
          arkadaşlarınla konuş.
        </P>
      </Section>

      <Section id="no-warranty" title="Garanti yok">
        <P>
          Kasa olduğu gibi, hiçbir garanti olmadan sunulur. Yavaş çalışabilir, kapalı olabilir, haber vermeden değişebilir
          ya da sıfırlanabilir. Demo verileri kaybolabilir. Önemli olan her şeyin kaydını kendin de tut. Kanunun izin
          verdiği ölçüde proje ekibi, Kasa&apos;yı kullanmaktan ya da rakamlarına güvenmekten doğan kayıplardan sorumlu
          değildir.
        </P>
      </Section>

      <Section id="deletion" title="Verilerini ve hesabını silmek">
        <List>
          <li>Kendi harcamalarını Harcamalar sayfasından silebilirsin.</li>
          <li>
            Google bağlantısını istediğin zaman <A href="/settings">Ayarlar</A> sayfasından kesebilirsin. Kasa o zaman
            Google anahtarını siler.
          </li>
          <li>
            Hesabının tamamını ve bütün verilerini silmenin bir yolu planlanıyor (<A href={DELETE_ISSUE_URL}>issue #13</A>
            ). O zamana kadar bizden iste, senin için silelim.
          </li>
        </List>
      </Section>

      <Section id="third-parties" title="Diğer hizmetler">
        <P>
          Kasa, Google&apos;ın hizmetlerini (Gemini, Firebase Authentication, Gmail, Google Takvim, Cloud Run) ve planlanan
          veritabanı için Microsoft Azure&apos;u kullanır. Sağladıkları hizmetler için onların kendi koşulları geçerli.
        </P>
      </Section>

      <Section id="changes" title="Değişiklikler ve iletişim">
        <P>
          Proje değiştikçe bu koşulları güncelleyebiliriz. En üstteki tarih son sürümü gösterir. Soruların için{" "}
          <A href={NEW_ISSUE_URL}>GitHub deposunda</A> bir issue aç, içine kişisel veri yazma.
        </P>
      </Section>
    </TextPage>
  );
}
