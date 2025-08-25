#!/bin/bash

SCRIPTDIR="/app"
# Run workspace.sh and wait for it to complete
$SCRIPTDIR/workspace.sh

# After workspace.sh completes, run surf.sh with --pause
$SCRIPTDIR/surf.sh --pause
