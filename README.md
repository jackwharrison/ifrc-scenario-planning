# Problem tree builder

A small Flask app that turns a completed hazard workbook into a problem tree, laid out like the eastern DRC problem tree (Current priorities, Humanitarian conditions, Impact, Shock, Context), and exports it as a Word document in IFRC branding.

The app counts what can be counted and shows how it did it. Everything that needs judgement (risk scores, context, affected groups, expected consequences) stays with the analyst.

## How it works

1. **Start.** Choose the country and the type of tree. Every country can be used (see "Areas and countries").
2. **Upload.** Upload the completed workbook. The app reads tab 3, the hazard list, by column name.
3. **Check.** Every row is checked. Rows with errors are left out; warnings are listed with row numbers so they can be fixed in Excel.
4. **Score risks.** The analyst sets likelihood and impact for each hazard. Scores of 16 or more become priority hazards.
5. **Review tree.** Boxes marked Automatic are written from the counts, each line with the rule and rows behind it. Boxes marked Needs you are written by hand. A "By area" view (By oblast, By province...) shows a table of events per area and hazard type, with filters.
6. **Export.** Choose landscape or portrait, and Word or PDF, then download. Save a version to compare with the next update.

Uploading a newer workbook keeps the scores, edited wording and hand-written lines.

## What is in this repository

```
app/
  __init__.py          starts the app, security settings, signed-in user
  routes.py            the pages and the small edit API used by the tree page
  storage.py           SQLite storage for trees, uploads and saved versions
  lists/               plain YAML lists: hazard types, sectors, factors, countries
    areas/             optional: built-in area lists for some countries (names, P-codes)
  workbook/            reading tab 3, the row checks, and the blank template generator
  tree/rules.py        the counting rules that write the tree
  export/word.py       the Word document
  export/pdf.py        the same layout as a PDF (reportlab, with the Liberation Sans font in export/fonts)
  templates/           the HTML pages
  static/              styles, scripts, IFRC logo
samples/               the Kyrgyzstan example workbook
tests/                 automatic tests (run on every push)
.github/workflows/     tests and deployment to Azure
startup.sh             the command Azure uses to start the app
Dockerfile             only needed if you run it as a container instead
```

## Run it on your own computer

You need Python 3.12.

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

export SECRET_KEY=dev SESSION_COOKIE_SECURE=false      # Windows: set SECRET_KEY=dev  and  set SESSION_COOKIE_SECURE=false
flask --app wsgi run
```

Open http://127.0.0.1:5000, start a tree for Kyrgyzstan and choose "Use the example" on the upload page.

Run the tests:

```bash
python -m unittest discover -s tests -v
```

## Put it on GitHub

1. Create a new, empty repository on GitHub (private is sensible).
2. Unzip this folder and push it:

```bash
cd problem-tree-builder
git init
git add .
git commit -m "First version of the problem tree builder"
git branch -M main
git remote add origin https://github.com/<your-organisation>/<your-repo>.git
git push -u origin main
```

The first push runs the tests. The deploy step will fail until the Azure settings below are in place; that is expected.

## Deploy to Azure App Service

These steps use the Azure portal. Names in quotes are the labels you will see; Azure sometimes moves them slightly between versions.

**1. Create the web app**

- Create a resource, then "Web App".
- Publish: Code. Runtime stack: Python 3.12. Operating system: Linux. Choose a region close to your users, such as West Europe.
- Pick a pricing plan. A Basic plan is enough for a small team; the free plan sleeps and is not suitable.

**2. Settings** (web app, then "Environment variables", "App settings")

| Name | Value |
|---|---|
| `SECRET_KEY` | a long random string (for example from `python -c "import secrets; print(secrets.token_hex(32))"`) |
| `DATABASE_PATH` | `/home/data/app.db` |
| `SCM_DO_BUILD_DURING_DEPLOYMENT` | `true` |
| `CLASSIFICATION` | `Internal` (printed at the bottom of the Word and PDF documents) |
| `SUPPORT_EMAIL` | optional, the support address in the page footer (default `jack.harrison@ifrc.org`) |
| `REPO_URL` | optional, the "Source code on GitHub" link in the page footer |

**3. Startup command** (web app, then "Configuration", "General settings", "Startup command")

```
gunicorn --bind=0.0.0.0:8000 --workers=1 --threads=4 --timeout=120 wsgi:app
```

**4. Connect GitHub**

- In the web app, open "Configuration", "General settings" and switch on "SCM Basic Auth Publishing Credentials". This is needed to download a publish profile.
- On the web app's "Overview" page, choose "Download publish profile".
- In your GitHub repository, open "Settings", "Secrets and variables", "Actions":
  - add a **secret** named `AZURE_WEBAPP_PUBLISH_PROFILE` and paste the whole content of the downloaded file;
  - add a **variable** named `AZURE_WEBAPP_NAME` with the name of your web app.
- Run the workflow again from the "Actions" tab, or push any change to `main`.

If your organisation does not allow publish profiles, use the web app's "Deployment Center" to connect GitHub instead. It creates its own workflow file; delete `.github/workflows/azure-webapp.yml` so you do not deploy twice.

**5. Sign-in**

- In the web app, open "Authentication", "Add identity provider", "Microsoft".
- Choose your organisation's tenant and require authentication for every request.
- Staff then sign in with their normal work account, and the app records their name on uploads, edits and saved versions.

Decide early whose accounts may sign in (your National Society only, or IFRC and partner staff too). That is set in your organisation's Microsoft Entra settings, usually by IT.

**6. Check it works**

Open `https://<your-app>.azurewebsites.net/health`. It should show `{"status": "ok"}`.

## Areas and countries

Every country in `countries.yaml` can be used. No map or boundary files are needed: events are counted per area in a table, so the app only needs the area names.

The app decides which areas to count against when a workbook is uploaded, in this order:

1. **Tab Lists of the uploaded workbook.** The column with the same header as the area column in tab 3 (`Areas` in the generic template). This lets a National Society use its own names, or another level, without changing the app.
2. **A built-in list** in `app/lists/areas/` for that country, if there is one.
3. **The names typed in tab 3.** Nothing is rejected, but names that look alike ("Jalal-Abad", "Jalalabad") get a warning so they can be made consistent.

With 1 and 2, a name in tab 3 that is not on the list is an error and the row is left out. The Check page says which list was used.

On the Start page, for a country without a built-in list, the user can say what the areas are called (province, region, district...). That word is used in the tree and the area table.

The area table copes with long lists: above 15 areas it shows a search box, the 20 areas with most events (with "Show all"), and lists the areas without events in one line.

### Adding a built-in area list (optional)

A built-in list pre-fills tab Lists of the template and names the area column. Copy `kyrgyzstan.yaml`, rename it after the country (lower case, spaces as hyphens, for example `south-sudan.yaml`) and change:

- `area_column`: the header of the area column in the workbook, for example `Regions`.
- `area_label`: how one area is called in sentences, for example `region`.
- `areas`: one entry per first-level area. `pcode` is optional; if you add it, take it from the OCHA administrative boundaries for that country on HDX. Do not type P-codes from memory. `city: true` adds "city" after the name in the table.
- `example_workbook` (optional): a file in `samples/` offered on the upload page.

The blank template for the country is generated from these lists, so its dropdowns match what the app accepts. Workbooks made from the generic template (column `Areas`) are accepted for every country, including ones with a built-in list.

## Changing the lists

- `hazards.yaml`: hazard types and sub-types.
- `sectors.yaml`: sectors that can be tagged.
- `factors.yaml`: underlying factor tags, and which Context column each one goes into (Political, Economic, Socio-cultural, Security, or Environmental and physical).

After changing a list, download a fresh template. Old workbooks with tags that are no longer on the list will show a warning, not an error.

## Data storage

Trees, uploaded workbooks and saved versions are kept in one SQLite file at `DATABASE_PATH`. On App Service, the `/home` folder is persistent storage that survives restarts and deployments.

This suits a small internal tool on a single instance. Keep the web app at one instance (no scale-out) and one worker, as in the startup command. If many people start using it at the same time, move to Azure Database for PostgreSQL; only `app/storage.py` needs to change.

Back up the database by downloading `/home/data/app.db` through the web app's "Advanced Tools" (Kudu), or by setting up App Service backups.

## Known limitations and next steps

- **Crisis analysis** (for example Sudan) is shown on the start page but not built yet. It needs a second sheet in the workbook for current figures, and rules that flag figures older than three months.
- **No geographic map**, on purpose: the area table works for every country from names alone. A map would need P-codes and boundary files per country.
- **Built-in area lists** exist only for Kyrgyzstan. Pre-filling every country (names from OCHA or geoBoundaries) is a one-off data job; until then, National Societies list their areas in tab Lists.
- **The Kyrgyzstan example** was standardised by hand from the original hazard list. Some choices (which oblast, death tolls that include neighbouring countries) are judgement calls; check the figures before relying on them.
- **The Word document** is built in code (`app/export/word.py`). If colleagues want to change the layout in Word themselves, it can be switched to a Word template filled with `docxtpl`.
- **Fonts** load from Google Fonts. If your network blocks that, the app falls back to system fonts; you can also download the fonts into `app/static/`.
- **The IFRC logo** in `app/static/img/` was supplied for this project. Check with your communications team that this is the right version and use for an internal tool.
