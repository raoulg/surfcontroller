#!/bin/bash

SCRIPTDIR="$HOME/code/surfcontroller"
# Run workspace.sh and wait for it to complete
$SCRIPTDIR/workspace.sh

# After workspace.sh completes, run surf.sh with --pause
$SCRIPTDIR/surf.sh --pause
