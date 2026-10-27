# Kasa

Kasa, bir öğrencinin kişisel harcamalarını ve ev arkadaşlarıyla ortak giderlerini takip eden
bir AI agent (Google ADK + Gemini). Fişleri okuyor, harcamaları kaydediyor, faturaları
bölüşüyor, borçları kapatıyor ve parayla ilgili soruları grafiklerle cevaplıyor.

**Buradan başla:** [kullanıcı hikayeleri](docs/USER_STORIES.md) (Kasa ne yapıyor, her parça
ne durumda), [mimari](docs/ARCHITECTURE.md) (diyagramlarla beş dakikalık bir özet, ardından
modül haritası), [ekip](docs/TEAM.md) (kim neyden sorumlu, nasıl çalışıyoruz),
[demo rehberi](docs/DEMO.md) (kurulum, demo verisi ve 30 Ekim 2026 Cuma demosunun akışı) ve
[veritabanı planı](docs/DATABASE.md) (bugün SQLite, production için Azure SQL).
Coding agent'lar [AGENTS.md](AGENTS.md) dosyasını okur.

Modül haritası, veri modeli, hangi dosyanın kime ait olduğu ve bir isteğin sistemde nasıl
ilerlediği [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) içinde.

Tek kural: LLM *ne* yapılacağına karar verir, para hesabının tamamını düz Python yapar.
Tutarlar float olarak değil, tam sayı alt birim (kuruş/cent) olarak saklanır.

**Veritabanı:** Kasa bugün SQLite ile çalışıyor (geliştirme, testler ve demo). Production
için Azure SQL Database (Microsoft SQL Server) planlıyoruz. Alembic migration'ları,
row-level security ve bağlantı kodu (auto-pause için yeniden deneme, `SESSION_CONTEXT`)
yazıldı ve offline test edildi, ama henüz bir Azure veritabanı yok. Planın tamamı ve işi kimin
yapacağı [veritabanı planı](docs/DATABASE.md) dosyasında.

## Mimari

```
 Tarayıcı
   |
   v
 Next.js web arayüzü (frontend/)   sohbet, fiş yükleme, harcamalar, ev, grafikler
   |  HTTPS + Firebase ID token (dev modunda X-User-Id)
   v
 FastAPI backend (backend/app)
   |-- api/        REST router'ları
   |-- agents/     Google ADK agent'ları
   |     coordinator --> receipt_agent   (save_expense, list_recent_expenses)
   |                 --> house_agent     (bölüşüm, bakiyeler, hesaplaşma, geri ödemeler)
   |                 --> report_agent    (korumalı, salt okunur SQL -> grafik tanımı)
   |                 --> budget_agent    (bütçeler, abonelikler, döviz kurları)
   |                 --> inbox_agent     (Gmail'de ve banka ekstrelerinde bulunan harcamalar)
   |-- services/   düz Python veri katmanı + para hesapları (unit test'li)
   |-- db/         SQLAlchemy modelleri + session'lar (MSSQL'de SESSION_CONTEXT ayarlar)
   |-- alembic/    migration'lar, SQL Server için row-level security dahil
   |        |                                  |
   v        v                                  v
 Gemini API (dev ve     SQLite (bugün)  /  Azure SQL, row-level security ile (planlı)
 testlerde Ollama)      Gmail, Calendar ve TCMB döviz kurları: app/integrations/
```

Güvenlik önlemleri:
- Rapor SQL'i sqlglot ile parse edilir. Yalnızca tek bir düz `SELECT` kabul edilir, o da
  sadece `my_spending`, `my_expenses`, `my_expense_items`, `my_house_shares`, `my_budgets` ve
  `my_subscriptions` üzerinde.
  Bu isimler, o anki kullanıcıya göre filtrelenmiş CTE'ler olarak eklenir ve bir satır limiti
  uygulanır. İkinci bir agent (checker) her sorguyu kullanıcının sorusuyla birlikte okur ve
  sorgu çalışmadan önce düzeltilmesi için geri gönderebilir.
- E-postalar ve banka ekstreleri sadece inbox kaydı oluşturur. Kullanıcı onaylamadan hiçbir
  şey harcamaya dönüşmez ve bir e-postanın içindeki metin hiçbir şeyi onaylayamaz.
- Kullanıcılar yalnızca kendi verilerini görür. Bu üç yerde uygulanıyor: service sorguları,
  kullanıcıya göre filtrelenmiş rapor CTE'leri ve SQL Server RLS (`backend/alembic/versions/`
  içindeki Alembic migration'ları oluşturuyor; bugünkü SQLite kurulumunda ilk ikisi geçerli).
- Fiş ve e-posta içeriği talimat olarak değil, veri olarak ele alınır. Bu her agent
  prompt'unda yazıyor ve işlemi yapan kullanıcı her zaman istekten gelir, modelden asla.
- Kodda anahtar yok. Ayarlar env değişkenlerinden gelir; Cloud Run'da bunların arkasında
  Secret Manager olacak.

## Kim neyden sorumlu

Sprint 2-4 işleri dört track'e bölündü (HOUSE, MONEY, INGEST, REPORT) ve her track'in kendi
dosyaları var. Tablo [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md#trackler-ve-sahipleri) içinde.

## Yerelde çalıştırma

Python 3.12+ ve Node 20+ gerekiyor (Python 3.14 ve Node 24 ile test ettik). Backend'i :8000,
frontend'i :3000 portunda başlat.

### Backend: Windows (PowerShell)

```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
Copy-Item .env.example .env        # sonra GOOGLE_API_KEY'ini .env içine yapıştır
pytest
uvicorn app.main:app --reload --port 8000
```

### Backend: macOS / Linux

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env               # sonra GOOGLE_API_KEY'ini .env içine yapıştır
pytest
uvicorn app.main:app --reload --port 8000
```

Uygulama açılırken veritabanı şemasını Alembic oluşturur ve günceller (`AUTO_MIGRATE=true`).
Elle çalıştırmak için: `alembic upgrade head`.

Tek bir dev kullanıcısı için demo verisi (üç aylık harcama, ortak bir ev, bütçeler,
abonelikler ve inbox kayıtları; ağ ya da LLM gerekmez): `python -m scripts.seed_demo --user demo`,
sonra "Dev user" kutusuna `demo` yaz. Baştan başlamak için `--reset` ekle. Ayrıntılar
[docs/DEMO.md](docs/DEMO.md) içinde.

API dokümanı http://localhost:8000/docs adresinde. LLM sağlayıcısı yoksa `POST /receipts` ve
`POST /chat` dışında her şey çalışır, bu ikisi 503 döner. Henüz yazılmamış özelliklerin
endpoint'leri 501 döner.

### Agent'ları Gemini yerine Ollama ile çalıştırma

Gemini anahtarı olmadan geliştirme yapmak için `backend/.env` içinde agent'ları bir Ollama
sunucusuna yönlendir:

```bash
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434     # ya da ekibin Ollama sunucusu
OLLAMA_MODEL=gpt-oss:20b                    # sohbet ve tool calling
OLLAMA_VISION_MODEL=qwen3-vl:8b             # fiş fotoğrafları
```

Bunun için `requirements-dev.txt` gerekiyor (litellm'i o ekliyor). Canlı uçtan uca testler:
`KASA_LIVE_TESTS=1 pytest -m live -s`.

### Frontend (her işletim sistemi)

```bash
cd frontend
npm install
cp .env.example .env.local         # PowerShell: Copy-Item .env.example .env.local
npm run dev                        # http://localhost:3000
```

Farklı kullanıcılar gibi davranmak için nav bar'daki "Dev user" kutusunu kullan. Örneğin
`ali` olarak bir ev oluştur, `ayse`'yi ekle, sonra `ayse`'ye geç.

### Frontend testleri

CI ile aynı Node.js 24 sürümünü kullan.

```bash
cd frontend
npm ci
npm test
```

Vitest, React Testing Library ve jsdom ile testler tek sefer çalışır; izleme modu için
`npm test -- --watch` kullan. API yanıtları testlerde taklit edilir; backend veya API anahtarı
gerekmez. Para biçimlendirme, API hata yönetimi ve harcama listesinin gösterimi test edilir.

## Ortam değişkenleri

Backend ayarlarının hepsi açıklamalarıyla birlikte `backend/.env.example` içinde, frontend
ayarları `frontend/.env.example` içinde. En çok lazım olanlar:

| Değişken | Nerede | Varsayılan | Not |
| --- | --- | --- | --- |
| `DATABASE_URL` | backend | `sqlite:///./kasa.db` | Production (planlı): `mssql+pyodbc://user:pass@host:1433/kasa?driver=ODBC+Driver+18+for+SQL+Server` |
| `AUTO_MIGRATE` | backend | `true` | Production'da `false`, migration ayrı bir deploy adımı |
| `LLM_PROVIDER` | backend | `gemini` | Dev ve testler için `ollama` |
| `GOOGLE_API_KEY` | backend | boş | Gemini anahtarı. Boşsa agent endpoint'leri kapalı (503). |
| `GEMINI_MODEL` | backend | `gemini-3.5-flash-lite` | Anahtarının erişebildiği herhangi bir Gemini model id'si. Yeni anahtarlar 2.5 modellerini kullanamıyor. |
| `FIREBASE_PROJECT_ID` | backend | boş | Production'da dolu. Boşsa dev modu (X-User-Id) |
| `TOKEN_ENCRYPTION_KEY` | backend | boş | Google refresh token'ları için Fernet anahtarı: `python -m app.services.crypto` |
| `GOOGLE_OAUTH_CLIENT_ID` / `_SECRET` | backend | boş | Gmail ve Calendar bağlantısı |
| `INTERNAL_TASK_TOKEN` | backend | boş | `/internal/*` için Cloud Scheduler secret'ı |
| `CORS_ORIGINS` | backend | `http://localhost:3000` | Virgülle ayrılmış liste |
| `NEXT_PUBLIC_API_URL` | frontend | `http://localhost:8000` | Build sırasında koda gömülür |
| `NEXT_PUBLIC_FIREBASE_*` | frontend | boş | Google ile giriş; boşsa dev user kutusu görünür |

### Gemini API anahtarı alma

1. https://aistudio.google.com/apikey adresine git ve bir Google hesabıyla giriş yap.
2. **Create API key**'e tıkla, bir Google Cloud projesi seç ya da yeni bir tane oluştur.
3. Anahtarı `backend/.env` içine `GOOGLE_API_KEY=...` olarak yaz. Asla commit etme. `.env`
   gitignore'da.

## Deploy

Production için plan şu: Google Cloud Run (`europe-west1` bölgesinde `kasa-api` ve
`kasa-web`) ve ücretsiz teklifteki bir Azure SQL Database. Bunların hiçbiri henüz kurulmadı,
Kasa bugün SQLite ile çalışıyor. [docs/SETUP.md](docs/SETUP.md) boş bir hesaptan smoke test
edilmiş bir deploy'a kadar bütün adımları anlatıyor: Gemini anahtarı, Azure SQL sunucusu,
veritabanı ve düşük yetkili uygulama kullanıcısı, Google OAuth onay ekranı ve client,
Firebase Auth, secret'lar, Pub/Sub, Cloud Scheduler ve GitHub deploy workflow'u.

Kısa hali, rehberdeki console adımlarından sonra Cloud Shell'de:

```bash
bash deploy/gcp_bootstrap.sh     # API'ler, service account'lar, secret'lar, Pub/Sub, Scheduler (tekrar çalıştırılabilir)
bash deploy/deploy_backend.sh    # Cloud Build, Cloud Run job olarak `alembic upgrade head`, deploy
bash deploy/deploy_frontend.sh   # NEXT_PUBLIC_* build argümanlarıyla Cloud Build, deploy
```

Şema ve row-level security policy'si yalnızca Alembic migration'larından gelir. Migration'lar
admin login'iyle (`MIGRATION_DATABASE_URL`) bir Cloud Run job olarak çalışır. Servis ise
`AUTO_MIGRATE=false` ile, veriyi okuyup yazabilen ama şemayı değiştiremeyen bir contained
database user olarak çalışır. Her transaction `SESSION_CONTEXT('user_id')` ayarlar ve RLS
policy'si buna göre filtreler. SQL Server DDL'ini sunucu olmadan incelemek için:

```bash
cd backend
alembic -x url="mssql+pyodbc://u:p@host/kasa?driver=ODBC+Driver+18+for+SQL+Server" upgrade head --sql
```

`.github/workflows/deploy.yml` aynı deploy script'lerini GitHub'dan çalıştırır (elle
tetiklenir, sadece `main`). Anahtar dosyası yerine Workload Identity Federation kullanır.

## Sprint 1 kontrol listesi

- [x] Fiş fotoğrafı receipt agent'a inline görsel olarak gidiyor ve `save_expense` tool'u harcamayı kaydediyor
- [x] Harcama listesi ve elle ekleme formu
- [x] Üyeleriyle bir ev, eşit bölüşüm (kalan kuruşlar dağıtılıyor, paylar her zaman toplama eşit)
- [x] Ev bakiyeleri ve greedy hesaplaşma transferleri
- [x] Soru report agent'a gidiyor, agent korumalı SQL çalıştırıp recharts'ın çizdiği bir grafik tanımı döndürüyor
- [x] Cloud Run için Dockerfile'lar (backend ve frontend)
- [x] pytest: para hesapları, SQL koruması, API'nin normal akışları ve script'li sahte bir LLM ile ADK bağlantıları
- [ ] Gerçek bir anahtarla canlı Gemini çağrılarını denemek (fiş doğruluğu, yönlendirme kalitesi)
- [ ] SQL Server kurmak, migration'ları çalıştırmak ve RLS'i uçtan uca test etmek (Azure SQL adımları docs/SETUP.md içinde)
- [ ] İlk Cloud Run deploy'u (`deploy/` içindeki script'ler hazır ama gerçek bir projede çalışmadı)

## Sprint 2 altyapısı

- [x] SQLite ve SQL Server için Alembic migration'ları (RLS dahil); modellerle uyumlu olduklarını bir test kontrol ediyor
- [x] Sprint 2-4 için veri modeli (bölüşümler, hesaplaşmalar, bütçeler, döviz, inbox, Google, abonelikler, hatırlatmalar)
- [x] Ev arkadaşları arasında kaydedilen ödemeler bakiyeleri düşürüyor
- [x] Türkçe eş anlamlılarıyla sabit kategori listesi
- [x] Firebase Auth (isteğe bağlı), yedek olarak dev header'ı
- [x] Dev için Ollama sağlayıcısı; Sprint 1'in üç akışı ekibin Ollama sunucusunda canlı olarak geçiyor
- [x] HOUSE, MONEY, INGEST ve REPORT track'leri için iskelet modüller, route'lar ve sayfalar
- [x] CI: her push'ta ruff, pytest, eslint, Vitest ve next build

## Sprint 2-4 track'leri

Dört track'in hepsi tamamlandı, backend'de stub kalmadı. Google ve LLM için sahtelerle offline
test edildi; REPORT eval'leri Ollama üzerinde canlı da çalıştı (`backend/evals/latest.md`).

- [x] HOUSE: eşit, yüzdeli, tutara göre ve kalem bazlı bölüşüm, kaydedilen ödemeler, hesaplaşma hatırlatmaları (Google Calendar)
- [x] MONEY: TCMB döviz kurları, uyarılı bütçeler, abonelik tespiti, dashboard
- [x] INGEST: Google OAuth bağlantısı, Gmail senkronizasyonu ve push handler'ı, CSV ve PDF ekstre içe aktarma, inbox onayı
- [x] REPORT: kullanıcıya göre filtrelenmiş tablolar, her sorguyu inceleyen checker agent, eval runner
- [ ] Gerçek Google'a karşı OAuth onayı, Gmail push ve Calendar etkinlikleri
- [ ] Aynı akışlar Ollama yerine Gemini ile

## Deploy kiti

- [x] Boş bir hesaptan smoke test'e kadar kurulum rehberi: [docs/SETUP.md](docs/SETUP.md)
- [x] Cloud Shell için `deploy/` script'leri: bootstrap, backend (önce migration job, sonra servis), frontend; `bash -n` ve sahte bir `gcloud` ile dry run'larla kontrol edildi
- [x] Workload Identity Federation ile elle tetiklenen GitHub Actions deploy'u (`.github/workflows/deploy.yml`)
- [x] Backend, duraklatılmış bir Azure SQL serverless veritabanının uyanmasını bekliyor (bağlantıda yeniden deneme, unit test'li)
- [x] SQL Server DDL'i Azure SQL Database için gözden geçirildi; `USE`, veritabanları arası isimler ve sunucu seviyesindeki komutları bir test engelliyor
- [ ] Script'leri gerçek bir Google Cloud projesi ve Azure SQL veritabanına karşı çalıştırmak
- [ ] Azure SQL'de gerçek kullanıcılarla RLS'i kontrol etmek (smoke test docs/SETUP.md içinde)
