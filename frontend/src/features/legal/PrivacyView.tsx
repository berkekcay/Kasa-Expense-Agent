"use client";

// Privacy policy and the KVKK information notice (aydınlatma metni). The English and Turkish
// texts are separate components because they are long prose, not UI labels. Keep the two in
// step: a change to one needs the same change in the other, and a new LEGAL_UPDATED date.

import { Alert } from "@/components/ui";
import { useLocale } from "@/lib/i18n";
import { DELETE_ISSUE_URL, ISSUES_URL, LEGAL_UPDATED, NEW_ISSUE_URL } from "@/features/info/site";
import { A, Code, List, P, Section, SubHeading, TextPage } from "./parts";

export function PrivacyView() {
  return useLocale() === "tr" ? <PrivacyTr /> : <PrivacyEn />;
}

const SECTIONS_EN = [
  { id: "who", title: "Who is responsible" },
  { id: "data", title: "What data Kasa processes" },
  { id: "purposes", title: "Why we use it" },
  { id: "legal-basis", title: "Legal basis" },
  { id: "storage", title: "Where it is stored" },
  { id: "sharing", title: "Who else receives it" },
  { id: "abroad", title: "Transfers abroad" },
  { id: "retention", title: "How long we keep it" },
  { id: "security", title: "How we protect it" },
  { id: "rights", title: "Your rights (KVKK article 11)" },
  { id: "contact", title: "How to contact us" },
  { id: "changes", title: "Changes to this notice" },
];

export function PrivacyEn() {
  return (
    <TextPage
      title="Privacy policy"
      subtitle="How Kasa handles your personal data. This page is also our information notice under the Turkish Personal Data Protection Law No. 6698 (KVKK)."
      updated={`Last updated: ${LEGAL_UPDATED.en}`}
      tocLabel="On this page"
      toc={SECTIONS_EN}
      notice={
        <Alert title="Kasa is a student project and a demo">
          Kasa is built by students for a university course. It is not a commercial service. Please use test data, or
          only data you are comfortable sharing. Do not upload documents that show full card numbers, ID numbers or
          passwords.
        </Alert>
      }
    >
      <Section id="who" title="Who is responsible">
        <P>
          Kasa is a team project for the AI-Augmented Software Engineering course at Istinye University in 2026. The
          project team (Berke Eren Akçay, Mustafa, Ömer, Zehra and Yusuf) decides why and how your data is processed, so
          the team is the data controller (veri sorumlusu) for Kasa. The product owner, Berke Eren Akçay, is the contact
          person.
        </P>
      </Section>

      <Section id="data" title="What data Kasa processes">
        <SubHeading>Account</SubHeading>
        <P>
          When you sign in with Google, Kasa receives your Google user id, your name and your email address through
          Firebase Authentication. In the local demo there is no sign-in: you type a user name instead.
        </P>
        <SubHeading>Money data you add</SubHeading>
        <P>
          Expenses (shop, date, amount, currency, category, items and notes), your budgets and subscriptions, and for a
          shared flat: the house, its members, bills, each person&apos;s share, payments between flatmates and settle-up
          reminders.
        </P>
        <SubHeading>Receipt photos</SubHeading>
        <P>
          A photo you upload is sent to the AI model so it can read the shop, date, items and total. Kasa saves the
          expense it reads. It does not keep the photo.
        </P>
        <SubHeading>Bank statements</SubHeading>
        <P>
          A CSV, Excel or PDF statement you upload is read once. Each spending line becomes an inbox item (description, date,
          amount) that waits for your decision. Kasa does not keep the file. A PDF statement is sent to the AI model so
          it can find the lines; a CSV file is read by Kasa&apos;s own code.
        </P>
        <SubHeading>Gmail and Google Calendar (only if you connect them)</SubHeading>
        <List>
          <li>
            Gmail access is read-only. Kasa looks at emails from the last 30 days that look like receipts, invoices or
            orders. For each match it keeps the subject, the sender, a short excerpt and the details it read, as an
            inbox item. The email text is sent to the AI model to find those details.
          </li>
          <li>Kasa never sends, deletes or changes your email.</li>
          <li>Calendar access is only used to add the settle-up reminders you create.</li>
          <li>Kasa stores the Google refresh token that keeps the connection working, encrypted.</li>
        </List>
        <SubHeading>Chat with Ask Kasa</SubHeading>
        <P>
          Your questions and Kasa&apos;s answers. To answer, Kasa reads your own expenses, budgets, subscriptions and
          house shares. The conversation is held in the server&apos;s memory while it is open and is not written to the
          database. Your browser also keeps it in the current tab (see the <A href="/cookies">cookie notice</A>).
        </P>
        <SubHeading>Technical data</SubHeading>
        <P>
          Like most web services, the hosting platform may record basic request data such as time, address and errors.
          We only look at it to keep Kasa working and secure.
        </P>
      </Section>

      <Section id="purposes" title="Why we use it">
        <List>
          <li>To provide the features you use: tracking expenses, splitting bills, budgets and subscriptions.</li>
          <li>To turn receipts, statements and emails into expenses that you approve.</li>
          <li>To answer your questions in the chat, with charts.</li>
          <li>To keep Kasa secure, find errors and fix them.</li>
          <li>To build, test and present Kasa as a course project.</li>
        </List>
        <P>We do not sell your data, we do not show ads and we do not use your data to build an advertising profile.</P>
      </Section>

      <Section id="legal-basis" title="Legal basis">
        <P>In plain words, these are the grounds in article 5 of KVKK that we rely on:</P>
        <List>
          <li>
            Providing the service you asked for: we need your account and the data you add to run Kasa for you (KVKK
            article 5(2)(c)).
          </li>
          <li>
            Our legitimate interest in keeping Kasa secure and working, as long as it does not harm your rights (KVKK
            article 5(2)(f)).
          </li>
          <li>
            Your explicit consent for connecting Gmail and Google Calendar. You give it on Google&apos;s permission screen
            and you can withdraw it at any time with Disconnect Google in Settings.
          </li>
        </List>
      </Section>

      <Section id="storage" title="Where it is stored">
        <P>
          During development and the demo, Kasa stores data in a SQLite database on the computer that runs it. For the
          public version we plan to use Azure SQL Database in an EU region of Microsoft Azure, and to host the app on
          Google Cloud Run in the EU (Belgium). That setup is not live yet; we will update this page when it is.
        </P>
      </Section>

      <Section id="sharing" title="Who else receives it">
        <List>
          <li>
            <strong className="font-semibold">Google</strong>: the Gemini API reads receipt photos, PDF statements, emails
            and chat messages; Firebase Authentication handles sign-in; Gmail and Calendar if you connect them; Google
            Cloud Run hosts the app.
          </li>
          <li>
            <strong className="font-semibold">Microsoft</strong>: Azure SQL Database stores the data in the planned public
            version.
          </li>
          <li>
            <strong className="font-semibold">Your flatmates</strong>: members of a house you belong to see that
            house&apos;s bills, shares, payments and reminders, and your display name.
          </li>
        </List>
        <P>
          Kasa also downloads exchange rates from the Central Bank of the Republic of Türkiye (TCMB). No personal data is
          sent for that. Google&apos;s and Microsoft&apos;s own terms and privacy policies apply to what they process.
          Depending on the plan the project uses, Google may keep Gemini API content for a limited time or use it to
          improve its services.
        </P>
      </Section>

      <Section id="abroad" title="Transfers abroad">
        <P>
          Google and Microsoft process data on servers outside Türkiye, for example in the EU and, for some Google
          services, in other countries. This is a transfer of personal data abroad under article 9 of KVKK. It happens
          only to run the features described above. If you do not want this, please do not upload real documents and do
          not connect Gmail.
        </P>
      </Section>

      <Section id="retention" title="How long we keep it">
        <List>
          <li>Expenses, houses, budgets and subscriptions: while your account exists, or until you delete them.</li>
          <li>Inbox items: until you approve or reject them. An approved item stays linked to its expense.</li>
          <li>Chat: until the conversation ends or the server restarts. The copy in your browser tab goes when you close it.</li>
          <li>Google connection: until you disconnect it. Kasa then deletes the stored Google token.</li>
        </List>
        <P>
          A button to delete your account and all your data is planned (<A href={DELETE_ISSUE_URL}>issue #13</A>). Until it
          is ready, you can ask us to delete your data (see <A href="#contact">How to contact us</A>). We do not keep data
          longer than the project needs.
        </P>
      </Section>

      <Section id="security" title="How we protect it">
        <List>
          <li>Every query is limited to the signed-in user. You only see your own data and the houses you belong to.</li>
          <li>
            The chat can only run a single read-only query over your own data, and a second agent checks each query
            before it runs.
          </li>
          <li>Google refresh tokens are encrypted and never written to logs.</li>
          <li>Keys and passwords are kept out of the code, in environment settings.</li>
          <li>
            For the public version, the database itself will also hide other users&apos; rows (row-level security). This
            is written and tested offline, but not yet running on a real server.
          </li>
        </List>
        <P>No system is perfectly secure. As a student project, Kasa has not had an external security audit.</P>
      </Section>

      <Section id="rights" title="Your rights (KVKK article 11)">
        <P>You can ask us to:</P>
        <List>
          <li>tell you whether we process your personal data;</li>
          <li>give you information about it if we do;</li>
          <li>tell you why we process it and whether we use it for that purpose;</li>
          <li>tell you who we transfer it to, in Türkiye or abroad;</li>
          <li>correct it if it is incomplete or wrong;</li>
          <li>delete or destroy it under the conditions in article 7 of KVKK;</li>
          <li>tell the people we transferred it to about a correction or deletion;</li>
          <li>reconsider a result that goes against you and comes only from automated analysis of your data;</li>
          <li>compensate you if you suffer damage because your data was processed unlawfully.</li>
        </List>
        <P>We answer requests free of charge and within 30 days at the latest.</P>
      </Section>

      <Section id="contact" title="How to contact us">
        <P>
          Open an issue on our <A href={NEW_ISSUE_URL}>GitHub repository</A> and say that you have a privacy request.
          GitHub issues are public, so do not write personal data in the issue. We will reply there with a private way
          to continue. You can see earlier questions on the <A href={ISSUES_URL}>issues page</A>.
        </P>
        <P>
          You can also find your data yourself: everything you added is on the Expenses, House, Budgets, Subscriptions and
          Inbox pages, and your Google connection is in <A href="/settings">Settings</A>.
        </P>
      </Section>

      <Section id="changes" title="Changes to this notice">
        <P>
          If we change how Kasa uses data, we update this page and the date at the top. The previous versions are in the
          repository history (<Code>frontend/src/features/legal/PrivacyView.tsx</Code>).
        </P>
      </Section>
    </TextPage>
  );
}

const SECTIONS_TR = [
  { id: "who", title: "Veri sorumlusu" },
  { id: "data", title: "Hangi verileri işliyoruz" },
  { id: "purposes", title: "Verileri ne için kullanıyoruz" },
  { id: "legal-basis", title: "Hukuki sebep" },
  { id: "storage", title: "Veriler nerede saklanıyor" },
  { id: "sharing", title: "Veriler kimlere aktarılıyor" },
  { id: "abroad", title: "Yurt dışına aktarım" },
  { id: "retention", title: "Ne kadar süre saklıyoruz" },
  { id: "security", title: "Verileri nasıl koruyoruz" },
  { id: "rights", title: "KVKK 11. madde kapsamındaki hakların" },
  { id: "contact", title: "Bize nasıl ulaşırsın" },
  { id: "changes", title: "Bu metindeki değişiklikler" },
];

export function PrivacyTr() {
  return (
    <TextPage
      title="Gizlilik politikası ve KVKK aydınlatma metni"
      subtitle="Kasa'nın kişisel verilerini nasıl işlediği. Bu sayfa aynı zamanda 6698 sayılı Kişisel Verilerin Korunması Kanunu (KVKK) kapsamındaki aydınlatma metnimiz."
      updated={`Son güncelleme: ${LEGAL_UPDATED.tr}`}
      tocLabel="Bu sayfada"
      toc={SECTIONS_TR}
      notice={
        <Alert title="Kasa bir öğrenci projesi ve demo">
          Kasa, bir üniversite dersi için öğrenciler tarafından yapıldı. Ticari bir hizmet değil. Lütfen deneme verisi
          ya da paylaşmakta sakınca görmediğin veriler kullan. Kart numarasının tamamını, kimlik numarasını ya da şifre
          gösteren belgeleri yükleme.
        </Alert>
      }
    >
      <Section id="who" title="Veri sorumlusu">
        <P>
          Kasa, İstinye Üniversitesi&apos;nde 2026 yılında verilen AI-Augmented Software Engineering dersinin ekip
          projesi. Verilerinin neden ve nasıl işleneceğine proje ekibi (Berke Eren Akçay, Mustafa, Ömer, Zehra ve Yusuf)
          karar veriyor. Bu yüzden Kasa için veri sorumlusu proje ekibi. İletişim kişisi product owner Berke Eren
          Akçay.
        </P>
      </Section>

      <Section id="data" title="Hangi verileri işliyoruz">
        <SubHeading>Hesap bilgileri</SubHeading>
        <P>
          Google ile giriş yaptığında Firebase Authentication üzerinden Google kullanıcı kimliğin, adın ve e-posta
          adresin Kasa&apos;ya gelir. Yerel demoda giriş yok, onun yerine bir kullanıcı adı yazıyorsun.
        </P>
        <SubHeading>Eklediğin para verileri</SubHeading>
        <P>
          Harcamalar (mağaza, tarih, tutar, para birimi, kategori, kalemler ve notlar), bütçelerin ve aboneliklerin.
          Ortak evde ise ev, ev arkadaşların, faturalar, herkesin payı, ev arkadaşları arasındaki ödemeler ve hesaplaşma
          hatırlatmaları.
        </P>
        <SubHeading>Fiş fotoğrafları</SubHeading>
        <P>
          Yüklediğin fotoğraf, mağazayı, tarihi, kalemleri ve toplamı okuyabilmesi için yapay zeka modeline gönderilir.
          Kasa okuduğu harcamayı kaydeder, fotoğrafı saklamaz.
        </P>
        <SubHeading>Banka ekstreleri</SubHeading>
        <P>
          Yüklediğin CSV, Excel ya da PDF ekstre bir kez okunur. Her harcama satırı, senin kararını bekleyen bir gelen kutusu
          kaydı olur (açıklama, tarih, tutar). Kasa dosyanın kendisini saklamaz. PDF ekstre satırları bulabilmesi için
          yapay zeka modeline gönderilir, CSV dosyasını ise Kasa&apos;nın kendi kodu okur.
        </P>
        <SubHeading>Gmail ve Google Takvim (sadece bağlarsan)</SubHeading>
        <List>
          <li>
            Gmail erişimi salt okunur. Kasa son 30 günün fiş, fatura ya da sipariş gibi görünen e-postalarına bakar. Her
            eşleşme için konuyu, göndereni, kısa bir alıntıyı ve okuduğu bilgileri bir gelen kutusu kaydı olarak saklar.
            Bu bilgileri bulmak için e-posta metni yapay zeka modeline gönderilir.
          </li>
          <li>Kasa hiçbir zaman e-posta göndermez, silmez ya da değiştirmez.</li>
          <li>Takvim erişimi sadece senin oluşturduğun hesaplaşma hatırlatmalarını eklemek için kullanılır.</li>
          <li>Bağlantıyı açık tutan Google yenileme anahtarı (refresh token) şifrelenerek saklanır.</li>
        </List>
        <SubHeading>Kasa&apos;ya sor sohbeti</SubHeading>
        <P>
          Soruların ve Kasa&apos;nın cevapları. Kasa cevap vermek için sadece senin harcamalarını, bütçelerini,
          aboneliklerini ve ev paylarını okur. Sohbet açık olduğu sürece sunucunun belleğinde tutulur, veritabanına
          yazılmaz. Tarayıcın da sohbeti o sekmede saklar (<A href="/cookies">çerez bildirimine</A> bak).
        </P>
        <SubHeading>Teknik veriler</SubHeading>
        <P>
          Çoğu web hizmetinde olduğu gibi barındırma platformu istek zamanı, adres ve hata kaydı gibi temel bilgileri
          tutabilir. Bunlara sadece Kasa&apos;yı çalışır ve güvenli tutmak için bakarız.
        </P>
      </Section>

      <Section id="purposes" title="Verileri ne için kullanıyoruz">
        <List>
          <li>Kullandığın özellikleri sunmak için: harcama takibi, fatura bölüşme, bütçeler ve abonelikler.</li>
          <li>Fişleri, ekstreleri ve e-postaları senin onaylayacağın harcamalara çevirmek için.</li>
          <li>Sohbette sorularını grafiklerle cevaplamak için.</li>
          <li>Kasa&apos;yı güvenli tutmak, hataları bulmak ve düzeltmek için.</li>
          <li>Kasa&apos;yı bir ders projesi olarak geliştirmek, test etmek ve sunmak için.</li>
        </List>
        <P>Verilerini satmıyoruz, reklam göstermiyoruz ve verilerinle reklam profili oluşturmuyoruz.</P>
      </Section>

      <Section id="legal-basis" title="Hukuki sebep">
        <P>Kısaca, KVKK&apos;nın 5. maddesindeki şu sebeplere dayanıyoruz:</P>
        <List>
          <li>
            İstediğin hizmeti sunmak: Kasa&apos;yı senin için çalıştırmak için hesabına ve eklediğin verilere ihtiyacımız
            var (KVKK md. 5/2-c, sözleşmenin kurulması ve ifası).
          </li>
          <li>
            Kasa&apos;yı güvenli ve çalışır tutmaktaki meşru menfaatimiz, senin hak ve özgürlüklerine zarar vermemek
            şartıyla (KVKK md. 5/2-f).
          </li>
          <li>
            Gmail ve Google Takvim bağlantısı için açık rızan. Rızanı Google&apos;ın izin ekranında verirsin, istediğin
            zaman Ayarlar&apos;daki Google bağlantısını kes düğmesiyle geri alabilirsin.
          </li>
        </List>
      </Section>

      <Section id="storage" title="Veriler nerede saklanıyor">
        <P>
          Geliştirme ve demo sırasında Kasa verileri, onu çalıştıran bilgisayardaki bir SQLite veritabanında saklıyor.
          Herkese açık sürüm için verileri Microsoft Azure&apos;un AB bölgesindeki Azure SQL Database&apos;de tutmayı,
          uygulamayı da AB&apos;de (Belçika) Google Cloud Run üzerinde çalıştırmayı planlıyoruz. Bu kurulum henüz
          yayında değil, yayına girdiğinde bu sayfayı güncelleyeceğiz.
        </P>
      </Section>

      <Section id="sharing" title="Veriler kimlere aktarılıyor">
        <List>
          <li>
            <strong className="font-semibold">Google</strong>: Gemini API fiş fotoğraflarını, PDF ekstreleri,
            e-postaları ve sohbet mesajlarını okur. Firebase Authentication girişi yönetir. Bağlarsan Gmail ve Takvim.
            Google Cloud Run uygulamayı barındırır.
          </li>
          <li>
            <strong className="font-semibold">Microsoft</strong>: planlanan herkese açık sürümde verileri Azure SQL
            Database saklar.
          </li>
          <li>
            <strong className="font-semibold">Ev arkadaşların</strong>: üyesi olduğun bir evin diğer üyeleri o evin
            faturalarını, paylarını, ödemelerini, hatırlatmalarını ve görünen adını görür.
          </li>
        </List>
        <P>
          Kasa döviz kurlarını Türkiye Cumhuriyet Merkez Bankası&apos;ndan (TCMB) indirir, bunun için kişisel veri
          gönderilmez. Google ve Microsoft&apos;un işlediği veriler için onların kendi koşulları ve gizlilik politikaları
          geçerli. Projenin kullandığı plana göre Google, Gemini API&apos;ye gönderilen içeriği bir süre saklayabilir ya
          da hizmetlerini geliştirmek için kullanabilir.
        </P>
      </Section>

      <Section id="abroad" title="Yurt dışına aktarım">
        <P>
          Google ve Microsoft verileri Türkiye dışındaki sunucularda, örneğin AB&apos;de ve bazı Google hizmetlerinde
          başka ülkelerde işler. Bu, KVKK&apos;nın 9. maddesi kapsamında kişisel verilerin yurt dışına aktarılması
          demek. Aktarım sadece yukarıda anlatılan özellikleri çalıştırmak için yapılır. Bunu istemiyorsan lütfen gerçek
          belge yükleme ve Gmail&apos;i bağlama.
        </P>
      </Section>

      <Section id="retention" title="Ne kadar süre saklıyoruz">
        <List>
          <li>Harcamalar, evler, bütçeler ve abonelikler: hesabın durduğu sürece ya da sen silene kadar.</li>
          <li>Gelen kutusu kayıtları: onaylayana ya da reddedene kadar. Onaylanan kayıt, harcamasıyla bağlı kalır.</li>
          <li>Sohbet: konuşma bitene ya da sunucu yeniden başlayana kadar. Tarayıcındaki kopya sekmeyi kapatınca silinir.</li>
          <li>Google bağlantısı: bağlantıyı kesene kadar. Kesince Kasa sakladığı Google anahtarını siler.</li>
        </List>
        <P>
          Hesabını ve bütün verilerini silen bir düğme planlanıyor (<A href={DELETE_ISSUE_URL}>issue #13</A>). O hazır
          olana kadar verilerinin silinmesini bizden isteyebilirsin (<A href="#contact">Bize nasıl ulaşırsın</A>{" "}
          bölümüne bak). Verileri projenin ihtiyacından uzun süre tutmuyoruz.
        </P>
      </Section>

      <Section id="security" title="Verileri nasıl koruyoruz">
        <List>
          <li>Her sorgu giriş yapan kullanıcıyla sınırlı. Sadece kendi verilerini ve üyesi olduğun evleri görürsün.</li>
          <li>
            Sohbet, sadece senin verilerin üzerinde tek bir salt okunur sorgu çalıştırabilir. İkinci bir ajan her sorguyu
            çalışmadan önce kontrol eder.
          </li>
          <li>Google yenileme anahtarları şifreli tutulur ve loglara hiç yazılmaz.</li>
          <li>Anahtarlar ve şifreler kodda değil, ortam ayarlarında durur.</li>
          <li>
            Herkese açık sürümde veritabanının kendisi de diğer kullanıcıların satırlarını gizleyecek (row-level
            security). Bu kısım yazıldı ve çevrimdışı test edildi, ama henüz gerçek bir sunucuda çalışmıyor.
          </li>
        </List>
        <P>Hiçbir sistem tamamen güvenli değil. Kasa bir öğrenci projesi olduğu için dışarıdan bir güvenlik denetiminden geçmedi.</P>
      </Section>

      <Section id="rights" title="KVKK 11. madde kapsamındaki hakların">
        <P>Bize başvurarak şunları isteyebilirsin:</P>
        <List>
          <li>kişisel verilerinin işlenip işlenmediğini öğrenmek,</li>
          <li>işlenmişse buna ilişkin bilgi istemek,</li>
          <li>işlenme amacını ve verilerin amacına uygun kullanılıp kullanılmadığını öğrenmek,</li>
          <li>yurt içinde ya da yurt dışında verilerin aktarıldığı üçüncü kişileri bilmek,</li>
          <li>eksik ya da yanlış işlenmişse düzeltilmesini istemek,</li>
          <li>KVKK&apos;nın 7. maddesindeki şartlar çerçevesinde silinmesini ya da yok edilmesini istemek,</li>
          <li>düzeltme ya da silme işleminin, verilerin aktarıldığı üçüncü kişilere bildirilmesini istemek,</li>
          <li>
            verilerin sadece otomatik sistemlerle analiz edilmesi sonucunda aleyhine bir sonuç çıkmasına itiraz etmek,
          </li>
          <li>verilerin kanuna aykırı işlenmesi yüzünden zarara uğrarsan zararının giderilmesini istemek.</li>
        </List>
        <P>Başvurularını ücretsiz ve en geç 30 gün içinde cevaplıyoruz.</P>
      </Section>

      <Section id="contact" title="Bize nasıl ulaşırsın">
        <P>
          <A href={NEW_ISSUE_URL}>GitHub deposunda</A> bir issue aç ve bir gizlilik talebin olduğunu yaz. GitHub
          issue&apos;ları herkese açık, bu yüzden issue&apos;ya kişisel veri yazma. Sana orada, devam etmek için özel bir
          yol söyleyeceğiz. Önceki soruları <A href={ISSUES_URL}>issue sayfasında</A> görebilirsin.
        </P>
        <P>
          Verilerine kendin de bakabilirsin: eklediğin her şey Harcamalar, Ev, Bütçeler, Abonelikler ve Gelen kutusu
          sayfalarında, Google bağlantın da <A href="/settings">Ayarlar</A> sayfasında.
        </P>
      </Section>

      <Section id="changes" title="Bu metindeki değişiklikler">
        <P>
          Kasa&apos;nın verileri kullanma şeklini değiştirirsek bu sayfayı ve en üstteki tarihi güncelleriz. Önceki
          sürümler depo geçmişinde duruyor (<Code>frontend/src/features/legal/PrivacyView.tsx</Code>).
        </P>
      </Section>
    </TextPage>
  );
}
