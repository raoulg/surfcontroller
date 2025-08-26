#!/bin/bash

# Load the API token from the file
DATADIR="/data"
EXCLUSIONS_FILE="$DATADIR/exclusions.json"
LOG_FILE="$DATADIR/logs.log"
API_TOKEN=$(cat "$DATADIR/api-token.txt")
CSRF_TOKEN=$(cat "$DATADIR/csrf-token.txt")

# URL prefix
URL_PREFIX="https://gw.live.surfresearchcloud.nl/v1/workspace/workspaces"

# Initialize variables
ID_FILTER_STRING=""

# Parse command-line arguments
for arg in "$@"; do
	case $arg in
	--pause)
		ACTION="pause"
		ACTION_DESCRIPTION="Shutting down"
		shift
		;;
	--resume)
		ACTION="resume"
		ACTION_DESCRIPTION="Resuming"
		shift
		;;
	--id=*)
		ID_FILTER_STRING="${arg#*=}"
		shift
		;;
	*)
		echo "Usage: $0 --pause | --resume [--id=abc,xyz]"
		exit 1
		;;
	esac
done


# Ensure ACTION is set
if [ -z "$ACTION" ]; then
	echo "Usage: $0 --pause | --resume [--id=abc,xyz]"
	exit 1
fi

ID_FILTER=(${ID_FILTER_STRING//,/ })

echo "idfilterstring from args: $ID_FILTER_STRING" >>"$LOG_FILE"

# Read the IDs and names from the output.csv file
while IFS=',' read -r ID NAME STATUS; do
	TIMESTAMP=$(date +"%d-%m-%Y %H:%M:%S")
	# Remove quotes from the ID and NAME variables
	ID=$(echo "$ID" | tr -d '"')
	NAME=$(echo "$NAME" | tr -d '"')

	# Skip the header line
	if [ "$ID" == "id" ]; then
		continue
	fi

	# Check if ID filtering is applied and if this ID should be processed
	if [ ${#ID_FILTER[@]} -ne 0 ] && [[ ! " ${ID_FILTER[@]} " =~ " $ID " ]]; then
		echo "$TIMESTAMP | $NAME | $ID | $STATUS : Skipping (not in ids)" >>"$LOG_FILE"
		continue
	fi
	   
	IS_EXCLUDED=false
    if [ "$ACTION" == "pause" ] && [ -f "$EXCLUSIONS_FILE" ]; then
        # Using grep (simpler, less robust than jq)
        # Checks if the ID exists surrounded by quotes in the JSON file
        if grep -q "\"$ID\"" "$EXCLUSIONS_FILE"; then
            IS_EXCLUDED=true
        fi
        # Alternative using jq (more robust, needs jq installed)
        # if jq -e --arg id "$ID" '. | index($id) != null' "$EXCLUSIONS_FILE" > /dev/null; then
        #    IS_EXCLUDED=true
        # fi
    fi

	if $IS_EXCLUDED; then
         echo "$TIMESTAMP | $NAME | $ID | $STATUS : Skipping pause (found in $EXCLUSIONS_FILE)" >> "$LOG_FILE"
         continue # Skip to the next iteration
    fi

	# Construct the full URL
	echo "$TIMESTAMP | $NAME | $ID | $STATUS : ${ACTION}..." >>"$LOG_FILE"
	FULL_URL="${URL_PREFIX}/${ID}/actions/${ACTION}/"

	# Perform the API call
	RESPONSE=$(curl -X 'POST' \
		"$FULL_URL" \
		-H 'accept: application/json;Compute' \
		-H "authorization: $API_TOKEN" \
		-H "Content-Type: application/json;$ACTION" \
		-H "X-CSRFTOKEN: $CSRF_TOKEN" \
		-d '{}')

	# Check if the response contains an error
	if echo "$RESPONSE" | grep -q '"code":400'; then
		echo "$TIMESTAMP | $NAME | $ID | $STATUS : Success ${ACTION_DESCRIPTION}" >> "$LOG_FILE"
		echo "$TIMESTAMP | $NAME | $ID | $STATUS : $RESPONSE" >>"$LOG_FILE"
	else
		echo "$TIMESTAMP | $NAME | $ID | $STATUS : Success ${ACTION_DESCRIPTION}" >> "$LOG_FILE"
	fi
	sleep 1

done < "$DATADIR/output.csv"

echo "Finished ${ACTION_DESCRIPTION} all workspaces"
