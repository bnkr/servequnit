import logging, os, re, posixpath, errno
from six.moves import urllib
from six.moves import SimpleHTTPServer as http_server

SimpleHTTPRequestHandler = http_server.SimpleHTTPRequestHandler

QUNIT_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{title}</title>
{head}
</head>
<body>
  <div id="qunit"></div>
  <div id="qunit-fixture"></div>
</body>
</html>\n"""

class QunitRequestHandler(SimpleHTTPRequestHandler):
    """
    Three ways to use this (pretty much).

    * set doc root and use static files to reference whatever on the local
      filesystem.
    * configure libraries and use /unit/ to reference tests relative to the test
      root.
    * configure libraries including your test and use a view which just displays
      those files.

    Api:

    * /test/ -- a test runner with all the css and scripts.
    * /test/path -- as above which also adds a js file from the test root (using
      the /unit thing).
    * /read/ -- output data bound from a filesystem path.
    * /unit/ -- test js.
    * /static/ -- arbitrary file which comes from the doc root.
    """

    def _get_settings(self):
        """For some reason we can't store this in the constructor."""
        return self.server.get_handler_settings()

    def get_handlers(self):
        return (
            ('/shutdown/', self._respond_stop,),
            ('/test/', self._respond_test,),
            ('/static/', self._respond_static,),
            ('/unit/', self._respond_unit,),
            ('/read/', self._respond_read,),
            ('/favicon.ico', self._respond_favicon,),
        )

    def do_GET(self):
        """Url parsing, basically."""
        prefix_handlers = self.get_handlers()
        for prefix, handler in prefix_handlers:
            if self.path.startswith(prefix):
                handler()
                return

        allowed_paths = [prefix for (prefix, _) in prefix_handlers]
        error = "prefix must be one of {0!r}".format(allowed_paths)
        self._respond_404(error)

    def _respond_favicon(self):
        """Avoid spammy log messages."""
        self._respond("No favicon.", status=404, content_type="text/plain")

    def _respond_read(self):
        content = self._get_settings().bound_content() or []
        suffix = self.path[len("/read/"):]
        for url, path in content:
            if url == suffix:
                self._cat_file(path)
                return

        self._respond_404("no file bound for {0!r}".format(suffix))

    def _respond_static(self):
        settings = self._get_settings()
        self._respond_from_filesystem(relative_to=os.getcwd(),
                                      prefix="/static/")

    def _respond_unit(self):
        settings = self._get_settings()
        self._respond_from_filesystem(relative_to=settings.test_root(),
                                      prefix="/unit/")

    def _respond_default_case(self):
        default = self._get_settings().default_test()
        if default:
            self._cat_file(default)
        else:
            self._respond_404("no default case configured")

    def _respond_stop(self):
        self._respond("Server will shut down after this request.\n")
        # Causes an error later but does actually shut down.
        self.server.socket.close()

    def _respond_test(self):
        """Respond with the test runner containing all scripts and css
        specified, plus an additional link to the test case if the url specifies
        one."""
        scripts = self._get_test_scripts()
        if scripts is None:
            return
        self._respond_runner(scripts)

    def _get_test_scripts(self):
        settings = self._get_settings()
        test_name = self.path[len("/test/"):]
        if test_name:
            case = "/unit/{0}".format(test_name)
            if not settings.test_root():
                self._respond_404("no test root to serve named test from")
                return None

            # TODO:
            #   append .js if none already -- ideally we visit test/case-name so
            #   it's clear it's html
            local = self._get_local_path(path=case, prefix="/unit/",
                                         relative_to=settings.test_root(),)
            if not os.path.exists(local):
                message = "test case {1!r} (maps to {0!r}): does not exist"
                self._respond_404(message.format(local, case))
                return None

            return [case]
        else:
            return []

    def _respond_runner(self, extra_scripts=None):
        """A runner with some scripts in it."""
        extra_scripts = extra_scripts or []

        def link_js(source):
            return '<script type="text/javascript" src="{0}"></script>'.format(source)

        def link_css(source):
            return '<link rel="stylesheet" type="text/css" href="{0}">'.format(source)

        # TODO:
        #   Would be nice to check that these things will actually return a
        #   response...
        scripts = \
            ["http://code.jquery.com/qunit/qunit-1.12.0.js"] + \
            self._get_settings().scripts() + extra_scripts
        css = ["http://code.jquery.com/qunit/qunit-1.12.0.css"] + \
               self._get_settings().styles()

        tags = [link_js(name) for name in scripts]
        tags += [link_css(name) for name in css]

        context = {
            'title': "Qunit Test Case",
            'head': "\n".join(tags),
        }
        self._respond(QUNIT_HTML.format(**context).encode("utf-8"))

    def _respond_from_filesystem(self, prefix, relative_to):
        local = self._get_local_path(path=self.path, prefix=prefix,
                                     relative_to=relative_to)
        self._cat_file(local)

    def _respond_error(self, message, status):
        why = "{0}: {1}\n".format(status, message)
        self._respond(why, status=status, content_type="text/plain")

    def _respond_404(self, why, translated_path=None):
        message = "{0!r}".format(self.path)
        if translated_path:
            message += " (maps to {0!r}): ".format(translated_path)
        else:
            message += ": "
        message += "{0}".format(why)
        self._log("404: {0}", message)
        self._respond_error(message, status=404)

    def _respond(self, content, status=200, content_type='text/html'):
        self.send_response(status)
        self.send_header('Content-type', content_type + "; charset=utf-8")
        self.end_headers()
        self.wfile.write(content)

    def _get_local_path(self, path, relative_to, prefix=None):
        """Map a url onto some base directory."""
        if prefix:
            path = path[len(prefix):]
        path = path.split('?',1)[0]
        path = path.split('#',1)[0]
        path = posixpath.normpath(urllib.parse.unquote(path))
        words = path.split('/')
        words = [word for word in words if word]
        path = relative_to
        for word in words:
            drive, word = os.path.splitdrive(word)
            head, word = os.path.split(word)
            if word in (os.curdir, os.pardir): continue
            path = os.path.join(path, word)
        return path

    def _cat_file(self, path):
        if os.path.isdir(path):
            self._respond_404("is a directory", path)
            return

        try:
            # Always read in binary mode. Opening files in text mode may cause
            # newline translations, making the actual size of the content
            # transmitted *less* than the content-length!
            io = open(path, 'rb')
        except IOError as ex:
            if ex.errno == errno.ENOENT:
                self._respond_404("does not exist", path)
            else:
                self._respond_404(str(ex), path)
            return None

        try:
            self.send_response(200)
            self.send_header("Content-type", self.guess_type(path))
            stat = os.fstat(io.fileno())
            self.send_header("Content-Length", str(stat[6]))
            self.send_header("Last-Modified", self.date_time_string(stat.st_mtime))
            self.end_headers()
            self.copyfile(io, self.wfile)
        finally:
            io.close()

    def log_error(self, format, status, description):
        """We're already sending all requests to the log so no need to do
        anything more for errors."""
        pass

    def log_message(self, format, *args):
        self._log("{0} {1} {2}", *args)

    def _log(self, message, *args, **kw):
        logging.getLogger(__name__).info(message.format(*args, **kw))
