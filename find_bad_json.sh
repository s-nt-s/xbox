#!/bin/bash
cd "$(dirname "$0")"

if [ ! -d ./rec ]; then
    exit 0
fi

find ./rec -type f -name "*.json" -exec sh -c '
    for file do
        if ! jq -e . >/dev/null 2>&1 "$file"; then
            echo "$(realpath $file)" | tee "$0.log"
        fi
    done
' sh {} +