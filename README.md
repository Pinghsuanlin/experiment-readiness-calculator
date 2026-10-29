# Experiment readiness calculator

**[Try the live app →](https://pinghsuanli-experiment-readiness-calculator.streamlit.app/)**
*(Free hosting: if it has been idle, it takes about 30 seconds to wake up.)*

[![tests](https://github.com/Pinghsuanlin/experiment-readiness-calculator/actions/workflows/ci.yml/badge.svg)](https://github.com/Pinghsuanlin/experiment-readiness-calculator/actions)

<img width="1661" height="1192" alt="image" src="https://github.com/user-attachments/assets/25a55114-8103-471d-8386-bade1faecd93" />

Before a team argues about how to test a change, it should know whether a test can reach a
result at all: how many users it needs, which design fits, and how many days it will take in
each market. This app answers that for A/B tests, switchbacks and interleaving, and turns a list
of markets into a red / amber / green readiness table.

It is a public, generic rebuild of a readiness framework I specified for a ranking test at a
services marketplace. The sample data is synthetic.


## Why

In a marketplace, a plain user-level A/B test can leak: both arms compete for the same sellers,
so a seller who fills up because of the new ranker is also missing from the control group. The
standard fix, a switchback (randomising time windows within one market), costs far more
traffic. Teams often pick a design first and discover later that it needs months. The useful
question comes first: **for each market, which design is needed, and is it affordable?**

## What it does

| Tab | Question it answers |
|---|---|
| A/B test | Users per arm and days to a result for a conversion rate; smallest lift detectable in 1-8 weeks |
| Revenue per user | The same for an amount (revenue or contacts per user), using its mean and standard deviation |
| Switchback | Windows and days needed, with the design effect from correlated searches and a burn-in for carry-over |
| Interleaving | Sessions needed for a cheap preference test between two rankers, before a full A/B |
| Readiness table | For every market cell in a CSV: the design (A/B or switchback), users per arm, days, and a red / amber / green status |

The app explains itself: a "Start here" tab with a suggested path and a glossary, hover help on every input, a plain-English reading of each result, and "what if" tables (smaller lifts, window lengths, win shares).

All tabs share the settings for significance, power, smallest lift worth detecting, traffic
share and CUPED (variance reduction from a pre-period metric).

## Method

* **A/B on a proportion:** two-sided z-test for two proportions, pooled variance under the
  null, no continuity correction (the Fleiss formula).
* **Revenue per user:** two-sample z-test for a difference in means; the standard deviation is the noise,
  so users per arm = `2 * (z_alpha + z_power)^2 * SD^2 / difference^2`.
* **CUPED:** subtracting a multiple of each unit's pre-experiment metric cuts variance by
  `1 - rho^2`, so the sample needed shrinks by the same factor.
* **Switchback:** each window is one randomised unit. Units inside a window share the same
  market state, so a window of `m` units is worth `m / (1 + (m - 1) * ICC)` independent ones
  (the design effect). A share of each window is discarded as burn-in.
* **Interleaving:** a one-sample test that the new ranker wins more than half of the sessions
  with a decided preference; ties and no-click sessions are discarded.
* **Design choice in the table:** cells flagged `supply_constrained` get a switchback, the rest
  a within-cell A/B.

## Results on the synthetic sample

12 market cells, 10% relative lift, 5% significance, 80% power, all traffic in the test:

| Status | Cells | Meaning |
|---|---:|---|
| Green | 2 | result within 2 weeks |
| Amber | 3 | 2-6 weeks |
| Red | 7 | more than 6 weeks |

The busiest cell shows the cost of interference-proof designs: an A/B would finish in about
**1.6 days**, a 4-hour switchback with a within-window correlation of 0.01 needs about **111
days**, because each window of about 7,000 searches is worth only about 100 independent ones.
That trade-off is the decision the table is meant to make visible.

## Validation

* Sample sizes match textbook values (10% to 12%: 3,841 per arm; 5% baseline, 10% relative
  lift: 31,234 per arm; a 0.1 SD shift in a mean: 1,570 per arm).
* Simulated tests at the computed sample size reject the null about 80% of the time, and
  about 5% of the time when there is no effect.
* Simulated CUPED cuts variance by `1 - rho^2` within 0.02.
* 28 offline tests (`make test`); no network or data download needed.

## How to run

```bash
make setup      # uv sync with dev dependencies
make test       # offline tests
make app        # Streamlit app at http://localhost:8501
```

Without uv: `pip install -e ".[dev]"`, then `pytest` and `streamlit run app.py`.

Windows: `make` is not installed by default. Use WSL or Git Bash, or run the commands directly:
`uv sync --extra dev`, `uv run --extra dev pytest`, `uv run streamlit run app.py`.

Bring your own data as a CSV with `cell`, `daily_units`, `baseline_rate` and optionally
`supply_constrained` (true / false).

## How sensitive is the answer to the assumptions?

Baseline 5%, 20,000 eligible users a day, 5% significance, 80% power. Illustrative numbers.

| Smallest lift worth detecting (relative) | Users per arm | Days at 100% of traffic | Days at 20% of traffic |
|---:|---:|---:|---:|
| 10% | 31,234 | 3.1 | 15.6 |
| 5% | 122,124 | 12.2 | 61.1 |
| 2% | 752,703 | 75.3 | 376 |

Switchback at the same settings (10% lift, burn-in 25%, ICC 0.01): window length changes the cost a lot.

| Window | Design effect | Days |
|---:|---:|---:|
| 1 hour | 7.2x | 30 |
| 4 hours | 26.0x | 108 |
| 8 hours | 51.0x | 213 |

Changing the within-window correlation (ICC) at 4-hour windows: 0.001 gives about 15 days, 0.01 gives 108, 0.05 gives 525. The ICC is the most uncertain input, so estimate it from history before trusting a switchback number.

## How to set `supply_constrained`

A plain user-level A/B leaks when both groups compete for sellers who can run out: a seller who fills up
because of the new ranking is also missing from the control group. Flag a market as constrained when,
in recent history, a meaningful share of the sellers shown there hit their capacity (quota, budget or
availability) or are throttled by pacing within a typical test period. A simple 2x2:

| | Capacity rarely runs out | Capacity often runs out |
|---|---|---|
| **High traffic** | A/B within the market | Switchback |
| **Low traffic** | A/B, pooled with similar markets or run longer | Not testable live: offline evaluation, pooling |

The threshold is a judgement call; check how sensitive the table is to it.

## Caveats

* The sample markets are synthetic. No employer data, names or numbers are used.
* The smallest lift worth detecting is the most influential input. Ranking changes often move conversion 1-3%, so the 10% default is optimistic; set it to the lift the business would actually act on.
* ICC, burn-in share, window length, interleaving win share and tie rate are assumptions. They are placeholders until estimated from real event logs.
* CUPED correlation is 0 by default; use a value only if measured on a real pre-period metric.
* Interleaving measures click preference, not revenue. Use it as a cheap gate before an A/B, not instead of one.
* Red / amber / green thresholds (14 and 42 days) are business choices, not statistics.
* Fixed-horizon tests only. Looking at results early and stopping inflates false positives.
* Each cell is treated as an independent test; running tests in overlapping markets at once is not modelled.

## Limitations and next steps

* Normal approximations: fine at these sample sizes, not for tiny cells.
* Fixed-horizon tests only; no sequential or Bayesian stopping yet.
* The ICC and the pre-period correlation are inputs: estimate them from your own history.
  Next step: estimate both from an uploaded event log.
* Switchback carry-over is handled with a flat burn-in, not modelled.

## License

MIT, see [LICENSE](LICENSE).
