#!/bin/bash
# Sourced by Task A/B/C scripts. Sets up dock env + Java + P2Rank on PATH.
export MAMBA_ROOT_PREFIX="${MAMBA_ROOT_PREFIX:-$HOME/.claude-science/conda}"
export DOCK=$MAMBA_ROOT_PREFIX/envs/dock
export JAVA_HOME=$DOCK/lib/jvm
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"   # 05b_pocket_detection/
export PRANK="${PRANK:-$HERE/tools/p2rank_2.5/prank}"
export PATH=$DOCK/bin:$JAVA_HOME/bin:$PATH
