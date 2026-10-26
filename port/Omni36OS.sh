#!/bin/bash
# Omni36OS: atalho para o launcher de verdade (omni36os/launch.sh). Ver Ajuda > Mostrar no console.
exec bash "$(dirname "$(readlink -f "$0")")/omni36os/launch.sh"
