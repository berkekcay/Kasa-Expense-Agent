# Kasa kullanıcı hikayeleri

Bu dosya Kasa'nın kullanıcıları için neler yaptığını, her parçanın sahibini ve her parçanın ne
kadar ilerlediğini listeler. Tüm durumları 2026-10-27'de `main` üzerindeki kod ve testlerle
karşılaştırdık. Her story onu kanıtlayan endpoint'i, sayfayı ya da test dosyasını yazıyor, yani
isteyen herkes tekrar kontrol edebilir.

Durumlar:

- **Bitti**: kod `main` üzerinde, otomatik testler kapsıyor ve hiçbir dış servise ihtiyaç
  duymadan çalışıyor.
- **Kısmen**: kod var, ama bir parçası gerçek servise karşı hiç çalışmadı (Gemini, Google,
  Azure SQL, Firebase, Cloud Run) ya da bilinen bir eksik var. Notta hangisi olduğu yazıyor.
- **Başlanmadı**: henüz hiç kod yok.

Kısmen ve Başlanmadı durumundaki story'ler GitHub issue'su oluyor. Liste en sonda,
[Açık story'ler](#açık-storyler) bölümünde.

Veritabanı hakkında bir not: Kasa bugün SQLite ile çalışıyor (geliştirme, testler ve demo).
Production için ileride Azure SQL Database (Microsoft SQL Server) kullanmayı planlıyoruz.
Migration'lar, row-level security (RLS) ve bağlantı kodu yazıldı ve offline test edildi, ama henüz
bir Azure veritabanı yok. Planın tamamı [DATABASE.md](DATABASE.md) dosyasında.

## Sprintler

README'de bir Sprint 1 kontrol listesi, bir Sprint 2 temel listesi ve sprint 2 ile 4 arası için
dört track var (HOUSE, MONEY, INGEST, REPORT). README hangi track'in hangi sprint'e ait olduğunu
söylemiyor, bu yüzden bu dosya aşağıdaki planı kullanıyor. Ekip story'leri sprint'ler arasında
taşıyabilir.

| Sprint | Kapsam |
| --- | --- |
| 1 | README'deki "Sprint 1 checklist": fiş fotoğrafı, elle harcama, eşit bölüşümlü tek ev, bakiyeler, hesaplaşma, grafikli sohbet |
| 2 | "Sprint 2 foundation" (migration'lar, veri modeli, kayıtlı ödemeler, kategoriler, Firebase seçeneği, Ollama geçişi, CI) ve HOUSE track'i |
| 3 | MONEY ve INGEST track'leri |
| 4 | REPORT track'i (checker ajanı, eval'ler), deploy kiti, API eksiklerinin giderilmesi ve hâlâ açık kalan her şey |

## Roller

Sahip rolleri proje sayfasından geliyor. Kişilerin isimleri [TEAM.md](TEAM.md) dosyasında.

| Kısa ad | Rol | Ana alanlar |
| --- | --- | --- |
| Product owner | Product owner ve mimari | user story'ler, mimari, demo, öncelikler; ayrıca Backend, Frontend ve veritabanının ortak sahibi |
| Backend | Veritabanı ve backend | veri modeli, migration'lar, RLS, REST API, Google OAuth ve Gmail altyapısı |
| Agents 1 | Ajan geliştirici #1 | coordinator, fiş ajanı, bütçe ajanı (MONEY track'i), gelen kutusu ve ekstre okuma ajanları |
| Agents 2 | Ajan geliştirici #2 | ev ajanı, bölüşümler, bakiyeler, hesaplaşma, Calendar hatırlatmaları (HOUSE track'i) |
| Agents 3 / QA | Ajan geliştirici #3, QA ve cloud | rapor ajanı, checker ajanı, eval'ler, CI, Cloud Run ve Azure SQL deploy |
| Frontend | Frontend | Next.js sayfaları ve bileşenleri |

Proje sayfası gelen kutusu ve ekstre ajanları için bir sahip belirtmiyor. Bu dosya onları
Agents 1'e veriyor, çünkü bu ajanlar da fiş ajanı gibi alışveriş okuyor.

## Durum özeti

Her story için bir satır. "Yapan" sütunu kodu kimin yazdığını, "Kalan iş" sütunu kalan işin
kime ait olduğunu ve varsa issue numarasını gösteriyor.

| Story | Başlık | Sprint | Durum | Yapan | Kalan iş |
| --- | --- | --- | --- | --- | --- |
| US-CAPTURE-01 | Harcamayı elle ekle | 1 | Bitti | Berke | - |
| US-CAPTURE-02 | Fişi fotoğraftan kaydet | 1 | Kısmen | Berke | Yusuf (#4): fiş okumayı Gemini'de doğrulamak |
| US-CAPTURE-03 | Alışverişi sohbete yaz | 1 | Kısmen | Berke | Yusuf: Gemini'de doğrulamak |
| US-CAPTURE-04 | Başka para biriminde öde | 3 | Bitti | Berke | - |
| US-CAPTURE-05 | Harcamayı düzelt ya da sil | 4 | Bitti | Berke | - |
| US-CAPTURE-06 | Harcamalarımı filtrele | 4 | Bitti | Berke | - |
| US-BUDGET-01 | Aylık bütçe koy | 3 | Bitti | Berke | - |
| US-BUDGET-02 | Bütçe dolmak üzereyken uyar | 3 | Bitti | Berke | - |
| US-BUDGET-03 | Ayımı tek bakışta gör | 3 | Bitti | Berke | - |
| US-BUDGET-04 | Aboneliklerimi bul | 3 | Bitti | Berke | - |
| US-BUDGET-05 | Bütçe, abonelik ve kurları sohbette sor | 3 | Kısmen | Berke | Yusuf: cevap dili, Gemini'de doğrulamak |
| US-BUDGET-06 | Ayımı grafiklerle geçen ayla karşılaştır | 4 | Bitti | Berke | - |
| US-HOUSE-01 | Ev oluştur, ev arkadaşlarını ekle | 1 | Bitti | Berke | - |
| US-HOUSE-02 | Ev arkadaşını linkle davet et | 4 | Bitti | Berke | Ömer (#6): backend testi, Zehra (#11): arayüz testi |
| US-HOUSE-03 | Faturayı eşit böl | 1 | Bitti | Berke | - |
| US-HOUSE-04 | Yüzdeyle, tutarla ya da kalem kalem böl | 2 | Bitti | Berke | - |
| US-HOUSE-05 | Kimin kime borçlu olduğunu gör | 1 | Bitti | Berke | - |
| US-HOUSE-06 | Ev arkadaşları arasındaki ödemeyi kaydet | 2 | Bitti | Berke | - |
| US-HOUSE-07 | Herkese hesaplaşmayı hatırlat | 3 | Kısmen | Berke | Ömer: Calendar'ı gerçek Google'a karşı çalıştırmak |
| US-HOUSE-08 | Evden ayrıl, üyeyi çıkar, faturayı sil | 4 | Bitti | Berke | - |
| US-HOUSE-09 | Evi sohbetten yönet | 2 | Kısmen | Berke | Ömer: Gemini'de doğrulamak |
| US-ASK-01 | Harcamalarımı sor, grafik al | 1 | Kısmen | Berke | Yusuf: Gemini'de doğrulamak |
| US-ASK-02 | Toplamlar ev faturasında yalnızca benim payımı sayar | 4 | Bitti | Berke | - |
| US-ASK-03 | Her sorguyu ikinci bir ajan kontrol eder | 4 | Bitti | Berke | - |
| US-ASK-04 | Sohbet benim dilimde cevap verir | 4 | Kısmen | Berke | Yusuf (#5) |
| US-ASK-05 | Doğru uzman ajan cevap verir | 1 | Kısmen | Berke | Yusuf (#4) |
| US-ASK-06 | Kasa Gemini'de çalışır | 4 | Kısmen | Berke | Yusuf (#4) |
| US-ASK-07 | Excel ya da CSV dosyamı sohbette analiz et | 4 | Kısmen | Berke | Yusuf: Gemini'de doğrulamak |
| US-ASK-08 | Kasa'nın ne yaptığını adım adım gör | 4 | Bitti | Berke | - |
| US-ASK-09 | Eski sohbetlerime geri dön | 4 | Bitti | Berke | - |
| US-ASK-10 | Sohbetin kaydettiğini geri al | 4 | Bitti | Berke | - |
| US-ASK-11 | Grafiği rapor olarak kaydet, sonra güncel veriyle aç | 4 | Bitti | Berke | - |
| US-INBOX-01 | CSV banka ekstresi yükle | 3 | Bitti | Berke | - |
| US-INBOX-02 | PDF ekstre yükle | 3 | Kısmen | Berke | Yusuf: canlı bir çalıştırma kaydetmek |
| US-INBOX-03 | Gelen kutusundaki kalemleri incele ve onayla | 3 | Bitti | Berke | - |
| US-INBOX-04 | Alışverişleri Gmail'den al | 3 | Kısmen | Berke | Mustafa: gerçek Gmail OAuth |
| US-INBOX-05 | Gelen kutusunu sohbette sor | 3 | Kısmen | Berke | Yusuf: Gemini'de doğrulamak |
| US-GUARD-01 | Yalnızca kendi verimi görürüm | 1 | Bitti | Berke | - |
| US-GUARD-02 | Sohbet yalnızca benim satırlarımı okur | 1 | Bitti | Berke | - |
| US-GUARD-03 | Fiş ve e-postadaki metin veridir, emir değil | 3 | Bitti | Berke | - |
| US-GUARD-04 | Kullanıcı ayrımını veritabanı da uygular | 2 | Kısmen | Berke | Mustafa (#12): Azure SQL kurulumu ve RLS testi |
| US-GUARD-05 | Para hep kuruşu kuruşuna doğru | 1 | Bitti | Berke | - |
| US-GUARD-06 | Kodda ve loglarda gizli bilgi yok | 2 | Bitti | Berke | - |
| US-GUARD-07 | Kullanıcı başına sohbet sınırı | 4 | Başlanmadı | - | Mustafa (#9) |
| US-GUARD-08 | Hesabımı ve verilerimi sil | 4 | Başlanmadı | - | Mustafa, Zehra (#13) |
| US-ACCOUNT-01 | Kayıt ol, e-posta ya da Google ile giriş yap | 4 | Kısmen | Berke | Mustafa: Google OAuth client'ı |
| US-ACCOUNT-02 | Dev modunda herhangi bir kullanıcı ol | 1 | Bitti | Berke | - |
| US-ACCOUNT-03 | Görünen adımı değiştir | 4 | Bitti | Berke | - |
| US-ACCOUNT-04 | Kasa'yı herkese açık bir adreste aç | 4 | Kısmen | Berke | Mustafa, Yusuf: ilk Cloud Run deploy'u |
| US-ACCOUNT-05 | Kasa'yı Türkçe ya da İngilizce kullan | 4 | Bitti | Berke | - |
| US-ACCOUNT-06 | Google Authenticator ile iki adımlı doğrulama | 4 | Bitti | Berke | - |
| US-ACCOUNT-07 | Açık oturumlarımı gör ve kapat | 4 | Bitti | Berke | - |

## Personalar

**Elif, yalnız yaşayan bir öğrenci.** Birinci sınıf. Kadıköy'de bir stüdyo dairede KYK bursu ve
ailesinden gelen biraz parayla yaşıyor. Market, ulaşım, kahve ve iki üç abonelik için ödeme
yapıyor. Her ay paranın nereye gittiğini görmek ve bir kategori bitmeden önce uyarı almak
istiyor. Türkçe yazıyor, bazen de İngilizce.

**Ali, ortak evde yaşayan bir öğrenci.** Moda'da iki arkadaşıyla bir daireyi paylaşıyor. Kira,
faturalar ve ev alışverişini o hafta markette kim varsa ya da kimin parası varsa o ödüyor. Excel
tablosu tutmak istemiyor. Kime ne kadar borçlu olduğunu bilmek ve bunu olabildiğince az
havaleyle kapatmak istiyor.

**Deniz, evin "muhasebecisi".** Ali ve Ayşe ile yaşıyor. Her ay kirayı ödüyor, sonra payları
topluyor. Faturaları Deniz giriyor, her birinin nasıl bölüneceğini seçiyor (eşit, oda
büyüklüğüne göre, kaleme göre), geri gelen parayı kaydediyor ve herkese hesaplaşmayı
hatırlatıyor. Hiçbir alışveriş unutulmasın diye ayda bir de banka ekstresini yüklüyor.
[DEMO.md](DEMO.md) dosyasındaki demo kullanıcısı Deniz.

## Epik: harcama kaydı

### US-CAPTURE-01 Harcamayı elle ekle

Elif olarak, harcamayı elle eklemek istiyorum, böylece fişi olmayan alışverişler de sayılır.

- Sprint 1 · **Bitti** · Sahip: Backend (API), Frontend (form) · Yapan: Berke
- Diyelim ki Harcamalar sayfasındayım. "Migros" ve "84,90" girip kaydettiğimde, harcama
  listenin en üstünde Kasa'nın seçtiği bir kategoriyle ("groceries") görünür.
- Diyelim ki kategoriyi Türkçe yazdım ("market") ya da boş bıraktım. Kaydettiğimde, kategori 12
  sabit kategoriden biri olarak saklanır.
- Diyelim ki 0, negatif bir tutar ya da ikiden fazla ondalık girdim. Kaydettiğimde anlaşılır bir
  hata alırım ve hiçbir şey kaydedilmez.
- Kanıt: `POST /expenses`, `GET /categories`, sayfa `/expenses`,
  `tests/test_api.py::test_create_and_list_expenses_is_scoped_per_user`,
  `tests/test_api.py::test_expense_validation`,
  `tests/test_foundation_api.py::test_categories_endpoint_and_normalised_storage`.

### US-CAPTURE-02 Fişi fotoğraftan kaydet

Elif olarak, fişin fotoğrafını çekmek istiyorum, böylece mağaza, tarih, kalemler ve toplam hiç
yazmadan kaydedilir.

- Sprint 1 · **Kısmen** · Sahip: Agents 1 (fiş ajanı), Frontend (yükleme sayfası) · Yapan: Berke
- Diyelim ki sunucuda bir LLM sağlayıcısı var. `receipt_market.png` dosyasını yüklediğimde,
  2026-10-05 tarihli, 239.35 TRY tutarında "ÖZDEMİR MARKET" harcaması beş kalemiyle birlikte
  kaydedilir.
- Diyelim ki kalemlerin toplamı fişteki toplamı tutmuyor. Kaydedildiğinde bir uyarı görürüm.
- Diyelim ki hiçbir LLM sağlayıcısı ayarlı değil. Sayfayı açtığımda fiş okumanın kapalı olduğu
  yazar ve API 503 döner.
- Kanıt: `POST /receipts`, sayfa `/receipts`,
  `tests/test_agents_offline.py::test_receipt_upload_saves_expense_via_agent` (senaryolu sahte
  model), `tests/test_live.py::test_live_receipt_image` (yalnızca canlı).
- Eksik: Ollama'da (`qwen3-vl:8b`) canlı olarak geçti. Gemini'de hiç çalışmadı, yani
  `gemini-3.5-flash-lite` ile fiş okuma doğrulanmadı.

### US-CAPTURE-03 Alışverişi sohbete yaz

Elif olarak, "Bugün Migros'ta 245,90 TL harcadım" yazmak istiyorum, böylece harcama tek bir
cümleyle kaydedilir.

- Sprint 1 · **Kısmen** · Sahip: Agents 1 · Yapan: Berke
- Diyelim ki bu mesajı gönderdim. Coordinator mesajı yönlendirdiğinde, fiş ajanı
  `save_expense` aracını çağırır ve cevap tutarı Türkçe olarak onaylar.
- Diyelim ki "son harcamalarım neler?" diye sordum. Fiş ajanı son harcamalarımı listeler.
- Kanıt: `POST /chat`, sayfa `/chat`, `app/agents/tools/receipt_tools.py`,
  `backend/evals/cases.jsonl` içindeki `route-receipt-tr` eval vakası (Ollama'da geçti,
  `evals/latest.md`).
- Eksik: Gemini'de doğrulanmadı.

### US-CAPTURE-04 Başka para biriminde öde

Elif olarak, USD ya da EUR ile yaptığım bir alışverişi girmek istiyorum, böylece o günün resmi
TCMB kuruyla TL'ye çevrilir.

- Sprint 3 · **Bitti** · Sahip: Agents 1 (MONEY track'i), Backend · Yapan: Berke
- Diyelim ki 15.00 USD ekledim. Kaydettiğimde, toplam TRY olarak saklanır; asıl tutar, kur ve
  bülten tarihi de saklanır. Ekranda "Converted 15.00 USD to ... TRY at TCMB rate ... (date)"
  mesajını görürüm.
- Diyelim ki gün hafta sonu ya da tatil. Kaydettiğimde ondan önceki en son bülten kullanılır.
  TCMB'ye ulaşılamıyorsa son 7 günden önbellekteki bir kur kullanılır, o da yoksa kayıt anlaşılır
  bir mesajla reddedilir.
- Diyelim ki bir ev EUR kullanıyor. TRY ile bir fatura eklendiğinde, bölünmeden önce EUR'ya
  çevrilir.
- Kanıt: `POST /expenses`, `GET /fx/rates`, `GET /fx/convert`, sayfa `/expenses`,
  `tests/test_foundation_api.py::test_foreign_currency_expense_is_converted_with_a_warning`,
  `tests/test_money_fx.py::test_foreign_expense_through_the_api_and_a_house_in_euros`,
  `tests/test_money_fx.py::test_holiday_walks_back_and_remembers_the_missing_day`.

### US-CAPTURE-05 Harcamayı düzelt ya da sil

Elif olarak, bir harcamanın mağazasını, kategorisini, tarihini ya da notunu değiştirmek ya da
onu silmek istiyorum, böylece hatalar rakamlarımda kalmaz.

- Sprint 4 · **Bitti** · Sahip: Backend, Frontend · Yapan: Berke
- Diyelim ki kendi harcamamın kategorisini düzenliyorum. Yalnızca o alan değişir. Tutar
  düzenlenemez; silip yeniden eklerim.
- Diyelim ki bir ev faturası var. Onu kendi harcama listemden silmeye çalıştığımda 409 alırım ve
  cevap beni ev endpoint'ine yönlendirir, böylece bakiyeler doğru kalır.
- Diyelim ki başkasının harcama id'sini kullanıyorum. Düzenlemeye ya da silmeye çalıştığımda 404
  alırım.
- Kanıt: `PATCH /expenses/{id}`, `DELETE /expenses/{id}`, sayfa `/expenses`,
  `tests/test_expenses_api.py` (`test_patch_changes_only_the_given_fields`,
  `test_house_expense_is_409_and_points_to_the_house_endpoint`, `test_others_get_404`).

### US-CAPTURE-06 Harcamalarımı filtrele

Elif olarak, aya, kategoriye, kaynağa ve kişisel ya da ev harcaması olmasına göre filtrelemek
istiyorum, böylece bir alışverişi hızlıca bulurum.

- Sprint 4 · **Bitti** · Sahip: Backend, Frontend · Yapan: Berke
- Diyelim ki 150 harcamam var. "2026-10" ve "food" ile filtrelediğimde yalnızca bunlar gelir, en
  yenisi en üstte. Sayfalama için toplam sayı `X-Total-Count` header'ında döner.
- Kanıt: `GET /expenses?month=&category=&source=&scope=&limit=&offset=`, sayfa `/expenses`,
  `tests/test_expenses_api.py::test_month_category_source_and_scope`,
  `tests/test_expenses_api.py::test_paging_keeps_the_total`.

## Epik: kişisel bütçeler

### US-BUDGET-01 Aylık bütçe koy

Elif olarak, kategori başına ya da genel bir aylık limit koymak istiyorum, böylece ne kadar
kaldığını bilirim.

- Sprint 3 · **Bitti** · Sahip: Agents 1 (MONEY track'i), Frontend · Yapan: Berke
- Diyelim ki market bütçesini 3000 TL yaptım. Tekrar 3500 TL yaptığımda aynı bütçe güncellenir
  (her kategori için bir bütçe).
- Diyelim ki sohbete "Ulaşım için aylık 1500 TL bütçe koy" yazdım. Bütçe ajanı bütçeyi benim
  için koyar.
- Kanıt: `GET /budgets`, `PUT /budgets`, `DELETE /budgets/{id}`, `GET /budgets/status`,
  sayfa `/budgets`, `tests/test_money_budgets.py::test_set_budget_upserts_and_normalises`,
  `tests/test_money_budgets.py::test_budget_api`,
  `tests/test_money_tools.py::test_set_budget_and_status_tools`.

### US-BUDGET-02 Bütçe dolmak üzereyken ya da aşıldığında uyar

Elif olarak, bir harcama bütçeyi %80'in üstüne ya da limitin üstüne çıkardığında uyarı almak
istiyorum, böylece zamanında yavaşlayabilirim.

- Sprint 3 · **Bitti** · Sahip: Agents 1, Backend · Yapan: Berke
- Diyelim ki eğlence bütçesi 1200 TL'nin %84'ünde. Eğlence kategorisinde 15 USD'lik bir alışveriş
  eklediğimde, cevap eğlence bütçesinin aşıldığını tutarlarla birlikte söyler.
- Diyelim ki bir bütçe zaten "warning" seviyesinde. Onu aynı seviyede tutan küçük bir harcama
  eklediğimde tekrar uyarılmam.
- Diyelim ki üç kişilik bir ev faturasını ben ödedim. Bütçeme yalnızca kendi payım sayılır.
- Kanıt: `POST /expenses` (uyarılar), dashboard'daki bütçe göstergeleri,
  `tests/test_money_budgets.py::test_alerts_only_when_crossing_a_level`,
  `tests/test_money_budgets.py::test_status_counts_personal_and_own_house_shares_only`,
  `tests/test_integration.py::test_house_bill_warns_on_payers_share_only`.

### US-BUDGET-03 Ayımı tek bakışta gör

Elif olarak, bu ayın toplamını, kategorileri, altı aylık eğilimi, bütçeleri, ev bakiyelerini ve
yaklaşan ödemeleri tek sayfada görmek istiyorum, böylece sormama gerek kalmaz.

- Sprint 3 · **Bitti** · Sahip: Agents 1 (MONEY track'i), Frontend · Yapan: Berke
- Diyelim ki harcamalarım var. Dashboard'u açtığımda toplamı, geçen aya göre değişimi, kategori
  başına çubukları ve altı aylık bir çizgiyi görürüm.
- Diyelim ki gelen kutusunda bekleyen kalemler var. Bir banner gelen kutusuna link verir.
- Kanıt: `GET /dashboard`, sayfa `/`, `tests/test_money_dashboard.py`.

### US-BUDGET-04 Aboneliklerimi bul

Elif olarak, Kasa'nın aylık ödemelerimi (Netflix, Spotify) bulmasını istiyorum, böylece her ay
neye para verdiğimi ve neyin yakında çekileceğini görürüm.

- Sprint 3 · **Bitti** · Sahip: Agents 1 (MONEY track'i), Frontend · Yapan: Berke
- Diyelim ki üç ay boyunca 229.99 TL'lik Netflix ödemesi var. Tespit çalıştığında, bir sonraki
  beklenen tarihiyle aylık bir "Netflix" aboneliği görünür.
- Diyelim ki her ay market alışverişi yapıyorum. Bu bir abonelik sayılmaz.
- Diyelim ki bir aboneliği kapattım (dismiss). Bir daha geri gelmez.
- Kanıt: `GET /subscriptions`, `POST /subscriptions/detect`, `GET /subscriptions/upcoming`,
  `POST /subscriptions/{id}/dismiss`, sayfa `/subscriptions`, `tests/test_money_subscriptions.py`,
  `tests/test_integration.py::test_monthly_groceries_are_not_subscriptions`.

### US-BUDGET-05 Bütçe, abonelik ve kurları sohbette sor

Elif olarak, "Am I over any budget?", "Spotify aboneliğim ne kadar tutuyor?" ya da "100 dolar kaç
TL?" diye sormak istiyorum, böylece sayfa açmadan cevabı alırım.

- Sprint 3 · **Kısmen** · Sahip: Agents 1 · Yapan: Berke
- Diyelim ki bunlardan birini sordum. Coordinator soruyu bütçe ajanına gönderir ve cevaptaki
  tutarlar ajanın araçlarından gelir.
- Kanıt: `POST /chat`, `app/agents/budget_agent.py`, `app/agents/tools/budget_tools.py`,
  `tests/test_money_tools.py::test_chat_routes_to_budget_agent_and_saves_for_the_caller`,
  `route-budget-set-tr` ve `route-subscriptions-en` eval vakaları.
- Eksik: Ollama'da `route-subscriptions-en` İngilizce bir soruya Türkçe cevap verdi
  (`evals/latest.md`). Gemini'de doğrulanmadı.

### US-BUDGET-06 Ayımı grafiklerle geçen ayla karşılaştır

Elif olarak, ana sayfada bu ayın geçen aya göre nasıl gittiğini grafiklerle görmek istiyorum,
böylece nerede fazla harcadığımı bir bakışta anlarım.

- Sprint 4 · **Bitti** · Sahip: Frontend, Backend (MONEY) · Yapan: Berke
- Diyelim ki bu ay ve geçen ay harcamam var. Ana sayfada ayın içinde biriken toplamı geçen ayla
  aynı grafikte, kategori dağılımını, son 6 ayı, gün gün harcama takvimini, en çok harcadığım
  yerleri ve kategori bazında geçen aya göre artış ve azalışı görürüm.
- Diyelim ki başka bir ayı seçtim. Ay seçiciyle ya da son 6 ay grafiğinde bir aya tıklayarak o
  aya geçerim; gelecek aylar seçilemez.
- Kanıt: `GET /dashboard` (`daily`, `previous_daily`, `top_merchants`, `previous_by_category`),
  sayfa `/`, `tests/test_money_dashboard.py`.

## Epik: ortak evler

### US-HOUSE-01 Ev oluştur, ev arkadaşlarını ekle

Deniz olarak, "Moda evi"ni oluşturup Ali ile Ayşe'yi eklemek istiyorum, böylece faturaları
paylaşabiliriz.

- Sprint 1 · **Bitti** · Sahip: Agents 2 (HOUSE track'i), Backend, Frontend · Yapan: Berke
- Diyelim ki bir ev oluşturdum. Evin ilk üyesi ben olurum. "ayse"yi eklediğimde üye olur ve giriş
  yaptığında evi görür.
- Diyelim ki üye olmayan biri evi istiyor. 404 alır (ev id'leri yoklanarak bulunamaz).
- Kanıt: `POST /houses`, `GET /houses`, `POST /houses/{id}/members`, sayfa `/houses`
  (Members sekmesi), `tests/test_api.py::test_house_access_is_members_only`.

### US-HOUSE-02 Ev arkadaşını linkle davet et

Deniz olarak, Ali'nin kabul edeceği bir davet linki göndermek istiyorum, böylece kimse "evet"
demeden bir eve eklenmez.

- Sprint 4 · **Bitti** · Sahip: Backend, Frontend · Yapan: Berke · Test: Ömer (#6), Zehra (#11)
- Diyelim ki bir davet oluşturdum. Ev sayfasında 7 gün geçerli, en fazla 10 kullanımlık bir link
  çıkar; kopyalayabilir ya da WhatsApp'ta paylaşabilirim. Ali giriş yapmışken linki açtığında
  evin adını ve beni görür, "Eve katıl" deyince eve eklenir ve ev sayfası o evle açılır.
- Diyelim ki link süresi doldu, iptal edildi ya da kullanım hakkı bitti. Ali nedenini görür,
  kimse eklenmez. Ali giriş yapmamışsa önce giriş sayfasına, sonra linke döner.
- Diyelim ki "ev için davet linki oluştur" yazdım. Ev ajanı linki oluşturur.
- Kullanıcı id'siyle üye ekleme sadece geliştirme modunda görünür.
- Kanıt: `POST/GET/DELETE /houses/{id}/invites`, `GET /invites/{code}`,
  `POST /invites/{code}/accept`, sayfa `/invite/[code]`, `tests/test_house_invites.py`.

### US-HOUSE-03 Faturayı eşit böl

Deniz olarak, internet faturasını eşit bölmek istiyorum, böylece herkes aynı tutarı öder.

- Sprint 1 · **Bitti** · Sahip: Agents 2 · Yapan: Berke
- Diyelim ki üç kişi için 100.00 TL'lik bir fatura var. Kaydedildiğinde paylar 33.34, 33.33 ve
  33.33 olur ve toplamları her zaman faturayı tutar.
- Diyelim ki üç kişiden yalnızca ikisini seçtim. Faturayı yalnızca o ikisi paylaşır.
- Kanıt: `POST /houses/{id}/expenses`, sayfa `/houses` (Add expense, Equal),
  `tests/test_settlement.py`, `tests/test_api.py::test_house_equal_split_balances_and_settle_up`.

### US-HOUSE-04 Yüzdeyle, tutarla ya da kalem kalem böl

Deniz olarak, elektriği oda büyüklüğüne göre 40/30/30, marketi kesin tutarlarla ya da bir Migros
fişini kimin hangi kalemi aldığına göre bölmek istiyorum, böylece bölüşüm adil olur.

- Sprint 2 · **Bitti** · Sahip: Agents 2, Frontend · Yapan: Berke
- Diyelim ki toplamı 100 olan yüzdeler girdim. Kaydettiğimde her pay toplamın o yüzdesi olur ve
  paylar tam olarak toplamı tutar. Yüzdelerin toplamı 90 ise hata alırım.
- Diyelim ki girdiğim kesin tutarlar toplamı tutmuyor. Hata mesajı ne kadar eksik ya da fazla
  olduğunu söyler.
- Diyelim ki kalem kalem bölüşümde her satırda kişileri işaretledim. Her satırı işaretli kişiler
  paylaşır; vergi ya da indirim de orantılı olarak dağıtılır.
- Kanıt: `POST /houses/{id}/expenses/split`, sayfa `/houses` (Add expense),
  `tests/test_house_api.py` (`test_percent_split`, `test_exact_split_and_paid_by`,
  `test_items_split_stores_assignees_and_lists_them`), `tests/test_house_splits.py`.

### US-HOUSE-05 Kimin kime borçlu olduğunu gör

Ali olarak, bakiyemi ve evdeki hesabı kapatacak havaleleri görmek istiyorum, böylece kime ne
kadar ödeyeceğimi bilirim.

- Sprint 1 · **Bitti** · Sahip: Agents 2, Frontend · Yapan: Berke
- Diyelim ki evin faturaları ve ödemeleri var. Balances sekmesini açtığımda her üyenin net
  bakiyesi görünür ve bakiyelerin toplamı sıfırdır.
- Diyelim ki n kişilik bir grup var. Hesaplaşma en fazla n - 1 havale önerir.
- Kanıt: `GET /houses/{id}/balances`, sayfa `/houses` (Balances), dashboard'daki "House
  balances", `tests/test_settlement.py::test_random_groups_settle_exactly_with_at_most_n_minus_1_transfers`.

### US-HOUSE-06 Ev arkadaşları arasındaki ödemeyi kaydet

Deniz olarak, "Ali bana 6000 TL ödedi" diye kaydetmek istiyorum, böylece bakiyeler düşer.

- Sprint 2 · **Bitti** · Sahip: Agents 2, Frontend · Yapan: Berke
- Diyelim ki Ali bana 6128.33 TL borçlu. Ali'den bana 6000 TL kaydettiğimde, borcu 128.33 TL
  olur.
- Diyelim ki yanlışlıkla 60000 yazdım. Ödeme reddedilir ve mesaj sığabilecek en büyük tutarı
  söyler. "advance or loan" kutusunu işaretlersem kabul edilir.
- Diyelim ki bir ödeme kaydettim. Onu yalnızca ben geri alabilirim.
- Kanıt: `POST /houses/{id}/settlements`, `GET /houses/{id}/settlements`,
  `DELETE /houses/{id}/settlements/{id}`, sayfa `/houses` (Balances, Payments),
  `tests/test_house_api.py::test_overpayment_is_refused_unless_allowed`,
  `tests/test_house_api.py::test_delete_payment_by_creator_only`,
  `tests/test_foundation_api.py::test_recorded_payments_reduce_balances`.

### US-HOUSE-07 Herkese hesaplaşmayı hatırlat

Deniz olarak, son tarihi olan ve Google Calendar'a da düşen hatırlatmalar istiyorum, böylece
kimsenin peşinden koşmam gerekmez.

- Sprint 3 · **Kısmen** · Sahip: Agents 2 · Yapan: Berke
- Diyelim ki açık havaleler var. Bir tarih için hatırlatma oluşturduğumda her havale için bir
  hatırlatma kaydedilir. Bağlı bir Google hesabı varsa her biri iki ev arkadaşının da davetli
  olduğu tüm günlük bir Calendar etkinliği olur.
- Diyelim ki bakiyeler değişti. Hatırlatmaları tekrar oluşturduğumda eskiler "outdated" olarak
  iptal edilir.
- Kanıt: `POST /houses/{id}/reminders`, `GET /houses/{id}/reminders`,
  `PATCH /houses/{id}/reminders/{id}`, sayfa `/houses` (Reminders),
  `tests/test_house_reminders.py`.
- Eksik: Calendar çağrıları yalnızca sahte servislerle test edildi. Ortada bir OAuth client
  olmadığı için gerçek Google'a karşı hiç çalışmadılar.

### US-HOUSE-08 Evden ayrıl, üyeyi çıkar, faturayı sil

Ali olarak, taşındığımda evden ayrılmak, faturayı ödeyen kişi olarak da yanlış bir faturayı
silmek istiyorum, böylece evin hesabı doğru kalır.

- Sprint 4 · **Bitti** · Sahip: Agents 2, Frontend · Yapan: Berke
- Diyelim ki bakiyem sıfır. Ayrıldığımda evden çıkarılırım ve geçmiş faturalar yerinde kalır.
  Bakiyem sıfır değilse önce kapatmam gereken tutarla birlikte 409 alırım. Son üye evden
  ayrılamaz.
- Diyelim ki bir faturayı ben ödedim. Sildiğimde payları da silinir ve bakiyeler buna göre
  değişir. Diğerleri 403 alır.
- Kanıt: `DELETE /houses/{id}/members/{user_id}`, `DELETE /houses/{id}/expenses/{id}`,
  sayfa `/houses` (Members, Expenses), `tests/test_house_members.py`.

### US-HOUSE-09 Evi sohbetten yönet

Deniz olarak, "Evdeki 300 TL'lik su faturasını ben ödedim, 3 kişi arasında eşit bölüştür" ya da
"Ayşe bana 150 TL ödedi" yazmak istiyorum, böylece form doldurmam.

- Sprint 2 · **Kısmen** · Sahip: Agents 2 · Yapan: Berke
- Diyelim ki bu mesajı yazdım. Ev ajanı evimi bulur, araçlarla faturayı böler ya da ödemeyi
  kaydeder ve Türkçe onaylar. "Ayşe" gibi isimler üyelerle eşleştirilir.
- Kanıt: `POST /chat`, `app/agents/house_agent.py`, `app/agents/tools/house_tools.py`,
  `tests/test_house_tools.py`, `tests/test_live.py::test_live_chat_house_equal_split` (yalnızca
  canlı), `route-house-split-tr` ve `route-house-balance-tr` eval vakaları.
- Eksik: Ollama'da geçti, Gemini'de doğrulanmadı.

## Epik: düz dille sor

### US-ASK-01 Harcamalarımı sor, grafik al

Elif olarak, "Bu ay kategoriye göre ne kadar harcadım? Grafik çiz" diye sormak istiyorum,
böylece hem rakamları hem de bir grafik alırım.

- Sprint 1 · **Kısmen** · Sahip: Agents 3 / QA (rapor ajanı), Frontend (grafik) · Yapan: Berke
- Diyelim ki harcamalarım var. Bunu sorduğumda rapor ajanı tek bir SELECT yazar, guard ve
  checker onu onaylar, cevap da sohbet sayfasının çizdiği bir çubuk grafikle gelir.
- Diyelim ki bir eğilim sordum. Çizgi grafik alırım. Düz bir liste istersem tablo alırım.
- Kanıt: `POST /chat` (cevaptaki `chart`), sayfa `/chat`,
  `tests/test_agents_offline.py::test_chat_routes_to_report_agent_and_returns_chart`,
  `tests/test_reports.py`, `tests/test_report_guard.py`, `report-*` eval vakaları (Ollama'da 6
  vakanın 6'sı geçti).
- Eksik: Gemini'de doğrulanmadı.

### US-ASK-02 Toplamlar ev faturalarında yalnızca benim payımı sayar

Deniz olarak, "ne kadar harcadım" sorusunun ödediğim kiranın tamamını değil, kiradaki payımı
saymasını istiyorum, böylece sohbet, dashboard ve bütçeler aynı rakamı verir.

- Sprint 4 · **Bitti** · Sahip: Agents 3 / QA · Yapan: Berke
- Diyelim ki üç kişi için 18000 TL kira ödedim. Bu ay ne kadar harcadığımı sorduğumda bunun
  6000 TL'si sayılır.
- Diyelim ki model ev faturalarının tamamını topluyor. Guard sorguyu yeniden yazılması için geri
  gönderir.
- Kanıt: `app/services/reports.py` içindeki `my_spending` ilişkisi,
  `tests/test_integration.py::test_my_spending_matches_dashboard_and_blocks_double_counting`,
  `tests/test_report_guard.py` (`test_house_shares_use_my_share_not_the_bill`).

### US-ASK-03 Her sorguyu ikinci bir ajan kontrol eder

Product owner olarak, bir checker ajanının her sorguyu soruyla karşılaştırmasını istiyorum,
böylece yanlış ay ya da yanlış filtre cevap gösterilmeden düzeltilir.

- Sprint 4 · **Bitti** · Sahip: Agents 3 / QA · Yapan: Berke
- Diyelim ki bir sorgu soruyla uyuşmuyor. Checker gerekçesiyle birlikte "revise" der ve rapor
  ajanı sorguyu düzeltir (en fazla iki kez).
- Diyelim ki checker hata verdi ya da zaman aşımına uğradı. Sorgu yalnızca statik guard ile
  çalışır ve sonuç bunu belirtir.
- Kanıt: `app/agents/checker_agent.py`, `app/agents/tools/report_tools.py`,
  `tests/test_report_checker.py`.

### US-ASK-04 Sohbet benim dilimde cevap verir

Elif olarak, İngilizce soruya İngilizce, Türkçe soruya Türkçe cevap almak istiyorum.

- Sprint 4 · **Kısmen** · Sahip: Agents 1 (coordinator), Agents 3 / QA (eval'ler) · Yapan: Berke
- Diyelim ki "How much did I spend on groceries last month?" diye sordum. Cevap İngilizce gelir.
- Kanıt: `app/agents/language.py`, `tests/test_integration.py::test_reply_language_detection`,
  `tests/test_agents_offline.py::test_every_chat_agent_has_latest_message_language_instruction`,
  `tests/test_agents_offline.py::test_chat_language_note_follows_message_over_ui_locale`,
  `evals/run_evals.py` içindeki `lang` kontrolü.
- Eksik: Ollama'da altı yönlendirme vakasından biri dil kontrolünü geçemedi. Gemini'de
  ölçülmedi.

### US-ASK-05 Doğru uzman ajan cevap verir

Herhangi bir kullanıcı olarak, her mesajın onu işleyebilecek ajana (fiş, ev, rapor, bütçe,
gelen kutusu) gitmesini istiyorum, böylece her şeyi tek bir sohbette sorabilirim.

- Sprint 1 · **Kısmen** · Sahip: Agents 1 (coordinator), Agents 3 / QA (eval'ler) · Yapan: Berke
- Diyelim ki ev arkadaşları arasında bir ödeme yazdım ("Ali'ye 200 TL gönderdim"). Mesaj ev
  ajanına gider, asla fiş ajanına gitmez.
- Kanıt: `app/agents/coordinator.py`, `tests/test_agents_offline.py::test_every_runner_kind_builds`,
  `route-*` eval vakaları (Ollama'da 6 vakanın 5'i geçti; kalan vaka cevap dili yüzünden
  kaldı).
- Eksik: Gemini'de doğrulanmadı.

### US-ASK-06 Kasa Gemini'de çalışır

Product owner olarak, ajanların ücretsiz bir AI Studio anahtarıyla Gemini'de çalışmasını
istiyorum, böylece ürün ekibin Ollama sunucusu olmadan da çalışır.

- Sprint 4 · **Kısmen** · Sahip: Agents 3 / QA · Yapan: Berke
- Diyelim ki `LLM_PROVIDER=gemini`, bir anahtar ve `GEMINI_MODEL=gemini-3.5-flash-lite` ayarlı.
  `KASA_LIVE_TESTS=1 pytest -m live -s` ve `python -m evals.run_evals` komutlarını
  çalıştırdığımda canlı testler geçer ve eval puanı en az Ollama'daki kadar olur.
- Kanıt: `app/agents/common.py` (`build_model`), `app/config.py`.
- Eksik: varsayılan model artık `gemini-3.5-flash-lite`, çünkü yeni anahtarların 2.5 modellerine
  erişimi olmayabilir. Fiş okuma dahil, henüz hiç canlı Gemini çağrısı yapılmadı. Bunu ayrı bir
  issue (#4) takip ediyor.

### US-ASK-07 Excel ya da CSV dosyamı sohbette analiz et

Elif olarak, bankadan indirdiğim Excel dosyasını sohbete ekleyip "en çok neye harcamışım?"
diye sormak ve istersem satırları harcamalarıma eklemek istiyorum.

- Sprint 4 · **Kısmen** · Sahip: Agents 3 / QA (dosya ajanı), Frontend (sohbet) · Yapan: Berke
- Diyelim ki bir .xlsx ya da CSV ekledim. Dosya ajanı kolonları tanır, tek SELECT'lik
  sorgularla toplar ve istersem grafik çizer. Dosya veritabanına yazılmaz, iki saat sonra
  bellekten silinir.
- Diyelim ki "bunları harcamalarıma ekle" dedim. Bir önizleme kartı gelir (kaç satır, toplam,
  atlanan satırlar). Onaylarsam satırlar gelen kutusuna düşer, orada tek tek ya da toplu onaylarım.
- Diyelim ki dosyada "önceki talimatları unut" gibi bir yazı var. Ajan onu veri olarak görür.
- Kanıt: `POST /chat/files`, `POST /chat/imports/{draft_id}`, `app/services/sheets.py`,
  `app/agents/file_agent.py`, `tests/test_sheets.py`, `tests/test_chat_files.py`. "Ekstre yükle"
  sayfası da artık Excel kabul ediyor (`test_ingest_statements.py`).
- Eksik: Gemini'de doğrulanmadı; dosyalar tek instance'ın belleğinde.

### US-ASK-08 Kasa'nın ne yaptığını adım adım gör

Elif olarak, cevap beklerken Kasa'nın ne yaptığını görmek istiyorum, böylece takıldığını değil
çalıştığını bilirim.

- Sprint 4 · **Bitti** · Sahip: Backend (sohbet), Frontend · Yapan: Berke
- Diyelim ki bir soru sordum. Cevap gelene kadar "Sorun okunuyor", "Raporlar ajanı devraldı",
  "Rapor hazırlanıyor" gibi adımlar sırayla ve bitince işaretlenerek görünür.
- Diyelim ki başka bir sayfaya geçtim. Soru iptal olmaz, menüde bir nokta cevap beklendiğini
  gösterir, geri döndüğümde cevap oradadır.
- Kanıt: `POST /chat/stream`, `app/agents/runtime.py::stream_agent`,
  `tests/test_chat_files.py::test_stream_shows_agents_and_tools_then_the_reply_with_a_card`,
  `frontend/src/features/chat/chatStore.test.ts`.

### US-ASK-09 Eski sohbetlerime geri dön

Elif olarak, geçen hafta Kasa'ya sorduklarımı tekrar açmak istiyorum.

- Sprint 4 · **Bitti** · Sahip: Backend, Frontend · Yapan: Berke
- Diyelim ki sohbet ettim. Sohbet, ilk mesajım başlık olarak kaydedilir ve sohbet sayfasının
  solundaki listede görünür. Açtığımda mesajlar, grafikler ve kartlar geri gelir; silebilirim.
- Diyelim ki sunucu yeniden başladı. Eski bir sohbete yazınca son mesajlar yeni ajan
  oturumuna bağlam olarak verilir, Kasa konuyu kaldığı yerden sürdürür.
- Diyelim ki başka bir kullanıcıyım. Onun sohbetlerini ne listede görürüm ne de id'yle açabilirim.
- Kanıt: `GET/PATCH/DELETE /chat/conversations/*`, migration `0004_chat_history` (SQL Server'da
  RLS ile), `tests/test_chat_files.py`.

### US-ASK-10 Sohbetin kaydettiğini geri al

Elif olarak, "Starbucks'a 85 TL verdim" yazdığımda kaydedileni görmek ve yanlışsa tek tıkla geri
almak istiyorum.

- Sprint 4 · **Bitti** · Sahip: Frontend, Backend · Yapan: Berke
- Diyelim ki Kasa bir harcama kaydetti. Cevabın altında bir kart çıkar (işyeri, tarih, tutar) ve
  "Geri al" harcamayı siler. Kartın durumu sohbet yeniden açıldığında da korunur.
- Diyelim ki sohbete fiş fotoğrafı ekledim. Fiş okunur ve aynı kartla kaydedilir.
- Kanıt: `ChatOut.cards`, `POST /chat/receipt`, `PUT /chat/messages/{id}/cards/{i}`,
  `tests/test_chat_files.py`.

### US-ASK-11 Grafiği rapor olarak kaydet, sonra güncel veriyle aç

Elif olarak, "kategorilere göre bu ay" grafiğini her ay yeniden sormak istemiyorum; bir kere
kaydedip istediğimde güncel haliyle görmek istiyorum.

- Sprint 4 · **Bitti** · Sahip: Backend (REPORT), Frontend · Yapan: Berke
- Diyelim ki Kasa bir grafik çizdi. Altındaki "Raporu kaydet" ile Raporlar sayfasına eklenir.
  SQL tarayıcıya hiç gitmez, cevapla birlikte sunucuda saklanır.
- Diyelim ki Raporlar sayfasını açtım. Her rapor yapay zeka beklemeden bugünkü veriyle yeniden
  çalışır (aynı korumalı SQL ve kullanıcıya özel tablolar), CSV olarak iner, adı değişir,
  silinir, en fazla dördü Özet'e sabitlenir.
- Diyelim ki Kasa bir toplam söylüyor. Toplamı model değil araç hesaplar (`column_totals`).
- Kanıt: `app/services/saved_reports.py`, `app/api/reports.py`, migration `0006`,
  `tests/test_saved_reports.py`, `tests/test_reports.py`.

## Epik: gelen kutusu ve içe aktarma

### US-INBOX-01 CSV banka ekstresi yükle

Deniz olarak, bankamın CSV dışa aktarımını yüklemek istiyorum, böylece her kart harcaması
incelenecek bir kalem olur.

- Sprint 3 · **Bitti** · Sahip: Agents 1 (INGEST), Backend, Frontend · Yapan: Berke
- Diyelim ki Garanti tarzı bir dosya var (noktalı virgül, Windows-1254, "1.234,56").
  Yüklediğimde her harcama satırı bekleyen bir gelen kutusu kalemi olur. Gelirler, kart
  ödemeleri ve iadeler atlanır.
- Diyelim ki aynı dosyayı tekrar yükledim. Yeni bir şey oluşmaz ("Duplicates").
- Kanıt: `POST /imports/statement`, sayfa `/import`,
  `tests/test_ingest_statements.py::test_garanti_like_cp1254_semicolon_export`,
  `tests/test_ingest_statements.py::test_csv_upload_creates_pending_items_and_dedupes`.

### US-INBOX-02 PDF ekstre yükle

Deniz olarak, bankamın CSV'si olmadığında PDF ekstreyi yüklemek istiyorum.

- Sprint 3 · **Kısmen** · Sahip: Agents 1 (ekstre ajanı) · Yapan: Berke
- Diyelim ki PDF'te metin katmanı var. Ekstre okuma ajanı onu parça parça okur ve her satır bir
  gelen kutusu kalemi olur. PDF taranmış bir belgeyse anlaşılır bir 422 alırım.
- Kanıt: `POST /imports/statement`, `app/agents/statement_agent.py`,
  `tests/test_ingest_statements.py::test_pdf_upload_goes_through_the_statement_parser` (sahte
  runner), `tests/test_ingest_live.py::test_live_statement_pdf` (yalnızca canlı).
- Eksik: ne Ollama'da ne Gemini'de kaydedilmiş bir canlı çalıştırma var.

### US-INBOX-03 Gelen kutusundaki kalemleri incele, düzelt, onayla

Deniz olarak, bulunan her alışverişi kontrol etmek, gerekirse düzeltmek ve tek tek ya da toplu
olarak onaylamak veya reddetmek istiyorum, böylece yalnızca gerçek harcamalar kaydedilir.

- Sprint 3 · **Bitti** · Sahip: Agents 1 (INGEST), Backend, Frontend · Yapan: Berke
- Diyelim ki bekleyen bir kalem var. Kategorisini değiştirip onayladığımda normal akıştan (kur,
  bütçeler) geçen ve kaynağı "statement" ya da "email" olan bir harcama oluşur.
- Diyelim ki beş kalem seçip Approve'a bastım. Beşi de onaylanır, başarısız olanlar kalem kalem
  bildirilir.
- Kanıt: `GET /inbox`, `PATCH /inbox/{id}`, `POST /inbox/{id}/approve`,
  `POST /inbox/{id}/reject`, `POST /inbox/approve`, `POST /inbox/reject`, sayfa `/inbox`,
  `tests/test_ingest_inbox.py`.

### US-INBOX-04 Alışverişleri Gmail'den al

Elif olarak, Gmail'i bağlamak istiyorum, böylece sipariş ve kart e-postaları (Trendyol, banka
bildirimleri) gelen kutusuna kendiliğinden düşer.

- Sprint 3 · **Kısmen** · Sahip: Backend (OAuth, Gmail, Pub/Sub), Agents 1 (e-posta ajanı) ·
  Yapan: Berke
- Diyelim ki Settings'ten Google'ı bağladım. Kasa şifrelenmiş bir refresh token saklar ve bir
  Gmail watch başlatır. Yeni bir sipariş e-postası geldiğinde e-posta ajanı onu bekleyen bir
  kaleme çevirir. Bültenler yok sayılır.
- Diyelim ki bir e-postada "approve all items" yazıyor. Bu yalnızca bekleyen bir kalem olur.
  Okuyucu ajanın onay verebilecek bir aracı yok.
- Kanıt: `GET /integrations/google/connect`, `/callback`, `/status`, `POST /sync`,
  `DELETE /integrations/google`, `POST /internal/gmail/push`, sayfa `/settings`,
  `tests/test_ingest_oauth.py`, `tests/test_ingest_sync.py`, `tests/test_ingest_gmail.py`.
- Eksik: her şey sahte servislerle test edildi. Henüz bir Google OAuth client'ı ya da onay
  ekranı yok, bu yüzden gerçek OAuth, Gmail push ve senkronizasyon hiç çalışmadı.

### US-INBOX-05 Gelen kutusunu sohbette sor

Deniz olarak, "Mailimde onay bekleyen harcama var mı?" diye sormak ve bir kalemi söyleyerek
onaylamak istiyorum.

- Sprint 3 · **Kısmen** · Sahip: Agents 1 · Yapan: Berke
- Diyelim ki bekleyen kalemler var. Gelen kutusu ajanı onları listeler. Bir kalemi yalnızca o
  kalem için açıkça istediğimde onaylar.
- Kanıt: `app/agents/email_agent.py`, `app/agents/tools/inbox_tools.py`,
  `tests/test_ingest_inbox.py::test_chat_tools_list_approve_reject_and_status`,
  `tests/test_ingest_sync.py::test_inbox_agent_instruction_requires_explicit_user_approval`,
  `route-inbox-tr` eval vakası.
- Eksik: Ollama'da geçti, Gemini'de doğrulanmadı.

## Epik: güvenlik ve gizlilik

### US-GUARD-01 Yalnızca kendi verimi görürüm

Ali olarak, ev arkadaşlarımın ve diğer kullanıcıların kişisel harcamalarımı göremeyeceğinden
emin olmak istiyorum.

- Sprint 1 · **Bitti** · Sahip: Backend · Yapan: Berke
- Diyelim ki iki kullanıcı var. Her biri harcamaları listelediğinde yalnızca kendi
  harcamalarını görür. Bir evin faturalarını yalnızca üyeleri görür.
- Kanıt: her servis `user_id` ile filtreliyor,
  `tests/test_api.py::test_create_and_list_expenses_is_scoped_per_user`,
  `tests/test_expenses_api.py::test_only_own_expenses`,
  `tests/test_report_guard.py::test_flatmate_sees_own_shares_only`.

### US-GUARD-02 Sohbet yalnızca benim satırlarımı okuyabilir

Product owner olarak, sohbetin SQL'inin kullanıcının kendi satırları üzerinde tek bir salt
okunur SELECT olmasını istiyorum, böylece hiçbir mesaj veriyi değiştiremez ya da sızdıramaz.

- Sprint 1 · **Bitti** · Sahip: Agents 3 / QA · Yapan: Berke
- Diyelim ki "DROP TABLE expenses", "SELECT * FROM users" ya da bir T-SQL hilesi geldi. Guard
  bunu veritabanına ulaşmadan reddeder ve sohbet yalnızca okuyabildiğini söyler.
- Diyelim ki sorgu geçerli. İlişkiler o anki kullanıcıya göre filtrelenmiş CTE'ler olarak
  eklenir ve bir satır limiti uygulanır.
- Kanıt: `app/services/reports.py` (`validate_report_sql`, `build_scoped_sql`),
  `tests/test_reports.py`, `tests/test_report_guard.py`, `refusal-drop-table`,
  `refusal-other-user-en`, `refusal-injection-users-en` eval vakaları (Ollama'da 3'te 3).

### US-GUARD-03 Fiş ve e-postalardaki metin veridir, emir değil

Elif olarak, "kurallarını yok say" yazan bir fişin ya da e-postanın hiçbir şeyi değiştirmemesini
istiyorum.

- Sprint 3 · **Bitti** · Sahip: Agents 1, Agents 3 / QA · Yapan: Berke
- Diyelim ki injection içeren bir e-posta geldi. Normal bir bekleyen kalem olur ve hiçbir şey
  onaylanmaz.
- Diyelim ki kullanıcının sorusunda checker'a yönelik talimatlar var. Checker bunları veri
  olarak görür.
- Kanıt: `app/agents/common.py` içindeki `GUARDRAILS`,
  `tests/test_ingest_sync.py::test_injection_email_is_just_a_pending_item`,
  `tests/test_ingest_sync.py::test_parser_agent_cannot_approve_even_if_it_obeys_the_email`,
  `tests/test_report_checker.py` (`test_prompt_marks_user_text_as_data`).

### US-GUARD-04 Kullanıcı ayrımını veritabanı da uygular

Product owner olarak, son savunma hattı olarak SQL Server row-level security istiyorum, böylece
tek bir sorgudaki hata başka bir kullanıcının satırlarını gösteremez.

- Sprint 2 · **Kısmen** · Sahip: Backend, Agents 3 / QA (cloud) · Yapan: Berke
- Bu story production veritabanı içindir. Kasa bugün SQLite ile çalışıyor (geliştirme, testler,
  demo) ve SQLite'ta RLS yok; orada ayrımı servislerdeki `user_id` filtresi sağlıyor
  (US-GUARD-01). Production için ileride Azure SQL Database (Microsoft SQL Server) planlıyoruz.
  Planın tamamı [DATABASE.md](DATABASE.md) dosyasında.
- Diyelim ki oturumda `SESSION_CONTEXT('user_id')` ayarlı. Kullanıcıya ait her tablo yalnızca o
  kullanıcının satırlarını, ev tabloları da yalnızca üyesi olduğu evleri döndürür (ev faturaları
  üyelere de görünür). `fx_rates` herkesin ortak kullandığı referans verisidir.
- Kanıt: `alembic/versions/0001_sprint1_baseline.py`, `0002_sprints_2_4.py`,
  `app/db/session.py`, `tests/test_migrations.py::test_sql_server_ddl_renders_offline`,
  `tests/test_migrations.py::test_sql_server_ddl_fits_azure_sql_database`.
- Eksik: migration'lar, RLS ve bağlantı kodu yazıldı ve offline test edildi, ama henüz bir Azure
  veritabanı yok. DDL yalnızca offline üretildi, Azure SQL'de hiç çalışmadı. RLS gerçek
  kullanıcılarla denenmedi (smoke test `docs/SETUP.md` dosyasında).

### US-GUARD-05 Para hep kuruşu kuruşuna doğru

Ali olarak, her payın ve her kur çevriminin kuruşuna kadar tutmasını istiyorum, böylece kimse
yuvarlama yüzünden para kaybetmez.

- Sprint 1 · **Bitti** · Sahip: Backend, Agents 2 · Yapan: Berke
- Diyelim ki herhangi bir bölüşüm var. Payların toplamı toplam tutarı verir. Bir kur çevriminde
  tutar bir kez, half to even kuralıyla yuvarlanır.
- Kanıt: `app/services/money.py`, `app/services/splits.py`, `app/services/fx.py`,
  `tests/test_house_splits.py` ve `tests/test_settlement.py` içindeki property testleri,
  `tests/test_money_fx.py::test_convert_minor_rounds_half_even`.

### US-GUARD-06 Kodda ve loglarda gizli bilgi yok

Product owner olarak, anahtarların yalnızca ortam değişkenlerinde durmasını ve Google
token'larının şifrelenmesini istiyorum, böylece sızan bir repo ya da log hiçbir şey açığa
çıkarmaz.

- Sprint 2 · **Bitti** · Sahip: Backend · Yapan: Berke
- Diyelim ki bir Google refresh token'ı var. Fernet ile şifrelenmiş olarak saklanır ve hiç
  loglanmaz.
- Kanıt: `app/config.py`, `app/services/crypto.py`, `.gitignore` (`.env`),
  `tests/test_ingest_oauth.py::test_tokens_never_reach_the_logs`,
  `tests/test_categories_crypto.py`.

### US-GUARD-07 Kullanıcı başına sohbet sınırı

Product owner olarak, `/chat` ve `/receipts` için kullanıcı başına bir limit istiyorum, böylece
tek bir kullanıcı (ya da bir döngü) ücretsiz Gemini kotasını herkes için tüketemez.

- Sprint 4 · **Başlanmadı** · Sahip: Backend
- Diyelim ki bir kullanıcı dakikada N'den fazla mesaj gönderiyor. Anlaşılır bir mesajla 429
  alır.
- Bugün `backend/app` içinde hiç rate limiting yok.

### US-GUARD-08 Hesabımı ve verilerimi sil

Elif olarak, hesabımı ve Kasa'nın benim hakkımda sakladığı her şeyi silmek istiyorum, böylece
verilerimin kontrolü bende kalır (KVKK).

- Sprint 4 · **Başlanmadı** · Sahip: Backend, Frontend
- Diyelim ki silmeyi onayladım. Harcamalarım, bütçelerim, aboneliklerim, gelen kutusu kalemlerim
  ve Google bağlantım silinir. Başkalarıyla ortak ev faturaları da onların bakiyeleri bozulmadan
  ele alınır.
- Bugün yalnızca Google bağlantısı kaldırılabiliyor (`DELETE /integrations/google`).

## Epik: hesaplar

### US-ACCOUNT-01 Kayıt ol, e-posta ya da Google ile giriş yap

Elif olarak, e-postamla kayıt olup ya da Google hesabımla giriş yapmak istiyorum, böylece
verilerim her cihazda benim olur.

- Sprint 4 · **Kısmen** · Sahip: Backend, Frontend · Yapan: Berke
- Diyelim ki kayıt oldum (ad, e-posta, en az 10 karakterlik şifre, KVKK ve koşulları kabul).
  Hemen iki adımlı doğrulamayı kurarım, kurmadan uygulamaya giremem.
- Diyelim ki "Google ile devam et" dedim. Google sadece kim olduğumu söyler (Gmail izni
  istenmez), Kasa yine 2FA kodunu ister. Aynı e-postayla şifreli bir hesap varsa Google girişi o
  hesaba bağlanmaz.
- Diyelim ki 5 kere yanlış şifre girdim. Hesap 15 dakika kilitlenir.
- `AUTH_MODE=accounts` iken her endpoint oturum ister; dev modunda `X-User-Id` de çalışır.
- Kanıt: `app/api/auth.py`, `app/services/accounts.py`, `app/services/security.py`, sayfalar
  `/login`, `/register`, `/login/continue`, `tests/test_accounts.py`.
- Eksik: Google OAuth client'ı açılmadığı için Google ile giriş sadece testte (sahte Google ile)
  çalıştı. E-posta doğrulaması ve "şifremi unuttum" yok.

### US-ACCOUNT-06 Google Authenticator ile iki adımlı doğrulama

Elif olarak, şifrem çalınsa bile hesabıma girilemesin istiyorum.

- Sprint 4 · **Bitti** · Sahip: Backend, Frontend · Yapan: Berke
- Diyelim ki hesabım var. Her girişte Google Authenticator'daki 6 haneli kodu girerim; aynı kod
  ikinci kez kabul edilmez.
- Diyelim ki telefonumu kaybettim. Kurulumda bir kere gösterilen 10 kurtarma kodundan biriyle
  girerim, her kod bir kere çalışır. Ayarlar'dan yeni kodlar alabilirim (o anki kodla).
- Kanıt: `POST /auth/totp/setup`, `/auth/totp/confirm`, `/auth/login/verify`,
  `/auth/recovery-codes`, `tests/test_accounts.py` (RFC 6238 test vektörü dahil).

### US-ACCOUNT-07 Açık oturumlarımı gör ve kapat

Elif olarak, kütüphane bilgisayarında açık unuttuğum oturumu kapatmak istiyorum.

- Sprint 4 · **Bitti** · Sahip: Backend, Frontend · Yapan: Berke
- Diyelim ki Ayarlar'dayım. Giriş yapılmış cihazları, son kullanım zamanıyla görürüm ve
  istediğimi kapatırım; kapanan oturumun token'ı hemen çalışmaz olur. Şifremi değiştirince
  diğer bütün oturumlar kapanır.
- Kanıt: `GET /auth/sessions`, `DELETE /auth/sessions/{id}`, `POST /auth/logout`,
  `POST /auth/password`, `tests/test_accounts.py`.

### US-ACCOUNT-02 Dev modunda herhangi bir kullanıcı ol

Geliştirici ya da sunumu yapan kişi olarak, bir id yazarak kullanıcı değiştirmek istiyorum,
böylece iki Google hesabı olmadan iki ev arkadaşını gösterebilirim.

- Sprint 1 · **Bitti** · Sahip: Backend, Frontend · Yapan: Berke
- Diyelim ki Firebase ayarı yok. Dev user kutusuna "demo" yazıp Switch'e bastığımda her istek
  `X-User-Id: demo` ile gider.
- Kanıt: `app/auth.py`, `frontend/src/components/Nav.tsx` (`DevUserSwitcher`),
  `tests/test_api.py::test_default_dev_user_without_header`.

### US-ACCOUNT-03 Görünen adımı değiştir

Ali olarak, ev arkadaşlarımın gördüğü adı ben belirlemek istiyorum.

- Sprint 4 · **Bitti** · Sahip: Backend, Frontend · Yapan: Berke
- Diyelim ki Settings'te adımı değiştirdim. Ev yeni adı gösterir.
- Kanıt: `GET /me`, `PATCH /me`, sayfa `/settings`,
  `tests/test_expenses_api.py::test_get_and_patch_display_name`,
  `tests/test_expenses_api.py::test_house_members_show_the_new_name`.

### US-ACCOUNT-04 Kasa'yı herkese açık bir adreste aç

Elif olarak, Kasa'yı telefonumdan herkese açık bir URL ile açmak istiyorum, böylece laboratuvar
dışında da kullanabilirim.

- Sprint 4 · **Kısmen** · Sahip: Agents 3 / QA (cloud) · Yapan: Berke
- Diyelim ki deploy script'leri çalıştı. `kasa-api` ve `kasa-web` Cloud Run'da, Azure SQL ve
  Firebase ile çalışır ve `docs/SETUP.md` içindeki smoke test geçer.
- Kanıt: `deploy/*.sh`, `.github/workflows/deploy.yml`, `docs/SETUP.md`.
- Eksik: script'ler yalnızca `bash -n` ve sahte bir `gcloud` ile kontrol edildi. Hiçbir şey deploy
  edilmedi. Production veritabanı olarak planlanan Azure SQL Database de henüz yok
  ([DATABASE.md](DATABASE.md)); bugün Kasa SQLite ile çalışıyor.

### US-ACCOUNT-05 Kasa'yı Türkçe ya da İngilizce kullan

Elif olarak, arayüzü Türkçe kullanmak, yabancı ev arkadaşım Tom olarak da İngilizce kullanmak
istiyorum.

- Sprint 4 · **Bitti** · Sahip: Frontend · Yapan: Berke
- Diyelim ki tarayıcım Türkçe. Kasa Türkçe açılır; sol menüdeki TR / EN düğmesiyle ya da
  Ayarlar'dan dili değiştirebilirim, seçim hatırlanır. Ay adları ve kategoriler de çevrilir.
- Diyelim ki mesajım dil belli etmiyor ("Netflix?"). Kasa arayüzün dilinde cevap verir.
- Kanıt: `frontend/src/lib/i18n.ts`, her özelliğin `messages.ts` dosyası,
  `app/agents/language.py`, `tests/test_chat_files.py::test_reply_language_follows_the_ui_when_the_message_is_neutral`.

## Takip tablosu

Her story için bir satır. "Yalnızca canlı" testler `KASA_LIVE_TESTS=1` ile çalışır. Tüm test
yolları `backend/tests/` altında.

| Story | Durum | API endpoint(ler)i | Frontend sayfası | Testler |
| --- | --- | --- | --- | --- |
| US-CAPTURE-01 | Bitti | `POST /expenses`, `GET /categories` | `/expenses` | `test_api.py`, `test_foundation_api.py` |
| US-CAPTURE-02 | Kısmen | `POST /receipts` | `/receipts` | `test_agents_offline.py`, `test_live.py` (yalnızca canlı) |
| US-CAPTURE-03 | Kısmen | `POST /chat` | `/chat` | eval `route-receipt-tr` |
| US-CAPTURE-04 | Bitti | `POST /expenses`, `GET /fx/*` | `/expenses` | `test_money_fx.py`, `test_foundation_api.py` |
| US-CAPTURE-05 | Bitti | `PATCH /expenses/{id}`, `DELETE /expenses/{id}` | `/expenses` | `test_expenses_api.py` |
| US-CAPTURE-06 | Bitti | `GET /expenses` (filtreler) | `/expenses` | `test_expenses_api.py` |
| US-BUDGET-01 | Bitti | `GET/PUT /budgets`, `DELETE /budgets/{id}`, `GET /budgets/status` | `/budgets` | `test_money_budgets.py`, `test_money_tools.py` |
| US-BUDGET-02 | Bitti | `POST /expenses` (uyarılar) | `/expenses`, `/` | `test_money_budgets.py`, `test_integration.py` |
| US-BUDGET-03 | Bitti | `GET /dashboard` | `/` | `test_money_dashboard.py` |
| US-BUDGET-04 | Bitti | `GET /subscriptions`, `POST /subscriptions/detect`, `GET /subscriptions/upcoming`, `POST /subscriptions/{id}/dismiss` | `/subscriptions`, `/` | `test_money_subscriptions.py` |
| US-BUDGET-05 | Kısmen | `POST /chat` | `/chat` | `test_money_tools.py`, eval'ler |
| US-BUDGET-06 | Bitti | `GET /dashboard` | `/` | `test_money_dashboard.py` |
| US-HOUSE-01 | Bitti | `POST/GET /houses`, `POST /houses/{id}/members` | `/houses` | `test_api.py` |
| US-HOUSE-02 | Bitti | `POST/GET/DELETE /houses/{id}/invites`, `GET /invites/{code}`, `POST /invites/{code}/accept` | `/houses`, `/invite/[code]` | `test_house_invites.py` |
| US-HOUSE-03 | Bitti | `POST /houses/{id}/expenses` | `/houses` | `test_settlement.py`, `test_api.py` |
| US-HOUSE-04 | Bitti | `POST /houses/{id}/expenses/split` | `/houses` | `test_house_api.py`, `test_house_splits.py` |
| US-HOUSE-05 | Bitti | `GET /houses/{id}/balances` | `/houses`, `/` | `test_settlement.py`, `test_house_api.py` |
| US-HOUSE-06 | Bitti | `GET/POST /houses/{id}/settlements`, `DELETE /houses/{id}/settlements/{id}` | `/houses` | `test_house_api.py`, `test_foundation_api.py` |
| US-HOUSE-07 | Kısmen | `GET/POST /houses/{id}/reminders`, `PATCH /houses/{id}/reminders/{id}` | `/houses` | `test_house_reminders.py` (sahte) |
| US-HOUSE-08 | Bitti | `DELETE /houses/{id}/members/{user_id}`, `DELETE /houses/{id}/expenses/{id}` | `/houses` | `test_house_members.py` |
| US-HOUSE-09 | Kısmen | `POST /chat` | `/chat` | `test_house_tools.py`, `test_live.py` (yalnızca canlı) |
| US-ASK-01 | Kısmen | `POST /chat` | `/chat` | `test_agents_offline.py`, `test_reports.py`, `test_report_guard.py`, eval'ler |
| US-ASK-02 | Bitti | `POST /chat` | `/chat`, `/` | `test_integration.py`, `test_report_guard.py` |
| US-ASK-03 | Bitti | `POST /chat` | `/chat` | `test_report_checker.py` |
| US-ASK-04 | Kısmen | `POST /chat` | `/chat` | `test_integration.py`, eval'ler |
| US-ASK-05 | Kısmen | `POST /chat` | `/chat` | `test_agents_offline.py`, eval'ler |
| US-ASK-06 | Kısmen | `POST /chat`, `POST /receipts` | `/chat`, `/receipts` | `test_live.py` (yalnızca canlı), eval'ler |
| US-ASK-07 | Kısmen | `POST /chat/files`, `POST /chat/imports/{id}` | `/chat` | `test_sheets.py`, `test_chat_files.py` |
| US-ASK-08 | Bitti | `POST /chat/stream` | `/chat` | `test_chat_files.py`, `chatStore.test.ts` |
| US-ASK-09 | Bitti | `GET/PATCH/DELETE /chat/conversations/*` | `/chat` | `test_chat_files.py`, `test_migrations.py` |
| US-ASK-10 | Bitti | `POST /chat/receipt`, `PUT /chat/messages/{id}/cards/{i}` | `/chat` | `test_chat_files.py` |
| US-ASK-11 | Bitti | `POST/GET /reports`, `GET /reports/{id}/run`, `GET /reports/{id}/export.csv`, `PATCH/DELETE /reports/{id}` | `/chat`, `/reports`, `/` | `test_saved_reports.py`, `test_reports.py` |
| US-INBOX-01 | Bitti | `POST /imports/statement` | `/import` | `test_ingest_statements.py` |
| US-INBOX-02 | Kısmen | `POST /imports/statement` | `/import` | `test_ingest_statements.py` (sahte), `test_ingest_live.py` (yalnızca canlı) |
| US-INBOX-03 | Bitti | `GET /inbox`, `PATCH /inbox/{id}`, `POST /inbox/{id}/approve`, `POST /inbox/{id}/reject`, `POST /inbox/approve`, `POST /inbox/reject` | `/inbox` | `test_ingest_inbox.py` |
| US-INBOX-04 | Kısmen | `/integrations/google/*`, `POST /internal/gmail/push`, `POST /internal/gmail/sync-all` | `/settings`, `/inbox` | `test_ingest_oauth.py`, `test_ingest_sync.py`, `test_ingest_gmail.py` (sahte) |
| US-INBOX-05 | Kısmen | `POST /chat` | `/chat` | `test_ingest_inbox.py`, `test_ingest_sync.py`, eval'ler |
| US-GUARD-01 | Bitti | hepsi | hepsi | `test_api.py`, `test_expenses_api.py`, `test_report_guard.py` |
| US-GUARD-02 | Bitti | `POST /chat` | `/chat` | `test_reports.py`, `test_report_guard.py`, eval `refusal-*` |
| US-GUARD-03 | Bitti | `POST /chat`, `POST /receipts`, Gmail senkronizasyonu | `/chat`, `/inbox` | `test_ingest_sync.py`, `test_report_checker.py` |
| US-GUARD-04 | Kısmen | hepsi (yalnızca SQL Server'da, planlanan production veritabanı) | yok | `test_migrations.py` (offline DDL) |
| US-GUARD-05 | Bitti | parayla ilgili her endpoint | hepsi | `test_house_splits.py`, `test_settlement.py`, `test_money_fx.py` |
| US-GUARD-06 | Bitti | `/integrations/google/*` | `/settings` | `test_ingest_oauth.py`, `test_categories_crypto.py` |
| US-GUARD-07 | Başlanmadı | `POST /chat`, `POST /receipts` | yok | yok |
| US-GUARD-08 | Başlanmadı | yok | yok | yok |
| US-ACCOUNT-01 | Kısmen | `/auth/register`, `/auth/login`, `/auth/google/*` | `/login`, `/register` | `test_accounts.py`, `test_foundation_api.py` |
| US-ACCOUNT-02 | Bitti | her endpoint (`X-User-Id`) | sol menü | `test_api.py` |
| US-ACCOUNT-03 | Bitti | `GET/PATCH /me` | `/settings` | `test_expenses_api.py` |
| US-ACCOUNT-04 | Kısmen | `GET /health` | hepsi | yok (deploy script'leri yalnızca dry-run) |
| US-ACCOUNT-05 | Bitti | `POST /chat` (`locale`) | hepsi | `test_chat_files.py`, `pickers.test.tsx` |
| US-ACCOUNT-06 | Bitti | `/auth/totp/*`, `/auth/login/verify`, `/auth/recovery-codes` | `/register`, `/login`, `/settings` | `test_accounts.py` |
| US-ACCOUNT-07 | Bitti | `GET/DELETE /auth/sessions`, `POST /auth/logout`, `POST /auth/password` | `/settings` | `test_accounts.py` |

## Açık story'ler

Kısmen:

- US-CAPTURE-02 Fişi fotoğraftan kaydet: fiş okumayı Gemini'de doğrulamak. Yusuf (#4).
- US-CAPTURE-03 Alışverişi sohbete yaz: Gemini'de doğrulamak. Yusuf.
- US-BUDGET-05 Bütçe, abonelik ve kurlar sohbette: cevap dilini düzeltmek, Gemini'de
  doğrulamak. Yusuf.
- US-HOUSE-07 Hesaplaşma hatırlatmaları: Calendar'ı gerçek Google'a karşı çalıştırmak. Ömer.
- US-HOUSE-09 Evi sohbetten yönet: Gemini'de doğrulamak. Ömer.
- US-ASK-01 Grafikli harcama soruları: Gemini'de doğrulamak. Yusuf.
- US-ASK-04 Benim dilimde cevap: kalan vakayı düzeltmek, Gemini'de ölçmek. Yusuf (#5).
- US-ASK-05 Yönlendirme: Gemini'de doğrulamak. Yusuf (#4).
- US-ASK-06 Kasa Gemini'de çalışır: `gemini-3.5-flash-lite` ile canlı testler ve eval'ler.
  Yusuf (#4).
- US-INBOX-02 PDF ekstreler: canlı bir çalıştırma kaydetmek. Yusuf.
- US-INBOX-04 Gmail: OAuth client'ı ve onay ekranını oluşturup gerçek akışı çalıştırmak. Mustafa.
- US-INBOX-05 Sohbette gelen kutusu: Gemini'de doğrulamak. Yusuf.
- US-GUARD-04 Row-level security: Azure SQL Database'i kurmak, migration'ları orada çalıştırmak
  ve RLS smoke testini yapmak. Mustafa (#12).
- US-ACCOUNT-01 Google ile giriş: Firebase'i ayarlamak. Mustafa, Zehra.
- US-ACCOUNT-04 Herkese açık adres: ilk Cloud Run deploy'u. Mustafa, Yusuf.

Başlanmadı:

- US-HOUSE-02 Ev arkadaşını linkle davet et. Ömer (#6), Zehra (#11).
- US-GUARD-07 Kullanıcı başına sohbet sınırı. Mustafa (#9).
- US-GUARD-08 Hesabımı ve verilerimi sil. Mustafa, Zehra (#13).
