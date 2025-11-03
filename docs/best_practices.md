# Best Practices

## Ground Truth Sample Sizes

### Quick Testing / Development
- **5-10 samples**: Fast iteration, catch obvious bugs
- **Use case**: Development, quick validation

### Initial Evaluation / Parameter Tuning
- **20-50 samples**: Reasonable confidence, balanced speed
- **Use case**: Finding optimal chunking parameters (recommended default)
- **Current default**: 50 samples

### Production Evaluation
- **100-200+ samples**: High confidence, representative
- **Use case**: Final validation before deployment

### Research / Publication
- **200-500+ samples**: Statistical significance, comprehensive
- **Use case**: Academic research, detailed analysis

## Statistical Considerations

- **Minimum viable**: 20-30 samples for basic metrics
- **Recommended**: 50-100 samples for reliable results
- **Production**: 100+ samples for confidence
- **Margin of error** (95% confidence):
  - 50 samples: ~±14%
  - 100 samples: ~±10%
  - 200+ samples: ~±7%

## Current Recommendations

For chunking parameter optimization:
- Start with 50 samples (default)
- Use 20-30 for faster iteration
- Use 100+ for final validation

## Search Type Selection

### Performance Trade-offs

**SentenceTransformers (Vector Search):**
- **Pros**: Better semantic understanding, handles synonyms/paraphrasing
- **Cons**: Much slower (generates embeddings for all documents)
- **Best for**: Complex queries, semantic similarity, final validation when accuracy is critical

**MinSearch (Text Search):**
- **Pros**: Much faster, lower computational cost
- **Cons**: Keyword-based, less semantic understanding
- **Best for**: Exact matches, technical terms, speed-critical scenarios

### Observations

Based on evaluation results:
- **Accuracy gap**: SentenceTransformers is only slightly better than MinSearch for keyword-based queries
- **Speed difference**: SentenceTransformers is significantly slower for grid search
- **Use case dependent**: Accuracy advantage may not justify speed penalty for simple queries

### Recommendations

**Use MinSearch for:**
- Initial/fast parameter optimization (faster iteration)
- Testing when you need quick results
- Production if accuracy difference is acceptable
- Keyword-based queries with exact matches

**Use SentenceTransformers for:**
- Final validation when accuracy is critical
- Semantic queries that benefit from embeddings
- Production if the accuracy improvement matters significantly
- Complex natural language queries with paraphrasing

## Model Quantization for Performance

### What is Quantization?

Quantization reduces model precision (from 32-bit/16-bit to 8-bit or 4-bit) to make models smaller and faster, with minimal quality loss.

**Regular Model (F16):**
- Uses 16-bit floating point numbers
- Higher precision, larger file size, slower inference
- Example: `llama3.2:3b` (~1.8 GB)

**Quantized Model (Q4_0):**
- Uses 4-bit integers (quantized from 16-bit)
- Lower precision, smaller file size (~50% smaller), faster inference (~50-70% faster)
- Example: `llama3.2:3b-q4_0` (~800 MB)

### Quantization Levels (Ollama)

- **Q4_0** - 4-bit, fastest, smallest (~50% size reduction, ~50-70% speedup)
- **Q4_1** - 4-bit with slight quality boost
- **Q5_0** - 5-bit, balanced (~40% size reduction, ~40-60% speedup)
- **Q5_1** - 5-bit with slight quality boost
- **Q8_0** - 8-bit, higher quality (~30% size reduction, ~30-50% speedup)

### Trade-offs

**Benefits:**
- ✅ Faster inference (often 1.5-2x speedup)
- ✅ Smaller model size
- ✅ Lower memory usage
- ✅ Can fit larger models on same hardware

**Costs:**
- ⚠️ Slight quality drop (often negligible for RAG with good retrieval)
- ⚠️ Output may be slightly less nuanced

### When to Use Quantized Models

**Recommended for:**
- RAG systems with good retrieval (retrieval quality matters more than generation quality)
- Speed-critical applications
- Resource-constrained environments
- Production when speed > slight quality trade-off

**Not recommended for:**
- Creative writing tasks
- Complex reasoning requiring high precision
- When every nuance matters

### Recommendations

**For RAG Agent:**
- **Start with Q4_0**: Best speed improvement, quality loss usually negligible with good retrieval
- **If quality issues**: Try Q5_0 or Q8_0
- **Test first**: Compare quantized vs non-quantized on your use case

**Usage:**
```bash
# Pull quantized model
docker exec user_behavior-ollama-1 ollama pull llama3.2:3b-q4_0

# Use in config: Change model name to "llama3.2:3b-q4_0"
```

### Performance Impact

- **Current optimizations** (fewer searches, less context): ~30-40% faster
- **With Q4 model**: ~50-70% faster than base model
- **With 1B model**: ~60-80% faster than 3B model
- **Combined** (Q4 + 1B + optimizations): Potentially 2-3x faster overall
