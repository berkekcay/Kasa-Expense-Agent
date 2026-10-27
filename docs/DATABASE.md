# Veritabanı planı: şimdi SQLite, sonra Azure SQL

Kısaca: Kasa bugün **SQLite** ile çalışıyor. Production için **Azure SQL Database**'e
(Microsoft SQL Server) geçeceğiz. Geçişin kod tarafı yazıldı ve offline test edildi, ama henüz
gerçek bir Azure veritabanı açılmadı. Bu dosya neyin hazır olduğunu, neyin kaldığını ve kimin
yaptığını anlatıyor.

| Ortam | Veritabanı | Durum |
| --- | --- | --- |
| Geliştirme (herkesin laptopu) | SQLite, `backend/kasa.db` dosyası | Çalışıyor |
| Testler ve CI | SQLite, her test oturumunda geçici bir dosya | Çalışıyor, 600'den fazla test |
| Demo (Cuma 30 Ekim) | SQLite, veriyi `python -m scripts.seed_demo --user demo` kuruyor | Hazır |
| Production | Azure SQL Database, ücretsiz teklif (serverless) | Planlı, [#12](https://github.com/berkekcay/Kasa-Expense-Agent/issues/12) |

Hangi veritabanının kullanılacağına sadece `DATABASE_URL` karar veriyor. Kodda başka bir şey
değişmiyor.

## Neden şimdilik SQLite

- Kurulum yok. Veritabanı tek bir dosya, `pip install` sonrası hemen çalışıyor.
- Herkes kendi verisiyle çalışıyor, birinin denemesi diğerini bozmuyor.
- Testler hızlı ve internetsiz çalışıyor. CI'da da aynı şey.
- Demo internet olmadan da açılıyor. Sadece fiş okuma ve chat modele ihtiyaç duyuyor.

## Neden production'da Azure SQL

- **Row-level security (RLS):** SQL Server, her sorgunun sadece o kullanıcının satırlarını
  görmesini veritabanının kendisinde zorlayabiliyor. Kodda bir hata olsa bile başka birinin
  harcaması dönmüyor. SQLite'ta böyle bir özellik yok.
- **Ücretsiz:** Azure for Students okul mailiyle açılıyor, kredi kartı istemiyor. Azure SQL'in
  ücretsiz teklifi ayda 100.000 vCore saniye ve 32 GB veriyor. "Limit dolunca ay sonuna kadar
  duraklat" seçilirse hiç para çıkmıyor.
- **Yönetilen servis:** Yedekleme, güncelleme ve TLS Azure'da. Bizim sunucu yönetmemiz gerekmiyor.
- Cloud Run'daki backend çok kopya çalışabilir. SQLite dosyası bunu kaldırmaz, ortak bir
  veritabanı sunucusu gerekiyor.

## Kod tarafında hazır olanlar

Bunların hepsi yazıldı ve testlerle kontrol ediliyor (Yapan: Berke).

| Ne | Nerede | Nasıl kontrol ediliyor |
| --- | --- | --- |
| Aynı kod iki veritabanında | SQLAlchemy 2, `backend/app/db/` | Bütün testler SQLite'ta koşuyor; SQL Server'a özel kod sadece `db/session.py` içinde |
| Şema sadece migration'la değişiyor | `backend/alembic/versions/0001` ... `0003` | `test_upgrade_builds_exactly_the_models`, `test_downgrade_to_base_and_back` |
| SQL Server DDL'i | Aynı migration'lar | `test_sql_server_ddl_renders_offline`, `test_sql_server_ddl_fits_azure_sql_database` (Azure SQL'de olmayan `USE`, sunucu seviyesi komutlar vs. yok) |
| Row-level security | `security` şemasındaki fonksiyonlar ve `security.kasa_policy` | Migration testleri politikayı üretiyor; gerçek sunucuda deneme #12'de |
| Aktif kullanıcıyı veritabanına bildirmek | `db/session.py`, her transaction'da `SESSION_CONTEXT('user_id')` | Sadece SQL Server'da çalışıyor; gerçek sunucuda deneme #12'de |
| Arka plan işleri (Gmail senkronu) | `SESSION_CONTEXT('kasa_system')` | Gerçek sunucuda deneme #12'de |
| Azure'un uyuyan veritabanını beklemek | `db/session.py`, 40613 gibi geçici hatalarda yaklaşık 74 saniye tekrar deneme | `tests/test_db_connect_retry.py` |
| Sürücü | `backend/requirements-mssql.txt` (pyodbc), Dockerfile'da ODBC Driver 18 | Docker build |
| En az yetki | Uygulama `kasa_app` kullanıcısıyla bağlanıyor, şemayı değiştiremiyor. Migration ayrı bir admin login'le, Cloud Run job olarak çalışıyor | `deploy/` script'leri, SETUP.md |

RLS hangi tablolarda ne yapıyor:

- Harcamalar, kalemler ve paylar: sahibi ya da o evin üyeleri görüyor.
- Evler, ev üyelikleri, borç ödemeleri ve hatırlatıcılar: sadece o evin üyeleri.
- Bütçeler, abonelikler ve inbox: sadece sahibi.
- Google bağlantısı: sahibi ya da arka plandaki Gmail senkronu (`kasa_system`).
- `fx_rates` (döviz kurları) herkesin ortak verisi, `users` tablosunda RLS yok.

SQLite'ta bu üçüncü katman yok. Orada koruma iki katman: servisler her sorguyu kullanıcıya göre
filtreliyor, rapor ajanının SQL'i de sadece kullanıcıya göre filtrelenmiş tablolara erişebiliyor.
Azure'a geçince üçüncü katman olarak RLS ekleniyor.

## Geçiş adımları

Sahibi Mustafa, issue [#12](https://github.com/berkekcay/Kasa-Expense-Agent/issues/12).
Tıklama tıklama anlatım [SETUP.md](SETUP.md) içindeki Azure SQL bölümünde.

1. Azure for Students hesabı aç (okul maili).
2. Portalda ücretsiz teklifle bir SQL veritabanı oluştur: kaynak grubu `kasa-rg`, veritabanı
   `kasa`, SQL authentication, "auto-pause until next month".
3. Firewall kuralını ekle ve sorgu editöründe `kasa_app` kullanıcısını oluştur.
4. Bağlantı adreslerini sadece `backend/.env` içine yaz: `MIGRATION_DATABASE_URL` (admin) ve
   `DATABASE_URL` (`kasa_app`).
5. `alembic upgrade head` ile şemayı ve RLS politikasını kur.
6. Backend'i `AUTO_MIGRATE=false` ile Azure'a bağla, RLS smoke testini yap: B kullanıcısı A'nın
   verisini ne API'den ne de doğrudan SQL'den görebilmeli.
7. Demo verisini Azure'da da kur: `python -m scripts.seed_demo --user demo`.
8. Sonra Cloud Run deploy'u (US-ACCOUNT-04, Mustafa ve Yusuf).

## Veri taşıma

SQLite'taki veriyi Azure'a taşımıyoruz. Laptoplardaki veri deneme verisi, demo verisi de tek
komutla yeniden kuruluyor. Production boş bir veritabanıyla başlayacak.

## Dikkat edilecek farklar

- **İlk istek yavaş olabilir.** Ücretsiz veritabanı bir süre kullanılmayınca uyuyor ve uyanması
  yaklaşık bir dakika sürüyor. Backend bunu bekliyor, hata vermiyor.
- **Büyük küçük harf.** Azure SQL varsayılan olarak metin karşılaştırmasında büyük küçük harfe
  bakmıyor, SQLite bakıyor. Örneğin aynı `external_ref` farklı harflerle gelirse iki
  veritabanında farklı davranabilir. #12'de kontrol edilecek.
- **Ücretsiz limit.** Gmail senkronu veritabanını sık uyandırırsa aylık ücretsiz süre biter ve
  veritabanı ay sonuna kadar durur. Bu yüzden senkron 6 saatte bir, Gmail push kapalı.
- **Yeni tablo eklerken:** migration'a SQL Server için RLS predicate'i de eklenmeli
  (AGENTS.md'deki kural). Örneğin ev davet kodları (#6) yeni bir tablo getiriyor.

## Kim ne yaptı, kim ne yapacak

| İş | Kim | Durum |
| --- | --- | --- |
| Veri modeli, migration'lar, SQL Server DDL'i | Berke | Bitti |
| Row-level security politikası ve SESSION_CONTEXT | Berke | Bitti, gerçek sunucuda denenmedi |
| Uyuyan veritabanını bekleme, en az yetkili kullanıcı, deploy script'leri | Berke | Bitti |
| Azure hesabı, veritabanı kurulumu, RLS smoke testi | Mustafa | #12 |
| Cloud Run'ın Azure SQL'e bağlanması | Mustafa, Yusuf | US-ACCOUNT-04 |
| Yeni tabloların RLS'si (ev davetleri) | Ömer | #6 |

## Sunumda nasıl anlatılır

Hoca veritabanını sorarsa (İngilizce söylenecek):

> Today Kasa runs on SQLite, so everyone can run it on a laptop with no setup, and the tests
> and this demo work offline. For production we are moving to Azure SQL Database. The
> migrations already generate the SQL Server schema, and the row-level security policy is
> written: every transaction tells the database who the user is, and SQL Server itself hides
> other users' rows. That code is tested offline; setting up the real Azure database and
> testing it there is the next step, and Mustafa owns it.
