FROM tensorflow/tensorflow

RUN apt update
RUN apt-get install dcmtk -y

RUN python -m pip install --upgrade pip
COPY * /workspace/
RUN pip install -r /workspace/requirements.txt
WORKDIR /workspace/
