# PRD: experiment readiness calculator
*Last updated: 2026-10-26*

## Problem
Teams choose a test design (A/B, switchback, interleaving) before knowing whether their traffic
can reach a result. In marketplaces the interference-proof design (switchback) can cost
many times more traffic, so the choice should be made per market with the numbers in view.

## Users
A data scientist or product manager planning a test; an interviewer reviewing the portfolio.

## Success criteria
1. Sample sizes match textbook values and simulated power (within 3 points of target).
2. A CSV of markets becomes a red / amber / green table in one step.
3. Runs offline from a clean clone: `make setup && make test && make app`.

## Scope
In: A/B on proportions, CUPED, switchback with design effect and burn-in, interleaving, readiness
table, Streamlit app, offline tests, CI.
Out: sequential testing, Bayesian readout, estimating ICC from logs (next steps), any real
company data.

## Constraints
Synthetic data only; no employer data, names or numbers. Standard library plus numpy and pandas
for the maths so it's easy to audit.

## Assumptions and caveats
All switchback inputs (ICC, burn-in, window length) and the interleaving inputs (win share, tie rate) are placeholders, not measurements. The smallest lift worth detecting dominates every result: halving it roughly quadruples the sample. Thresholds for green and amber are business choices. Full list and a sensitivity table are in the README.

## Open questions
Whether to add a continuous-metric tab (the function exists) and a sequential-testing mode.
