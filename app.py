
import streamlit as st
import pandas as pd
import plotly.express as px
from pathlib import Path

st.set_page_config(
    page_title="Indian Fact-Check Explorer",
    page_icon="🔎",
    layout="wide"
)

DATA_PATH = Path(__file__).parent / "fact_check_cleaned.csv"

@st.cache_data
def load_data():
    df = pd.read_csv(DATA_PATH)
    df.columns = df.columns.str.strip()

    if "fake_news_date" in df.columns:
        df["fake_news_date"] = pd.to_datetime(
            df["fake_news_date"], errors="coerce"
        )

    for col in [
        "fact_checking_website",
        "fake_news_title",
        "Content",
        "Label"
    ]:
        if col in df.columns:
            df[col] = df[col].fillna("").astype(str)

    return df

st.title("🔎 Indian Fact-Check Explorer")
st.markdown(
    "An interactive research dashboard exploring fact-checking "
    "articles, publication trends, topic labels, and social media references."
)

if not DATA_PATH.exists():
    st.error("Dataset not found. Place fact_check_cleaned.csv beside app.py.")
    st.stop()

df = load_data()

total = len(df)
sources = (
    df["fact_checking_website"].nunique()
    if "fact_checking_website" in df.columns else 0
)
dated = (
    df["fake_news_date"].notna().sum()
    if "fake_news_date" in df.columns else 0
)
labelled = (
    (df["Label"].str.strip() != "").sum()
    if "Label" in df.columns else 0
)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Total Articles", f"{total:,}")
c2.metric("Fact-Checking Sources", sources)
c3.metric("Articles with Dates", f"{dated:,}")
c4.metric("Articles with Topic Labels", f"{labelled:,}")

st.divider()
st.subheader("Filter Articles")

filtered = df.copy()

if "fact_checking_website" in filtered.columns:
    all_sources = sorted(
        x for x in filtered["fact_checking_website"].unique() if x.strip()
    )
    selected_sources = st.multiselect(
        "Fact-checking source",
        all_sources,
        default=all_sources
    )
    filtered = filtered[
        filtered["fact_checking_website"].isin(selected_sources)
    ]

if "Label" in filtered.columns:
    all_labels = sorted(
        x for x in filtered["Label"].unique() if x.strip()
    )
    label_options = ["Unlabelled"] + all_labels
    selected_labels = st.multiselect(
        "Topic",
        label_options,
        default=label_options
    )

    include_unlabelled = "Unlabelled" in selected_labels
    selected_topics = [
        label for label in selected_labels if label != "Unlabelled"
    ]

    topic_mask = filtered["Label"].isin(selected_topics)
    if include_unlabelled:
        topic_mask |= filtered["Label"].str.strip().eq("")

    filtered = filtered[topic_mask]

if "fake_news_date" in filtered.columns:
    valid_dates = filtered["fake_news_date"].dropna()

    if not valid_dates.empty:
        date_range = st.date_input(
            "Date range",
            value=(valid_dates.min().date(), valid_dates.max().date())
        )

        if isinstance(date_range, (tuple, list)) and len(date_range) == 2:
            start_date, end_date = date_range
            date_mask = (
                filtered["fake_news_date"].isna()
                | (
                    filtered["fake_news_date"].dt.date.ge(start_date)
                    & filtered["fake_news_date"].dt.date.le(end_date)
                )
            )
            filtered = filtered[date_mask]

query = st.text_input(
    "Search titles and article content",
    placeholder="Enter a keyword..."
)

if query:
    search_cols = [
        col for col in ["fake_news_title", "Content"]
        if col in filtered.columns
    ]

    if search_cols:
        search_mask = pd.Series(False, index=filtered.index)
        for col in search_cols:
            search_mask |= filtered[col].str.contains(
                query, case=False, na=False, regex=False
            )
        filtered = filtered[search_mask]

st.caption(f"Displaying {len(filtered):,} of {total:,} articles")

st.divider()
st.subheader("Publication and Topic Insights")

left, right = st.columns(2)

with left:
    if "fact_checking_website" in filtered.columns:
        outlet_counts = (
            filtered["fact_checking_website"]
            .replace("", "Unknown")
            .value_counts()
            .rename_axis("Source")
            .reset_index(name="Articles")
        )

        st.plotly_chart(
            px.bar(
                outlet_counts,
                x="Source",
                y="Articles",
                title="Articles by Fact-Checking Source"
            ),
            use_container_width=True
        )

with right:
    if "Label" in filtered.columns:
        topic_counts = (
            filtered["Label"]
            .replace("", "Unlabelled")
            .value_counts()
            .head(15)
            .rename_axis("Topic")
            .reset_index(name="Articles")
        )

        st.plotly_chart(
            px.bar(
                topic_counts,
                x="Articles",
                y="Topic",
                orientation="h",
                title="Most Common Topic Labels"
            ),
            use_container_width=True
        )

if "fake_news_date" in filtered.columns:
    dated_df = filtered.dropna(subset=["fake_news_date"]).copy()

    if not dated_df.empty:
        dated_df["Year"] = dated_df["fake_news_date"].dt.year
        yearly = (
            dated_df.groupby("Year")
            .size()
            .reset_index(name="Articles")
        )

        st.plotly_chart(
            px.line(
                yearly,
                x="Year",
                y="Articles",
                markers=True,
                title="Fact-Check Articles Over Time"
            ),
            use_container_width=True
        )

st.divider()
st.subheader("Explore Individual Articles")

table_columns = [
    col for col in [
        "fake_news_date",
        "fact_checking_website",
        "fake_news_title",
        "Label",
        "fake_news_url"
    ]
    if col in filtered.columns
]

if table_columns:
    st.dataframe(
        filtered[table_columns],
        use_container_width=True,
        hide_index=True,
        column_config={
            "fake_news_url": st.column_config.LinkColumn(
                "Original Fact-Check Article"
            )
        }
    )

if not filtered.empty and "fake_news_title" in filtered.columns:
    st.subheader("Article Details")

    article_indices = list(filtered.index)

    def article_name(index):
        title = filtered.at[index, "fake_news_title"]
        return title.strip()[:120] if title.strip() else "Untitled article"

    selected_index = st.selectbox(
        "Select an article to inspect",
        article_indices,
        format_func=article_name
    )

    article = filtered.loc[selected_index]

    content = str(article.get("Content", "")).strip()
    st.write(content if content else "Article content is unavailable.")

    article_url = str(article.get("fake_news_url", "")).strip()
    if article_url and article_url.lower() != "nan":
        st.markdown(f"[Open original fact-check article]({article_url})")

    social_columns = [
        "twitter_tweets",
        "facebook_post",
        "youtube_link",
        "instagram_post"
    ]

    for col in social_columns:
        value = str(article.get(col, "")).strip()
        if value and value.lower() != "nan":
            st.write(f"**{col.replace('_', ' ').title()}:** {value}")

st.divider()

st.download_button(
    "Download Filtered Articles (CSV)",
    data=filtered.to_csv(index=False).encode("utf-8"),
    file_name="filtered_fact_check_articles.csv",
    mime="text/csv"
)

st.caption(
    "Research tool only. Topic labels are not true/false verdicts. "
    "The dataset contains collected fact-check articles and does not "
    "represent every claim circulating online."
)

