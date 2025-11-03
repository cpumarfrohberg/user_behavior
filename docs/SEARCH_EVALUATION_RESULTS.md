# Search Type Evaluation Results

## Summary

**MinSearch performs better than SentenceTransformers** for this RAG system, even with paraphrased queries.

## Results

### Best Performance Comparison

| Metric | MinSearch | SentenceTransformers | Winner |
|--------|-----------|---------------------|--------|
| **Best Score** | 1.400 | 1.373 | ✅ MinSearch |
| **Best Hit Rate** | 1.000 | 0.980 | ✅ MinSearch |
| **Best MRR** | 0.954 | 0.980 | SentenceTransformers |
| **Tokens (Best)** | 470.5 | 489.1 | ✅ MinSearch |

### Optimal Parameters (MinSearch)

- **chunk_size**: 200
- **overlap**: 15
- **top_k**: 5

## Key Findings

1. **MinSearch excels**: Perfect hit rate (1.000) and better overall score
2. **Paraphrasing doesn't change outcome**: MinSearch still wins even with semantic queries
3. **More efficient**: Lower token usage, faster execution
4. **SentenceTransformers has better MRR**: Better ranking, but lower overall score

## Decision

**Use MinSearch for production** - Better performance, faster, more efficient.

## Evaluation Methodology

- **Original Ground Truth**: Exact title matching (50 queries)
- **Paraphrased Ground Truth**: Semantic queries with same meaning (50 queries)
- **Grid Search**: 20 random parameter combinations per search type

## Next Steps

1. ✅ Search type decision: **MinSearch**
2. ⏭️ Answer quality evaluation (Judge LLM)
3. ⏭️ Unit tests for evaluation functions
4. ⏭️ Production deployment
