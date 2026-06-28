#!/usr/bin/env bash
# ============================================================
# Source Distiller — Demo Recording Script
# ============================================================
# This script produces clean terminal output for demo GIFs.
#
# Option A: Record with asciinema (recommended)
#   brew install asciinema
#   asciinema rec demo.cast -c "bash demo/record.sh"
#   # Then convert to GIF:
#   # npm install -g svg-term-cli
#   # svg-term --in demo.cast --out demo.svg --window
#   # Or use https://asciinema.org to share directly
#
# Option B: Just run it to see the output
#   bash demo/record.sh
# ============================================================

set +e

DEMO_DIR=$(mktemp -d)
trap "rm -rf $DEMO_DIR" EXIT

# Create sample documents
mkdir -p "$DEMO_DIR/papers"

cat > "$DEMO_DIR/papers/security_policy_v1.md" << 'DOC'
# Security Policy v1.0
Version: 2024-03-15
Status: superseded by v2.0

All customer data is encrypted at rest using AES-128.
Password rotation is required every 90 days.
Audit logs are retained for 30 days.
Two-factor authentication is optional for internal users.
The Chief Security Officer is Maria Chen.
DOC

cat > "$DEMO_DIR/papers/security_policy_v2.md" << 'DOC'
# Security Policy v2.0
Version: 2025-01-10
Status: current

This document replaces Security Policy v1.0.
All customer data is encrypted at rest using AES-256.
Password rotation is required every 60 days.
Audit logs are retained for 90 days.
Two-factor authentication is mandatory for all users.
The Chief Security Officer is James Park.
DOC

cat > "$DEMO_DIR/papers/incident_report.md" << 'DOC'
# Incident Report IR-2025-042
Date: 2025-02-18

During routine penetration testing, the red team discovered that
the authentication service still enforces 90-day password rotation
instead of the 60-day requirement in Security Policy v2.0.

The encryption module was verified to use AES-256 as required.
However, two-factor authentication enforcement has not been
deployed to the staging environment.

Risk assessment: HIGH — policy compliance gap in production.
Remediation deadline: 2025-03-01.
DOC

cat > "$DEMO_DIR/papers/marketing_brief.md" << 'DOC'
# Marketing Brief Q1 2025

Our platform provides enterprise-grade security.
Customers trust us with their most sensitive data.
Award-winning support team available 24/7.
This document does not define security requirements.
DOC

# Colors
CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BOLD='\033[1m'
NC='\033[0m'

type_cmd() {
    echo ""
    echo -e "${GREEN}\$${NC} $1"
    sleep 0.3
    eval "$1"
    sleep 0.5
}

echo -e "${BOLD}${CYAN}"
echo "  ╔══════════════════════════════════════════════╗"
echo "  ║         Source Distiller — Demo              ║"
echo "  ║  Zero-hallucination citation engine          ║"
echo "  ╚══════════════════════════════════════════════╝"
echo -e "${NC}"
sleep 1

echo -e "${YELLOW}--- Step 1: Index your documents ---${NC}"
type_cmd "source-distiller index $DEMO_DIR/papers --out $DEMO_DIR/index.json"

echo ""
echo -e "${YELLOW}--- Step 2: Search with a question ---${NC}"
type_cmd "source-distiller search --index $DEMO_DIR/index.json --query 'password rotation policy compliance gap' --top-k 3"

echo ""
echo -e "${YELLOW}--- Step 3: Verify a citation ---${NC}"
type_cmd "source-distiller quote --index $DEMO_DIR/index.json --cite S4:L1-L10"

echo ""
echo -e "${YELLOW}--- Step 4: Detect cross-document conflicts ---${NC}"
type_cmd "source-distiller conflicts --index $DEMO_DIR/index.json"

echo ""
echo -e "${YELLOW}--- Step 5: Audit a draft answer ---${NC}"

# Create a draft with one good and one bad citation
cat > "$DEMO_DIR/draft.md" << 'DRAFT'
Password rotation is required every 60 days per the current policy [S2:L7-L7].

The incident report confirms that production still enforces the old 90-day
rotation period, creating a compliance gap [S3:L4-L6].

Encryption has been upgraded to AES-256 as required [S2:L6-L6].

Two-factor authentication is now mandatory but has not been deployed
to staging yet [S99:L1-L5].
DRAFT

type_cmd "source-distiller audit --index $DEMO_DIR/index.json --answer $DEMO_DIR/draft.md"

echo ""
echo -e "${YELLOW}--- Step 6: Generate a full report ---${NC}"
type_cmd "source-distiller report --index $DEMO_DIR/index.json --query 'security compliance gaps' --max-conflicts 3"

echo ""
echo -e "${YELLOW}--- Step 7: Quick stats ---${NC}"
type_cmd "source-distiller stats --index $DEMO_DIR/index.json"

echo ""
echo -e "${BOLD}${CYAN}Done. Install: pip install source-distiller${NC}"
echo ""
