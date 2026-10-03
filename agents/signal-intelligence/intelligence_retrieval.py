"""Original-passage retrieval shared by all intelligence interfaces."""
from __future__ import annotations


def chunk_text(source: str, *, size: int = 1600, overlap: int = 160) -> list[dict]:
    if size < 200 or not 0 <= overlap < size:
        raise ValueError('Invalid chunk bounds')
    chunks, start, heading = [], 0, ''
    while start < len(source):
        end = min(start + size, len(source))
        if end < len(source):
            boundary = source.rfind('\n\n', start + size // 2, end)
            if boundary >= 0:
                end = boundary + 2
        passage = source[start:end]
        for line in passage.splitlines():
            if line.startswith('#'):
                heading = line.lstrip('#').strip()[:300]
        chunks.append(dict(text=passage, start=start, end=end, heading=heading))
        if end == len(source):
            break
        start = end - overlap
    return chunks

from intelligence_embeddings import validate_vectors
from memory.knowledge import KnowledgeStore


class KnowledgeService:
    def __init__(self, engine, *, embedder=None,chunk_size=1600,chunk_overlap=160):
        if not 200<=chunk_size<=1600 or not 0<=chunk_overlap<chunk_size:
            raise ValueError('Invalid chunk bounds')
        self.chunk_size,self.chunk_overlap=chunk_size,chunk_overlap
        chunker=f'paragraph-{chunk_size}-{chunk_overlap}-v1'
        self.store=KnowledgeStore(engine,chunker)
        self.embedder=embedder
        self.config=(embedder.config if embedder else 'lexical-v1')+':'+chunker

    def status(self):
        return dict(self.store.status(self.config),embedding_available=self.embedder is not None)

    def index_pending(self, *, limit=2):
        if not 1<=limit<=4:
            raise ValueError('Index batch must contain 1–4 documents')
        done,failed=0,0
        for doc in self.store.pending(self.config,self.embedder is not None,limit):
            try:
                chunks=chunk_text(doc['body'],size=self.chunk_size,overlap=self.chunk_overlap)
                vectors=None
                if self.embedder:
                    inputs=[doc['title'][:300]+'\n'+c['text'] for c in chunks]
                    vectors=[]
                    for i in range(0,len(inputs),16):
                        vectors.extend(validate_vectors(self.embedder.embed(inputs[i:i+16]),len(inputs[i:i+16])))
                done+=int(self.store.commit_index(doc,chunks,vectors,self.config))
            except RuntimeError:
                self.store.fail(doc)
                failed+=1
        return dict(self.status(),indexed=done,batch_failed=failed)

    def search(self, query, *, opportunity_id=None, research_id=None,purpose='comparison',persist=True):
        if not isinstance(query,str) or not query.strip() or len(query)>1200:
            raise ValueError('Query must contain 1–1200 characters')
        status=self.status()
        mode='lexical'
        vector=None
        if self.embedder:
            try:
                vector=validate_vectors(self.embedder.embed([query],query=True),1)[0]
                mode='hybrid'
            except RuntimeError:
                mode='lexical-provider-unavailable'
        lexical,semantic=self.store.candidates(query,self.config,vector,research_id)
        by_id={}
        for channel in (lexical,semantic):
            for rank,hit in enumerate(channel,1):
                existing=by_id.setdefault(hit['chunk_id'],dict(hit,score=0.0))
                existing['score']+=1/(60+rank)
        selected,per_document=[],{}
        chars=0
        for hit in sorted(by_id.values(),key=lambda h:(-h['score'],h['chunk_id'])):
            count=per_document.get(hit['document_id'],0)
            if count>=2 or len(selected)>=8 or chars+len(hit['passage'])>10000:
                continue
            selected.append(hit);chars+=len(hit['passage']);per_document[hit['document_id']]=count+1
        eligible=[d for d in status['documents'] if (d['content_id'] is not None if research_id is None else d['research_run_id']==research_id)]
        ready=sum(d['semantic_ready'] if mode=='hybrid' else d['chunks_ready'] for d in eligible)
        coverage=ready/len(eligible) if eligible else 0.0
        if not persist:
            return dict(id=None,hits=selected,mode=mode,coverage=coverage,corpus_revision=status['revision'],config=self.config)
        return self.store.save_retrieval(query,selected,purpose=purpose,mode=mode,coverage=coverage,
          revision=status['revision'],config=self.config+':rrf60-cutoff055-top8-v1',opportunity_id=opportunity_id,research_id=research_id)

    def get_retrieval(self,id):
        return self.store.get_retrieval(id)
