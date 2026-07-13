#!/usr/bin/env bash
# Blind-dock AMP into OPLAH with DiffDock on CPU (Apple Silicon).
#
# Environment notes (differ from the Colab recipe in 03_diffdock_attempt/):
#  * data.pyg.org ships no macOS-arm64 wheels, so torch_cluster/torch_scatter are
#    SOURCE-COMPILED against the installed torch. That is correct here, not a bug.
#  * torch_sparse / torch_spline_conv are in requirements.txt but never imported.
#  * openfold / fair-esm[esmfold] are only needed to FOLD from sequence. We supply a
#    structure, so they are omitted.
#  * This Python has no CA bundle wired up, so urlopen() fails cert verification when
#    DiffDock downloads its model weights and ESM-2. Export certifi's bundle.
set -euo pipefail

BASE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY="$BASE/.venv/bin/python"
cd "$BASE/DiffDock"   # torus/SO(3) caches (.p.npy/.score.npy) are written to CWD

CERT="$("$PY" -c 'import certifi; print(certifi.where())')"
export SSL_CERT_FILE="$CERT" REQUESTS_CA_BUNDLE="$CERT"
export OMP_NUM_THREADS=8 MKL_NUM_THREADS=8 TOKENIZERS_PARALLELISM=false

exec "$PY" -W ignore -m inference \
  --config blind.yaml \
  --protein_ligand_csv batch.csv \
  --out_dir out/ "$@"
