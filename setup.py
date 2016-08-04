#!/usr/bin/env python
#*******************************************************************************
# Copyright (c) 2016 IBM Corp.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#*******************************************************************************

"""kleiber project"""
from setuptools import find_packages, setup

REQUIRES = [
    'docopt',
    'softlayer',
    'softlayer-object-storage',
    'pyyaml',
    'jinja2'
]

setup(name='kleiber',
      version='0.1',
      description='kleiber softlayer orchestrator',
      long_description='test',
      platforms=["Linux"],
      author="IBM SoftLayer",
      author_email="softlayer@softlayer.com",
      url="http://sldn.softlayer.com",
      license="MIT",
      packages=find_packages(),
      entry_points={
        'console_scripts': [
            'kleiber=kleiber:main',
        ],
      },
      install_requires=REQUIRES,
      zip_safe=False,
      include_package_data=True,
      )
