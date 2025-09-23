import sys,os
from query import TCIAClient, get_response
import pandas as pd
import traceback
import zipfile
import xnat



def upload(xnatsession,project,zip_path):
    xnatsession.services.import_(zip_path, project=project, destination='/prearchive', content_type="application/zip")


    
if __name__ == '__main__':
    
    csv_file_path = sys.argv[1]
    root_folder = sys.argv[2]
    project= sys.argv[3]
    host = sys.argv[4]
    username = sys.argv[5]
    password= sys.argv[6]

    xnatsession=xnat.connect(host,user=username,password=password)

    if csv_file_path.endswith('.csv'):
        df = pd.read_csv(csv_file_path)
        
    if csv_file_path.endswith('.tcia'):

        with open(csv_file_path,'r') as f:
            content = f.read()
        content = [x for x in content.split('\n') if len(x) > 0]
        i = content.index('ListOfSeriesToDownload=')
        series_instance_uid_list = content[i+1:]
        mylist = []
        for n,uid in enumerate(series_instance_uid_list):
            mylist.append(dict(study_instance_uid='na',series_instance_uid=uid))
        
        df = pd.DataFrame(mylist)
    else:
        raise NotImplementedError()

    for n,row in df.iterrows():
        print(n,len(df))
        study_instance_uid = row.study_instance_uid
        series_instance_uid = row.series_instance_uid
        if study_instance_uid == 'na':
            file_path = os.path.join(root_folder,series_instance_uid,'img.zip')
        else:
            file_path = os.path.join(root_folder,study_instance_uid,series_instance_uid,'img.zip')
        
        if os.path.exists(file_path):
            continue
            
        os.makedirs(os.path.dirname(file_path),exist_ok=True)
        
        folder = os.path.dirname(file_path)
        basename = os.path.basename(file_path)
        print("downloading series_instance_uid:",series_instance_uid," directory:",folder," zipfile:",basename)
        tcia_client = TCIAClient(apiKey=None, baseUrl="https://services.cancerimagingarchive.net/services/v3",resource="TCIA")
        tcia_client.get_image(seriesInstanceUid=series_instance_uid,downloadPath=folder,zipFileName=basename)
        zip_file_path = folder+'/'+basename
        upload(xnatsession,project,zip_file_path)
        
        # Remove zip file after successful upload to save disk space
        try:
            os.remove(zip_file_path)
            print(f"Removed zip file: {zip_file_path}")
        except OSError as e:
            print(f"Warning: Could not remove zip file {zip_file_path}: {e}")


