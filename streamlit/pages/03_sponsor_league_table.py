import streamlit as st

from db import sponsor_league_table

st.set_page_config(page_title="Sponsor League Table | PharmaPulse", page_icon="💊", layout="wide")

st.title("Sponsor League Table")
st.caption("Business question: which sponsors run the most trials, and how successful are they?")

df = sponsor_league_table()

classes = sorted(df["sponsor_class"].dropna().unique().tolist())
selected = st.multiselect("Filter by sponsor_class", classes, default=classes)

filtered = df[df["sponsor_class"].isin(selected)] if selected else df
filtered = filtered.sort_values("trials_total", ascending=False).reset_index(drop=True)

st.caption(f"{len(filtered):,} sponsors shown (of {len(df):,} total). Top 10 by trials_total marked with 🏆.")

# NOTE: a pandas Styler-based row highlight (background-color per row) hits
# Streamlit's Styler cell-render ceiling (262,144 cells) at this table's real
# size (51K+ sponsors x 6 cols = 300K+ cells) -- found by testing, not by
# inspection. A plain indicator column scales fine at any row count and
# avoids the Styler path entirely.
display_df = filtered.copy()
display_df.insert(0, "rank", range(1, len(display_df) + 1))
display_df.insert(1, "top_10", ["🏆" if r <= 10 else "" for r in display_df["rank"]])

st.dataframe(
    display_df,
    width='stretch',
    hide_index=True,
    column_config={
        "rank": st.column_config.NumberColumn("Rank"),
        "top_10": st.column_config.TextColumn("Top 10"),
        "sponsor_name": st.column_config.TextColumn("Sponsor"),
        "sponsor_class": st.column_config.TextColumn("Class"),
        "trials_total": st.column_config.NumberColumn("Trials (total)"),
        "trials_completed": st.column_config.NumberColumn("Trials (completed)"),
        "success_rate": st.column_config.NumberColumn("Success rate", format="percent"),
    },
    height=650,
)

st.markdown("---")
st.caption(
    "**Data notes:** trials_total/trials_completed/success_rate come directly "
    "from `dim_sponsor` (M3) -- success_rate is trials_completed / trials_total "
    "and does not account for trials still in progress (a young sponsor with "
    "several currently-recruiting trials will show a lower success_rate than a "
    "sponsor whose trials have all reached a terminal status, even if none have "
    "actually failed)."
)
