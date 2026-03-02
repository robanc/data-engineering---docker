#!/usr/bin/env bash
set -e

if [ -z "$1" ] || [ -z "$2" ]; then
  echo "Usage: $0 <taxi_type> <year>"
  exit 1
fi

TAXI_TYPE=$1
YEAR=$2

URL_PREFIX="https://github.com/DataTalksClub/nyc-tlc-data/releases/download"

for MONTH in {1..12}; do
  FMONTH=$(printf "%02d" ${MONTH})

  URL="${URL_PREFIX}/${TAXI_TYPE}/${TAXI_TYPE}_tripdata_${YEAR}-${FMONTH}.csv.gz"

  LOCAL_PREFIX="data/raw/${TAXI_TYPE}/${YEAR}/${FMONTH}"
  LOCAL_FILE="${TAXI_TYPE}_tripdata_${YEAR}_${FMONTH}.csv.gz"
  LOCAL_PATH="${LOCAL_PREFIX}/${LOCAL_FILE}"

  mkdir -p ${LOCAL_PREFIX}

  if [ -f "${LOCAL_PATH}" ]; then
    echo "${LOCAL_PATH} exists, skipping..."
  else
    echo "Downloading ${URL}"
    wget ${URL} -O ${LOCAL_PATH}
  fi
done
