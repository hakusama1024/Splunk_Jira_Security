# -*- coding: utf-8 -*-


"""setup.py: setuptools control."""

import re
from setuptools import setup

with open("README.md", "rb") as f:
    long_descr = f.read().decode("utf-8")

setup(
    name="splunk-jira",
    packages=["app"],
    entry_points={
        "console_scripts": ['splunk-jira = app.splunk_jira:main']
    },
    version="0.1.0",
    install_requires=[
        "easydict",
        "jira",
        "pyyaml",
        "requests",
        "python-dateutil",
        "retrying"
    ],
    description="Python CLI for ingesting jira metrics into splunk",
    long_description=long_descr,
    author="Siva Sundaresan",
    author_email="siva.sundaresan@rackspace.com"
)
