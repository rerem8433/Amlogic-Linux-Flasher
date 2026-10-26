#!/bin/sh
echo "$(basename "$0") $*"
case "$*" in
  "devices -l") echo "0123456789ABCDEF   fastboot";;
  "getvar unlocked") echo "unlocked: yes" >&2;;
esac
