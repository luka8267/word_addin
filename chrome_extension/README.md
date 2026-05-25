# bunken Web Importer

Load this folder as a Chrome or Brave Manifest V3 extension. It extracts citation metadata from the active paper page and saves it to bunken through the Vercel API.

## Local loading

1. Open `chrome://extensions` or `brave://extensions`.
2. Enable Developer mode.
3. Choose Load unpacked and select this `chrome_extension` folder.
4. Open the popup, enter the Vercel API URL and bunken app URL, then sign in with the same Supabase account used by bunken.
5. Open a paper page and click Save to bunken.

## Saved data

- title, authors, journal, year, DOI, URL, abstract
- `citation_pdf_url` and PDF-like links found on the page
- DOI or title/year duplicates are treated as existing records and are not inserted again.
- Fetchable PDF candidates are uploaded to the `paper-pdfs` Storage bucket and linked through `attachments`.
- If the PDF cannot be fetched by the API, the popup shows the first PDF candidate and provides an Open bunken app button for manual upload from the paper detail pane.
- Some publishers such as ACS can block server-side PDF fetches with Cloudflare or institutional-login checks. In that case, use Open PDF candidate in the extension, download the PDF in the browser, then upload it from the bunken paper detail pane.
- The extension stores a Supabase refresh token after sign-in, so you should not need to enter your password every time.

