Tado Boost
==========

Tado Boost je jednoduchá custom integrace pro Home Assistant, která poskytuje službu pro dočasné "boost" zapnutí všech Tado topných zón (výchozí 15 minut) a poté obnoví jejich původní stavy.

Rychlý přehled
-------------
- Integrace používá OAuth2 flow (Home Assistant OAuth helper) pro autorizaci u Tado.
- Po nastavení je k dispozici služba `tado_boost.boost_all_zones` s volitelným parametrem `minutes`.

Co v tomto repozitáři najdete
-----------------------------
- `custom_components/tado_boost/` — samotná integrace (config flow, API klient, služby).
- `hacs.json` — metadata pro HACS.
- `translations/en.json` — základní překlady pro UI.
- `README.md`, `LICENSE`, `CODEOWNERS` — dokumentace a metadata.

Instalace lokálně (manual)
--------------------------
1. Zkopírujte složku `custom_components/tado_boost` do vašeho HA config adresáře: `C:\config\custom_components\tado_boost`.
2. Restartujte Home Assistant.
3. V UI: Settings → Devices & Services → Add Integration → hledejte "Tado Boost".

Instalace přes GitHub + HACS (doporučeno pro uživatele)
---------------------------------------------------
Postup pro zveřejnění repozitáře na GitHub a instalaci přes HACS:

1) Vytvořte veřejný repozitář na GitHubu (např. `tado_boost`).
2) Nahrajte tento projekt do repozitáře a vytvořte release (tag). Příklad příkazů (Windows cmd):

```cmd
cd C:\Users\Pepik\IdeaProjects\tado_boost
git init
git add --all
git commit -m "Initial Tado Boost integration with OAuth2 support"
git branch -M main
git remote add origin https://github.com\<your-github-username>\tado_boost.git
git push -u origin main
```

3) Na GitHubu vytvořte nový Release (např. `v1.0.0`) — HACS preferuje, když je k dispozici alespoň jeden tag/release.

4) Přidejte repozitář do HACS (Home Assistant Community Store):
   - V Home Assistant → HACS → Integrations → tři tečky (vpravo nahoře) → Custom repositories → vložte URL do vašeho repozitáře (https://github.com/<your-github-username>/tado_boost) a vyberte kategorii "integration".
   - Po přidání nainstalujte integraci přes HACS → Integrations → Install.

Poznámka: v `hacs.json` jsou meta informace; upravte pole `owner`/`repo` podle vašeho GitHub účtu před publikováním.

OAuth konfigurace (Tado)
------------------------
Integrace používá OAuth2 autorizaci. Abyste poskytli uživatelům hladký onboarding, postupujte následovně:

1. Zaregistrujte aplikaci v Tado developer portálu (pokud Tado vyžaduje registraci třetích stran). Získejte `client_id` a `client_secret`.
2. Redirect URI, které doporučujeme zaregistrovat u Tado: `https://auth.home-assistant.io/redirect`.
3. Scopes: integrace v kódu používá `home.user:all` — ověřte, zda Tado tento scope podporuje, případně upravte.
4. Pokud chcete zabudovat `client_id`/`client_secret` přímo do integrace, upravte `custom_components/tado_boost/const.py` (proměnné `OAUTH2_CLIENT_ID` a `OAUTH2_CLIENT_SECRET`).

Bez vloženého `client_id`/`client_secret` může být nutné, aby si koncový uživatel zaregistroval vlastní OAuth aplikaci u Tado a zadal detaily při přidávání integrace (některé instance HA zobrazí dialog pro registraci nebo použijí sdíleného klienta Home Assistant).

Testování služby
----------------
Po úspěšné autorizaci vyzkoušejte službu přes Developer Tools → Services:

```yaml
service: tado_boost.boost_all_zones
data:
  minutes: 15
```

Tipy a doporučení před zveřejněním
---------------------------------
- V `manifest.json` a `CODEOWNERS` nahraďte `@<your-github-username>` vaším uživatelským jménem.
- Ujistěte se, že `hacs.json` obsahuje správné `owner` a `repo` pole.
- Přidejte `README.md` a screenshoty konfigurace pro lepší přijetí v HACS. HACS dále preferuje, když je repozitář veřejný a má alespoň jeden release.
- Přidejte `strings.json` (překlady) pro lepší UI zážitek; v této verzi je základní `translations/en.json` k dispozici.
- Zvažte přidání jednoduchých unit testů.

Bezpečnost a soukromí
---------------------
- Nikdy nezveřejňujte `client_secret` pokud nemáte důvod; pokud chcete veřejnou integraci, zvažte použít centrálně registrovaného klienta nebo poskytněte instrukce, jak si jej uživatel vytvoří.

Další pomoc
-----------
Chcete, abych:
1) doplnil `manifest.json`, `hacs.json` a `CODEOWNERS` s vaším GitHub jménem (uvedete ho) a vytvořil návrh `release` tagu, nebo
2) vytvořil `strings.json` a rozšířil překlady do dalších jazyků, nebo
3) připravil pull-request template / issue template pro nový repozitář?

Napište, kterou z možností chcete, a provedu to dál.
