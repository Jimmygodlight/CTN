import json
import re
from collections import Counter
from pathlib import Path

import pandas as pd
import streamlit as st

# The dashboard only reads saved JSON. It won't use CTN API requests.
project = Path(__file__).resolve().parent
data_file = project / "data" / "trending.json"
history_folder = project / "data" / "history"

# Quite basic keyword groups for now. We can improve this later.
topic_words = {
    "Health / hospitals": ["hospital", "nurse", "doctor", "health", "medical", "sick", "capacity"],
    "Mandates / freedom": ["mandate", "requirement", "freedom", "rights", "control", "compulsory", "forced"],
    "Evidence / risk": ["evidence", "proof", "risk", "research", "data", "science"],
    "Safeguards": ["sunset", "exemption", "appeal", "review", "safeguard", "end date", "time-bound"],
    "Privacy": ["privacy", "passport", "identity", "biometric", "surveillance", "digital id"],
    "Economy / jobs": ["economy", "business", "tourism", "jobs", "work", "employment"],
}


def get_topics(text):
    text = str(text).lower()
    found = []
    for name, words in topic_words.items():
        for word in words:
            # Match whole words so e.g. 'work' doesn't match 'network'
            if re.search(r"(?<!\w)" + re.escape(word) + r"(?!\w)", text):
                found.append(name)
                break
    return found if found else ["Other"]


def open_snapshot(path):
    with open(path, encoding="utf-8") as f:
        content = json.load(f)
    if isinstance(content, list):
        return content, "Unknown"
    if not isinstance(content, dict) or not isinstance(content.get("posts"), list):
        raise ValueError("JSON doesn't contain a list of posts")
    return content["posts"], content.get("timestamp", content.get("collected_at", "Unknown"))


st.set_page_config(page_title="CTN Post Dashboard", layout="wide")
st.title("CTN 2026 - Narrative Dashboard")
st.caption("Made with locally saved CTN posts. Opening this page makes no API requests.")

if not data_file.exists():
    st.error("No posts saved yet. Run main.py first.")
    st.stop()

try:
    posts, saved_at = open_snapshot(data_file)
except (OSError, ValueError, json.JSONDecodeError) as e:
    st.error(f"Couldn't load trending.json: {e}")
    st.stop()

if not posts:
    st.warning("The saved file is empty.")
    st.stop()

# Put the posts in a table
rows = []
for i, post in enumerate(posts):
    if not isinstance(post, dict):
        continue
    body = str(post.get("body") or "")
    links = re.findall(r"https?://[^\s]+", body)
    rows.append({
        "Rank": i + 1,
        "Post ID": str(post.get("post_id", "")),
        "Author": str(post.get("author_id", "")),
        "Text": body,
        "Topics": ", ".join(get_topics(body)),
        "Link": links[0] if links else ""
    })

if not rows:
    st.warning("No valid post objects in the saved file.")
    st.stop()

df = pd.DataFrame(rows)
counts = Counter()
for row in rows:
    counts.update(get_topics(row["Text"]))

st.write("Last saved:", saved_at)
a, b, c = st.columns(3)
a.metric("Posts", len(df))
b.metric("Authors", df["Author"].nunique())
c.metric("Topic groups", len(counts))

st.subheader("What people are discussing")
chart_data = pd.DataFrame([{"Topic": k, "Posts": v} for k, v in counts.most_common()])

# Keep a simple summary visible even if Streamlit's charts have issues.
for topic, amount in counts.most_common():
    st.write(f"**{topic}:** {amount} posts")
    st.progress(min(amount / len(df), 1.0))

# The chart is optional until we've confirmed it works on this computer.
if st.checkbox("Show topic bar chart"):
    st.bar_chart(chart_data.set_index("Topic"))

st.subheader("Browse posts")
search = st.text_input("Find a word, author or post ID")
choose_topics = st.multiselect("Filter topics", sorted(counts))

shown = df.copy()
if search.strip():
    # Simple substring search, not anything fancy
    value = search.strip()
    check = (
        shown["Text"].str.contains(value, case=False, regex=False)
        | shown["Post ID"].str.contains(value, case=False, regex=False)
        | shown["Author"].str.contains(value, case=False, regex=False)
    )
    shown = shown[check]

if choose_topics:
    shown = shown[shown["Text"].apply(lambda text: any(t in get_topics(text) for t in choose_topics))]

st.write(f"Showing {len(shown)} out of {len(df)} posts")
st.dataframe(shown, hide_index=True)
st.download_button("Download CSV", shown.to_csv(index=False), "ctn_posts.csv", "text/csv")

# This part is a bit separate from the table above but easier to update for now.
st.subheader("Topic history")
history = []
if history_folder.exists():
    for file in sorted(history_folder.glob("*.json")):
        try:
            older_posts, collected = open_snapshot(file)
            date = pd.to_datetime(collected, utc=True, errors="coerce")
            if pd.isna(date):
                continue
            topic_counts = Counter()
            for post in older_posts:
                if isinstance(post, dict):
                    topic_counts.update(get_topics(post.get("body", "")))
            history.append({"Date": date, **topic_counts})
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            continue

if len(history) < 2:
    st.info("Take a couple of snapshots with main.py at different times to see the chart.")
else:
    history_df = pd.DataFrame(history).fillna(0).sort_values("Date")
    history_df = history_df.set_index("Date")
    st.write("Here is what was collected in each snapshot:")
    st.dataframe(history_df)
    if st.checkbox("Show history line chart"):
        st.line_chart(history_df)
    st.caption("This is topic frequency in the sampled trending feed, not referendum votes or persuasion scores.")

with st.expander("A few things to keep in mind"):
    st.write("Keywords aren't perfect. One post might show up under multiple topics.")
    st.write("Trending posts aren't a representative sample of all citizens.")
    st.write("These charts don't tell us our official competition score.")
