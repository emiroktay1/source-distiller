#!/usr/bin/env bash
# Quick Start Example — Source Distiller
# Run this after: pip install source-distiller

set -e

# Create sample documents
mkdir -p /tmp/sd-example/docs

cat > /tmp/sd-example/docs/api_spec.md << 'EOF'
# API Specification v2.1
Rate limit: 1000 requests per minute per API key.
Authentication: Bearer token via OAuth 2.0.
Maximum payload size: 5 MB.
Retry policy: exponential backoff, max 3 retries.
Deprecation notice: v1 endpoints removed on 2025-09-01.
EOF

cat > /tmp/sd-example/docs/ops_runbook.md << 'EOF'
# Operations Runbook
Rate limit is set to 500 requests per minute in staging.
Production rate limit matches API spec: 1000 req/min.
Alert threshold: 80% of rate limit sustained for 5 minutes.
Known issue: retry logic does not respect backoff in batch client v3.2.
Maximum payload observed in production: 12 MB (exceeds spec).
EOF

# 1. Index
source-distiller index /tmp/sd-example/docs --out /tmp/sd-example/index.json

# 2. Search
echo ""
echo "=== Searching for rate limit info ==="
source-distiller search --index /tmp/sd-example/index.json \
    --query "rate limit requests per minute" --top-k 3

# 3. Detect conflicts
echo ""
echo "=== Checking for conflicts ==="
source-distiller conflicts --index /tmp/sd-example/index.json

# 4. Full report
echo ""
echo "=== Generating report ==="
source-distiller report --index /tmp/sd-example/index.json \
    --query "rate limit and payload size" \
    --out /tmp/sd-example/report.md

echo ""
echo "Report saved to /tmp/sd-example/report.md"

# Cleanup
# rm -rf /tmp/sd-example
