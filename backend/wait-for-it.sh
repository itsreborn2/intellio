#!/bin/bash
# wait-for-it.sh

WAITFORIT_cmdname=${0##*/}

echoerr() { if [[ $WAITFORIT_QUIET -ne 1 ]]; then echo "$@" 1>&2; fi }

usage()
{
    cat << USAGE >&2
Usage:
    $WAITFORIT_cmdname host:port [-s] [-t timeout] [-- command args]
    -h HOST | --host=HOST       Host or IP under test
    -p PORT | --port=PORT       TCP port under test
    -s | --strict               Only execute subcommand if the test succeeds
    -q | --quiet                Don't output any status messages
    -t TIMEOUT | --timeout=TIMEOUT
                                Timeout in seconds, zero for no timeout
    -- COMMAND ARGS             Execute command with args after the test finishes
USAGE
    exit 1
}

wait_for()
{
    local wait_host=$1
    local wait_port=$2
    local timeout=${3:-15}
    local quiet=${4:-0}
    local strict=${5:-0}

    if [[ $timeout -gt 0 ]]; then
        echoerr "$WAITFORIT_cmdname: waiting $timeout seconds for $wait_host:$wait_port"
    else
        echoerr "$WAITFORIT_cmdname: waiting for $wait_host:$wait_port without a timeout"
    fi

    local start_ts=$(date +%s)
    while :
    do
        (echo > /dev/tcp/$wait_host/$wait_port) >/dev/null 2>&1
        result=$?
        if [[ $result -eq 0 ]]; then
            end_ts=$(date +%s)
            echoerr "$WAITFORIT_cmdname: $wait_host:$wait_port is available after $((end_ts - start_ts)) seconds"
            break
        fi
        sleep 1
    done
    return $result
}

parse_arguments()
{
    local index=0
    while [[ $# -gt 0 ]]
    do
        case "$1" in
            *:* )
            WAITFORIT_hostport=(${1//:/ })
            WAITFORIT_HOST=${WAITFORIT_hostport[0]}
            WAITFORIT_PORT=${WAITFORIT_hostport[1]}
            shift 1
            ;;
            --host=*)
            WAITFORIT_HOST="${1#*=}"
            shift 1
            ;;
            --port=*)
            WAITFORIT_PORT="${1#*=}"
            shift 1
            ;;
            -q | --quiet)
            WAITFORIT_QUIET=1
            shift 1
            ;;
            -s | --strict)
            WAITFORIT_STRICT=1
            shift 1
            ;;
            -t)
            WAITFORIT_TIMEOUT="$2"
            if [[ $WAITFORIT_TIMEOUT == "" ]]; then break; fi
            shift 2
            ;;
            --timeout=*)
            WAITFORIT_TIMEOUT="${1#*=}"
            shift 1
            ;;
            --)
            shift
            WAITFORIT_CLI=("$@")
            break
            ;;
            --help)
            usage
            ;;
            *)
            echoerr "Unknown argument: $1"
            usage
            ;;
        esac
    done
}

WAITFORIT_TIMEOUT=${WAITFORIT_TIMEOUT:-15}
WAITFORIT_QUIET=${WAITFORIT_QUIET:-0}
WAITFORIT_STRICT=${WAITFORIT_STRICT:-0}
WAITFORIT_CLI=()

parse_arguments "$@"

if [[ "$WAITFORIT_HOST" == "" || "$WAITFORIT_PORT" == "" ]]; then
    echoerr "Error: you need to provide a host and port to test."
    usage
fi

wait_for "$WAITFORIT_HOST" "$WAITFORIT_PORT" "$WAITFORIT_TIMEOUT" "$WAITFORIT_QUIET" "$WAITFORIT_STRICT"
WAITFORIT_result=$?

if [[ $WAITFORIT_CLI != "" ]]; then
    if [[ $WAITFORIT_result -ne 0 && $WAITFORIT_STRICT -eq 1 ]]; then
        echoerr "$WAITFORIT_cmdname: strict mode, refusing to execute subprocess"
        exit $WAITFORIT_result
    fi
    exec "${WAITFORIT_CLI[@]}"
else
    exit $WAITFORIT_result
fi
