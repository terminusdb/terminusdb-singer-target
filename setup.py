#!/usr/bin/env python
from setuptools import setup

setup(
    name="target-terminusdb",
    version="0.1.0",
    description="Singer.io target for inserting data in TerminusDB",
    author="Cheuk",
    url="http://singer.io",
    classifiers=["Programming Language :: Python :: 3 :: Only"],
    py_modules=["target_terminusdb"],
    install_requires=[
        "singer-python>=5.0.12",
        # "terminusdb-client>=2.0.0"
    ],
    entry_points="""
    [console_scripts]
    target-terminusdb=target_terminusdb:main
    """,
    packages=["target_terminusdb"],
    package_data = {},
    include_package_data=True,
)
