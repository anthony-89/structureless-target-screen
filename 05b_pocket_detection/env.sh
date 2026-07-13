#!/bin/bash
# Sourced by Task A/B/C scripts. Sets up dock env + Java + P2Rank on PATH.
export MAMBA_ROOT_PREFIX=/Users/antonioesquivel/.claude-science/conda
export DOCK=$MAMBA_ROOT_PREFIX/envs/dock
export JAVA_HOME=$DOCK/lib/jvm
export PRANK=/Users/antonioesquivel/Desktop/claude_code_handoff/05b_pocket_detection/tools/p2rank_2.5/prank
export PATH=$DOCK/bin:$JAVA_HOME/bin:$PATH
