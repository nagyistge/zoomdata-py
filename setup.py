# ===================================================================
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#  
#      http://www.apache.org/licenses/LICENSE-2.0
#  
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#  
# ===================================================================
from setuptools import setup, find_packages

setup(
        name = 'zoomdata',
        version = '0.1',
        packages = find_packages(),
        install_requires=[ 'pandas', 'urllib3', 'websocket-client'],
        author = 'Aktiun',
        keywords=['aktiun','zoomdata','jupyter','jupyterhub','zoomdata-py'],
        author_email = 'eduardo@aktiun.com',
        url = 'https://github.com/Zoomdata/zoomdata-py',
        description = 'Integrates Zoomdata with Jupyter notebooks',
        include_package_data=True,
        )
