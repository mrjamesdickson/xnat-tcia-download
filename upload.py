import os
import sys
import zipfile
import yaml

import xnat





def upload(xnatsession,project,zip_path):
    xnatsession.services.import_(zip_path, project=project, destination='/prearchive', content_type="application/zip")


host = sys.argv[1]
username = sys.argv[2]
password= sys.argv[3]
project = sys.argv[4]
root = sys.argv[5]

target_folders = []

xnatsession=xnat.connect(host,user=username,password=password)




for x in os.listdir(root):
    y = os.path.join(root,x)
    y = os.path.join(root,x,os.listdir(y)[0])
    if y.endswith('.zip'):
        zip_path = y
    
        upload(xnatsession,project,zip_path)
        
    else:
        for z in os.listdir(y):
            q = os.path.join(y,z)
            f = [x for x in os.listdir(q) if x.endswith('.zip')][0]
            zip_path = os.path.join(q,f)
            unzip_folder = os.path.join(target,x,z)
            upload(xnatsession,project,zip_path)