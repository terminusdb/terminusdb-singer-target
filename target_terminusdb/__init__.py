#!/usr/bin/env python3

import argparse
import collections
import http.client
import io
import json
import sys
import threading
import urllib
from datetime import datetime

import pkg_resources
import singer
from jsonschema.validators import Draft4Validator
from terminusdb_client.errors import DatabaseError
from terminusdb_client.scripts.scripts import _connect, _load_settings, _sync
from terminusdb_client.woqlschema import LexicalKey

logger = singer.get_logger()


def emit_state(state):
    if state is not None:
        line = json.dumps(state)
        logger.debug(f"Emitting state {line}")
        sys.stdout.write(f"{line}\n")
        sys.stdout.flush()


def flatten(d, parent_key="", sep="__"):
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
    validators = {}

    client, _ = _connect(config)
    buffer_size = config.get("buffer")

    if buffer_size is None:
        buffer_size = 1000

    # Initize list for terminusdb client
    doc_dict_list = []
    doc_ids = []

    datetime.now().strftime("%Y%m%dT%H%M%S")

    # Loop over lines from stdin
    for line in lines:
        try:
            o = json.loads(line)
        except json.decoder.JSONDecodeError:
            logger.error(f"Unable to parse:\n{line}")
            raise

        if "type" not in o:
            raise Exception(f"Line is missing required key 'type': {line}")
        t = o["type"]

        if t == "RECORD":
            if "stream" not in o:
                raise Exception(f"Line is missing required key 'stream': {line}")
            if o["stream"] not in schemas:
                raise Exception(
                    "A record for stream {} was encountered before a corresponding schema".format(
                        o["stream"]
                    )
                )

            # Get schema for this record's stream
            # record_schema = schemas[o["stream"]]

            # Validate record
            validators[o["stream"]].validate(o["record"])

            # If the record needs to be flattened, uncomment this line
            # flattened_record = flatten(o['record'])

            # Process Record message here..

            doc_dict = {"@type": o["stream"]}
            doc_dict.update(o["record"])
            doc_dict["@id"] = LexicalKey(key_properties[o["stream"]]).idgen(doc_dict)
            if doc_dict["@id"] not in doc_ids:
                doc_dict_list.append(doc_dict)
                doc_ids.append(doc_dict["@id"])

            state = None

            if len(doc_dict_list) >= buffer_size:
                try:
                    client.update_document(
                        doc_dict_list,
                        commit_msg="Dcouments insert by Singer.io target.",
                    )
                    logger.info("Documents inserted")
                except DatabaseError as error:
                    logger.info("Error inserting documents")
                    with open(".terminusdb_error_log", "a") as file:
                        file.write("\nDocument insert error:\n")
                        file.write(str(error))
                        file.write("\nwhile insert\n")
                        file.write(str(doc_dict_list))
                        file.write("\n===================\n")
                finally:
                    doc_dict_list = []
        elif t == "STATE":
            logger.debug("Setting state to {}".format(o["value"]))
            state = o["value"]
        elif t == "SCHEMA":
            if "stream" not in o:
                raise Exception(f"Line is missing required key 'stream': {line}")
            stream = o["stream"]
            schemas[stream] = o["schema"]
            validators[stream] = Draft4Validator(o["schema"])
            if "key_properties" not in o:
                raise Exception("key_properties field is required")
            key_properties[stream] = o["key_properties"]

            # Process Schema message here..

            class_dict = {
                "@type": "Class",
                "@id": stream,
            }
            for key, value in o["schema"]["properties"].items():
                if isinstance(value["type"], str):
                    if value["type"] == "number":
                        class_dict[key] = "xsd:decimal"
                    else:
                        class_dict[key] = "xsd:" + value["type"]
                elif "null" in value["type"]:
                    convert_type = value["type"][-1]
                    if convert_type == "number":
                        class_dict[key] = {"@type": "Optional", "@class": "xsd:decimal"}
                    else:
                        class_dict[key] = {
                            "@type": "Optional",
                            "@class": "xsd:" + convert_type,
                        }
                if "format" in value and value["format"] == "date-time":
                    class_dict[key] = "xsd:dateTime"

            # schema got update immediately

            try:
                client.update_document(
                    class_dict,
                    commit_msg="Schema objects insert by Singer.io target.",
                    graph_type="schema",
                )
                logger.info(f"Schema of {stream} inserted")
                logger.info(_sync(client))
            except DatabaseError as error:
                logger.info(f"Error inserting schema of {stream}")
                with open(".terminusdb_error_log", "a") as file:
                    file.write("Schema insert error:\n")
                    file.write(str(error))
                    file.write("\nWhile insert:\n")
                    file.write(str(class_dict))
                    file.write("\n===================\n")
        else:
            raise Exception(
                "Unknown message type {} in message {}".format(o["type"], o)
            )

    return state


def send_usage_stats():
    try:
        version = pkg_resources.get_distribution("target-csv").version
        conn = http.client.HTTPConnection("collector.singer.io", timeout=10)
        conn.connect()
        params = {
            "e": "se",
            "aid": "singer",
            "se_ca": "terget-terminusdb",
            "se_ac": "open",
            "se_la": version,
        }
        conn.request("GET", "/i?" + urllib.parse.urlencode(params))
        conn.getresponse()
        conn.close()
    except Exception:
        logger.debug("Collection request failed")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-c", "--config", help="Config file")
    args = parser.parse_args()

    if args.config:
        with open(args.config) as user_input:
            config = _load_settings(args.config)
    else:
        config = {}

    if not config.get("disable_collection", False):
        logger.info(
            "Sending version information to singer.io. "
            + "To disable sending anonymous usage data, set "
            + 'the config parameter "disable_collection" to true'
        )
        threading.Thread(target=send_usage_stats).start()

    user_input = io.TextIOWrapper(sys.stdin.buffer, encoding="utf-8")
    state = persist_lines(config, user_input)

    emit_state(state)
    logger.debug("Exiting normally")


if __name__ == "__main__":
    main()
