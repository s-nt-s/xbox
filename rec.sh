#!/bin/bash
rm -rf rec/
mkdir rec/
cd rec/
curl -q https://s-nt-s.github.io/xbox/json.tar.xz | tar -xJ
find . -type f -exec touch '{}' \;

