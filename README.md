# SLMArena

**A leaderboard and forecast of the most capable language models that run on one 32 GB GPU.**
Live site: https://grassyhilltop.github.io/SLMArena/

By Joel Sadler, University of Virginia, School of Data Science. The earlier name, tiny-LMArena, redirects here.

## What it shows

* **Top 3 and full leaderboard** of single-GPU models, ranked by their capability score on the
  [Epoch Capabilities Index](https://epoch.ai/eci) (ECI). Each row has the ECI interval, Rank (UB), parameters,
  4-bit weight size, the smallest GPU it fits, and a link to its Hugging Face model card. Filters for GPU memory,
  release date, region and active parameters; CSV download of the filtered table.
* **Fig. 1, the forecast chart**, building on Figure 4 of Anthropic's
  [“AI models may be capable of self-replicating without access to a datacenter”](https://www.anthropic.com/research/self-replicating-ai)
  (William Zhou and Daniel Freeman, 12 October 2026): a least-squares trend through the best-at-release models, a 90%
  prediction band, and where the trend meets one of three bars, each tied to a plain question:
  * **Can SLMs self-replicate?** Anthropic's self-replication floor (GLM-5.2's current ECI).
  * **When do SLMs match today's best model?** Time to today's state of the art (best ECI of any model today).
  * **How good is today's best SLM?** Frontier lag: which past frontier it matches, and which much larger open models
    it outscores.
* **Controls**: models from all labs, US, China or the rest of the world, and by active parameters (dense, mixture of
  experts, ≤ 4B active), each refitting the trend; switches for the state of the art and for estimates; From/To time
  controls (full history to the last six months); colour by region or lab; a wide-chart mode; beige, white or dark
  themes. Hover any point or date for details; download the chart data as CSV.
* **Findings**: the headline events (measured, on trend, projected), and what changed since Anthropic's post.
* **Contenders**: new single-GPU models Epoch has not scored yet, with estimates from their developers' benchmark
  claims (Fig. 5) where possible, anchored to a model with a known ECI in the same table and converted with Epoch's
  benchmark slope. Estimates are never used for ranks, fits, thresholds or alerts.
* **Frontier gap** (Figs. 2–3) and a **second opinion** from the Artificial Analysis Intelligence Index (Fig. 4).

## Definition of a single-GPU model (SLM)

Open weights, an ECI score, and 4-bit weights that fill at most 75% of a 32 GB GPU such as an RTX 5090: at an idealized
0.5 GB per billion parameters, **at most 48B total parameters** (mixture-of-experts models count all experts). Real
4-bit files run 5–20% larger, and on a 32 GB Mac the GPU gets about two-thirds of memory by default, so the practical
cap there is lower. The
same rule gives the GPU filter: max parameters = 1.5 × GPU memory in GB (8 GB → 12B, 16 GB → 24B, 24 GB → 36B).
The rule lives in `config/site.json`.

## How it updates

`.github/workflows/update.yml` runs every day at 11:17 UTC (and on demand from the Actions tab):

1. `scripts/aa_snapshot.py` refreshes the Artificial Analysis snapshot, only if the `AA_API_KEY` secret is set.
2. `scripts/update_data.py` downloads Epoch's `eci_scores.csv` and `benchmarked_models.csv`, takes parameter counts
   from Epoch (else Hugging Face safetensors metadata), classifies models, fits the trends, computes crossing dates and
   lags, and writes `data/leaderboard.json`, `data/slm_leaderboard.csv` and a daily top-10 log in `data/history.csv`.
3. `scripts/build_page.py` embeds the data in `index.html` (served by GitHub Pages from `main`).
4. `scripts/send_alerts.py` announces events: a new #1, a new top-3 entry, a newly scored model, or a threshold crossed.
   Each fires once (`data/alert_state.json` remembers what was announced). Announcing runs before the data commit, so a
   failed release leaves nothing committed and the next run retries.

Run locally with Python 3.9+ and no dependencies:

```bash
python3 scripts/update_data.py && python3 scripts/build_page.py
```

## Alerts

* **GitHub**: every alert is published as a release. Anyone can follow with *Watch → Custom → Releases*, or the feed
  at `/releases.atom`. Works now, no setup.
* **Email (Buttondown, list `tinylm`)**: the sign-up form posts to Buttondown. Alert emails are sent by whichever
  repository has the secret `BUTTONDOWN_API_KEY` (Settings → Secrets and variables → Actions); add it to one of the
  two mirrors only, or subscribers get each alert twice. Use **Actions → Daily update → Run workflow →
  Test alert** to check: it creates a pre-release here and a draft (not a send) in Buttondown.

## Curating models

* `config/models.csv` maps Epoch model names to display names and Hugging Face repos, and fills in sizes Epoch lacks.
  The daily log lists open models with unknown size; add them here.
* `config/watchlist.csv` lists notable single-GPU models without an ECI score yet. They drop off once Epoch scores them.
* `config/claims.csv` holds developer-reported scores for those models, each with its source and the reference models
  (known ECI) reported in the same table. Only ECI benchmarks are used (today Terminal-Bench 2.x and GPQA Diamond);
  the method and back-test are in `estimate_unscored()` in `scripts/update_data.py` and on the page.

## Credits

* Scores: Epoch AI, [Epoch Capabilities Index](https://epoch.ai/eci), [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
  Methodology: https://epoch.ai/data/eci-documentation
* Forecast framing and chart design: William Zhou and Daniel Freeman, Anthropic Frontier Red Team.
* Second-opinion index: [Artificial Analysis](https://artificialanalysis.ai) (attribution required; ask them before
  redistributing more than this small snapshot).
* Layout and the Rank (UB) convention: [LMArena](https://arena.ai/leaderboard).
* Model metadata and links: [Hugging Face](https://huggingface.co).

Not affiliated with Epoch AI, Anthropic, Artificial Analysis or LMArena.
