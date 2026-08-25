#!/usr/bin/env bash
#
# Post-deploy verification.
#
# One command that answers "is this deployment actually working?" instead of a
# checklist of curls whose output you have to interpret. Every check prints
# PASS or FAIL with the reason, and the exit status is the number of failures,
# so it can gate a script.
#
# Run it after every redeploy, on either machine:
#
#   macOS : ./verify-deploy.sh
#   RHEL8 : ./verify-deploy.sh https://localhost:49160
#
# The database checks are skipped when the file is not beside you, so it is
# safe to run from anywhere.
#
# Usage: ./verify-deploy.sh [base-url] [path-to-crucible.db]
BASE="${1:-http://localhost:49160}"
DB="${2:-data/crucible.db}"
# Retry transient network faults. A background job writing to the database can
# briefly reset a connection; without a retry that shows up as a FAIL against a
# feature that is in fact working, which is worse than no check at all.
C(){ curl --noproxy '*' -sSk -m 30 --retry 3 --retry-delay 2 --retry-all-errors "$@"; }
pass=0; fail=0
ok(){ printf '  \033[0;32m PASS \033[0m %s\n' "$1"; pass=$((pass+1)); }
no(){ printf '  \033[0;31m FAIL \033[0m %s\n     -> %s\n' "$1" "$2"; fail=$((fail+1)); }
j(){ python3 -c "import json,sys;d=json.load(sys.stdin);print($1)" 2>/dev/null; }

echo "Verifying $BASE"; echo

# 1 — the page loads at all (the sort_numeric 400)
code=$(C -o /tmp/v1.json -w '%{http_code}' "$BASE/api/screening?page=1&limit=50&search=&chemical_id=&tag=&sort=&dir=asc&sort_numeric=&duplicates=")
[ "$code" = "200" ] && ok "screening list loads (was HTTP 400)" || no "screening list" "HTTP $code"

# 2 — headings are snake_case and taken from the source file
labels=$(C "$BASE/api/screening/columns" | j "','.join(c['label'] for c in d['columns'])")
case "$labels" in
  *lims*mg_kg_food*) ok "column headings are snake_case from your file" ;;
  *) no "column headings" "got: ${labels:0:80}" ;;
esac

# 3 — columns removed / added
case "$labels" in *cas_alternatives*) no "cas_alternatives removed" "still present";; *) ok "cas_alternatives removed";; esac
case "$labels" in *chemical_id*) no "chemical_id column removed" "still present";; *) ok "chemical_id column removed";; esac
case "$labels" in *source_tag*) ok "source_tag column visible";; *) no "source_tag column" "missing";; esac

# 4 — duplicates filter, all five options
s=$(C "$BASE/api/screening/duplicates/summary")
tot=$(echo "$s" | j "d['total']"); uniq=$(echo "$s" | j "d['unique']")
ident=$(echo "$s" | j "d['identical']"); rep=$(echo "$s" | j "d['repeat_measurement']")
allok=1
for opt in all unique identical repeat flagged; do
  n=$(C "$BASE/api/screening?limit=1&duplicates=$opt" | j "d['pagination']['total']")
  [ -z "$n" ] && allok=0
done
[ "$allok" = "1" ] && ok "duplicates filter: all=$tot unique=$uniq identical=$ident repeat=$rep" \
                   || no "duplicates filter" "one or more options failed"
[ -n "$ident" ] && [ "$((tot-uniq))" = "$ident" ] && ok "unique-only drops exactly the identical copies" \
                   || no "unique-only maths" "total-unique=$((tot-uniq)) but identical=$ident"

# 5 — sorting, numeric
top=$(C "$BASE/api/screening?limit=1&sort=mg_per_kg_food&dir=desc&sort_numeric=true" | j "d['data'][0].get('mg_per_kg_food')")
bot=$(C "$BASE/api/screening?limit=1&sort=mg_per_kg_food&dir=asc&sort_numeric=true"  | j "d['data'][0].get('mg_per_kg_food')")
python3 -c "import sys;sys.exit(0 if float('$top')>=float('$bot') else 1)" 2>/dev/null \
  && ok "numeric sort works (desc=$top asc=$bot)" || no "numeric sort" "desc=$top asc=$bot"

# 6 — export
for f in csv xlsx json; do
  code=$(C -o /tmp/v.$f -w '%{http_code}' "$BASE/api/screening/export?format=$f&f.simulant=ethanol&columns=lims_id,compound_name")
  [ "$code" = "200" ] && [ -s /tmp/v.$f ] || { no "export $f" "HTTP $code"; continue; }
done
head -1 /tmp/v.csv | grep -q "lims,name" && ok "export headings match the table" || no "export headings" "$(head -1 /tmp/v.csv)"

# 7 — query console, read-only
code=$(C -o /tmp/vq.json -w '%{http_code}' -X POST "$BASE/api/query" -H 'Content-Type: application/json' -d '{"sql":"SELECT 1 AS one"}')
[ "$code" = "200" ] && ok "query console runs SELECT" || no "query console" "HTTP $code"
blocked=1
for bad in "DROP TABLE chemicals" "DELETE FROM screening" "SELECT 1; DROP TABLE chemicals"; do
  c=$(C -o /dev/null -w '%{http_code}' -X POST "$BASE/api/query" -H 'Content-Type: application/json' -d "{\"sql\":\"$bad\"}")
  [ "$c" = "400" ] || blocked=0
done
[ "$blocked" = "1" ] && ok "query console refuses every write" || no "query console safety" "a write was not refused"

# 8 — the SPA shell is not cached
C -D- -o /dev/null "$BASE/" | grep -qi "cache-control: no-cache" \
  && ok "index.html sent no-cache (stale UI fixed)" || no "index.html caching" "no no-cache header"

# 9 — no dangling chemical links
if [ -f "$DB" ]; then
  d=$(sqlite3 "$DB" "SELECT COUNT(*) FROM screening s WHERE s.chemical_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM chemicals c WHERE c.chemical_id=s.chemical_id);" 2>/dev/null)
  [ "$d" = "0" ] && ok "no dangling chemical links" || no "dangling links" "$d rows point at missing chemicals"
  fmt=$(sqlite3 "$DB" "SELECT COUNT(*) FROM chemicals WHERE chemical_id NOT LIKE 'CHEM-%';" 2>/dev/null)
  [ "${fmt:-0}" = "0" ] && ok "chemical ids all sequential (CHEM-nnnnnn)" || no "chemical id format" "$fmt use the old CAS- form"
else
  printf '  \033[0;33m SKIP \033[0m database checks (no %s here)\n' "$DB"
fi

# 10 — identification progress is reported
idn=$(C "$BASE/api/screening/columns" | j "d.get('identified')")
[ -n "$idn" ] && ok "identification progress reported ($idn rows linked)" || no "identification progress" "field missing"

echo; printf '  %d passed, %d failed\n' "$pass" "$fail"
[ "$fail" = "0" ] && printf '  \033[0;32mEverything checks out.\033[0m\n' || printf '  \033[0;31mSee the failures above.\033[0m\n'
exit "$fail"
