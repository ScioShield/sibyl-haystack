from haystack.document_stores import ElasticsearchDocumentStore
from haystack.document_stores import elasticsearch_index_to_document_store
from haystack.nodes import FARMReader
from haystack.nodes import EmbeddingRetriever
from haystack import Pipeline
from haystack.utils import print_answers
from dotenv import load_dotenv
from elasticsearch import Elasticsearch
from elasticsearch.exceptions import NotFoundError
import os
import gc

def load_env():
    with open('.env', 'r') as f:
        return dict(tuple(line.strip().split('=')) for line in f if line.strip() and not line.strip().startswith('#'))

def save_env(env_dict):
    with open('.env', 'w') as f:
        for key, value in env_dict.items():
            f.write(f"{key}={value}\n")


def setup_api_credentials():
    load_dotenv()
    return {
        "es_host": os.getenv("E_HOST"),
        "es_port": os.getenv("E_PORT"),
        "es_username": os.getenv("E_USER"),
        "es_password": os.getenv("E_PASS"),
        "es_scheme": os.getenv("E_SCHEME"),
        "ca_certs_path": os.getenv("E_CA_PATH"),
    }

def create_document_store(api_credentials):
    return ElasticsearchDocumentStore(
        host=api_credentials["es_host"],
        port=api_credentials["es_port"],
        username=api_credentials["es_username"],
        password=api_credentials["es_password"],
        scheme=api_credentials["es_scheme"],
        ca_certs=api_credentials["ca_certs_path"],
        index="my-document-store",
        similarity="dot_product",
        embedding_dim=768
    )

def index_documents(api_credentials, document_store):
    elasticsearch_index_to_document_store(
        host=api_credentials["es_host"],
        port=api_credentials["es_port"],
        username=api_credentials["es_username"],
        password=api_credentials["es_password"],
        scheme=api_credentials["es_scheme"],
        ca_certs=api_credentials["ca_certs_path"],
        document_store=document_store,
        original_index_name="staging-index",
        included_metadata_fields="concatenated_fields",
        original_content_field="concatenated_fields"
    )

def query_pipeline(document_store, es_client, index_name):
    reader = FARMReader(model_name_or_path="deepset/roberta-base-squad2", use_gpu=True)
    retriever = EmbeddingRetriever(
        document_store=document_store,
        embedding_model="sentence-transformers/all-mpnet-base-v2",
        model_format="sentence_transformers"
    )

    current_index_count = count_documents(es_client, index_name)

    env_dict = load_env()

    previous_index_count = int(env_dict.get("PREVIOUS_INDEX_COUNT", 0))

    if current_index_count != previous_index_count or current_index_count == 0:
        document_store.update_embeddings(retriever)
    
        env_dict["PREVIOUS_INDEX_COUNT"] = str(current_index_count)
        save_env(env_dict)

    pipeline = Pipeline()
    pipeline.add_node(component=retriever, name="Retriever", inputs=["Query"])
    pipeline.add_node(component=reader, name="Reader", inputs=["Retriever"])

    return pipeline


def query_loop(pipeline):
    while True:
        user_input = input("Please enter your query (or 'q' to quit): ")
        if user_input.lower() == 'q':
            break
        else:
            prediction = pipeline.run(
                query=user_input,
                params={
                    "Retriever": {"top_k": 10},
                    "Reader": {"top_k": 3}
                }
            )

            print_answers(prediction, details="medium")

def create_elasticsearch_client(api_credentials):
    return Elasticsearch(
        [api_credentials["es_host"]],
        http_auth=(api_credentials["es_username"], api_credentials["es_password"]),
        scheme=api_credentials["es_scheme"],
        port=api_credentials["es_port"],
        verify_certs=True,
        ca_certs=api_credentials["ca_certs_path"]
    )

def update_mapping(es_client, index_name, body):
    return es_client.indices.put_mapping(index=index_name, body=body)

def update_index_by_query(es_client, index_name, body):
    return es_client.update_by_query(index=index_name, body=body)

def create_staging_index_if_not_exists(es_client, staging_index_name, mapping_body):
    if not es_client.indices.exists(index=staging_index_name):
        es_client.indices.create(index=staging_index_name, body=mapping_body)

def upsert_document(es_client, index_name, doc_id, body):
    es_client.update(index=index_name, id=doc_id, doc=body, doc_as_upsert=True)

def ingest_alerts_to_staging_index(es_client, index_name, alerts):
    for alert in alerts:
        try:
            es_client.get(index=index_name, id=alert["_id"])
        except NotFoundError:
            upsert_document(es_client, index_name, alert["_id"], alert["_source"])

def count_documents(es_client, index_name):
    return es_client.count(index=index_name)['count']

def main():
    api_credentials = setup_api_credentials()
    es_client = create_elasticsearch_client(api_credentials)
    try:
        staging_index_name = "staging-index"
        original_index_name = ".alerts-security.alerts-default"
        new_field_name = "concatenated_fields"
        embedding_index = "my-document-store"
    
        mapping_body = {
            "mappings": {
                "properties": {
                    new_field_name: {
                        "type": "text",
                        "index": "true"
                    }
                }
            }
        }
    
        body = {
            "script": {
                "source": """
                ctx._source.""" + new_field_name + """ = 
                    (ctx._source.containsKey('kibana.alert.start') ? 'kibana.alert.start: ' + ctx._source['kibana.alert.start'] : '') + ' ' +
                    (ctx._source.containsKey('kibana.alert.severity') ? 'kibana.alert.severity: ' + ctx._source['kibana.alert.severity'] : '') + ' ' +
                    (ctx._source.containsKey('kibana.alert.rule.name') ? 'kibana.alert.rule.name: ' + ctx._source['kibana.alert.rule.name'] : '') + ' ' +
                    (ctx._source.containsKey('kibana.alert.rule.description') ? 'kibana.alert.rule.description: ' + ctx._source['kibana.alert.rule.description'] : '') + ' ' +
                    (ctx._source.containsKey('kibana.alert.reason') ? 'kibana.alert.reason: ' + ctx._source['kibana.alert.reason'] : '') + ' ' +
                    (ctx._source.containsKey('kibana.alert.risk_score') ? 'kibana.alert.risk_score: ' + ctx._source['kibana.alert.risk_score'] : '') + ' ' +
                    (ctx._source.containsKey('kibana.alert.rule.threat') ? 'kibana.alert.rule.threat: ' + ctx._source['kibana.alert.rule.threat'] : '') + ' ' +
                    (ctx._source.containsKey('kibana.alert.rule.rule_id') ? 'kibana.alert.rule.rule_id: ' + ctx._source['kibana.alert.rule.rule_id'] : '') + ' ' +
                    (ctx._source.containsKey('host') ? 'host: ' + ctx._source['host'] : '') + ' ' +
                    (ctx._source.containsKey('process.args') ? 'process.args: ' + ctx._source['process.args'] : '');
                """,
                "lang": "painless"
            }
        }
    
        create_staging_index_if_not_exists(es_client, staging_index_name, mapping_body)
        
        all_alerts = es_client.search(index=original_index_name, size=10000)["hits"]["hits"]

        staging_index_count = count_documents(es_client, staging_index_name)
        original_index_count = count_documents(es_client, original_index_name)
        if staging_index_count != original_index_count:
            ingest_alerts_to_staging_index(es_client, staging_index_name, all_alerts)
            update_index_by_query(es_client, staging_index_name, body)
            document_store = create_document_store(api_credentials)
            index_documents(api_credentials, document_store)
        else:
            document_store = create_document_store(api_credentials)

        pipeline = query_pipeline(document_store, es_client, embedding_index)
        query_loop(pipeline)
    finally:
        es_client.close()
        gc.collect()

if __name__ == "__main__":
    main()
