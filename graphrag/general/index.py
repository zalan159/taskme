#
#  Copyright 2024 The InfiniFlow Authors. All Rights Reserved.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#
import json
import logging
from functools import reduce, partial
import networkx as nx
import trio

from api import settings
from graphrag.general.community_reports_extractor import CommunityReportsExtractor
from graphrag.entity_resolution import EntityResolution
from graphrag.general.extractor import Extractor
from graphrag.general.graph_extractor import DEFAULT_ENTITY_TYPES
from graphrag.utils import graph_merge, set_entity, get_relation, set_relation, get_entity, get_graph, set_graph, \
    chunk_id, update_nodes_pagerank_nhop_neighbour
from rag.nlp import rag_tokenizer, search
from rag.utils.redis_conn import RedisDistributedLock


class Dealer:
    def __init__(self,
                 extractor: Extractor,
                 tenant_id: str,
                 kb_id: str,
                 llm_bdl,
                 chunks: list[tuple[str, str]],
                 language,
                 entity_types=DEFAULT_ENTITY_TYPES,
                 embed_bdl=None,
                 callback=None,
                 task_id=None
                 ):
        self.tenant_id = tenant_id
        self.kb_id = kb_id
        self.chunks = chunks
        self.llm_bdl = llm_bdl
        self.embed_bdl = embed_bdl
        self.ext = extractor(self.llm_bdl, language=language,
                        entity_types=entity_types,
                        get_entity=partial(get_entity, tenant_id, kb_id),
                        set_entity=partial(set_entity, tenant_id, kb_id, self.embed_bdl),
                        get_relation=partial(get_relation, tenant_id, kb_id),
                        set_relation=partial(set_relation, tenant_id, kb_id, self.embed_bdl),
                        task_id=task_id
                        )
        self.graph = nx.Graph()
        self.callback = callback

    async def __call__(self):
        docids = list(set([docid for docid, _ in self.chunks]))
        ents, rels = await self.ext(self.chunks, self.callback)
        for en in ents:
            self.graph.add_node(en["entity_name"], entity_type=en["entity_type"])#, description=en["description"])

        for rel in rels:
            self.graph.add_edge(
                rel["src_id"],
                rel["tgt_id"],
                weight=rel["weight"],
                #description=rel["description"]
            )

        with RedisDistributedLock(self.kb_id, 60*60):
            old_graph, old_doc_ids = get_graph(self.tenant_id, self.kb_id)
            if old_graph is not None:
                logging.info("Merge with an exiting graph...................")
                self.graph = reduce(graph_merge, [old_graph, self.graph])
            update_nodes_pagerank_nhop_neighbour(self.tenant_id, self.kb_id, self.graph, 2)
            if old_doc_ids:
                docids.extend(old_doc_ids)
                docids = list(set(docids))
            set_graph(self.tenant_id, self.kb_id, self.graph, docids)


class WithResolution(Dealer):
    def __init__(self,
                 tenant_id: str,
                 kb_id: str,
                 llm_bdl,
                 embed_bdl=None,
                 callback=None
                 ):
        self.tenant_id = tenant_id
        self.kb_id = kb_id
        self.llm_bdl = llm_bdl
        self.embed_bdl = embed_bdl
        self.callback = callback
    async def __call__(self):
        with RedisDistributedLock(self.kb_id, 60*60):
            self.graph, doc_ids = await trio.to_thread.run_sync(lambda: get_graph(self.tenant_id, self.kb_id))
            if not self.graph:
                logging.error(f"Faild to fetch the graph. tenant_id:{self.kb_id}, kb_id:{self.kb_id}")
                if self.callback:
                    self.callback(-1, msg="Faild to fetch the graph.")
                return

            if self.callback:
                self.callback(msg="Fetch the existing graph.")
            er = EntityResolution(self.llm_bdl,
                                  get_entity=partial(get_entity, self.tenant_id, self.kb_id),
                                  set_entity=partial(set_entity, self.tenant_id, self.kb_id, self.embed_bdl),
                                  get_relation=partial(get_relation, self.tenant_id, self.kb_id),
                                  set_relation=partial(set_relation, self.tenant_id, self.kb_id, self.embed_bdl))
            reso = await er(self.graph)
            self.graph = reso.graph
            logging.info("Graph resolution is done. Remove {} nodes.".format(len(reso.removed_entities)))
            if self.callback:
                self.callback(msg="Graph resolution is done. Remove {} nodes.".format(len(reso.removed_entities)))
            await trio.to_thread.run_sync(lambda: update_nodes_pagerank_nhop_neighbour(self.tenant_id, self.kb_id, self.graph, 2))
            await trio.to_thread.run_sync(lambda: set_graph(self.tenant_id, self.kb_id, self.graph, doc_ids))

        await trio.to_thread.run_sync(lambda: settings.docStoreConn.delete({
            "knowledge_graph_kwd": "relation",
            "kb_id": self.kb_id,
            "from_entity_kwd": reso.removed_entities
        }, search.index_name(self.tenant_id), self.kb_id))
        await trio.to_thread.run_sync(lambda: settings.docStoreConn.delete({
            "knowledge_graph_kwd": "relation",
            "kb_id": self.kb_id,
            "to_entity_kwd": reso.removed_entities
        }, search.index_name(self.tenant_id), self.kb_id))
        await trio.to_thread.run_sync(lambda: settings.docStoreConn.delete({
            "knowledge_graph_kwd": "entity",
            "kb_id": self.kb_id,
            "entity_kwd": reso.removed_entities
        }, search.index_name(self.tenant_id), self.kb_id))


class WithCommunity(Dealer):
    def __init__(self,
                 tenant_id: str,
                 kb_id: str,
                 llm_bdl,
                 embed_bdl=None,
                 callback=None
                 ):

        self.tenant_id = tenant_id
        self.kb_id = kb_id
        self.community_structure = None
        self.community_reports = None
        self.llm_bdl = llm_bdl
        self.embed_bdl = embed_bdl
        self.callback = callback
    async def __call__(self):
        with RedisDistributedLock(self.kb_id, 60*60):
            self.graph, doc_ids = get_graph(self.tenant_id, self.kb_id)
            if not self.graph:
                logging.error(f"Faild to fetch the graph. tenant_id:{self.kb_id}, kb_id:{self.kb_id}")
                if self.callback:
                    self.callback(-1, msg="Faild to fetch the graph.")
                return
            if self.callback:
                self.callback(msg="Fetch the existing graph.")

            cr = CommunityReportsExtractor(self.llm_bdl,
                                  get_entity=partial(get_entity, self.tenant_id, self.kb_id),
                                  set_entity=partial(set_entity, self.tenant_id, self.kb_id, self.embed_bdl),
                                  get_relation=partial(get_relation, self.tenant_id, self.kb_id),
                                  set_relation=partial(set_relation, self.tenant_id, self.kb_id, self.embed_bdl))
            cr = await cr(self.graph, callback=self.callback)
            self.community_structure = cr.structured_output
            self.community_reports = cr.output
            await trio.to_thread.run_sync(lambda: set_graph(self.tenant_id, self.kb_id, self.graph, doc_ids))

        if self.callback:
            self.callback(msg="Graph community extraction is done. Indexing {} reports.".format(len(cr.structured_output)))

        await trio.to_thread.run_sync(lambda: settings.docStoreConn.delete({
            "knowledge_graph_kwd": "community_report",
            "kb_id": self.kb_id
        }, search.index_name(self.tenant_id), self.kb_id))

        for stru, rep in zip(self.community_structure, self.community_reports):
            obj = {
                "report": rep,
                "evidences": "\n".join([f["explanation"] for f in stru["findings"]])
            }
            chunk = {
                "docnm_kwd": stru["title"],
                "title_tks": rag_tokenizer.tokenize(stru["title"]),
                "content_with_weight": json.dumps(obj, ensure_ascii=False),
                "content_ltks": rag_tokenizer.tokenize(obj["report"] +" "+ obj["evidences"]),
                "knowledge_graph_kwd": "community_report",
                "weight_flt": stru["weight"],
                "entities_kwd": stru["entities"],
                "important_kwd": stru["entities"],
                "kb_id": self.kb_id,
                "source_id": doc_ids,
                "available_int": 0
            }
            chunk["content_sm_ltks"] = rag_tokenizer.fine_grained_tokenize(chunk["content_ltks"])
            #try:
            #    ebd, _ = self.embed_bdl.encode([", ".join(community["entities"])])
            #    chunk["q_%d_vec" % len(ebd[0])] = ebd[0]
            #except Exception as e:
            #    logging.exception(f"Fail to embed entity relation: {e}")
            await trio.to_thread.run_sync(lambda: settings.docStoreConn.insert([{"id": chunk_id(chunk), **chunk}], search.index_name(self.tenant_id)))

