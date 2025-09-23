
python3 ./command2Label.py ./command.json >> Dockerfile
docker build -t xnatworks/xnat-tcia-download:1.2.0 .
docker push xnatworks/xnat-tcia-download:1.2.0