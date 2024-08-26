#!/bin/bash

# Run workspace.sh and wait for it to complete
/Users/rgrouls/code/mads-autoshutdown/workspace.sh

# After workspace.sh completes, run surf.sh with --pause
/Users/rgrouls/code/mads-autoshutdown/surf.sh --pause
