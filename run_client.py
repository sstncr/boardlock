#!/usr/bin/env python3

import os
import sys
import socket
import subprocess
import time
import signal
import argparse

import lockservice.client as sockclient

HOST = "127.0.0.1"
PORT = 9999

def signal_handler(signal, frame):
    print("\nCaught signal {}".format(signal))
    raise SystemExit(signal)

def start_proc(script, board, serial, extra_args):
    cmd = "{} {} {}".format(script, board, serial).split()
    cmd += extra_args
    print("[RUNNING]:$ {}".format(cmd))
    proc = subprocess.Popen(cmd, preexec_fn=os.setsid)
    return proc

def clean_proc(proc):
    try:
        if proc:
            if proc.returncode == None:
                pid = os.getpgid(proc.pid)
                os.killpg(pid, signal.SIGTERM)
                time.sleep(2)
                try:
                    os.killpg(pid, signal.SIGKILL)
                except OSError:
                    pass
                else:
                    print("Subprocess killed")
                proc.communicate()
    except Exception as e:
        print("Unhandled exception while cleaning up: {}".format(e))

def main(args):

    host = args.host
    port = args.port
    timeout = args.timeout
    lock_timeout = args.lock_timeout
    board = args.board
    properties = args.properties
    script = args.script
    extra_args = args.extra_args

    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    client = sockclient.LockClient(host, port)
    client.connect()

    lock_payload = board
    if properties:
        lock_payload += " " + properties
    serial = client.lock(lock_payload, lock_timeout)

    unlock_payload = board + " " + serial

    try:
        proc = start_proc(script, board, serial, extra_args)
        proc.communicate(timeout=timeout)
        ret = proc.returncode
    except subprocess.TimeoutExpired:
        print("\nSubprocess timed out.")
        clean_proc(proc)
        ret = 1
    except Exception as e:
        clean_proc(proc)
        ret = 1
        raise
    except SystemExit:
        print("Cleanup and exit...")
        clean_proc(proc)
        raise
    finally:
        client.unlock(unlock_payload)
        client.close()

    sys.exit(ret)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('--host', default=HOST,
            help='Hostname where the boardlock daemon is running')
    parser.add_argument('--port', type=int, default=PORT,
            help='Port for the daemon')
    parser.add_argument('--timeout', required=True, type=int,
            help='Timeout for running the subprocess')
    parser.add_argument('--lock-timeout', type=int, default=0,
            help='Timeout for aquiring a lock. This will be multiplied by the number of clients in the queue.')
    parser.add_argument('--board', required=True, type=str,
            help='Board name for which to lock a device')
    parser.add_argument('--properties', type=str, default='',
            help='Space separated strings of required board properties. E.g --properties "pts wifi"')
    parser.add_argument('--script', required=True, type=str,
            help='Script or command to run')
    parser.add_argument('extra_args', metavar="<passthrough arguments>", nargs="+",
            help='Extra arguments to pass to real script')
    args = parser.parse_args()
    main(args)
