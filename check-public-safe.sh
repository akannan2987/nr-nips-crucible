#!/bin/bash

# check-public-safe.sh — verify this checkout is safe to push to the PUBLIC repo.
#
# Run it before every public push (see docs/GITOPS-WORKFLOW.md):
#     ./check-public-safe.sh
#
# Exit 0 = safe to push. Exit 1 = something sensitive would be published.
#
# It checks three things against the files git actually tracks:
#   1. No secret/runtime paths are tracked (certs, data, backups, .env.local, …)
#   2. No non-template workbooks are tracked under docs/excel-templates/
#   3. No internal identifiers appear in tracked content
#
# Safe to run in the private checkout too — there it is expected to FAIL,
# because the private repo legitimately holds real data.

cd "$(dirname "$0")" || exit 1

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'

fail=0

echo "Checking whether this checkout is safe to publish..."
echo ""

# ── 1. Paths that must never be tracked ─────────────────────────────
echo "1. Secret / runtime paths"
for p in certs data backups .env .env.local crucible-costar-prompt.md \
         CLAUDE.md CLAUDE.local.md .claude \
         .claude/settings.local.json backend/.venv client/node_modules; do
    tracked=$(git ls-files -- "$p" 2>/dev/null)
    if [ -n "$tracked" ]; then
        echo -e "   ${RED}✗ TRACKED: $p${NC}"
        echo "$tracked" | sed 's/^/       /'
        fail=1
    fi
done
# Extension sweep: catches a sensitive file force-added (git add -f) at ANY
# path — mirrors the .gitignore extension lists.
ext=$(git ls-files | grep -iE '\.(key|pem|crt|cer|csr|p12|pfx|jks|der|db|sqlite3?|dump|bak)$')
if [ -n "$ext" ]; then
    echo -e "   ${RED}✗ sensitive file extension(s) tracked:${NC}"
    echo "$ext" | sed 's/^/       /'
    fail=1
fi
[ $fail -eq 0 ] && echo -e "   ${GREEN}✓ none tracked${NC}"

# ── 2. Only sanitized templates under docs/excel-templates/ ─────────
echo ""
echo "2. Upload templates"
extra=$(git ls-files -- docs/excel-templates \
        | grep -vE '/(chemicals_template\.(csv|xlsx|sdf)|screening_template\.xlsx|toxicology_template\.xlsx|Upload_Sample_Template\.xlsx|README\.md|generate_templates\.py)$')
if [ -n "$extra" ]; then
    echo -e "   ${RED}✗ non-template file(s) tracked — real data must not be published:${NC}"
    echo "$extra" | sed 's/^/       /'
    fail=1
else
    echo -e "   ${GREEN}✓ only synthetic templates tracked${NC}"
fi

# ── 3. Internal identifiers in tracked content ──────────────────────
# Hard failures: internal host, corporate username, shared-filesystem
# paths, and internal project/data identifiers.
echo ""
echo "3. Internal identifiers in tracked content"
hits=$(git grep -inE 'nr-ubp|rdkannanab|gpfs|PIPM|NQAC' -- \
       ':!check-public-safe.sh' 2>/dev/null)
if [ -n "$hits" ]; then
    echo -e "   ${RED}✗ found — redact before pushing:${NC}"
    echo "$hits" | cut -c1-120 | sed 's/^/       /'
    fail=1
else
    echo -e "   ${GREEN}✓ none found${NC}"
fi

# Informational only: org-level attribution is a deliberate, accepted
# exception (README authors, self-signed cert subject, UI footer).
echo ""
echo "4. Org attribution (informational — accepted exceptions)"
org=$(git grep -inE 'nihs|nestle\.com' -- \
      ':!check-public-safe.sh' 2>/dev/null | cut -c1-100)
if [ -n "$org" ]; then
    echo "$org" | sed 's/^/       /'
    echo -e "   ${YELLOW}– review these are intended attribution, not new leaks${NC}"
else
    echo -e "   ${GREEN}✓ none${NC}"
fi

echo ""
if [ $fail -eq 0 ]; then
    echo -e "${GREEN}✓ SAFE TO PUSH to the public repository${NC}"
    exit 0
fi
echo -e "${RED}✗ NOT SAFE TO PUSH — fix the items marked ✗ above${NC}"
exit 1
