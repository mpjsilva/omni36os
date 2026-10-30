#!/bin/bash
# Omni36OS: atalho para o launcher de verdade (omni36os/launch.sh).
exec bash "$(dirname "$(readlink -f "$0")")/omni36os/launch.sh"
