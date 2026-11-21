"""Streamlit entity search, dataset lineage view, and suggestion review queue."""

import streamlit as st
from neo4j import GraphDatabase

from docgraph.config import settings
from docgraph.feedback.service import review_lineage
from docgraph.feedback.store import FeedbackStore
from docgraph.lineage.queries import (
    dataset_lineage,
    list_datasets,
    list_suggestions,
    search_entities,
)

st.set_page_config(page_title="DocGraph review", page_icon="🕸️", layout="wide")
st.title("DocGraph")
st.caption("Explore entities and lineage, then review proposed links.")


@st.cache_resource
def get_driver():
    driver = GraphDatabase.driver(
        settings.neo4j_uri, auth=(settings.neo4j_user, settings.neo4j_password)
    )
    driver.verify_connectivity()
    return driver


try:
    driver = get_driver()
except Exception as exc:
    st.error(f"Could not connect to Neo4j: {exc}")
    st.stop()

tabs = st.tabs(["Entity search", "Dataset lineage", "Suggestion review"])

with tabs[0]:
    term = st.text_input("Search entity name or alias")
    if term:
        matches = search_entities(driver, settings.neo4j_database, term)
        if matches:
            st.dataframe(matches, use_container_width=True, hide_index=True)
        else:
            st.info("No matching entities.")

with tabs[1]:
    datasets = list_datasets(driver, settings.neo4j_database)
    if not datasets:
        st.info("No datasets are loaded yet. Run ingest, extract, resolve, and load first.")
    else:
        labels = {f"{item['name']} · {item['id'][:8]}": item["id"] for item in datasets}
        selected = st.selectbox("Dataset", list(labels))
        dataset_id = labels[selected]
        upstream_col, downstream_col = st.columns(2)
        with upstream_col:
            st.subheader("Upstream")
            paths = dataset_lineage(driver, settings.neo4j_database, dataset_id, "upstream")
            if paths:
                for index, path in enumerate(paths):
                    with st.expander(
                        " → ".join(step["name"] for step in path["steps"]), expanded=index == 0
                    ):
                        st.json(path)
            else:
                st.caption("No upstream path found.")
        with downstream_col:
            st.subheader("Downstream")
            paths = dataset_lineage(driver, settings.neo4j_database, dataset_id, "downstream")
            if paths:
                for index, path in enumerate(paths):
                    with st.expander(
                        " → ".join(step["name"] for step in path["steps"]), expanded=index == 0
                    ):
                        st.json(path)
            else:
                st.caption("No downstream path found.")

with tabs[2]:
    feedback = FeedbackStore(settings.feedback_database_path)
    queue = list_suggestions(driver, settings.neo4j_database, status="proposed", limit=100)
    if not queue:
        st.info("The review queue is empty.")
    for item in queue:
        title = f"{item['source_name']} → {item['target_name']} · score {item['score']:.2f}"
        with st.expander(title):
            st.write(item["rationale"])
            st.caption(
                f"Model {item['model_name']} · prompt {item['prompt_version']} · ID {item['id']}"
            )
            st.write("Evidence")
            for quote in item.get("evidence", []):
                st.markdown(f"> {quote}")
            accept_col, reject_col = st.columns(2)
            with accept_col:
                if st.button("Accept", key=f"accept-{item['id']}"):
                    review_lineage(
                        driver,
                        settings.neo4j_database,
                        feedback,
                        item["id"],
                        "accepted",
                        reviewer="streamlit-reviewer",
                    )
                    st.success("Suggestion accepted.")
                    st.rerun()
            with reject_col:
                if st.button("Reject", key=f"reject-{item['id']}"):
                    review_lineage(
                        driver,
                        settings.neo4j_database,
                        feedback,
                        item["id"],
                        "rejected",
                        reviewer="streamlit-reviewer",
                    )
                    st.success("Suggestion rejected.")
                    st.rerun()
