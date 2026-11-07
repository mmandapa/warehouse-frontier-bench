"""Reference preflight: the model endpoint is reachable, external data is blocked."""
import urllib.error
import urllib.request

def status(url):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, method='HEAD'), timeout=10) as response:
            return response.status
    except urllib.error.HTTPError as exc:
        return exc.code
    except urllib.error.URLError:
        return 'blocked'

api = status('https://api.openai.com/v1/models')
external = status('https://archive.ics.uci.edu/')
print(f'Unauthenticated API endpoint status: {api}; external-data endpoint status: {external}', flush=True)
if api != 401:
    raise RuntimeError('Model endpoint is not reachable as expected')
if external not in (403, 'blocked'):
    raise RuntimeError('External data endpoint is unexpectedly reachable')
