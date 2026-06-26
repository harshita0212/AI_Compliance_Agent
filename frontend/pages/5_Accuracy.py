"""
Accuracy - how often the system gets it right.

Runs a labelled test set (campaigns with known-correct verdicts) through the
live pipeline and reports accuracy, plus the two error types that matter for
compliance: unsafe misses (let risky content through) and over-blocks (flagged
clean content). This turns "it seems to work" into a measured number.
"""
from __future__ import annotations

import streamlit as st

import api_client as api

st.set_page_config(page_title="Accuracy", page_icon="target", layout="wide")
api.sign_in_widget()
st.title("Accuracy")
st.caption("Measured against a labelled test set of campaigns with known-correct verdicts")

if st.button("Run evaluation", type="primary"):
    st.session_state.pop("eval", None)

if "eval" not in st.session_state:
    with st.spinner("Running the test set through the live pipeline..."):
        try:
            st.session_state.eval = api.run_eval()
        except Exception as e:  # noqa: BLE001
            st.error(f"Could not run evaluation: {e}")
            st.stop()

r = st.session_state.eval

c1, c2, c3 = st.columns(3)
c1.metric("Accuracy", f"{r['accuracy']:.0%}", help=f"{r['correct']} of {r['total']} correct")
c2.metric("Unsafe misses", r["unsafe_misses"], help="Risky content wrongly APPROVED - the dangerous error")
c3.metric("Over-blocks", r["over_blocks"], help="Clean content wrongly FLAGGED/REJECTED")

if r["unsafe_misses"] == 0:
    st.success("No unsafe misses: nothing non-compliant was approved on the test set.")
else:
    st.error(f"{r['unsafe_misses']} unsafe miss(es): risky content was approved. Investigate before any real use.")

st.caption(f"Rule corpus {r['rule_corpus_version']}")
st.divider()

st.subheader("Per-case results")
rows = []
for c in r["results"]:
    outcome = "ok" if c["correct"] else ("UNSAFE MISS" if c["unsafe_miss"] else "over-block")
    rows.append({
        "case": c["id"],
        "category": c["category"],
        "expected": c["expected"],
        "actual": c["actual"],
        "result": outcome,
    })
st.dataframe(rows, use_container_width=True, hide_index=True)

st.subheader("Confusion matrix")
st.caption("Rows = correct answer, columns = what the system said. Off-diagonal cells are errors.")
labels = ["APPROVED", "FLAGGED", "REJECTED"]
matrix = []
for exp in labels:
    row = {"expected \\ actual": exp}
    for act in labels:
        row[act] = r["confusion"][exp][act]
    matrix.append(row)
st.dataframe(matrix, use_container_width=True, hide_index=True)
