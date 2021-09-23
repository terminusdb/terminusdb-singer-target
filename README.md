# target-terminusdb

This is a [Singer](https://singer.io) target that reads JSON-formatted data
following the [Singer spec](https://github.com/singer-io/getting-started/blob/master/SPEC.md).

## To install

`target-terminusdb` can be install via pip with Python >= 3.7:

`python3 -m pip install -U target-terminusdb`

## To use

You can start a project in a directory using conjunction with TerminusDB easily by:

`terminusdb startproject`

This will create the config.json that stores information about the endpoint and database that you are connecting to.

Then you can pipe in data using a Singer.io tap to TerminusDB. For details about how to use a Singer.io tap you can [see here](https://github.com/singer-io/getting-started/blob/master/docs/RUNNING_AND_DEVELOPING.md#running-and-developing-singer-taps-and-targets). For example you have a Python tap like this:

```Python
import singer
import urllib.request
from datetime import datetime, timezone

now = datetime.now(timezone.utc).isoformat("T","milliseconds")
schema = {
    'properties':   {
        'ip': {'type': 'string'},
        'timestamp': {'type': 'string', 'format': 'date-time'},
    },
}

with urllib.request.urlopen('http://icanhazip.com') as response:
    ip = response.read().decode('utf-8').strip()
    singer.write_schema('my_ip', schema, 'timestamp')
    singer.write_records('my_ip', [{'timestamp': now, 'ip': ip}])
```

Then you can use it to put `my_ip` in TerminusDB like this:

`python tap_ip.py | target-terminusdb -c config.json`
