#!/bin/bash
# Sab: atalho para o launcher de verdade (sab/launch.sh). Ver Ajuda > Mostrar no ES.
exec bash "$(dirname "$(readlink -f "$0")")/sab/launch.sh"
