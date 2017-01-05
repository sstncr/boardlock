import socket
import struct

class RequestCmds:
    LOCK = 'LOCK'
    UNLOCK = 'UNLOCK'

class ResponseStatus:
    OK = 'OK'
    WARN = 'Warning'
    BAD = 'Bad Request'
    ERROR = 'Error'
    RETRY = 'Retry'

class SocketConnectionHelper:

    def __init__(self, sock):
        self.sock = sock

    def send(self, data):
        data = str(data)
        data = data.encode()
        # Prefix each message with a 4-byte length (network byte order)
        self.sock.sendall(struct.pack('>I', len(data)))
        self.sock.sendall(data)

    def recv(self):
        # Read message length and unpack it into an integer
        lenbuf = self._recvall(4)
        if not lenbuf:
            return ''
        msglen, = struct.unpack('>I', lenbuf)
        # Read the message data
        data = self._recvall(msglen)
        return data.decode()

    def _recvall(self, n):
        # Helper function to recv n bytes or break if EOF is hit
        data = b''
        while len(data) < n:
            packet = self.sock.recv(min(16384, n - len(data)))
            if not packet:
                break
            data += packet
        return data
