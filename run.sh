#!/bin/bash



aetitle=$1
host=$2
port=$3
output=$4
manifest=$5


python /workspace/download.py ${manifest} ${output}/zipped
python /workspace/unzip_all.py ${output}/zipped ${output}/unzipped/ ${output}/zipped/*.yaml
dcmsend -aec ${aetitle} -v ${host} ${port} --scan-directories --recurse ${output}/unzipped +sp *.dcm
