import socket
import time

from lockservice.common import SocketConnectionHelper
from lockservice.common import RequestCmds, ResponseStatus

class SockClient:

    def __init__(self, host, port):
        self.host = host
        self.port = port

    def connect(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((self.host, self.port))
        self.connection = SocketConnectionHelper(self.sock)

    def close(self):
        self.sock.shutdown(socket.SHUT_RDWR)
        self.sock.close()

    def send(self, data):
        self.connection.send(data)
        print("Sent:{}".format(data))

    def recv(self):
        data = self.connection.recv()
        print("Received:{}".format(data))
        return data


class LockClient(SockClient):

    def lock(self, payload, timeout=0):
        self.send("{} {}".format(RequestCmds.LOCK, payload))
        response = self.recv()
        start_time = time.time()
        time_factor = 1
        while response == ResponseStatus.RETRY:
            time_factor = int(self.recv())
            if timeout:
                if time.time() > start_time + time_factor * timeout:
                    raise Exception("Timed out while waiting for an available device...")
            time.sleep(time_factor * 10)
            self.send("{} {}".format(RequestCmds.LOCK, payload))
            response = self.recv()
        if response == ResponseStatus.OK:
            # get the actual serial
            serial = self.recv()
            return serial
        elif response == ResponseStatus.WARN:
            # for lock this should never happen...
            raise NotImplemented()
        else:
            # here it can only be BAD and ERROR
            content = self.recv()
            raise Exception("{}\n{}".format(response, content))

    def unlock(self, payload):
        self.send("{} {}".format(RequestCmds.UNLOCK, payload))
        response = self.recv()
        if response == ResponseStatus.RETRY:
            # for unlock this should never happen...
            raise NotImplemented()
        if response == ResponseStatus.OK:
            print("Device unlocked")
        elif response == ResponseStatus.WARN:
            print("Warning: device already unlocked...")
        else:
            content = self.recv()
            raise Exception("{}\n{}".format(response, content))
