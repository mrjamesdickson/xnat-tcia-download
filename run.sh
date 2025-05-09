#!/bin/bash



host=$1
username=$2
password=$3
output=$4
project=$5
manifest=$6


python /workspace/download.py ${manifest} ${output}/zipped

python  /workspace/upload.py ${host} ${username} ${password} ${project} ${output}/zipped

#python /workspace/unzip_all.py ${output}/zipped ${output}/unzipped/ ${output}/zipped/*.yaml
#dcmsend -aec ${aetitle} -v ${host} ${port} --scan-directories --recurse ${output}/unzipped +sp *.dcm
