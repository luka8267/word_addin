from api._bunken_vercel import BunkenHandler, handle_documents_citations


class handler(BunkenHandler):
    def do_OPTIONS(self):
        self.options_response()

    def do_GET(self):
        try:
            handle_documents_citations(self)
        except Exception as error:
            self.handle_error(error)
