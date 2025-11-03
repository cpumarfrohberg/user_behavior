"""
Save grid search evaluation results.

This module provides functions to save grid search results as DataFrame (CSV)
for easy comparison between different search types and parameter combinations.

Usage:
    from evals.save_results import save_grid_search_results

    save_grid_search_results(
        results=grid_search_results,
        output_path="evals/results/results.csv",
        metadata={
            "search_type": "sentence_transformers",
            "chunk_sizes": [300, 500],
            ...
        }
    )
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd


def save_grid_search_results(
    results: list[dict[str, Any]],
    output_path: str | Path,
    metadata: dict[str, Any] | None = None,
) -> Path:
    """
    Save grid search results as DataFrame (CSV) for easy comparison.

    The saved CSV file contains all results with search_type as a column,
    making it easy to compare metrics between MinSearch and SentenceTransformers.
    Also saves metadata as a separate JSON file.

    Args:
        results: List of evaluation results from evaluate_chunking_grid
        output_path: Path to output CSV file (should end with .csv)
        metadata: Optional metadata dict with evaluation parameters
                 (e.g., search_type, chunk_sizes, overlaps, top_ks, n_samples)

    Returns:
        Path to the saved CSV file

    Example:
        results = [
            {
                "hit_rate": 0.8,
                "mrr": 0.75,
                "num_tokens": 1500.0,
                "score": 2.5,
                "chunk_size": 300,
                "overlap": 15,
                "top_k": 5,
                "search_type": "sentence_transformers"
            },
            ...
        ]

        metadata = {
            "search_type": "sentence_transformers",
            "chunk_sizes": [300, 500],
            "overlaps": [0, 15],
            "top_ks": [5, 10],
            "n_samples": 10,
            "ground_truth_file": "evals/ground_truth.json",
            "num_documents": 1000
        }

        path = save_grid_search_results(results, "evals/results/results.csv", metadata)
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Ensure .csv extension
    if output_path.suffix != ".csv":
        output_path = output_path.with_suffix(".csv")

    # Convert results to DataFrame
    df = pd.DataFrame(results)

    # Ensure search_type is in the DataFrame (from metadata if not in results)
    if "search_type" not in df.columns and metadata and "search_type" in metadata:
        df["search_type"] = metadata["search_type"]

    # Reorder columns to put search_type first for easy comparison
    if "search_type" in df.columns:
        cols = ["search_type"] + [c for c in df.columns if c != "search_type"]
        df = df[cols]

    # Sort by score descending (best results first)
    if "score" in df.columns:
        df = df.sort_values("score", ascending=False).reset_index(drop=True)

    # Save DataFrame as CSV
    df.to_csv(output_path, index=False)

    # Also save metadata as JSON in same directory
    if metadata:
        metadata_path = output_path.with_suffix(".metadata.json")
        metadata_data = {
            "timestamp": datetime.now().isoformat(),
            "metadata": metadata,
            "summary": {
                "num_results": len(results),
                "best_score": float(df["score"].max())
                if "score" in df.columns
                else None,
                "best_hit_rate": float(df["hit_rate"].max())
                if "hit_rate" in df.columns
                else None,
                "best_mrr": float(df["mrr"].max()) if "mrr" in df.columns else None,
            },
        }
        with open(metadata_path, "w") as f:
            json.dump(metadata_data, f, indent=2)

    return output_path
