#!/bin/bash

# Define the URL and Authorization token
SCRIPTDIR="$HOME/code/surfcontroller"

URL="https://gw.live.surfresearchcloud.nl/v1/workspace/workspaces/?application_type=Compute&deleted=false"
AUTH_TOKEN=$(cat "$SCRIPTDIR/api-token.txt")
# Define the output CSV file
OUTPUT_FILE="$SCRIPTDIR/output.csv"

# Make the GET request and process the JSON response
curl -X 'GET' \
	"$URL" \
	-H "accept: application/json;Compute" \
	-H "authorization: $AUTH_TOKEN" |
	jq -r '(["id","name", "active"], (.results[] | [.id, .name, .active])) | @csv' >"$OUTPUT_FILE"

# Print a success message
echo "Data successfully saved to $OUTPUT_FILE"
