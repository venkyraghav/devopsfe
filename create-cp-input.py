#!/usr/bin/env python3

###################
#
# Creates input to cp-ansible (ksql, connect) & julieops (topic provision)
#
# Author: Venky Narayanan (vnarayanan@confluent.io)
# Date:   May 26, 2021
#
###################

from __future__ import print_function
from datetime import datetime
import argparse
from jinja2 import Template
import yaml
import json
import logging
import requests

CONST_TIMESTAMP = 'timestamp'
CONST_NAME = 'name'
CONST_PARTITIONS = 'partitions'
CONST_REPLICATION = 'replication'
CONST_OVERRIDE = 'override'
CONST_DEPENDENCIES = 'dependencies'
CONST_KSQL = 'ksql'
CONST_CONNECT = 'connect'
CONST_TOPIC = 'topic'
CONST_TOPICS = 'topics'
CONST_BROKER = 'broker'
CONST_PROVISION = 'provision'
CONST_CONNECTORS = 'connectors'
CONST_DESCRIPTION = 'description'
CONST_QUERIES = 'queries'
CONST_HOSTS = 'hosts'
CONST_PLUGINS = 'plugins'
CONST_PLUGINS_HUB = 'hub'
CONST_PLUGINS_LOCAL = 'local'
CONST_PLUGINS_REMOTE = 'remote'
CONST_CLUSTERDATA = 'cluster_data'
CONST_SSH_USER = 'ssh_username'
CONST_SSH_KEY = 'ssh_key'

CONST_BOOTSTRAP_SERVERS = 'bootstrap_servers'
CONST_API_KEY = 'api_key'
CONST_API_SECRET = 'api_secret'
CONST_CONSUMER = 'consumer'
CONST_PRODUCER = 'producer'
CONST_SR = 'schema_registry'
CONST_KSQL = 'ksql'
CONST_URL = 'url'

CONST_ENV = 'env'
CONST_CONTEXT = 'context'
CONST_COMPANY = 'company'
CONST_PROJECTS = 'projects'
CONST_SOURCE = 'source'

inputs_map = {CONST_TIMESTAMP: '', CONST_CONTEXT: '', CONST_COMPANY: '', CONST_ENV: '', CONST_SOURCE: '', CONST_PROJECTS: {}, CONST_BOOTSTRAP_SERVERS: '', CONST_CONNECT: [], CONST_CONSUMER: [], CONST_PRODUCER: [], CONST_CLUSTERDATA: {CONST_SSH_USER: 'TODO', CONST_SSH_KEY: 'TODO'}, CONST_KSQL + '_' + CONST_QUERIES: [], CONST_KSQL + '_' + CONST_HOSTS: [], CONST_CONNECT + '_' + CONST_HOSTS: [], CONST_CONNECT + '_' + CONST_CONNECTORS: [], CONST_CONNECT + '_' + CONST_PLUGINS: []}

def create_template(temp_file):
    with open(temp_file) as f:
        temp = f.read()
    f.close()
    return Template(temp)

def print_hosts(template, ip_dict, output_file):
    with open(output_file, "w+") as f:
        print(template.render(ip_dict), file=f)
    f.close()

# Identify topic name, replication factor, and partitions by topic
def process_topic_item (feid, topic_item, override_part, override_repl, output_file):
    name = topic_item[CONST_NAME]
    fqname = feid + "." + name
    if CONST_PARTITIONS in topic_item:
        use_part = topic_item[CONST_PARTITIONS]
    elif override_part != 0:
        use_part = override_part
    else:
        use_part = 1

    if CONST_REPLICATION in topic_item:
        use_repl = topic_item[CONST_REPLICATION]
    elif override_repl != 0:
        use_repl = override_repl
    else:
        use_repl = 1

    logging.debug ('REPLACE with Topic creation script Topic ' + fqname + ', Partitions = ' + str(use_part) + ', Replication = ' + str(use_repl))

# Create Julieops descriptor file
def process_broker (feid, doc, output_file, template_julie):
    logging.debug ('-------')
    if CONST_OVERRIDE in doc[CONST_TOPIC]:
        override = doc[CONST_TOPIC][CONST_OVERRIDE]
        if CONST_PARTITIONS in override:
            override_part = override[CONST_PARTITIONS]
        
        if CONST_REPLICATION in override:
            override_repl = override[CONST_REPLICATION]

        logging.info ('partition = ' + str(override_part) + ', replication = ' + str(override_repl))

    if CONST_DEPENDENCIES not in doc[CONST_TOPIC]:
        logging.info ('No dependency topics')

    for dependency in doc[CONST_TOPIC][CONST_DEPENDENCIES]:
        process_topic_item (feid, dependency, override_part, override_repl, output_file)

    if CONST_TOPICS not in doc[CONST_TOPIC]:
        logging.info ('No topics to provision')
        return

    topics = doc[CONST_TOPIC][CONST_TOPICS]
    for topic in topics:
        process_topic_item (feid, topic, override_part, override_repl, output_file)
    
    logging.debug ('-------')

def provision_ksql_query (feid, doc):
    queries = []
    for query in doc:
        logging.info ('TODO May need to copy the query file to hosts ' + query)
        queries.append(query)
    inputs_map[CONST_KSQL + '_' + CONST_QUERIES] = queries

def provision_ksql_hosts (feid, doc):
    hosts = []
    for host in doc:
        logging.info ('ksql host is ' + host)
        hosts.append(host)
    inputs_map[CONST_KSQL + '_' + CONST_HOSTS] = hosts

# Create cp-ansible yaml with ksql section
def process_ksql (feid, doc):
    logging.debug ('-------')
    if CONST_PROVISION in doc and doc[CONST_PROVISION] == True:
        provision_ksql_hosts (feid, doc[CONST_HOSTS])
        provision_ksql_query (feid, doc[CONST_QUERIES])

    logging.debug ('-------')

def provision_connect_plugins (feid, doc, plugin_type):
    plugins = []
    for plugin in doc:
        logging.info ('Connect Plugin ' + plugin_type + ' is ' + plugin)
        plugins.append(plugin)
    inputs_map[CONST_CONNECT + '_' + CONST_PLUGINS + "_" + plugin_type] = plugins

def provision_connect_connectors (feid, doc):
    connectors = []
    connectors_json = []
    for connector in doc:
        connectors.append(connector)
        f = open(connector, 'r')
        data = json.load(f)
        f.close()
        name = data['name']
        config = data['config']
        config2 = []
        for item in config:
            config2.append(item + " : " + str(config[item]))
        data2 = {'name': name, 'config': config2}
        connectors_json.append(data2)
    inputs_map[CONST_CONNECT + '_' + CONST_CONNECTORS] = connectors
    inputs_map[CONST_CONNECT + '_' + CONST_CONNECTORS + '_' + 'json'] = connectors_json

def provision_connect_hosts (feid, doc):
    hosts = []
    for host in doc:
        logging.info ('Connect host is ' + host)
        hosts.append(host)
    inputs_map[CONST_CONNECT + '_' + CONST_HOSTS] = hosts

# Create cp-ansible yaml with connect section
def process_connect (feid, doc):
    logging.debug ('-------')
    if CONST_PROVISION in doc and doc[CONST_PROVISION] == True:
        provision_connect_hosts (feid, doc[CONST_HOSTS])
        provision_connect_plugins (feid, doc[CONST_PLUGINS][CONST_PLUGINS_HUB], CONST_PLUGINS_HUB)
        provision_connect_plugins (feid, doc[CONST_PLUGINS][CONST_PLUGINS_LOCAL], CONST_PLUGINS_LOCAL)
        provision_connect_plugins (feid, doc[CONST_PLUGINS][CONST_PLUGINS_REMOTE], CONST_PLUGINS_REMOTE)
        provision_connect_connectors (feid, doc[CONST_CONNECTORS])

    logging.debug ('-------')

def process (doc, args):
    inputs_map[CONST_TIMESTAMP] = datetime.now()
    fe_id = doc[CONST_NAME]
    inputs_map[CONST_NAME] = fe_id

    output_ansible = fe_id + ".ansible.yaml"
    output_julie = fe_id + ".julieops.yaml"
    template_ansible = create_template (args.ansibletemplate)
    template_julie = create_template (args.julietemplate)

    logging.info("Feature name is " + fe_id)
    logging.info("Ansible YAML is " + output_ansible + ", Template is " + args.ansibletemplate)
    logging.info("Julieops YAML is " + output_julie + ", Template is " + args.julietemplate)
    
    process_broker  (doc[CONST_NAME], doc[CONST_BROKER], output_julie, template_julie)
    process_ksql    (doc[CONST_NAME], doc[CONST_KSQL])
    process_connect (doc[CONST_NAME], doc[CONST_CONNECT])

    render_template (inputs_map, template_ansible, output_ansible)
    render_template (inputs_map, template_julie, output_julie)

def render_template (input_map, input_template, output_file):
    with open(output_file, "w+") as f:
        print (input_template.render(input_map), file=f)
    f.close()

def get_api_config(docs):
    newdocs = {}
    newdocs[CONST_API_KEY] = docs[CONST_API_KEY]
    newdocs[CONST_API_SECRET] = docs[CONST_API_SECRET]
    return newdocs

def process_ccloud_config (docs):
    inputs_map[CONST_BOOTSTRAP_SERVERS] = docs[CONST_BOOTSTRAP_SERVERS]
    inputs_map[CONST_CONNECT] = get_api_config (docs[CONST_CONNECT])
    inputs_map[CONST_CONSUMER] = get_api_config (docs[CONST_CONSUMER])
    inputs_map[CONST_PRODUCER] = get_api_config (docs[CONST_PRODUCER])
    inputs_map[CONST_KSQL] = get_api_config (docs[CONST_KSQL])
    inputs_map[CONST_SR] = get_api_config (docs[CONST_SR])
    inputs_map[CONST_SR][CONST_URL] = docs[CONST_SR][CONST_URL]

def do_process(args):
    ccloud_config_file = args.commandconfig
    with open(ccloud_config_file) as f:
        ccloud_config_docs = yaml.load(f, Loader=yaml.FullLoader)
        logging.debug ('-------')
        logging.debug(ccloud_config_docs)
        logging.debug ('-------')
        process_ccloud_config (ccloud_config_docs)

    feconfig_file = args.feconfig
    with open(feconfig_file) as f:
        doc = yaml.load(f, Loader=yaml.FullLoader)
        logging.debug ('-------')
        logging.debug(doc)
        logging.debug ('-------')
        process(doc, args)
        logging.debug ('-------')
        logging.debug (inputs_map)
        logging.debug ('-------')
    f.close()

def parse_arguments():
    parser = argparse.ArgumentParser(
        prog='create-cp-input.py', usage='%(prog)s [options]',
        description="Reads the feature environment YAML config file; converts it into julieops and cp-ansible inventory"
    )

    # parser.add_argument("-h", "--help", help="Prints help")
    parser.add_argument("-f", "--feconfig", help="Feature environment config YAML input file (default = input.yaml)", default="./input.yaml")
    parser.add_argument("-a", "--ansibletemplate", help="Inventory template (default = cpansible.j2)", default="./cpansible.j2")
    parser.add_argument("-j", "--julietemplate", help="Inventory template (default = julie.j2)", default="./julie.j2")
    parser.add_argument("-c", "--commandconfig", help="Command Config (default = ccloud.yaml)", default="./ccloud.yaml")

    return parser.parse_args()

if __name__ == '__main__':
    logging.basicConfig(format='%(asctime)s | %(levelname)s | %(filename)s | %(funcName)s | %(lineno)d | %(message)s', level=logging.INFO)

    logging.info("Started ...")
    args = parse_arguments()
    do_process (args)
    logging.info("Completed ...")