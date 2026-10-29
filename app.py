"""Streamlit front end: run with `make app`."""

from pathlib import Path

import pandas as pd
import streamlit as st

from readiness.coverage import plan_table, summary
from readiness.stats import (
    cuped_factor,
    days_needed,
    mde_mean,
    mde_proportion,
    n_per_arm_mean,
    n_per_arm_proportion,
    n_sessions_interleaving,
    switchback_plan,
)

SAMPLE = Path(__file__).parent / "data" / "sample_cells.csv"


def verdict(days: float, green: float = 14, amber: float = 42) -> None:
    """One plain-English line under a result, coloured like the readiness table."""
    if days <= green:
        st.success(f"About {days:,.0f} days: affordable. A result within {green:.0f} days counts as green.")
    elif days <= amber:
        st.warning(f"About {days:,.0f} days: possible but slow (amber: up to {amber:.0f} days).")
    else:
        st.error(
            f"About {days:,.0f} days: too slow at these settings (red: over {amber:.0f} days). "
            "Options: a larger lift worth detecting, more traffic in the test, CUPED if you have a measured "
            "correlation, a more frequent metric, or a cheaper first check such as interleaving."
        )


st.set_page_config(page_title="Experiment readiness", layout="wide")
st.title("Experiment readiness calculator")
st.caption(
    "Before arguing about the design, check whether a test can reach a result: how many users, "
    "which design, and how many days. Synthetic sample data; bring your own CSV."
)

with st.sidebar:
    st.header("Test settings")
    st.caption("These apply to every tab. Hover the (?) next to each for what it means.")
    alpha = st.number_input(
        "Significance level (two-sided)", 0.001, 0.2, 0.05, 0.005, format="%.3f",
        help="How often you accept calling a win when nothing changed. 0.05 = 1 false alarm in 20 "
        "do-nothing tests. Lower is stricter and needs more users.",
    )
    power = st.number_input(
        "Power", 0.5, 0.99, 0.80, 0.05,
        help="If the lift below is real, how often the test should catch it. 0.80 = 8 times in 10. "
        "Higher needs more users.",
    )
    mde_pct = st.number_input(
        "Smallest lift worth detecting (% relative)", 1.0, 100.0, 10.0, 1.0,
        help="MDE (minimum detectable effect). The smallest improvement that would make you ship. "
        "Relative: 5.0% to 5.5% is a 10% lift. The biggest driver of cost: halving it needs about 4x the users. "
        "Ranking changes often deliver 1-3%, so 10% is optimistic.",
    )
    share = st.slider(
        "Share of traffic in the test", 0.05, 1.0, 1.0, 0.05,
        help="Fraction of eligible users you allow into the test. Days scale as 1 / share: 20% of traffic "
        "takes 5 times as long.",
    )
    rho = st.slider(
        "CUPED: correlation with pre-period metric", 0.0, 0.95, 0.0, 0.05,
        help="CUPED uses each unit's past behaviour to remove predictable noise. rho is how strongly the past "
        "predicts the test period (0 = not at all). Leave at 0 unless you have measured it on real data. "
        "Needs units with history (sellers, markets), not one-time buyers.",
    )
    mde = mde_pct / 100
    if mde_pct >= 8:
        st.info("A 10% lift is a big win for a ranking change. Try 3-5% to see a realistic planning number.")

tab_start, tab_ab, tab_rev, tab_sb, tab_il, tab_table, tab_method = st.tabs(
    ["Start here", "A/B test", "Revenue per user", "Switchback", "Interleaving", "Readiness table", "Method"]
)

with tab_start:
    st.subheader("What this answers")
    st.write(
        "Before a team argues about how to test a change, this checks whether a test can reach a trustworthy "
        "result at all: how many users it needs, which design fits, and how many days that takes."
    )
    st.markdown(
        """
**A suggested path**

1. **Set the rules in the sidebar.** The most important one is *smallest lift worth detecting*: the smallest
   improvement that would make you ship. Be honest here; everything else follows from it.
2. **A/B test tab.** For a yes/no metric (for example "buyer contacts a seller"): users per arm and days.
   Read the table below it to see what lift you could detect in 1-8 weeks.
3. **Revenue per user tab.** The same for an amount. It needs the metric's standard deviation (its noise).
4. **Switchback tab.** Use it when sellers can run out of capacity, so a normal split leaks between groups.
   It shows how much more traffic that costs.
5. **Interleaving tab.** A cheap preference check between two rankers, usually before any of the above.
6. **Readiness table.** Does steps 2 and 4 for a whole list of markets and colours each green, amber or red.
"""
    )
    st.subheader("Which design when?")
    st.table(
        pd.DataFrame(
            {
                "Situation": [
                    "Groups don't compete for the same limited supply",
                    "Sellers can run out of capacity (quota, budget, availability)",
                    "You just want to know if the new ranker is plausibly better",
                    "Very little traffic and constrained supply",
                ],
                "Use": [
                    "A/B test",
                    "Switchback (costs much more traffic)",
                    "Interleaving first (hours, not weeks)",
                    "Not testable online: offline evaluation, pooling similar markets",
                ],
            }
        )
    )
    with st.expander("Words used in this app"):
        st.markdown(
            """
- **Lift:** improvement as a share of today's value. 5.0% to 5.5% is a **10% lift** (0.5 percentage points).
- **MDE:** minimum detectable effect, the smallest lift the test is built to catch.
- **Significance level (alpha):** the false-alarm rate you accept.
- **Power:** the chance of catching a real effect of MDE size.
- **Baseline:** today's value of the metric before any change.
- **Noise vs signal:** signal is the gap you want to see (baseline x lift). Noise is how jumpy the metric is
  per user. More users average out the noise.
- **CUPED:** adjusts each unit by its own past behaviour to cut noise. Saves a share of users equal to rho squared.
- **Switchback:** randomise time windows (for example 4 hours) instead of users.
- **Window:** one time slice in a switchback. It is one randomised unit, not a test duration.
- **ICC:** how alike outcomes in the same window are (0 = independent, 1 = identical).
- **Design effect:** how many times less information a window's correlated searches carry than independent ones.
- **Burn-in:** the first part of each window discarded while the previous version's effect wears off.
- **Interleaving:** both rankers' results mixed in one list; clicks are credited to whoever supplied the result.
- **Tie:** an interleaved session with no click or equal clicks. Discarded.
"""
        )
    with st.expander("Honest limits"):
        st.markdown(
            """
- The sample markets are synthetic. Nothing here is real company data.
- ICC, burn-in, window length, interleaving win share and tie rate are **assumptions** until estimated from real logs.
- Interleaving measures click preference, not revenue. Use it as a gate, not a verdict.
- Fixed-horizon tests only: do not stop early because the result looks good.
- Green / amber / red thresholds are business choices, not statistics.
"""
        )

with tab_ab:
    st.write(
        "For a yes/no metric, such as the share of searches where a buyer contacts a seller. "
        "Answers: how many users does each group need, and how many days is that?"
    )
    c1, c2 = st.columns(2)
    baseline = c1.number_input(
        "Baseline conversion rate (%)", 0.01, 99.0, 5.0, 0.1,
        help="Today's yes/no rate, for example 5 means 5 in 100 users do the action. Pull it from the last 4-8 weeks.",
    ) / 100
    daily = c2.number_input(
        "Eligible users per day", 1, 10_000_000, 20_000, 500,
        help="Users who could enter the test each day, before the traffic-share setting.",
    )
    n = round(n_per_arm_proportion(baseline, mde, alpha, power) * cuped_factor(rho))
    d = days_needed(2 * n, daily, share)
    m1, m2, m3 = st.columns(3)
    m1.metric("Users per arm", f"{n:,}")
    m2.metric("Days to result", f"{d:,.1f}")
    m3.metric("Variance kept by CUPED", f"{cuped_factor(rho):.0%}")
    st.write(
        f"To see a **{mde_pct:.0f}% lift** (from {baseline:.1%} to {baseline * (1 + mde):.2%}) with "
        f"{power:.0%} power and a {alpha:.0%} false-alarm rate, each group needs **{n:,} users**. "
        f"With {daily:,} eligible users a day and {share:.0%} of them in the test, that takes **{d:,.1f} days**."
    )
    verdict(d)

    st.subheader("What if the lift is smaller than hoped?")
    st.caption("Same settings, different smallest lift. This is the table to show when someone asks for a quick test.")
    rows = []
    for m in [10, 5, 3, 2, 1]:
        nm = round(n_per_arm_proportion(baseline, m / 100, alpha, power) * cuped_factor(rho))
        rows.append({"smallest lift (%)": m, "users per arm": f"{nm:,}", "days": round(days_needed(2 * nm, daily, share), 1)})
    st.dataframe(pd.DataFrame(rows), hide_index=True)

    st.subheader("What can you detect in a fixed time?")
    weeks = [1, 2, 3, 4, 6, 8]
    rows = []
    for w in weeks:
        per_arm = daily * share * 7 * w / 2 / cuped_factor(rho)
        rows.append({"weeks": w, "smallest detectable lift (%)": round(100 * mde_proportion(baseline, int(per_arm), alpha, power), 1)})
    st.dataframe(pd.DataFrame(rows), hide_index=True)
    st.caption(
        "More weeks means more users, so averages bounce less and smaller differences stand out. "
        "Detectable lift shrinks with the square root of users: four times the time halves it."
    )
    with st.expander("How to read this tab"):
        st.markdown(
            """
- **Users per arm:** how many users each group (old and new) needs. Total users = twice this.
- **Days to result:** total users / (eligible users per day x traffic share).
- **Not enough traffic?** The test simply takes longer. Run whole weeks (weekday and weekend patterns balance),
  and remember novelty fades and seasons change. Or accept a larger smallest lift.
- **Rare outcomes are expensive.** At a 0.4% baseline, a 10% lift needs about 400,000 users per arm.
  A more frequent but still relevant metric (a click, a contact) is much cheaper.
"""
        )

with tab_rev:
    st.write(
        "For a metric that is an amount, not a yes/no (revenue per user, contacts per user). "
        "The noise is the metric's standard deviation (SD): how far a typical user sits from the average. "
        "Revenue is usually skewed (many users at zero, a few large), so the SD is often several times the mean."
    )
    c1, c2, c3 = st.columns(3)
    rev_mean = c1.number_input(
        "Average revenue per user today", 0.01, 1_000_000.0, 20.0, 1.0,
        help="The current average of the metric per user, over the same period you would run the test.",
    )
    rev_sd = c2.number_input(
        "Standard deviation of revenue per user", 0.01, 10_000_000.0, 80.0, 5.0,
        help="Compute it from recent history for the same users. Cap extreme values (for example at the "
        "99th percentile) first: it usually cuts the SD a lot.",
    )
    rev_daily = c3.number_input("Eligible users per day", 1, 10_000_000, 20_000, 500, key="rev_daily")
    n_rev = round(n_per_arm_mean(rev_sd, rev_mean * mde, alpha, power) * cuped_factor(rho))
    rev_days = days_needed(2 * n_rev, rev_daily, share)
    m1, m2, m3 = st.columns(3)
    m1.metric("Users per arm", f"{n_rev:,}")
    m2.metric("Days to result", f"{rev_days:,.1f}")
    m3.metric("Noise relative to mean (SD / mean)", f"{rev_sd / rev_mean:.1f}x")
    st.write(
        f"To see a **{mde_pct:.0f}% change** in average revenue per user (a difference of {rev_mean * mde:,.2f}), "
        f"each group needs **{n_rev:,} users**, which takes **{rev_days:,.1f} days**."
    )
    if rev_sd / rev_mean > 3:
        st.info(
            "The SD is more than 3 times the mean, typical of skewed revenue. Doubling the SD quadruples the users "
            "needed, so capping extreme values is usually worth doing before the test."
        )
    verdict(rev_days)
    rev_rows = []
    for w in [1, 2, 3, 4, 6, 8]:
        per_arm = rev_daily * share * 7 * w / 2 / cuped_factor(rho)
        rev_rows.append({"weeks": w, "smallest detectable lift (%)": round(100 * mde_mean(rev_sd, int(per_arm), alpha, power) / rev_mean, 1)})
    st.dataframe(pd.DataFrame(rev_rows), hide_index=True)
    st.caption(
        "Revenue is the slower, noisier metric. A common plan: a frequent proxy (a contact) as the primary metric, "
        "revenue as the confirmation and guardrail. Always check the proxy moves the money metric."
    )

with tab_sb:
    st.write(
        "Use a switchback when both arms compete for the same constrained supply (sellers fill up or "
        "are paced), so a user-level split leaks. Time windows are randomised within one market."
    )
    c1, c2, c3, c4 = st.columns(4)
    sb_base = c1.number_input("Baseline rate (%)", 0.01, 99.0, 5.0, 0.1, key="sb_base") / 100
    sb_daily = c2.number_input("Units per day in the market", 1, 10_000_000, 20_000, 500, key="sb_daily")
    window = c3.selectbox(
        "Window length (hours)", [1, 2, 3, 4, 6, 8, 12, 24], index=3,
        help="Each window is randomised to the old or new version as a whole. Shorter windows give more of them "
        "(cheaper) but carry-over from the previous window matters more.",
    )
    icc = c4.number_input(
        "Within-window correlation (ICC)", 0.0, 0.5, 0.01, 0.005, format="%.3f",
        help="How alike outcomes in the same window are. 0 = independent, higher = more alike. "
        "The most uncertain input here: estimate it from past data cut into windows of this length.",
    )
    burn = st.slider(
        "Burn-in discarded per window (carry-over)", 0.0, 0.75, 0.25, 0.05,
        help="Share of each window thrown away while the previous version's effect (used-up seller quotas, "
        "pacing, buyers mid-session) wears off. At least the typical session length.",
    )
    n_sb = round(n_per_arm_proportion(sb_base, mde, alpha, power) * cuped_factor(rho))
    plan = switchback_plan(n_sb, sb_daily * share, window, icc, burn)
    ab_days = days_needed(2 * n_sb, sb_daily, share)
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Design effect", f"{plan.design_effect:.1f}x")
    m2.metric("Windows needed", f"{plan.total_windows:,}")
    m3.metric("Days to result", f"{plan.days:,.1f}")
    m4.metric("Same traffic as A/B", f"{ab_days:,.1f} days")
    eff = plan.units_per_window / plan.design_effect
    st.write(
        f"Each {window}-hour window holds about **{plan.units_per_window:,.0f}** usable units after burn-in, but they "
        f"behave alike (design effect {plan.design_effect:.1f}x), so a window is worth only about **{eff:,.0f}** "
        f"independent units. You need **{plan.total_windows:,} windows**, so **{plan.days:,.1f} days**, "
        f"against {ab_days:,.1f} days for a plain A/B: about **{plan.days / max(ab_days, 1e-9):,.0f} times** as long."
    )
    if icc > 0:
        st.info(
            f"Ceiling: a window can never be worth more than 1 / ICC = {1 / icc:,.0f} independent units, however busy "
            "the market. More traffic barely helps; more windows (shorter windows or more days) is what helps."
        )
    verdict(plan.days)

    st.subheader("What window length does to the cost")
    st.caption("Same settings, different window length. Remember ICC and carry-over also change with window length.")
    wrows = []
    for w in [1, 2, 4, 8, 12, 24]:
        p = switchback_plan(n_sb, sb_daily * share, w, icc, burn)
        wrows.append({"window (hours)": w, "design effect": round(p.design_effect, 1), "windows": f"{p.total_windows:,}", "days": round(p.days, 1)})
    st.dataframe(pd.DataFrame(wrows), hide_index=True)
    with st.expander("How to set the ICC and burn-in from your own data"):
        st.markdown(
            """
**ICC.** Cut 4-8 weeks of history for one market into windows of the length you plan to use. For each window,
compute the number of units and the rate. Let V be the variance of the window rates and p the overall rate.
Chance alone would give p(1-p) / average units per window. Anything above that is real window-to-window difference:

`ICC = (V - p(1-p) / average n) / (p(1-p))`, and use 0 if it comes out negative.

**Burn-in.** At least the typical session length. Better, look at past switches or ranking changes and see how long
the metric takes to settle. Carry-over channels in a marketplace: seller quotas and pacing, notifications already sent.

**Impact.** At high traffic burn-in barely changes the days (each window is capped near 1/ICC anyway). In thin markets it
costs more, because discarded traffic is traffic you did not have to spare.
"""
        )

with tab_il:
    st.write(
        "Interleaving merges both rankers' results into one list and credits each click to the "
        "ranker that supplied it. It needs far fewer sessions, but it measures click preference, "
        "not revenue: use it as a cheap gate before a full A/B."
    )
    c1, c2, c3 = st.columns(3)
    win = c1.number_input(
        "New ranker's expected win share (%)", 50.5, 80.0, 55.0, 0.5,
        help="Of sessions with a decided preference, the share the new ranker wins. 50 = no preference. "
        "Closer to 50 is harder to tell from luck, so more sessions are needed. Use the dark-launch or offline "
        "result to set it, or test a range.",
    ) / 100
    ties = c2.slider(
        "Sessions with no click or a tie", 0.0, 0.95, 0.6, 0.05,
        help="These sessions carry no information and are discarded. 0.6 means only 40% of sessions count.",
    )
    il_daily = c3.number_input("Searches per day", 1, 10_000_000, 20_000, 500, key="il_daily")
    sessions = n_sessions_interleaving(win, alpha, power, ties)
    il_days = days_needed(sessions, il_daily, share)
    m1, m2 = st.columns(2)
    m1.metric("Sessions needed", f"{sessions:,}")
    m2.metric("Days to result", f"{il_days:,.1f}")
    st.write(
        f"If the new ranker really wins {win:.0%} of decided sessions, you need **{sessions:,} sessions** "
        f"(only {1 - ties:.0%} of sessions are decisive), about **{il_days:,.1f} days**. "
        "Under 'no difference' each ranker wins 50%, like a fair coin."
    )
    st.subheader("How the win share changes the cost")
    irows = []
    for w in [52, 55, 60, 70]:
        s = n_sessions_interleaving(w / 100, alpha, power, ties)
        irows.append({"true win share (%)": w, "sessions needed": f"{s:,}", "days": round(days_needed(s, il_daily, share), 2)})
    st.dataframe(pd.DataFrame(irows), hide_index=True)
    st.caption(
        "A coin that lands heads 70% of the time shows itself in a few dozen flips. One at 52% can look fair for "
        "thousands. Passing this gate says people prefer the new results, not that revenue improved."
    )

with tab_table:
    st.write(
        "One row per market cell. Required columns: `cell`, `daily_units`, `baseline_rate`; "
        "optional `supply_constrained` (true gives a switchback)."
    )
    up = st.file_uploader("Upload a CSV", type="csv")
    cells = pd.read_csv(up) if up is not None else pd.read_csv(SAMPLE)
    if up is None:
        st.caption("Showing the synthetic sample file.")
    c1, c2 = st.columns(2)
    green = c1.number_input(
        "Green if a result within (days)", 1, 365, 14,
        help="A business choice, not a statistic: how long you can easily wait.",
    )
    amber = c2.number_input("Amber if within (days)", 1, 365, 42, help="Slower but possible. Beyond this the cell is red.")
    with st.expander("Switchback assumptions used for constrained cells"):
        t1, t2, t3 = st.columns(3)
        t_win = t1.selectbox("Window length (hours)", [1, 2, 3, 4, 6, 8, 12, 24], index=3, key="t_win")
        t_icc = t2.number_input("ICC", 0.0, 0.5, 0.01, 0.005, format="%.3f", key="t_icc")
        t_burn = t3.slider("Burn-in", 0.0, 0.75, 0.25, 0.05, key="t_burn")
    try:
        table = plan_table(
            cells, mde, alpha, power, share, rho,
            window_hours=float(t_win), icc=float(t_icc), burn_in_share=float(t_burn),
            green_days=float(green), amber_days=float(max(amber, green)),
        )
        counts = summary(table)
        m1, m2, m3 = st.columns(3)
        m1.metric("Green", counts["green"])
        m2.metric("Amber", counts["amber"])
        m3.metric("Red", counts["red"])
        st.dataframe(table, hide_index=True)
        st.download_button("Download table", table.to_csv(index=False), "readiness_table.csv", "text/csv")
        n_sb_cells = int((table["design"] == "switchback").sum())
        st.write(
            f"{counts['green']} of {len(table)} cells can reach a result within {green} days, "
            f"{counts['amber']} within {amber}, and {counts['red']} would take longer. "
            f"{n_sb_cells} cell(s) are flagged supply-constrained and get a switchback."
        )
    except ValueError as err:
        st.error(str(err))
    with st.expander("How to read this table"):
        st.markdown(
            """
Each row goes through three layers:

1. **Design.** The `supply_constrained` column picks it: true means switchback, otherwise a plain A/B. You supply
   that flag; the app does not detect it. Interleaving is not in the table, it is a separate gate.
2. **Days.** That design's users or windows needed, divided by the cell's daily traffic.
3. **Colour.** Green, amber or red by the day limits above.

**Red means "this design does not fit here at these settings", not "do not test".** A busy constrained cell can be red
because the switchback is expensive, not because traffic is low. Options: shorter windows, a larger smallest lift,
interleaving as a gate, or accepting a plain A/B with a stated interference risk.

**How to set `supply_constrained`.** Look at recent weeks of the sellers shown in that market: how often do they hit
capacity (quota used up, budget, pacing) within a typical test period? If a meaningful share do, a normal split leaks,
so flag it. Thin cells with constrained supply are usually not testable online at all.
"""
        )

with tab_method:
    st.markdown(
        """
**A/B on a conversion rate.** Two-sided z-test for two proportions, pooled variance under the
null (Fleiss, no continuity correction). Checked against textbook values and by simulation.

`users per arm = (z_alpha * sqrt(2 * pbar * (1 - pbar)) + z_power * sqrt(p1(1-p1) + p2(1-p2)))^2 / (p2 - p1)^2`

*Signal* is `p2 - p1` (baseline x lift). *Noise* is the `p(1-p)` terms. `z_alpha` (1.96 at 0.05) and `z_power`
(0.84 at 0.80) are the safety margin from your significance and power settings. Worked example: 5% to 5.5% gives
about 31,234 per arm.

**Revenue per user.** Two-sample z-test for a difference in means: users per arm =
`2 * (z_alpha + z_power)^2 * SD^2 / difference^2`. Same logic as the conversion rate, with the SD
as the noise.

**CUPED.** Adjusting each unit by its pre-experiment value cuts variance by `1 - rho^2`, so the
sample needed shrinks by the same factor. At rho 0.5, 25% fewer users; at 0.7, about half.

**Switchback.** Each time window is one randomised unit. Units in a window are correlated, so a
window of `m` units is worth `m / (1 + (m - 1) * ICC)` independent units. A burn-in share of
each window is discarded so the previous arm's effect can wash out. A window is never worth more than 1 / ICC.

**Interleaving.** A one-sample test that the new ranker wins more than half of the sessions
with a decided preference; undecided sessions are discarded.

**Days.** `total users / (eligible users per day x traffic share)`.

**Limits.** Normal approximations (fine for large samples); no sequential testing; ICC and
pre-period correlation must come from your own historical data.
"""
    )
