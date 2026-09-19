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

## What's in this repo

- `app.py` — the dashboard (3 controls, 3 charts, caching, provenance,
  blind-spot panel)
- `requirements.txt` — `streamlit`, `pandas`, `plotly`
- `data/` — 4 sample days of CDTA Route 12 APC extracts (Jul 4–7, 2025)
