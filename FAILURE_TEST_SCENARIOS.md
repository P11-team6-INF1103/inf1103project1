# Failed-API test scenarios

Run from the `secret/` folder with the venv active. Always back up `.env` first (`cp .env .env.bak`) and restore after.
Use this incident for every scenario (menu option 1):

- What happened: `Worker slipped on a wet floor near the stairwell`
- Location: `Site A`   Role: `supervisor`   Injury: `no`

"Wet" makes it weather-relevant, so the weather call runs too.

| # | How to trigger | Expected on-screen result (under "NOTE: SOME AI STEPS DID NOT WORK") |
|---|---|---|
| 1 | **No Gemini key**: set `GEMINI_API_KEY=` (empty) in `.env`, keep Groq key | Hazard details, causes/prevention and "NOT ASSESSED"/manual review messages. Key hint line appears. |
| 2 | **No Groq key**: set `GROQ_API_KEY=` (empty), keep Gemini key | Only "couldn't look up similar incidents... online". Rest of report normal. |
| 3 | **Both keys empty** | First line: "AI services are currently unavailable..." plus all per-step lines and key hint. Record still saved. |
| 4 | **Invalid key**: set `GEMINI_API_KEY=wrong` | Same friendly lines as #1 (after a short wait). No HTTP code / model name shown. |
| 5 | **No internet**: turn Wi-Fi off, then run | Weather line ("Current weather could not be retrieved") plus the AI lines. No traceback. |
| 6 | **Weather only**: block just the weather host: `sudo sh -c 'echo "127.0.0.1 api.open-meteo.com" >> /etc/hosts'` (remove the line afterwards) | Only the weather line appears. |
| 7 | **Own-site search fails**: save 2+ incidents at a non-weather location first (e.g. "Forklift hit a pallet"), remove Gemini key, log another | "couldn't compare this with earlier incidents on our own sites". |
| 8 | **Batch mode**: `python main.py --batch tests/sample_batch.json` with keys empty | Every report shows the banner; run ends with the summary, exit code 0, no traceback. |
| 9 | **Cached reply masks the failure**: after a successful run, delete `data/ai_cache.json` before retrying | Without deleting it, repeat inputs reuse cached answers and show no error. |

Checks for every scenario:
1. No Python traceback.
2. No raw text such as `503`, `429`, `UNAVAILABLE`, `last error`, model names.
3. The incident still appears in the summary (menu option 2) and in `data/incidents.json`.
4. Technical detail IS in `data/app.log`.

Automated checks: `python -m unittest discover -s tests -t . -p "test_*.py"` (new file: `tests/test_failure_messages.py`).
