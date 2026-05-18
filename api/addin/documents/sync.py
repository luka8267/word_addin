from api._bunken_vercel import BunkenHandler, handle_documents_sync


class handler(BunkenHandler):
    def do_OPTIONS(self):
        self.options_response()

    def do_POST(self):
        try:
            handle_documents_sync(self)
        except Exception as error:
            self.handle_error(error)
