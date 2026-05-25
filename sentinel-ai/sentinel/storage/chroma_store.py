"""
SENTINEL-AI ChromaDB vector store.

Provides semantic search over past incidents and analyst feedback
so that agents can leverage few-shot examples from similar historical
cases.  Backed by a ChromaDB ``PersistentClient`` stored at
``config.SENTINEL_CHROMA_PATH``.

Usage::

    from sentinel.storage import chroma_store
    results = chroma_store.search_similar_incidents("brute force SSH login", n=3)

Seed the database from the command line::

    python -m sentinel.storage.chroma_store --seed
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

import chromadb
from chromadb.api.models.Collection import Collection

from sentinel import config

# ── Singleton client ─────────────────────────────────────────────────────────

_client: Optional[chromadb.ClientAPI] = None


def get_client() -> chromadb.ClientAPI:
    """Return (and lazily create) the singleton ChromaDB PersistentClient."""
    global _client
    if _client is None:
        path = config.SENTINEL_CHROMA_PATH
        Path(path).mkdir(parents=True, exist_ok=True)
        _client = chromadb.PersistentClient(path=path)
    return _client


def get_collection(name: str) -> Collection:
    """
    Return an existing collection or create a new one.

    Parameters
    ----------
    name:
        Collection name (e.g. ``"past_incidents"``, ``"analyst_feedback"``).
    """
    client = get_client()
    return client.get_or_create_collection(name=name)


# ── Seeding from file ────────────────────────────────────────────────────────


def seed_from_file(path: Optional[str] = None) -> int:
    """
    Load seed incidents from a JSON file and upsert them into the
    ``past_incidents`` collection.

    Parameters
    ----------
    path:
        Path to the JSON file.  Defaults to ``config.SEED_INCIDENTS_PATH``.

    Returns
    -------
    int
        Number of incidents upserted.

    The JSON file should contain a list of objects, each with at least:
    - ``id`` (str): unique incident identifier
    - ``summary`` (str): human-readable summary used as the document text
    - ``metadata`` (dict, optional): additional metadata fields
    """
    if path is None:
        path = str(config.SEED_INCIDENTS_PATH)

    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"Seed file not found: {file_path}")

    with open(file_path, "r", encoding="utf-8") as fh:
        data: List[Dict[str, Any]] = json.load(fh)

    if not data:
        return 0

    collection = get_collection("past_incidents")

    ids: List[str] = []
    documents: List[str] = []
    metadatas: List[Dict[str, Any]] = []

    for item in data:
        inc_id = item.get("id", str(uuid.uuid4()))
        summary = item.get("summary", "")
        meta = item.get("metadata", {})

        # ChromaDB metadata values must be str, int, float, or bool
        safe_meta: Dict[str, Any] = {}
        for k, v in meta.items():
            if isinstance(v, (str, int, float, bool)):
                safe_meta[k] = v
            else:
                safe_meta[k] = json.dumps(v)

        # Always include severity and conclusion in metadata if present at top level
        for field in ("severity", "conclusion", "confidence", "mitre_techniques"):
            if field in item and field not in safe_meta:
                val = item[field]
                if isinstance(val, (list, dict)):
                    safe_meta[field] = json.dumps(val)
                else:
                    safe_meta[field] = val

        ids.append(inc_id)
        documents.append(summary)
        metadatas.append(safe_meta)

    # Upsert in batches (ChromaDB has batch size limits)
    batch_size = 100
    for i in range(0, len(ids), batch_size):
        collection.upsert(
            ids=ids[i : i + batch_size],
            documents=documents[i : i + batch_size],
            metadatas=metadatas[i : i + batch_size],
        )

    return len(ids)


# ── Incident storage ────────────────────────────────────────────────────────


def store_incident(
    incident_id: str,
    summary_text: str,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Store a resolved incident in the ``past_incidents`` collection
    so it can be used as a few-shot example in future analyses.

    Parameters
    ----------
    incident_id:
        Unique identifier for the incident.
    summary_text:
        Human-readable summary (becomes the embedded document).
    metadata:
        Optional key-value metadata (severity, MITRE IDs, etc.).
    """
    collection = get_collection("past_incidents")

    safe_meta: Dict[str, Any] = {}
    if metadata:
        for k, v in metadata.items():
            if isinstance(v, (str, int, float, bool)):
                safe_meta[k] = v
            else:
                safe_meta[k] = json.dumps(v)

    collection.upsert(
        ids=[incident_id],
        documents=[summary_text],
        metadatas=[safe_meta] if safe_meta else None,
    )


# ── Feedback storage ────────────────────────────────────────────────────────


def store_feedback(
    incident_id: str,
    summary_text: str,
    label: str,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Store analyst feedback in the ``analyst_feedback`` collection.

    Parameters
    ----------
    incident_id:
        The incident this feedback relates to.
    summary_text:
        Text description used for similarity search.
    label:
        Analyst label (``true_positive``, ``false_positive``, etc.).
    metadata:
        Optional additional metadata.
    """
    collection = get_collection("analyst_feedback")

    safe_meta: Dict[str, Any] = {"incident_id": incident_id, "label": label}
    if metadata:
        for k, v in metadata.items():
            if isinstance(v, (str, int, float, bool)):
                safe_meta[k] = v
            else:
                safe_meta[k] = json.dumps(v)

    feedback_id = f"fb-{incident_id}-{uuid.uuid4().hex[:8]}"
    collection.upsert(
        ids=[feedback_id],
        documents=[summary_text],
        metadatas=[safe_meta],
    )


# ── Similarity search ───────────────────────────────────────────────────────


def search_similar_incidents(
    query_text: str, n: int = 3
) -> List[Dict[str, Any]]:
    """
    Find past incidents most similar to the given query text.

    Returns
    -------
    list[dict]
        Each dict has ``id``, ``document``, ``metadata``, and ``distance``.
    """
    collection = get_collection("past_incidents")

    # Guard against empty collection
    if collection.count() == 0:
        return []

    results = collection.query(
        query_texts=[query_text],
        n_results=min(n, collection.count()),
    )

    items: List[Dict[str, Any]] = []
    if results and results["ids"] and results["ids"][0]:
        for idx, doc_id in enumerate(results["ids"][0]):
            item: Dict[str, Any] = {"id": doc_id}
            if results["documents"] and results["documents"][0]:
                item["document"] = results["documents"][0][idx]
            if results["metadatas"] and results["metadatas"][0]:
                item["metadata"] = results["metadatas"][0][idx]
            if results["distances"] and results["distances"][0]:
                item["distance"] = results["distances"][0][idx]
            items.append(item)

    return items


def search_feedback(
    query_text: str, n: int = 3
) -> List[Dict[str, Any]]:
    """
    Find analyst feedback entries most similar to the given query text.

    Returns
    -------
    list[dict]
        Each dict has ``id``, ``document``, ``metadata``, and ``distance``.
    """
    collection = get_collection("analyst_feedback")

    if collection.count() == 0:
        return []

    results = collection.query(
        query_texts=[query_text],
        n_results=min(n, collection.count()),
    )

    items: List[Dict[str, Any]] = []
    if results and results["ids"] and results["ids"][0]:
        for idx, doc_id in enumerate(results["ids"][0]):
            item: Dict[str, Any] = {"id": doc_id}
            if results["documents"] and results["documents"][0]:
                item["document"] = results["documents"][0][idx]
            if results["metadatas"] and results["metadatas"][0]:
                item["metadata"] = results["metadatas"][0][idx]
            if results["distances"] and results["distances"][0]:
                item["distance"] = results["distances"][0][idx]
            items.append(item)

    return items


# ── CLI Entry-point ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="SENTINEL-AI ChromaDB vector store utilities"
    )
    parser.add_argument(
        "--seed",
        action="store_true",
        help="Seed the past_incidents collection from data/seed_incidents.json.",
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Print collection statistics.",
    )
    args = parser.parse_args()

    if args.seed:
        try:
            count = seed_from_file()
            print(f"✅  Seeded {count} incidents into ChromaDB")
        except FileNotFoundError as exc:
            print(f"❌  {exc}")

    if args.stats:
        client = get_client()
        collections = client.list_collections()
        print("📊  ChromaDB collections:")
        for col in collections:
            c = client.get_collection(col.name)
            print(f"    {col.name}: {c.count()} documents")

    if not args.seed and not args.stats:
        parser.print_help()
