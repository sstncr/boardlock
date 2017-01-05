#!/usr/bin/env python3
import os
import sys
import threading
import signal
import time

try:
    import simplejson as json
except:
    import json

import lockservice.server as sockserver

def handler(signal, frame):
    print("Caught signal {} - cleanup and exit...".format(signal))
    raise SystemExit()

def main(configfile):

    with open(configfile) as f:
        config = json.load(f)
    host = config["host"]
    port = config["port"]

    server = sockserver.ThreadedTCPServer((host, port), sockserver.ThreadedRequestHandler, config)
    signal.signal(signal.SIGTERM, handler)
    signal.signal(signal.SIGINT, handler)

    try:
        server.serve_forever(5)
    except SystemExit:
        print("Close server socket...")
        server.__shutdown_request = True
        server.server_close()
        raise

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: {} <config.json>".format(sys.argv[0]))
        sys.exit(1)
    main(sys.argv[1])
