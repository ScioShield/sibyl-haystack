# Sibyl-Haystack

This script sets up an information retrieval pipeline with Haystack for searching over an existing Elasticsearch index. The Elasticsearch index contains alerts from a default security index. The provided code uses a staging document store to process and store new concatenated fields in the alerts.

## Acknowledgments

## Requirements
Python 3.6 or higher  
- farm-haystack
- elasticsearch (We are using version 7.17.9, due to changes in 8.x listed [here](https://www.elastic.co/guide/en/elasticsearch/client/python-api/current/migration.html), the target cluster can be 8.x, a migration of the script is planned)
- python-dotenv

Install the required libraries using:  

```
python3 -m pip install -r requirements.txt --user
```
[Why "python3 -m pip"?](https://stackoverflow.com/questions/25749621/whats-the-difference-between-pip-install-and-python-m-pip-install)

An Elastic instance with **open** alerts. I have a provisioning [script](https://github.com/ScioShield/AtomicFireFly) if you want to bring one up locally.  
## Features
1. Set up API credentials for accessing the Elasticsearch instance.  
2. Create a new staging index if it doesn't exist and update its mapping.  
3. Populate concatenated fields in the staging index.  
4. Create a document store with an embedding retriever and FARMReader.  
5. If the current index count is different from the index count saved in .env file, update the document embeddings in the document store and save the current index count to the .env file.  
6. Construct a Haystack pipeline with the retriever and reader components.  
7. Allow users to input questions and interact with the created pipeline.  

## Caveats
**This script is an experiment!**  

**I am not a programmer!** :) The code probably has bugs/issues, please raise an issue if you have any problems running it.  

I would strongly advise to spin up a test cluster first! Wouldn't want to `rm -rf /` prod, unless you really want to wake up on a Monday morning!  

Sending large amounts of data to OpenAI can be quite costly especially for the GPT-4 model, hence the save to file feature.  
## Usage
1. Add your Elasticsearch credentials to a `.env` file in the script directory:  
Or rename the `.env.example` file to `.env` and change the required felids. Replace the item after "=" with the value, no quotes! The file must be `key=value` per line no comments!  

```
E_HOST=Elastic_Host # Example: 192.168.56.10 or atomicfirefly
E_PORT=Elastic_Port # Example: 9200
E_SCHEME=Elastic_Scheme # Example: http or https
E_USER=Elastic_Username # Example: elastic
E_PASS=Elastic_Password # Example: o2PAhmXC9eYVNUKpoieBYKbXqJ83vNo0
E_CA_PATH=Path_to_CA_certificate # Example: /tmp/certs/ca.crt
```
Remove the `CA_CERTS_PATH` var from the script and `.env` if you are using an unsecured cluster or the Elastic Cloud  

A value `PREVIOUS_INDEX_COUNT` will be appended when you run the script.  

2. Run the script using:

```
python3 sibyl-haystack.py
```
## Improvements and future work
- finish the readme

## Demo

## References