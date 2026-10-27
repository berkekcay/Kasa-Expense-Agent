# Kasa kurulum rehberi

Bu rehber, ekipte bulut hesaplarını kuran kişi için yazıldı (bulut kurulumu Mustafa'da).
Hiçbir şey yokken başlayıp çalışan bir Kasa deploy'una kadar gidiyor. Adımları sırayla izle.
Bir iki saat ayır, çoğu console'larda tıklamakla geçiyor.

**Bugünkü durum:** Kasa şu an SQLite ile çalışıyor (geliştirme, testler ve demo). Bu
rehberdeki production kurulumu planlanan kurulum. Henüz ne Azure veritabanı ne de Cloud Run
servisleri var. Veritabanı planının tamamı ve kimin ne yapacağı [docs/DATABASE.md](DATABASE.md)
dosyasında.

Rehberin sonunda elinde şunlar olacak:

- Google Cloud Run'da, `europe-west1` bölgesinde `kasa-api` (FastAPI backend) ve `kasa-web`
  (Next.js frontend)
- ücretsiz teklifte bir Azure SQL Database, Alembic migration'larından gelen row-level
  security policy'siyle
- Firebase Auth üzerinden Google ile giriş, Google OAuth üzerinden Gmail ve Calendar erişimi,
  bir AI Studio anahtarıyla Gemini
- Pub/Sub ile Gmail push bildirimleri ve üç Cloud Scheduler job'u

Google Cloud'daki komut satırı işlerini `deploy/` içindeki script'ler yapıyor. Geri kalanı web
console'larında. Buradaki her şey sadece offline kontrol edildi (sahte bir `gcloud` ile script
dry run'ları, SQL Server DDL'inin sunucusuz üretilmesi). İlk gerçek çalıştırmayı sen
yapacaksın, o yüzden her script'in çıktısını oku.

## 1. Gereksinimler

- Projeyi kuran kişinin bir Google hesabı.
- Google Cloud Shell (https://shell.cloud.google.com). İçinde `gcloud`, `git`, `python3` ve
  `docker` hazır geliyor, bir şey kurman gerekmiyor. gcloud CLI ile kendi bilgisayarını da
  kullanabilirsin ama script'ler Cloud Shell (bash) için yazıldı ve öyle anlatılıyor.
- Azure for Students üzerinden bir Azure hesabı (adım 4). Azure CLI (`az`) şart değil, bu
  rehber Azure portal'ını kullanıyor.
- GitHub reposuna okuma erişimi.

## 2. Google Cloud projesi ve faturalandırma

1. https://console.cloud.google.com adresini aç, proje seçiciye tıkla, sonra **New project**.
   Projeye örneğin `kasa-ekip` adını ver. **Project ID**'yi not al (addan farklı olabilir).
2. Bir billing account bağla (menüde **Billing**). Free tier içinde kalsan bile Cloud Run
   bunu istiyor. Yeni billing account'larla genelde ücretsiz deneme kredisi geliyor.
3. Sürpriz fatura olmasın diye bir bütçe uyarısı kur: **Billing > Budgets & alerts > Create
   budget**, örneğin 5 USD, uyarılar yüzde 50, 90 ve 100'de.
4. Cloud Shell'i aç ve kodu çek:

   ```bash
   gcloud config set project <PROJECT_ID>
   git clone https://github.com/berkekcay/Kasa-Expense-Agent.git kasa
   cd kasa
   source deploy/config.sh && echo "API: $API_URL" && echo "Web: $WEB_URL"
   ```

   Cloud Run URL'leri `https://<service>-<project number>.<region>.run.app` kalıbında, yani
   iki URL de daha hiçbir şey deploy edilmeden belli. Bunlar 5. ve 6. adımlarda lazım olacak.
   Script'lerin bütün ayarları `deploy/config.sh` içinde.

## 3. Gemini API anahtarı

1. https://aistudio.google.com/apikey adresine git ve projeyi kuran hesapla giriş yap.
2. **Create API key**'e tıkla ve Kasa projesini seç (ya da başka bir proje, aşağıya bak).
3. Anahtarı 7. adım için sakla. Repodaki hiçbir dosyaya koyma.

Billing'i açık bir projedeki anahtar ücretli tier'ı kullanır. Free tier'da kalmak için
anahtarı billing'i olmayan ayrı bir projede oluştur; AI Studio her anahtarın yanında tier'ı
gösteriyor. Free tier'da Google prompt'ları kendi ürünlerini geliştirmek için kullanabilir,
o yüzden bu tier'dayken test fişleri ve test e-postaları kullan.

## 4. Azure SQL Database (ücretsiz teklif)

Bu bölüm planlanan production veritabanını anlatıyor. Henüz kurulmadı, Kasa bugün SQLite ile
çalışıyor. Migration'lar, row-level security ve bağlantı kodu hazır ve offline test edildi.
Plan, sıralama ve görev dağılımı için [veritabanı planı](DATABASE.md) dosyasına bak.

### 4.1 Azure for Students

https://azure.microsoft.com/free/students adresinden okul e-postanla kaydol. Yıllık bir kredi
veriyor ve kredi kartı istemiyor. Aşağıdaki SQL Database ücretsiz teklifi, 4.2'deki
auto-pause ayarını değiştirmediğin sürece bu krediden harcamıyor.

### 4.2 Sunucu ve veritabanı

https://portal.azure.com içinde **SQL databases** ara ve **Create**'e tıkla.

1. **Basics**
   - Resource group: **Create new**, `kasa-rg`.
   - Database name: `kasa`.
   - Server: **Create new**. Server name: benzersiz bir şey, örneğin `kasa-sql-ekip`.
     Location: Belçika'ya yakın bir bölge, örneğin **West Europe**. Öğrenci aboneliği bölgeyi
     reddederse (bir policy hatası) başka bir Avrupa bölgesi dene.
     Authentication method: **Use SQL authentication**. Bir server admin login'i seç (örneğin
     `kasaadmin`) ve uzun, rastgele bir parola belirle (en az 20 karakter; bağlantı
     string'i basit kalsın diye sadece harf, rakam ve `-_.!` kullan). Bu admin login'i sadece
     migration'lar için.
   - Bir banner ücretsiz teklifi öneriyor ("Want to try Azure SQL Database for free?").
     **Apply offer**'a tıkla. Compute tier General Purpose serverless oluyor.
   - **Behavior when free limit reached**: **Auto-pause the database until next month**'u
     seç. Böylece veritabanı hiçbir zaman para tutmaz, limit dolunca ayın geri kalanında
     durur.
2. **Networking**
   - Connectivity method: **Public endpoint**.
   - Allow Azure services and resources to access this server: **No** (Cloud Run bir Azure
     servisi değil ve bu ayar sunucuyu bütün Azure müşterilerine açar).
   - Add current client IP address: **Yes**, portal'daki query editor çalışsın diye.
   - Minimum TLS version: **1.2**.
3. Gerisini olduğu gibi bırak, **Review + create**'e, sonra **Create**'e tıkla.

### 4.3 Cloud Run için firewall

Cloud Run'ın sabit bir çıkış IP adresi yok, bu yüzden sunucuda "sadece Cloud Run'a izin ver"
diye bir kural yazılamıyor. İki seçenek var:

- **Bütün adreslere izin vermek** (bu rehberin kullandığı yol). Veritabanını değil sunucuyu
  aç, **Security > Networking**'e git ve **Firewall rules** altında `0.0.0.0` ile
  `255.255.255.255` arası için `AllowCloudRun` adında bir kural ekle. Kaydet. Sunucu artık
  internetten erişilebilir; onu SQL login'i, uzun parola ve TLS koruyor (bağlantı string'i
  `Encrypt=yes` ve geçerli bir sertifika istiyor).
- **Sabit çıkış IP'si** (daha sıkı, ücretli). Backend'i Cloud NAT ve ayrılmış sabit bir IP ile
  bir VPC üzerinden geçir (`--vpc-egress=all-traffic` ile Cloud Run Direct VPC egress), sonra
  sadece o IP'ye izin ver. NAT gateway ve IP ayda birkaç dolar tutuyor, bu yüzden burada
  varsayılan değil.

### 4.4 Uygulamanın veritabanı kullanıcısı

Uygulama, sadece veri erişimi olan bir contained database user ile bağlanır. Bu kullanıcı
şemayı ya da security policy'yi değiştiremez, yani row-level security ona her zaman uygulanır.
4.2'deki admin login'ini sadece migration job kullanır.

`kasa` veritabanını aç, **Query editor (preview)**'a tıkla, admin login'iyle giriş yap ve
şunu çalıştır (farklı, uzun bir parola seç):

```sql
CREATE USER kasa_app WITH PASSWORD = '<app password>';
GRANT SELECT, INSERT, UPDATE, DELETE ON SCHEMA::dbo TO kasa_app;
```

Bu yetki, migration'ların sonradan oluşturacağı tabloları da kapsıyor. İlk deploy'dan sonra
(adım 8) uygulama kullanıcısının migration kayıt tablosuna dokunmasını da engelleyebilirsin:

```sql
DENY INSERT, UPDATE, DELETE ON dbo.alembic_version TO kasa_app;
```

Predicate fonksiyonları `security` şemasında duruyor ve `kasa_app`'in orada hiçbir yetkisi
yok. Policy schema-bound olduğu için kullanıcıların bu fonksiyonlarda yetkiye ihtiyacı yok.

### 4.5 Bağlantı URL'leri

Backend'in iki SQLAlchemy URL'ine ihtiyacı var. `gcp_bootstrap.sh` (adım 7) parçaları sorup
ikisini de senin için oluşturuyor, bu kısım sadece bilgi için:

```
mssql+pyodbc://<user>:<password, URL-encoded>@<server>.database.windows.net:1433/kasa?driver=ODBC+Driver+18+for+SQL+Server&Encrypt=yes&TrustServerCertificate=no
```

| Secret Manager adı | Env değişkeni | Kullanıcı | Kim okuyor |
| --- | --- | --- | --- |
| `database-url` | `DATABASE_URL` | `kasa_app` | backend servisi |
| `migration-database-url` | `MIGRATION_DATABASE_URL` | admin login | sadece migration job |

Parolada `@`, `:`, `/` ve `%` gibi karakterler percent-encode edilmezse URL'i bozar. Elle
encode etmek için:

```bash
python3 -c 'import getpass, urllib.parse; print(urllib.parse.quote(getpass.getpass(), safe=""))'
```

Backend image'ında Microsoft ODBC Driver 18 zaten var.

### 4.6 Auto-pause ve ilk istek

Ücretsiz veritabanı bir süre bağlantı gelmezse duraklıyor (bu süre veritabanının
**Compute + storage** sayfasındaki auto-pause delay; sunulan en düşük değere ayarla).
Duraklamışken ilk login 40613 hatasıyla düşüyor ve veritabanının uyanması yaklaşık bir dakika
sürüyor.

Backend bunu hallediyor: `app/db/session.py`, 40613 (ve Azure'un diğer geçici login
hataları) ile düşen bir login'i yaklaşık 75 saniye boyunca yeniden deniyor. Yani duraklamadan
sonraki ilk istek yavaş ama başarılı oluyor. Migration job da aynı yeniden denemeyi
kullanıyor. `pool_pre_ping`, instance boşta beklerken ölen pool bağlantılarını yeniliyor.
Pool'daki bağlantılar da Cloud Run instance'ı kapanana kadar veritabanını uyanık tutuyor, bu
da son istekten birkaç dakika sonra oluyor.

Gmail sync zamanlamasını seçmeden önce sondaki "Ücretsiz limitler ve maliyetler" bölümünü oku.

## 5. Gmail ve Calendar için Google OAuth

Kasa, backend'deki standart bir OAuth web akışıyla Gmail'den fişleri okuyor ve Google
Calendar'a hesaplaşma hatırlatmaları ekliyor.

### 5.1 Onay ekranı

1. Kasa projesinde https://console.cloud.google.com/auth/overview (Google Auth Platform)
   adresini aç ve **Get started**'a tıkla.
2. App name `Kasa`, support email olarak kendi e-postan, audience **External**, contact
   olarak yine kendi e-postan. Policy'yi kabul et ve oluştur.
3. **Audience**: publishing status'u **Testing**'de bırak. **Test users** altına Kasa'yı
   kullanacak herkesin Google hesabını ekle (en fazla 100).
4. **Data access > Add or remove scopes**: şu dört scope'u ekle (listede yoksa "Manually add
   scopes" altına yapıştır) ve kaydet:

   ```
   openid
   https://www.googleapis.com/auth/userinfo.email
   https://www.googleapis.com/auth/gmail.readonly
   https://www.googleapis.com/auth/calendar.events
   ```

Testing modunun Kasa için anlamı:

- `gmail.readonly` kısıtlı bir scope. Uygulamayı herkese açmak için Google'ın doğrulaması ve
  her yıl üçüncü taraf bir güvenlik değerlendirmesi gerekiyor, bu yüzden uygulama Testing'de
  kalıyor.
- Sadece test kullanıcıları giriş yapabiliyor. Bu, aynı projeyi kullanan Firebase'in Google
  ile girişi için de geçerli.
- Testing'deki uygulamaların Google refresh token'ları 7 gün sonra geçersiz oluyor. Kasa
  ölmüş token'ı fark ediyor, Google'ı bağlantısı kopmuş olarak gösteriyor ve kullanıcı
  **Settings**'ten tekrar bağlanıyor.
- Onay sırasında Google bir "unverified app" uyarısı gösteriyor. **Advanced**'e tıklayıp
  devam et.

### 5.2 OAuth client

1. **Clients > Create client**, tür **Web application**, ad `kasa-api`.
2. **Authorized redirect URIs** altına ikisini de ekle:

   ```
   http://localhost:8000/integrations/google/callback
   <API_URL>/integrations/google/callback
   ```

   `<API_URL>`, 2. adımda yazdırılan backend URL'i, örneğin
   `https://kasa-api-123456789012.europe-west1.run.app`.
3. **Create**'e tıkla ve client ID ile client secret'ı hemen kopyala (JSON'u da indir; console
   secret'ı bir daha göstermeyebilir). İkisini 7. adımda gireceksin.

Gmail ve Calendar API'lerini `gcp_bootstrap.sh` açıyor.

## 6. Firebase Auth

1. https://console.firebase.google.com adresini aç, **Create a project**'e (ya da **Add
   project**'e) tıkla ve 2. adımdaki mevcut Google Cloud projesini seç, böylece ikisi aynı
   projeyi paylaşır. Google Analytics gerekmiyor.
2. **Build > Authentication > Get started > Sign-in method**: **Google**'ı aç, support
   email'i seç, kaydet.
3. **Authentication > Settings > Authorized domains**: frontend host'unu ekle. Bu,
   `https://` olmadan `<WEB_URL>`, örneğin `kasa-web-123456789012.europe-west1.run.app`.
   `localhost` zaten listede.
4. **Project settings > General > Your apps**: bir **Web** uygulaması ekle (`</>`), nickname
   `kasa-web`, Hosting yok. `apiKey`, `authDomain`, `projectId` ve `appId` değerlerini kopyala.
5. Bunları Cloud Shell'de kaydet. Bu dosya gitignore'da ve Cloud Shell home klasörünü
   saklıyor:

   ```bash
   cat > deploy/config.local.sh <<'EOF'
   NEXT_PUBLIC_FIREBASE_API_KEY="<apiKey>"
   NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN="<authDomain>"
   NEXT_PUBLIC_FIREBASE_PROJECT_ID="<projectId>"
   NEXT_PUBLIC_FIREBASE_APP_ID="<appId>"
   # deploy/config.sh ayarlarını ezmek için, örneğin:
   # SYNC_SCHEDULE="0 * * * *"     # 6 saatte bir yerine saatte bir
   # ENABLE_GMAIL_PUSH=true        # yeni mail saniyeler içinde (daha çok ücretsiz veritabanı süresi harcar)
   EOF
   ```

Bu dört değer public web config (tarayıcıya giden bundle'ın içine giriyor), secret değil.
Backend, Firebase ID token'larını `FIREBASE_PROJECT_ID`'ye göre kontrol ediyor ve deploy
script'i bunu proje ID'sine ayarlıyor. İki taraf da aynı projeyi göstermeli.

## 7. Google Cloud bootstrap

Bunu Cloud Shell'de repo klasöründen bir kez çalıştır. Tekrar çalıştırmak sorun değil: var
olanı atlıyor ve sadece hâlâ boş olan secret'ları soruyor.

```bash
bash deploy/gcp_bootstrap.sh
```

Azure SQL sunucu adını, admin login'ini ve parolasını, `kasa_app` parolasını, Gemini
anahtarını ve OAuth client ID ile secret'ını soruyor. Bir soruyu atlamak için boş bırak, script'i
sonra tekrar çalıştırırsın. Oluşturdukları:

- **API'ler**: Cloud Run, Cloud Build, Artifact Registry, Secret Manager, Pub/Sub, Cloud
  Scheduler, Gmail, Calendar, IAM, Identity Toolkit (Firebase Auth) ve birkaç yardımcı API.
- `kasa` adında bir **Artifact Registry** reposu; en yeni 5 image'ı tutan bir cleanup
  policy'siyle.
- Cloud Build yüklemeleri için `<project>-kasa-build` **bucket**'ı (dosyalar 7 gün sonra
  siliniyor).
- Her biri sadece ihtiyacı olan yetkiye sahip **service account**'lar:

  | Hesap | Kullanan | Yetkiler |
  | --- | --- | --- |
  | `kasa-api` | backend servisi | kendi altı secret'ını okumak |
  | `kasa-migrate` | migration job | `migration-database-url`'i okumak |
  | `kasa-web` | frontend servisi | yok |
  | `kasa-build` | Cloud Build | `kasa` reposuna push, build bucket'ını okumak, log yazmak |
  | `kasa-pubsub-push` | Pub/Sub push token'ı | yok (sadece kimliği kullanılıyor) |

- Secret Manager'da **secret'lar**: `database-url`, `migration-database-url`,
  `gemini-api-key`, `google-oauth-client-id`, `google-oauth-client-secret` ve kendi ürettiği
  iki tane: `token-encryption-key` (`TOKEN_ENCRYPTION_KEY`, saklanan Google refresh
  token'ları için Fernet anahtarı) ve `internal-task-token` (`INTERNAL_TASK_TOKEN`).
  Şifreleme anahtarını sonradan değiştirme: eski anahtarla şifrelenmiş token'lar okunamaz ve
  her kullanıcının Google'ı yeniden bağlaması gerekir.
- Gmail push için **Pub/Sub** (`ENABLE_GMAIL_PUSH=false` ile atlanır): `kasa-gmail` topic'i,
  Gmail'in kendi hesabına bu topic'te publish yetkisi ve her mesajı Google imzalı bir OIDC
  token'ıyla backend'e gönderen bir push subscription. Backend bu token'ın audience'ını ve
  service account'unu kontrol ediyor. Temel komutlar:

  ```bash
  gcloud pubsub topics create kasa-gmail
  gcloud pubsub topics add-iam-policy-binding kasa-gmail \
    --member serviceAccount:gmail-api-push@system.gserviceaccount.com --role roles/pubsub.publisher
  gcloud pubsub subscriptions create kasa-gmail-push --topic kasa-gmail \
    --push-endpoint "$API_URL/internal/gmail/push" \
    --push-auth-service-account "kasa-pubsub-push@$PROJECT_ID.iam.gserviceaccount.com" \
    --push-auth-token-audience "$API_URL/internal/gmail/push" --ack-deadline 30
  ```

- **Cloud Scheduler** job'ları, saat dilimi Europe/Istanbul; her biri
  `X-Kasa-Task-Token: <internal-task-token>` header'ıyla bir `POST`:

  | Job | Varsayılan zamanlama | Endpoint | Süre sınırı |
  | --- | --- | --- | --- |
  | `kasa-gmail-sync-all` | 6 saatte bir (`SYNC_SCHEDULE`) | `/internal/gmail/sync-all` | 900 s |
  | `kasa-gmail-renew-watches` | her gün 08:10 | `/internal/gmail/renew-watches` | 180 s |
  | `kasa-fx-refresh` | her gün 16:00 | `/internal/fx/refresh` | 180 s |

  Sync job'unun süre sınırı uzun, çünkü her yeni e-postayı Gemini ile parse ediyor. Gmail
  watch'ları 7 gün sonra bitiyor, günlük yenileme push'u ayakta tutuyor. TCMB günün döviz
  kurlarını 15:30 civarı yayımlıyor. Token job ayarlarında saklanıyor ve proje viewer'ları
  onu görebiliyor; başka herkes `/internal/*`'dan 401 alıyor.

Bitince URL'leri yazdırıyor ve hâlâ boş olan secret'ları listeliyor.

## 8. Backend deploy

```bash
bash deploy/deploy_backend.sh
```

İlk çalıştırma yaklaşık on dakika sürüyor. Script şunları yapıyor:

1. `database-url` ya da `migration-database-url` boşsa duruyor.
2. `backend/Dockerfile`'ı `kasa-build` olarak Cloud Build ile build ediyor ve
   `europe-west1-docker.pkg.dev/<project>/kasa/api:<git commit>` olarak push ediyor.
3. Aynı image'dan `kasa-migrate` Cloud Run job'unu `alembic upgrade head` komutuyla ve
   sadece `MIGRATION_DATABASE_URL` bağlı olarak deploy ediyor, sonra çalıştırıp bekliyor.
   Migration başarısız olursa script, yeni kod trafik almaya başlamadan duruyor.
4. `kasa-api` servisini deploy ediyor: `AUTO_MIGRATE=false`, `LLM_PROVIDER=gemini`,
   `FIREBASE_PROJECT_ID`, frontend URL'ine ayarlanmış `CORS_ORIGINS` ve `FRONTEND_URL`,
   `GOOGLE_OAUTH_REDIRECT_URI`, üç `PUBSUB_*` ayarı ve env değişkeni olarak bağlanan altı
   secret (`DATABASE_URL`, `GOOGLE_API_KEY`, `TOKEN_ENCRYPTION_KEY`,
   `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET`, `INTERNAL_TASK_TOKEN`). Hâlâ boş
   olan bir secret atlanıyor ve ona bağlı özellik kendini yapılandırılmamış olarak
   gösteriyor.
5. `/health`'i çağırıyor.

Servis ayarları ve nedenleri:

| Ayar | Değer | Neden |
| --- | --- | --- |
| CPU, bellek | 1 vCPU, 1 GiB | ADK, Google client'ları ve pyodbc 512 MiB'a pek sığmıyor |
| Concurrency | 20 | istekler çoğunlukla Gemini'yi ve veritabanını bekliyor |
| Timeout | 900 s | `sync-all` her yeni e-posta için bir Gemini çağrısı yapıyor |
| Max instances | 1 | sohbet session'ları instance belleğinde duruyor, maliyet de sınırlı kalıyor |
| `--no-cpu-throttling` | açık | aşağıya bak |
| `--allow-unauthenticated` | açık | Firebase token'larını, push token'ını ve task token'ını uygulama kendisi kontrol ediyor |

`--no-cpu-throttling` gerekiyor, çünkü iki endpoint cevap verdikten sonra da çalışmaya devam
ediyor: `POST /internal/gmail/push` hemen 204 dönüyor ve e-postayı bir background task'te
parse ediyor, OAuth callback de ilk Gmail sync'ini aynı şekilde başlatıyor. Varsayılan
request-based billing'de Cloud Run, cevap gönderilir gönderilmez CPU'yu kısıyor ve bu iş
yarıda kalıyor. Instance-based billing, instance yaşadığı sürece CPU'yu açık tutuyor.
Trafik yokken instance'lar yine sıfıra iniyor.

## 9. Frontend deploy

```bash
bash deploy/deploy_frontend.sh
```

`NEXT_PUBLIC_*` değerleri build sırasında bundle'a gömülüyor. Bu yüzden script
`NEXT_PUBLIC_API_URL`'i (backend URL'i) ve dört Firebase değerini Docker build argümanı olarak
veriyor, sonra `kasa-web`'i deploy ediyor (512 MiB, sıfıra iniyor). Firebase değerleri eksikse
duruyor, çünkü production API dev user kutusunu reddediyor.

Kod değiştikten sonra yeniden deploy etmek için Cloud Shell'de `git pull` yap ve değişen
kısmın script'ini çalıştır. İkisi de değiştiyse önce backend'i çalıştır.

## 10. GitHub Actions ile deploy (isteğe bağlı)

`.github/workflows/deploy.yml`, GitHub'dan elle basılan bir butonla ve JSON anahtarı olmadan
deploy ediyor. GitHub job'a kısa ömürlü bir OIDC token veriyor, Google'ın Workload Identity
Federation'ı bunu `kasa-deployer` service account'unun kimlik bilgileriyle değiştiriyor ve
sadece senin reponun `main` branch'indeki workflow'lar kabul ediliyor.

Bir kerelik kurulum:

1. Cloud Shell'de:

   ```bash
   GITHUB_REPO=berkekcay/Kasa-Expense-Agent bash deploy/gcp_bootstrap.sh
   ```

   Bu, normal işlerine ek olarak `github` identity pool'unu, `kasa-repo` provider'ını
   (koşul: bu repo ve `refs/heads/main`) ve şu rollere sahip `kasa-deployer`'ı oluşturuyor:
   Cloud Run Admin, Secret Manager Viewer (secret versiyonlarını listeler, değerleri
   okuyamaz), `kasa` reposunda Artifact Registry Writer ve sadece `kasa-api`, `kasa-migrate`
   ve `kasa-web` üzerinde Service Account User. Workflow image'ları runner'da Docker ile build
   ediyor, bu yüzden deployer'ın Cloud Build ya da Storage rolüne ihtiyacı yok.
2. GitHub'da **Settings > Secrets and variables > Actions > Variables** altına script'in
   yazdırdığı değişkenleri (`GCP_PROJECT_ID`, `GCP_PROJECT_NUMBER`, `GCP_REGION`,
   `GCP_WIF_PROVIDER`, `GCP_DEPLOYER_SA`) ve dört `NEXT_PUBLIC_FIREBASE_*` değerini ekle.
   GitHub CLI ile: `gh variable set GCP_PROJECT_ID --body <value>` ve diğerleri için de aynı
   şekilde.
3. **Actions > Deploy > Run workflow** ile `main` üzerinde çalıştır; backend, frontend ya da
   ikisini birden seç.

## 11. Smoke test

Bunları Cloud Shell'de `source deploy/config.sh`'tan sonra çalıştır:

- [ ] `curl -s "$API_URL/health"` çıktısında `"status":"ok"`, `"agents_enabled":true` ve
  `"auth":"firebase"` var.
- [ ] `curl -s -o /dev/null -w '%{http_code}\n' "$API_URL/expenses"` `401` yazdırıyor.
- [ ] `curl -s -o /dev/null -w '%{http_code}\n' -X POST "$API_URL/internal/fx/refresh"`
  `401` yazdırıyor (task token yok).
- [ ] `gcloud run jobs executions list --job kasa-migrate --region "$REGION"` başarılı bir
  çalıştırma gösteriyor.
- [ ] `gcloud scheduler jobs run kasa-fx-refresh --location "$REGION"` çalıştır; job
  **Cloud Scheduler**'da başarılı bir son çalıştırma, `kasa-api` log'larında da 200 gösteriyor.

Sonra tarayıcıda, `$WEB_URL` adresinde bir test kullanıcısıyla giriş yapmışken:

- [ ] Google ile giriş çalışıyor ve nav bar'da dev user kutusu değil senin adın görünüyor.
- [ ] Elle bir harcama ekle; listede görünüyor.
- [ ] Bir fiş fotoğrafı yükle; receipt agent kaydediyor (ilk canlı Gemini çağrısı).
- [ ] Sohbete "bu ay kategoriye göre ne kadar harcadım?" diye sor; bir grafik geliyor.
- [ ] Bir ev oluştur, ikinci bir test kullanıcısı ekle, ortak bir harcama gir. İkinci
  kullanıcı giriş yapınca aynı bakiyeleri görüyor, üçüncü bir hesap ise evi görmüyor.
- [ ] **Settings > Connect Google**, scope'ları kabul et; Google bağlı ve bir Gmail watch
  bitiş tarihiyle Settings'e geri dönüyorsun.
- [ ] Kendine konusunda "Sipariş" ya da "Order" geçen bir e-posta gönder. Bir dakika içinde
  (push) ya da Settings'teki Gmail sync butonuna bastıktan sonra bir inbox kaydı çıkıyor.
- [ ] Row-level security, Azure query editor'da admin olarak:

  ```sql
  SELECT name, is_enabled FROM sys.security_policies;   -- kasa_policy, 1
  SELECT COUNT(*) FROM dbo.expenses;                    -- 0: SESSION_CONTEXT'te kullanıcı yok
  EXEC sp_set_session_context @key = N'user_id', @value = N'<your Firebase UID>';
  SELECT COUNT(*) FROM dbo.expenses;                    -- sadece senin harcamaların
  ```

  UID, **Firebase console > Authentication > Users** içinde.
- [ ] Portal veritabanını **Paused** olarak gösterene kadar uygulamaya dokunma, sonra Kasa'yı
  yenile. İlk sayfa bir dakikaya kadar sürüyor, sonra çalışıyor.

## Ücretsiz limitler ve maliyetler

Fiyatlar ve limitler değişiyor, her servisin kendi sayfasına bak.

- **Azure SQL ücretsiz teklif**: veritabanı başına ayda 100.000 vCore saniye compute ve
  32 GB depolama. Veritabanı uyanıkken en az minimum vCore'u kadar faturalanıyor (bkz.
  **Compute + storage**). 0,5 vCore'da bu ayda yaklaşık 55 saat uyanıklık demek, günde iki
  saatten az. Saatlik bir `sync-all` job'u ya da aktif posta kutuları için Gmail push,
  veritabanının duraklamasını engelliyor ve ücretsiz miktar birkaç günde bitiyor; sonra
  veritabanı gelecek aya kadar duraklamış kalıyor. Varsayılanların 6 saatte bir sync ve
  kapalı push olmasının nedeni bu. Bir demo için push'u açmak istersen
  `deploy/config.local.sh` içine şunu yaz:

  ```bash
  ENABLE_GMAIL_PUSH=true        # yeni mail saniyeler içinde
  ```

  sonra `bash deploy/gcp_bootstrap.sh` ve `bash deploy/deploy_backend.sh` komutlarını tekrar
  çalıştır. Ücretsiz miktardan ne kadar kaldığını veritabanının **Overview** sayfası
  gösteriyor.
- **Cloud Run**: aylık ücretsiz bir vCPU ve bellek saniyesi kotası var. Instance-based billing
  (`--no-cpu-throttling`) bir instance'ın açık kaldığı bütün süreyi sayıyor; instance'lar
  sıfıra indiği için birkaç kullanıcıda bu yine az.
- **Artifact Registry**: 0,5 GB ücretsiz; cleanup policy kullanımı bunun civarında tutuyor.
- **Cloud Scheduler**: billing account başına 3 ücretsiz job, Kasa da tam olarak bu kadar
  kullanıyor.
- **Secret Manager**: birkaç aktif secret versiyonu ücretsiz; Kasa'nın yedi tanesi birkaç
  cent tutuyor.
- **Cloud Build, Pub/Sub, Firebase Auth**: Kasa'nın kullanımı free tier'lara sığıyor.
- **Gemini**: rate limit'li free tier ya da token başına ücretli (adım 3).

## Sorun giderme

| Belirti | Neden ve çözüm |
| --- | --- |
| Girişten sonra her API çağrısı 401 | `NEXT_PUBLIC_FIREBASE_PROJECT_ID` ile backend'deki `FIREBASE_PROJECT_ID` farklı projeleri gösteriyor |
| Girişte `auth/unauthorized-domain` | frontend host'unu Firebase authorized domains'e ekle (adım 6) |
| Tarayıcı console'unda CORS hatası | `CORS_ORIGINS` frontend URL'iyle birebir aynı olmalı, sonda eğik çizgi olmadan |
| Google'dan `redirect_uri_mismatch` | OAuth client'ta `<API_URL>/integrations/google/callback` olmalı (adım 5.2) |
| `Login failed for user 'kasa_app'` | kullanıcı `kasa` yerine `master`'da oluşturulmuş ya da parola secret'takinden farklı |
| İki dakikadan uzun süren 40613 hatası | ücretsiz miktar bitmiş, veritabanı gelecek aya kadar duraklatıldı |
| Migration job başarısız | **Cloud Run > Jobs > kasa-migrate** içinde çalıştırmayı aç ve log'ları oku |
| Push log'larında "unexpected service account" | subscription'ın push hesabı `PUBSUB_PUSH_SERVICE_ACCOUNT`'tan farklı; iki script'i de tekrar çalıştır |
| Scheduler job'ları 401 alıyor | task token değişmiş; `gcp_bootstrap.sh` ve `deploy_backend.sh`'ı tekrar çalıştır |

Bir secret'ı değiştirmek için yeni bir versiyon ekle ve yeni instance'lar okusun diye
yeniden deploy et:

```bash
printf '%s' '<new value>' | gcloud secrets versions add gemini-api-key --data-file=-
bash deploy/deploy_backend.sh
```
