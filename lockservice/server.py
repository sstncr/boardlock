import os
import sys
import socket
import threading
import socketserver
import time
import enum

from lockservice.common import SocketConnectionHelper
from lockservice.common import ResponseStatus, RequestCmds

class ThreadedRequestHandler(socketserver.BaseRequestHandler):

    def setup(self):
        self.connection = SocketConnectionHelper(self.request)

        cur_thread = threading.current_thread()
        self.client_key = cur_thread.name.replace("-","")

        self.connection_info = "{}: {}:{}".format(cur_thread.name, self.client_address[0], self.client_address[1])
        print("{}: Connected".format(self.connection_info))

        self.board = None
        self.properties = None

    def send(self, data):
        self.connection.send(data)
        print("{}: Sent:{}".format(self.connection_info, data))

    def recv(self):
        data = self.connection.recv()
        if data:
            # if data is empty it means socket was closed by remote
            # don't print
            print("{}: Received:{}".format(self.connection_info, data))
        return data

    def search_props(self):
        found = False
        devices = self.server.config["boards"][self.board]["devices"]
        for i, device in enumerate(devices):
            props = set(self.properties)
            if props.issubset(set(device["properties"])):
                found = True
                break
        return found


    def lock_device(self, payload):
        serial = None

        board, *properties = payload.split()
        self.board = board
        self.properties = properties

        if properties:
            found = self.search_props()
            if not found:
                raise Exception("No board with the requested properties exists...")

        self.add_to_queue()

        if self.next_in_queue():
            with self.server.lock:
                devices = self.server.config["boards"][board]["devices"]
                for i, device in enumerate(devices):
                    if device["status"] == "unlocked":
                        if properties:
                            props = set(properties)
                            if props.issubset(set(device["properties"])):
                                serial = device["serial"]
                                device["status"] = "locked"
                                break
                        else:
                            serial = device["serial"]
                            device["status"] = "locked"
                            break
            if serial:
                self.remove_from_queue()

        return serial

    def unlock_device(self, payload):
        board, serial = payload.split()
        with self.server.lock:
            old_status_ok = False
            devices = self.server.config["boards"][board]["devices"]
            for i, device in enumerate(devices):
                if device["serial"]  == serial:
                    if device["status"] == "locked":
                        old_status_ok = True
                        device["status"] = "unlocked"
                    break
        return old_status_ok

    def handle(self):

        while True:
            data = self.recv()
            if not data:
                 break
            try:
                cmd, payload = data.split(" ", 1)
                if cmd == RequestCmds.LOCK:
                    serial = self.lock_device(payload)
                    if serial:
                        self.send(ResponseStatus.OK)
                        self.send(serial)
                    else:
                        self.send(ResponseStatus.RETRY)
                        index = self.get_queue_index()
                        self.send(index)

                elif cmd == RequestCmds.UNLOCK:
                    status = self.unlock_device(payload)
                    if status:
                        self.send(ResponseStatus.OK)
                    else:
                        self.send(ResponseStatus.WARN)

                else:
                    self.send(ResponseStatus.BAD)
                    self.send("Unknown command: {}".format(cmd))
                    break

            except (IndexError, ValueError, KeyError) as e:
                self.send(ResponseStatus.BAD)
                self.send("Data format wrong: {}".format(e))
                # we raise the exception here since it will be logged
                # in base class without raising it again
                raise
            except Exception as e:
                self.send(ResponseStatus.ERROR)
                self.send(e)
                raise

    def add_to_queue(self):
        with self.server.queue_lock:
            if self.board in self.server.queue and self.client_key not in self.server.queue[self.board]:
                    self.server.queue[self.board].append(self.client_key)
                    if not self.properties:
                        if self.client_key not in self.server.queue_noprops[self.board]:
                            self.server.queue_noprops[self.board].append(self.client_key)


    def remove_from_queue(self):
        with self.server.queue_lock:
            if self.board and self.board in self.server.queue:
                for i in self.server.queue[self.board]:
                    if self.client_key in self.server.queue[self.board]:
                        self.server.queue[self.board].remove(self.client_key)
                    if self.client_key in self.server.queue_noprops[self.board]:
                        self.server.queue_noprops[self.board].remove(self.client_key)

    def next_in_queue(self):
        with self.server.queue_lock:
            is_next = True
            if self.board in self.server.queue and self.server.queue[self.board]:
                if self.properties:
                    if self.client_key != self.server.queue[self.board][0]:
                        is_next = False
                else:
                    if self.client_key != self.server.queue_noprops[self.board][0]:
                        is_next = False
        return is_next

    def get_queue_index(self):
        with self.server.queue_lock:
            index = self.server.queue[self.board].index(self.client_key) + 1
        return index

    def finish(self):
        self.remove_from_queue()

class ThreadedTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, server_address, RequestHandlerClass, config, bind_and_activate=True):
        self.config = config
        self.lock = threading.Lock()
        self.init_queue()
        socketserver.TCPServer.__init__(self, server_address, RequestHandlerClass, bind_and_activate=True)

    def init_queue(self):
        self.queue_lock = threading.Lock()
        self.queue = {}
        self.queue_noprops = {}
        for board in self.config["boards"]:
            self.queue[board] = []
            self.queue_noprops[board] = []
