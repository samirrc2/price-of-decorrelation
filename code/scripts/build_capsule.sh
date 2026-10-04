#!/usr/bin/env bash
# Assemble the Code Ocean capsule for upload, then PROVE it runs.
#
#   bash code/scripts/build_capsule.sh [DEST]      DEST defaults to build/capsule
#
# A capsule is a /code + /data mount with no manuscript, no submission directory and no git
# history. Three things follow, and each one has bitten this artifact before:
#
#   * it is assembled from `git archive HEAD`, never from the working tree, so an uncommitted
#     file cannot end up in a capsule that a reader can never reproduce;
#   * the document gates (manuscript binding, letter checks, IEEE ordering, freeze receipts)
#     cannot run there and must exit 2, "not checkable", rather than 0. reproduce.sh already
#     distinguishes those cases; this script asserts the distinction held;
#   * the capsule must carry every input the analysis arms read. make_manifest.py --capsule
#     keeps that list, and its list was six entries stale after the revision added the
#     cross-domain replication, the control arm and the temperature sweep.
#
# The build ends by running the capsule's own entry point inside DEST and diffing the claims it
# produces against the committed claims.json, key by key. Assembling a capsule without running
# it is how a broken capsule gets a DOI.
set -euo pipefail
CODE_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
REPO_ROOT="$(cd "$CODE_ROOT/.." && pwd)"
cd "$REPO_ROOT"

# Stage OUTSIDE the repository by default. Staging at build/capsule inside the checkout gave
# the capsule an enclosing .git, which `git rev-parse` resolves from any nested directory --
# so a gate that asked "am I in a git checkout?" said yes, fetched the as-submitted baseline
# from the parent repo, and then failed on a paper/ the capsule correctly lacks. The gate is
# fixed to require the repo root to be its own tree, and the staging area no longer invites
# the question.
DEST="${1:-$(dirname "$REPO_ROOT")/$(basename "$REPO_ROOT")-capsule}"
PY="${PY:-$REPO_ROOT/.venv/bin/python}"
[[ -x "$PY" ]] || PY="python3"

command -v git >/dev/null || { echo "build_capsule: git is required" >&2; exit 2; }
if [[ -n "$(git status --porcelain)" ]]; then
  echo "build_capsule: the working tree has uncommitted changes." >&2
  echo "build_capsule: a capsule is built from HEAD, so those changes would be SILENTLY" >&2
  echo "build_capsule: absent from it. Commit or stash first." >&2
  exit 2
fi
COMMIT="$(git rev-parse HEAD)"

echo "== building capsule from $COMMIT =="
rm -rf "$DEST"; mkdir -p "$DEST"
# Export the committed tree, then keep only the capsule mounts.
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
git archive HEAD | tar -x -C "$TMP"
for p in code data environment metadata; do
  [[ -e "$TMP/$p" ]] && cp -R "$TMP/$p" "$DEST/$p"
done
cp "$TMP/LICENSE" "$DEST/" 2>/dev/null || true
mkdir -p "$DEST/results"

# data/raw/ and cache/ are gitignored and absent from the archive by construction; say so
# rather than leaving a reader to wonder whether the capsule is missing them.
cat > "$DEST/README.md" <<TXT
# Capsule contents

Built from commit \`$COMMIT\` by \`code/scripts/build_capsule.sh\`.

| Mount | Contents |
|-------|----------|
| \`/code\` | \`run\`, \`src/\`, \`scripts/\`, \`tests/\`, \`requirements.txt\` |
| \`/data\` | frozen captures, \`configs/\`, \`inputs/\`, \`inputs_mmlu/\`, \`mmlu/\`, \`datacache/\`, \`MANIFEST.sha256\`, clinical ground truth |
| \`/results\` | written by the run |

Entry point: \`/code/run\`. No API keys, no network, no cost.

The per-call JSON dumps (\`data/raw/\`) and the API response cache (\`cache/\`) are deliberately
absent: the analysis is a function of the frozen \`runs.csv\` files, and \`reproduce.sh\` verifies
every one of them against \`data/MANIFEST.sha256\` before it computes anything.

The document gates cannot run here -- there is no manuscript and no git history to compare
against -- and they exit 2, "not checkable", rather than reporting a pass.
TXT

echo "  size: $(du -sh "$DEST" | cut -f1)"
echo "  mounts: $(cd "$DEST" && ls -d */ | tr '\n' ' ')"

echo "== capsule completeness =="
( cd "$DEST" && "$PY" code/src/make_manifest.py --capsule ) | sed 's/^/   /'

echo "== running the capsule's own entry point =="
( cd "$DEST" && PY="$PY" bash code/run ) > "$DEST/_run.log" 2>&1 || {
  echo "!! the capsule FAILED to run; see $DEST/_run.log" >&2
  tail -20 "$DEST/_run.log" >&2
  exit 1
}
grep -E "NOT CHECKABLE|capsule layout|all gates passed" "$DEST/_run.log" | sed 's/^/   /'
# A document gate inside a capsule must say "not checkable" (exit 2), never "failed" (exit 1).
# The first build of this script caught check_letter_actions doing exactly that.
if grep -q "FAILED (exit 1)" "$DEST/_run.log"; then
  echo "!! a gate reported a FAILURE inside the capsule; a gate that cannot run here must" >&2
  echo "!! exit 2, not 1. Offending lines:" >&2
  grep -n "FAILED (exit 1)" "$DEST/_run.log" >&2
  exit 1
fi

echo "== claims produced in the capsule vs the committed claims.json =="
"$PY" - "$DEST" <<'TXT'
import json, sys
from pathlib import Path
dest = Path(sys.argv[1])
cand = sorted(dest.glob("results/**/claims.json"))
if not cand:
    print("   !! the capsule produced no claims.json"); raise SystemExit(1)
got = json.loads(cand[-1].read_text())
want = json.loads(Path("results/latest/claims.json").read_text())
keys = sorted(set(got) | set(want))
diff = [k for k in keys if got.get(k, "<absent>") != want.get(k, "<absent>")]
print(f"   {len(keys) - len(diff)}/{len(keys)} claim keys identical to the committed analysis")
for k in diff[:20]:
    print(f"     DIFFERS {k}: capsule {got.get(k, '<absent>')!r} vs committed {want.get(k, '<absent>')!r}")
raise SystemExit(1 if diff else 0)
TXT
echo "== capsule ready: $DEST =="
