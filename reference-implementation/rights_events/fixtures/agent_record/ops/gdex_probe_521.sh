#!/usr/bin/env bash
# A14 R77 (ii): the operator's probe of the registry's current GDEX MCP server binary
# (5.2.1, released 2026-10-31 02:27Z; its 5.2.0 changelog names the 403 SESSION_ORIGIN_DENIED
# fix after the backend change deployed 2026-10-28). The executor's fetch of a newer binary is
# denied by its permission classifier, so the operator runs this:
#   ! bash rights_events/fixtures/agent_record/ops/gdex_probe_521.sh
# Step 1 is read-only (gdex_status). Step 2 (one gdex_connect refresh of the account) runs only
# if step 1 answered "api": "ok". Each answer is saved verbatim beside the previews, to be
# pinned by sha in A14.2. No secret enters the terminal: the server reads the key file itself.
set -uo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
VERSION="${GDEX_PROBE_VERSION:-5.2.1}"
export GDEX_MCP_SERVER_CMD="npx.cmd -y @gemachdao/gdex-mcp-server@${VERSION}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
echo "PROBE server=@gemachdao/gdex-mcp-server@${VERSION} node=$(node --version) npx=$(npx.cmd --version) at ${STAMP}"
STATUS="$HERE/probe_${VERSION}_status_${STAMP}.json"
CONNECT="$HERE/probe_${VERSION}_connect_${STAMP}.json"
python "$HERE/gdex_stdio_client.py" call gdex_status '{}' --timeout 300 --save "$STATUS"
rc=$?
echo "STATUS rc=${rc} saved=${STATUS}"
if [ "$rc" -eq 0 ] && grep -q 'api\\": \\"ok' "$STATUS"; then
  python "$HERE/gdex_stdio_client.py" call gdex_connect '{"accountRef":"acct_8c48b321e89c"}' --timeout 300 --save "$CONNECT"
  echo "CONNECT rc=$? saved=${CONNECT}"
else
  echo "CONNECT skipped (status not ok)"
fi
