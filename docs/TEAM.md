# Ekip ve çalışma anlaşması

Bu dosya kimin neyin sahibi olduğunu, repo üzerinde nasıl çalıştığımızı ve herkesin kendi
kısmını nasıl sunduğunu anlatıyor. Aşağıdaki rol dağılımı bir **öneri**. Ekibe daha iyi
uyacaksa satırlar arasında kişileri değiştirin, sonra bu dosyayı bir PR ile güncelleyin.

## Roller ve sahipler

Beş rol proje sayfasından geliyor. Ajan geliştirici #3 (QA ve cloud) rolünde henüz kimse yok,
o yüzden başka biri katılana kadar bu rolü Mustafa ve Yusuf paylaşıyor. Berke, product owner
rolünün yanında ajanlar dışındaki her şeyin ortak sahibi: backend, veritabanı, frontend, cloud
ve yönetim.

| Kişi | GitHub | Rol | Sahip olduğu işler |
| --- | --- | --- | --- |
| Berke | @berkekcay | Product owner, mimari, backend, veritabanı, frontend | user story'ler, mimari, öncelikler, issue triage, demo kiti, dokümanların son incelemesi; Mustafa ile veri modeli, migration'lar ve RLS, REST API ve cloud; Zehra ile frontend |
| Mustafa | @MustafaPar | Veritabanı ve backend (Berke ile) | veri modeli, migration'lar ve RLS, auth, REST API, Google OAuth ve Gmail altyapısı, ekstre CSV ayrıştırma |
| Yusuf | @Yusufrmak497 | Ajan geliştirici #1 | koordinatör, fiş ajanı, bütçe ajanı ve MONEY track'i, e-posta ve ekstre ayrıştırıcı ajanlar |
| Ömer | @omertarikcandir | Ajan geliştirici #2 | ev ajanı, bölüşümler, bakiyeler, hesaplaşma, ödemeler, Calendar hatırlatıcıları (HOUSE track'i) |
| Zehra | @zehraoz36 | Frontend (Berke ile) | `frontend/` içindeki bütün sayfalar ve bileşenler |
| Mustafa ve Yusuf | | Ajan geliştirici #3, QA ve cloud (ortak) | Yusuf: rapor ajanı, kontrol ajanı, eval'ler. Mustafa ve Berke: CI, Cloud Run deploy, Azure SQL |

### Hangi dosyalar kimde

Bu tablo, [ARCHITECTURE.md](ARCHITECTURE.md#trackler-ve-sahipleri) içindeki track tablosunun her
satırına bir kişi eklenmiş hali. Backend yolları `backend/app/`, frontend yolları
`frontend/src/` altında. `backend/`, `frontend/`, `deploy/`, `docs/` ya da `.github/` ile
başlayan yollar bunun dışında.

| Alan | Sahibi | Backend dosyaları | Frontend dosyaları |
| --- | --- | --- | --- |
| Ortak çekirdek | Mustafa, Berke | `main.py`, `config.py`, `auth.py`, `db/*`, `backend/alembic/*`, `api/expenses.py`, `api/users.py`, `api/internal.py`, `services/expenses.py`, `services/users.py`, `services/categories.py`, `services/crypto.py`, `services/clock.py`, `schemas/common.py`, `schemas/expenses.py`, `schemas/users.py` | `lib/api/client.ts`, `lib/auth.ts` (Zehra ve Berke ile) |
| Ajan runtime'ı | Yusuf | `agents/common.py`, `agents/runtime.py`, `agents/coordinator.py`, `agents/language.py`, `api/agents.py`, `schemas/agents.py`, `agents/receipt_agent.py`, `agents/tools/receipt_tools.py` | |
| HOUSE | Ömer | `services/splits.py`, `services/settlement.py`, `services/houses.py`, `services/reminders.py`, `integrations/google_calendar.py`, `api/houses.py`, `schemas/houses.py`, `agents/house_agent.py`, `agents/tools/house_tools.py` | `features/houses` (Zehra ile) |
| MONEY | Yusuf | `services/fx.py`, `integrations/tcmb.py`, `services/budgets.py`, `services/subscriptions.py`, `services/dashboard.py`, `api/budgets.py`, `api/subscriptions.py`, `api/dashboard.py`, `api/fx.py`, `schemas/budgets.py`, `schemas/subscriptions.py`, `schemas/dashboard.py`, `schemas/fx.py`, `agents/budget_agent.py`, `agents/tools/budget_tools.py` | `features/dashboard`, `features/budgets`, `features/subscriptions` (Zehra ile) |
| INGEST altyapısı | Mustafa, Berke | `integrations/google_oauth.py`, `integrations/gmail.py`, `services/gmail_sync.py`, `services/inbox.py`, `services/statements.py`, `api/integrations.py`, `api/inbox.py`, `api/imports.py`, `schemas/inbox.py`, `schemas/imports.py`, `schemas/integrations.py` | `features/inbox`, `features/imports`, `features/settings` (Zehra ile) |
| INGEST ajanları | Yusuf | `agents/email_agent.py`, `agents/statement_agent.py`, `agents/tools/inbox_tools.py` | |
| REPORT | Yusuf (QA payı) | `services/reports.py`, `agents/report_agent.py`, `agents/tools/report_tools.py`, `agents/checker_agent.py`, `backend/evals/` | `features/chat` (Zehra ile) |
| Cloud ve CI | Mustafa (QA payı), Berke | `backend/Dockerfile`, `deploy/*`, `.github/workflows/*`, `docs/SETUP.md` | `frontend/Dockerfile` |
| Frontend | Zehra, Berke | | `frontend/src/**` |
| Ürün dokümanları ve demo | Berke | `docs/USER_STORIES.md`, `docs/ARCHITECTURE.md`, `docs/DATABASE.md`, `docs/TEAM.md`, `docs/DEMO.md`, `README.md`, `backend/scripts/seed_demo.py` | |

"Zehra ile" şu demek: sayfada ne olacağına track'in sahibi karar veriyor, sayfayı Zehra ya da
Berke yapıyor veya review ediyor. Herkes kendi dosyalarının testlerini kendisi yazıyor.

### Herkesin ilk issue'ları

[USER_STORIES.md](USER_STORIES.md) içinde yarım kalmış ya da hiç başlanmamış her story bir
issue oluyor. Açık olanlar aşağıda, her birinde bir coding agent için hazır bir prompt var:

- **Herkes:** [#3](https://github.com/berkekcay/Kasa-Expense-Agent/issues/3) Cuma demosunu
  kurmak, prova etmek ve kaydetmek.
- **Mustafa:** [#7](https://github.com/berkekcay/Kasa-Expense-Agent/issues/7) CSV export PR'ını
  bitirmek, [#8](https://github.com/berkekcay/Kasa-Expense-Agent/issues/8) Next.js 16.4.3,
  [#9](https://github.com/berkekcay/Kasa-Expense-Agent/issues/9) kullanıcı başına sohbet
  limiti (US-GUARD-07). Sonra: Azure SQL veritabanını kurmak ve RLS smoke testi (US-GUARD-04),
  Yusuf ile ilk Cloud Run deploy'u (US-ACCOUNT-04), "verilerimi sil" özelliğinin backend
  kısmı (US-GUARD-08).
- **Yusuf:** [#4](https://github.com/berkekcay/Kasa-Expense-Agent/issues/4) Gemini'yi
  `gemini-3.5-flash-lite` ile doğrulamak (US-ASK-06, US-CAPTURE-02), sonra
  [#5](https://github.com/berkekcay/Kasa-Expense-Agent/issues/5) cevap dili (US-ASK-04).
- **Ömer:** [#6](https://github.com/berkekcay/Kasa-Expense-Agent/issues/6) ev davet kodları,
  backend ve ev ajanı (US-HOUSE-02). Sonra: OAuth client hazır olunca Calendar
  hatırlatıcılarını gerçek bir Google hesabıyla denemek (US-HOUSE-07).
- **Zehra:** [#10](https://github.com/berkekcay/Kasa-Expense-Agent/issues/10) frontend
  testlerini CI'a eklemek, [#11](https://github.com/berkekcay/Kasa-Expense-Agent/issues/11)
  davet kodu sayfaları (US-HOUSE-02). Sonra: Ayarlar sayfasında "verilerimi sil" (US-GUARD-08),
  backend kısmı Mustafa'da.

## Çalışma anlaşması

- **`main`'e doğrudan push yok.** `main` korumalı. Her değişiklik bir pull request üzerinden
  geçiyor, bir onay ve yeşil CI gerekiyor. Berke repo admini olduğu için kendi doküman
  değişikliklerini doğrudan merge ediyor, diğer herkesin değişikliği bir onayı ve yeşil CI'ı
  olan bir PR istiyor.
- **Her PR'da tek issue.** Önce issue'yu aç, sonra `feature/<short-name>` adında bir branch aç
  (örneğin `feature/house-invites`). Bug fix'ler için `fix/<short-name>`, sadece doküman
  değişikliği için `docs/<short-name>` kullan.
- **PR template'ini kullan** (`.github/pull_request_template.md`): Problem, Approach,
  Testing, Screenshots, Linked issue. Merge olunca issue kapansın diye `Closes #<issue>` yaz.
- **Tek review.** Dokunduğun dosyaların sahibinden review iste. Sadece kendi dosyalarına
  dokunduysan, senin kodunu çağıran kişiden iste. PR'ı açan kişi onay almadan merge etmiyor.
- **CI yeşil olmalı**: ruff, ruff format, Python 3.12 ve 3.14 üzerinde pytest, frontend için
  eslint ve `next build`.
- **Merge etmeden önce her review thread'ini çöz**, CodeRabbit'inkiler de dahil. Bir yoruma
  katılmıyorsan gerekçeni yazıp resolve et, açık bırakma.
- **Küçük PR'lar.** Mümkünse 400 değişen satırın altında kalsın. Büyük özellikleri böl.
- **Secret yok.** Key'ler gitignore'daki `backend/.env` dosyasına gidiyor. Bir key'i asla
  issue'ya, PR'a, ekran görüntüsüne ya da sohbete yapıştırma.
- **Testler offline kalıyor.** live olarak işaretlenmemiş hiçbir test Gemini'yi, Google'ı ya
  da TCMB'yi çağıramaz.

## Uygulamayı ve testleri çalıştırmak

Windows ve macOS için adımların tamamı [DEMO.md](DEMO.md#bir-gün-önce-kurulum) dosyasında ve
README'de. Kısaca:

```bash
cd backend
python -m venv .venv            # Windows: py -m venv .venv
# activate it: .\.venv\Scripts\Activate.ps1 (Windows) or source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env            # Windows: Copy-Item .env.example .env
ruff check . && ruff format --check . && pytest -q
python -m scripts.seed_demo --user demo
uvicorn app.main:app --reload --port 8000

cd ../frontend
npm install
npm run dev                     # http://localhost:3000, type "demo" in the Dev user box
```

Bir modele karşı canlı testler: `KASA_LIVE_TESTS=1 pytest -m live -s`. Eval'ler:
`python -m evals.run_evals` (bkz. `backend/evals/run_evals.py` içindeki docstring).

## Bu repoda kodlama ajanı kullanmak

Claude Code, Codex, Copilot ve benzeri ajanlar repo kökündeki [AGENTS.md](../AGENTS.md)
dosyasını okuyor (`CLAUDE.md` onu import ediyor). Orada klasör yapısı, komutlar ve asla
bozulmaması gereken kurallar var: tam sayı alt birimler, tool'lar kullanıcıyı `tool_context`'ten
alır, güvenilmeyen metin veridir, secret yok. Birkaç ipucu:

- Ajana her seferinde tek bir issue ve story id'si ver, önce testi yazmasını iste.
- "Bitti" demeden önce CI komutlarını çalıştırmasını iste.
- Push etmeden önce diff'in her satırını oku. Yazar sensin, ajan değil.
- Bir ajan sohbetine asla gerçek bir API key yapıştırma.

## Lab sunumları

Herkes sahibi olduğu kısmı sunuyor, böylece hoca beşimizi de dinlemiş oluyor. Kısa bir lab
sunumu şöyle olabilir:

| Bölüm | Kim | Süre |
| --- | --- | --- |
| Problem, kullanıcılar ve mimari | Berke (Berke yoksa Mustafa) | 2 dk |
| Veri modeli, API, güvenlik katmanları | Mustafa | 2 dk |
| Koordinatör, fişler, bütçeler ve para hesabı | Yusuf | 2 dk |
| Evler, bölüşümler ve hesaplaşma | Ömer | 2 dk |
| Uygulamanın kendisi, sayfa sayfa | Zehra | 2 dk |

Herkes son labdan beri yaptığı ya da düzelttiği bir şeyi, bunu kanıtlayan bir testi ve sırada
ne yapacağını gösteriyor. 30 Ekim 2026 Cuma günkü demo için [DEMO.md](DEMO.md) dosyasını takip
edin.
