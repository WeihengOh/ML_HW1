# CDTA Route 12 — What Counts (HW1)

A Streamlit dashboard over stop-level Automatic Passenger Counter (APC) data
for CDTA Route 12 (downtown Albany ↔ Crossgates Mall, Guilderland NY).

## Run it locally

```bash
pip install -r requirements.txt
python -m streamlit run app.py
```

(Always launch with `python -m streamlit run app.py`, not the bare `streamlit`
command — it sidesteps PATH / PowerShell execution-policy issues entirely.)

## Add more days of data

Drop any additional `apc4rpi_*.csv` extracts (same column layout as the
samples already in `data/`) into the `data/` folder. The loader globs
everything matching that pattern, so no code changes are needed — just
re-run or redeploy. Only 4 sample days ship in this repo to keep it small;
add more before your final submission if you want a wider date range for
the date-range slider to actually do something.

## Deploy to Streamlit Community Cloud

1. **Do this first, before building anything further:** push this folder as
   a GitHub repo (public or with Streamlit Cloud given access), go to
   [share.streamlit.io](https://share.streamlit.io), point it at `app.py`,
   and get the URL working — even before you're happy with the app. First
   deploys fail for reasons that have nothing to do with your code
   (`requirements.txt` in the wrong place, repo permissions, file paths),
   and those are cheap to fix on day one.
2. Make sure `requirements.txt` sits in the **repo root** (it does here).
3. Make sure `data/*.csv` is committed to the repo — Streamlit Cloud only
   sees what's in the repository, nothing on your laptop's disk.
4. Once deployed, test the URL in a **private/incognito browser window,
   signed out of GitHub** — that's the only way to know it works for someone
   who isn't you.
5. Check the URL again the day before it's due. An idle app goes to sleep
   and needs a "wake" click; an app that fails to wake is an app that fails
   to grade.

## What's in this repo

- `app.py` — the dashboard (3 controls, 3 charts, caching, provenance,
  blind-spot panel)
- `requirements.txt` — `streamlit`, `pandas`, `plotly`
- `data/` — 4 sample days of CDTA Route 12 APC extracts (Jul 4–7, 2025)
