from collections import defaultdict
from devpi_server.log import threadlog as log
from devpi_server.readonly import get_mutable_deepcopy
from devpi_web.whoosh_index import project_name
from elasticsearch import Elasticsearch
from elasticsearch.helpers import streaming_bulk


class Index:
    def __init__(self):
        self.index = 'devpi'
        self.es = Elasticsearch()

    def delete_index(self):
        self.es.indices.delete(index=self.index, ignore_unavailable=True)

    def _update_projects(self, projects):
        main_keys = [
            'path', 'name', 'user', 'index', 'classifiers', 'keywords',
            'version', 'doc_version', 'type',
            'text_path', 'text_title', 'text']
        for i, project in enumerate(projects, 1):
            data = {
                x: get_mutable_deepcopy(project[x])
                for x in main_keys if x in project}
            data['path'] = u"/{user}/{index}/{name}".format(**data)
            data['type'] = "project"
            data['text'] = "%s %s" % (data['name'], project_name(data['name']))
            yield dict(
                _index=self.index,
                _type=data['type'],
                _id=data['path'],
                _source=data)

    def update_projects(self, projects, clear=False):
        results = streaming_bulk(client=self.es, actions=self._update_projects(projects))
        for i, result in enumerate(results):
            if i % 1000 == 0:
                log.info("Indexed %s", i)

    def query_projects(self, querystring, page=1):
        items = []
        result_info = dict()
        result = {"items": items, "info": result_info}
        res = self.es.search(
            index=self.index,
            body={"query": {"match_all": {}}},
            from_=(page - 1) * 10)
        hits = res.pop('hits')
        raw_items = hits.pop('hits')
        print(res)
        print(hits)
        result_info['collapsed_counts'] = defaultdict(int)
        result_info['pagecount'] = hits['total'] // 10
        if result_info['pagecount'] > 999:
            result_info['pagecount'] = 999
        result_info['pagenum'] = page
        result_info['total'] = hits['total']
        for item in raw_items:
            info = dict(
                data=dict(item['_source']),
                sub_hits=())
            items.append(info)
        return result

    def get_query_parser_html_help(self):
        return []
