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
