"""Key-safe, bounded Gemini embedding transport with explicit vector-space identity."""
from __future__ import annotations
import json
import math
import re
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

DIMENSIONS = 768


def validate_vectors(vectors, count):
    try:
        if len(vectors) != count:
            raise ValueError
        result = []
        for vector in vectors:
            if len(vector) != DIMENSIONS or any(isinstance(x, bool) for x in vector):
                raise ValueError
            values = [float(x) for x in vector]
            if not all(math.isfinite(x) for x in values):
                raise ValueError
            norm = math.sqrt(sum(x*x for x in values))
            if norm <= 0:
                raise ValueError
            result.append([x/norm for x in values])
        return result
    except (TypeError, ValueError, OverflowError):
        raise RuntimeError('Invalid embedding response') from None


class GeminiEmbedder:
    def __init__(self, key, model='gemini-embedding-2'):
        if not key or not re.fullmatch(r'[A-Za-z0-9._-]+', model):
            raise ValueError('Embedding credentials and valid model required')
        self.key, self.model = key, model
        self.config = f'{model}:768:retrieval-prefix-v1'

    def embed(self, texts, *, query=False):
        if not texts or len(texts) > 16 or any(len(t) > 2400 for t in texts):
            raise ValueError('Embedding request exceeds bounds')
        prefix = 'task: search result | query: ' if query else 'title and text: '
        requests = [{'model': f'models/{self.model}', 'content': {'parts': [{'text': prefix+t}]},
                     'outputDimensionality': DIMENSIONS} for t in texts]
        request = Request(f'https://generativelanguage.googleapis.com/v1beta/models/{self.model}:batchEmbedContents',
                          data=json.dumps({'requests': requests}).encode(),
                          headers={'Content-Type':'application/json', 'x-goog-api-key':self.key}, method='POST')
        try:
            with urlopen(request, timeout=25) as response:
                payload = json.loads(response.read(2_000_000))
            return validate_vectors([item['values'] for item in payload['embeddings']], len(texts))
        except (HTTPError, URLError, TimeoutError, OSError, KeyError, ValueError, TypeError):
            raise RuntimeError('Embedding provider unavailable; check access and quota') from None
