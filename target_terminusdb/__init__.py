#!/usr/bin/env python3

import argparse
import io
import os
import sys
import json
import threading
import http.client
import urllib
from datetime import datetime
import collections

import pkg_resources
from jsonschema.validators import Draft4Validator
import singer

from terminusdb_client import WOQLClient
from terminusdb_client.errors import DatabaseError
from terminusdb_client.woqlschema import LexicalKey

logger = singer.get_logger()

def emit_state(state):
    if state is not None:
        line = json.dumps(state)
        logger.debug('Emitting state {}'.format(line))
        sys.stdout.write("{}\n".format(line))
        sys.stdout.flush()

def flatten(d, parent_key='', sep='__'):
    items = []
    for k, v in d.items():
        new_key = parent_key + sep + k if parent_key else k
        if isinstance(v, collections.MutableMapping):
            items.extend(flatten(v, new_key, sep=sep).items())
        else:
            items.append((new_key, str(v) if type(v) is list else v))
    return dict(items)

def persist_lines(config, lines):
    state = None
    schemas = {}
    key_properties = {}
    headers = {}
    validators = {}

    client = WOQLClient(config["server"])
    client.connect()
    try:
        client.create_database(config["database"])
    except DatabaseError as error:
        if "Database already exists." in str(error):
            client.connect(db=config["database"])
        else:
            raise InterfaceError(f"Cannot connect to {config['database']}.")
    # Initize list for terminusdb client
    class_dict_list = []
    doc_dict_list = []

    now = datetime.now().strftime('%Y%m%dT%H%M%S')

    # Loop over lines from stdin
    for line in lines:
        try:
            o = json.loads(line)
        except json.decoder.JSONDecodeError:
            logger.error("Unable to parse:\n{}".format(line))
            raise

        if 'type' not in o:
            raise Exception("Line is missing required key 'type': {}".format(line))
        t = o['type']

        if t == 'RECORD':
            if 'stream' not in o:
                raise Exception("Line is missing required key 'stream': {}".format(line))
            if o['stream'] not in schemas:
                raise Exception("A record for stream {} was encountered before a corresponding schema".format(o['stream']))

            # Get schema for this record's stream
            schema = schemas[o['stream']]

            # Validate record
            validators[o['stream']].validate(o['record'])

            # If the record needs to be flattened, uncomment this line
            # flattened_record = flatten(o['record'])

            # TODO: Process Record message here..

            doc_dict = {'@type': o['stream']}
            doc_dict.update(o['record'])
            doc_dict['@id'] = LexicalKey(key_properties[o['stream']]).idgen(doc_dict)
            doc_dict_list.append(doc_dict)

            state = None
        elif t == 'STATE':
            logger.debug('Setting state to {}'.format(o['value']))
            state = o['value']
        elif t == 'SCHEMA':
            if 'stream' not in o:
                raise Exception("Line is missing required key 'stream': {}".format(line))
            stream = o['stream']
            schemas[stream] = o['schema']
            validators[stream] = Draft4Validator(o['schema'])
            if 'key_properties' not in o:
                raise Exception("key_properties field is required")
            key_properties[stream] = o['key_properties']

            # TODO: Process Schema message here..

            class_dict = {"@type": "Class", "@id": stream, "@key": {"@type": "Lexical", "@fields": o['key_properties']}}
            for key, value in o['schema']["properties"].items():
                class_dict[key] = 'xsd:' + value["type"]
                if "format" in value and value["format"] == "date-time":
                    class_dict[key] = "xsd:dateTime"

            class_dict_list.append(class_dict)
        else:
            raise Exception("Unknown message type {} in message {}"
                            .format(o['type'], o))

    client.update_document(
                class_dict_list,
                commit_msg="Schema objects insert by Singer.io target.",
                graph_type="schema",
            )
    print("Schema inserted")
    client.update_document(
                doc_dict_list,
                commit_msg="Dcouments insert by Singer.io target.",
            )
    print("Documents inserted")
    return state


def send_usage_stats():
    try:
        version = pkg_resources.get_distribution('target-csv').version
        conn = http.client.HTTPConnection('collector.singer.io', timeout=10)
        conn.connect()
        params = {
            'e': 'se',
            'aid': 'singer',
            'se_ca': 'terget-terminusdb',
            'se_ac': 'open',
            'se_la': version,
        }
        conn.request('GET', '/i?' + urllib.parse.urlencode(params))
        response = conn.getresponse()
        conn.close()
    except:
        logger.debug('Collection request failed')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-c', '--config', help='Config file')
    args = parser.parse_args()

    if args.config:
        if args.config.split('.')[-1] == 'json':
            with open(args.config) as input:
                config = json.load(input)
        elif args.config.split('.')[-1] == 'py':
            sys.path.append(os.getcwd())
            _temp = __import__(args.config.split('.')[0], globals(), locals(), ["SERVER", "DATABASE"], 0)
            server = _temp.SERVER
            database = _temp.DATABASE
            config = {"server": server, "database": database}
    else:
        config = {}

    if not config.get('disable_collection', False):
        logger.info('Sending version information to singer.io. ' +
                    'To disable sending anonymous usage data, set ' +
                    'the config parameter "disable_collection" to true')
        threading.Thread(target=send_usage_stats).start()

    input = io.TextIOWrapper(sys.stdin.buffer, encoding='utf-8')
    state = persist_lines(config, input)

    emit_state(state)
    logger.debug("Exiting normally")


if __name__ == '__main__':
    main()
