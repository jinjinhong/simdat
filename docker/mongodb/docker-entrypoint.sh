#!/bin/bash

# Copyright https://github.com/docker-library/mongo
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

# http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
#   limitations under the License.


if [ "${1:0:1}" = '-' ]; then
    set -- mongod "$@"
fi

if [ "$1" = 'mongod' ]; then
    chown -R mongodb /data/db

    numa='numactl --interleave=all'
    if $numa true &> /dev/null; then
        set -- $numa "$@"
    fi

    exec gosu mongodb "$@"
fi

exec "$@"