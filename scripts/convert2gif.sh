#!/usr/bin/env bash

set -e

[[ -e "${1%.*}.gif" ]] && rm -f "${1%.*}.gif"
[[ -e "${1%.*}.png" ]] && rm -f "${1%.*}.png"

ffmpeg -i "$1" -vf "palettegen" -y "${1%.*}.png"
ffmpeg -i "$1" -i "${1%.*}.png" -r "$2" -y "${1%.*}.gif"

