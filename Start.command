#!/bin/sh
cd "$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)" || exit 1
if ! python3 -c 'import sys; assert sys.version_info >= (3, 11)' 2>/dev/null; then
  echo 'Please install Python 3.11 or newer from https://www.python.org/downloads/'
  echo 'Установите Python 3.11 или новее и запустите этот файл снова.'
  read -r answer
  exit 1
fi
python3 -m gtnh_migrator
