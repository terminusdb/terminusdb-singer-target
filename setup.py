#!/usr/bin/env python
# read the contents of your README file
import re
from os import path

from setuptools import setup

# Add README.md in PyPI project description, reletive links are changes to obsolute

page_target = "https://github.com/terminusdb/terminusdb-client-python/blob/master/"
this_directory = path.abspath(path.dirname(__file__))
with open(path.join(this_directory, "README.md"), encoding="utf-8") as f:
    long_description = f.read()

matched = re.finditer(r"\]\(\S+\)", long_description)
replace_pairs = {}
for item in matched:
    if item.group(0)[2:10] != "https://" and item.group(0)[2:9] != "http://":
        replace_pairs[item.group(0)] = (
            item.group(0)[:2] + page_target + item.group(0)[2:]
        )
for old_str, new_str in replace_pairs.items():
    long_description = long_description.replace(old_str, new_str)

# ---

setup(
    name="target-terminusdb",
    version="0.1.2",
    description="Singer.io target for inserting data in TerminusDB",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Cheuk",
    url="http://singer.io",
    classifiers=["Programming Language :: Python :: 3 :: Only"],
    py_modules=["target_terminusdb"],
    install_requires=["singer-python>=5.0.12", "terminusdb-client>=10.0.11"],
    entry_points="""
    [console_scripts]
    target-terminusdb=target_terminusdb:main
    """,
    packages=["target_terminusdb"],
    package_data={},
    include_package_data=True,
)
