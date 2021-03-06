"""Utilities nicked from python's unit tests"""
from six.moves import urllib

class MockFile(object):
    """Mock file object returned by MockSocket.makefile()."""
    def __init__(self, lines):
        self.lines = lines
        self.closed = False
        self.writes = []

    def readline(self, size=None):
        try:
            line = self.lines.pop(0) + b'\r\n'
            return line
        except IndexError:
            # Python 3 doesn't stop until it sees something like this, so None
            # is no good there.
            return b'\r\n'

    def write(self, data):
        self.writes.append(data)

    def close(self):
        self.closed = True

    def flush(self):
        pass

class MockSocket(object):
    """Mock socket object used by smtpd and smtplib tests."""
    def __init__(self, lines=None):
        self.output = []
        self.lines = []
        if lines:
            self.lines.extend(lines)
        self.conn = None
        self.timeout = None
        self.files = []

    def queue_recv(self, line):
        self.lines.append(bytes(line.encode("latin-1")))

    def recv(self, bufsize, flags=None):
        data = self.lines.pop(0) + b'\r\n'
        return data

    def fileno(self):
        return 0

    def settimeout(self, timeout):
        if timeout is None:
            self.timeout = _defaulttimeout
        else:
            self.timeout = timeout

    def gettimeout(self):
        return self.timeout

    def setsockopt(self, level, optname, value):
        pass

    def getsockopt(self, level, optname, buflen=None):
        return 0

    def bind(self, address):
        pass

    def accept(self):
        self.conn = MockSocket()
        return self.conn, 'c'

    def getsockname(self):
        return ('0.0.0.0', 0)

    def setblocking(self, flag):
        pass

    def listen(self, backlog):
        pass

    def makefile(self, mode='r', bufsize=-1):
        handle = MockFile(self.lines)
        self.files.append(handle)
        return handle

    def sendall(self, buffer, flags=None):
        self.last = data
        self.output.append(data)
        return len(data)

    def send(self, data, flags=None):
        self.last = data
        self.output.append(data)
        return len(data)

    def getpeername(self):
        return 'peer'

    def close(self):
        pass

def dump_page(*url_parts):
    """Test an HTTP connection to the page and ignore some errors.  Basically
    just asserts that the networking part of the server works."""
    url = urllib.parse.urljoin(*url_parts)
    return urllib.request.urlopen(url).read()
