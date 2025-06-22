FROM nikolaik/python-nodejs:python3.10-nodejs22

# Install python deps
COPY backend/requirements.txt /
RUN pip3 install -r /requirements.txt

# Copy the frontend, needed to install Quasar
COPY frontend /frontend

# Init Quasar
RUN npm install -g npm@10.3.0
RUN (cd /frontend && npm install --force)
RUN npm i -g @quasar/cli --force

# Copy and chmod start script
COPY start.sh /
RUN chmod a+x start.sh

# Run the server
CMD [ "/start.sh" ]