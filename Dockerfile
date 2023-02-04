# Use the official lightweight Python image.
# https://hub.docker.com/_/python
FROM python:3.10-slim

# Allow statements and log messages to immediately appear in the Knative logs
ENV PYTHONUNBUFFERED True

# Copy local code to the container image.
ENV APP_HOME /app
WORKDIR $APP_HOME
COPY . ./

# Install production dependencies.
RUN apt install -y unzip xvfb libxi6 libgconf-2-4 
RUN apt install default-jdk 
RUN apt-get update
RUN apt-get -y install tesseract-ocr 
RUN apt-get -y install poppler-utils
RUN apt-get -y install google-chrome-stable 
RUN pip install --no-cache-dir -r requirements.txt

RUN wget https://chromedriver.storage.googleapis.com/94.0.4606.61/chromedriver_linux64.zip 
RUN unzip chromedriver_linux64.zip 

RUN mv chromedriver /usr/bin/chromedriver 
RUN chown root:root /usr/bin/chromedriver 
RUN chmod +x /usr/bin/chromedriver 
RUN wget https://selenium-release.storage.googleapis.com/3.141/selenium-server-standalone-3.141.59.jar 
RUN mv selenium-server-standalone-3.141.59.jar selenium-server-standalone.jar 
RUN wget http://www.java2s.com/Code/JarDownload/testng/testng-6.8.7.jar.zip 
RUN unzip testng-6.8.7.jar.zip 

# Run the web service on container startup. Here we use the gunicorn
# webserver, with one worker process and 8 threads.
# For environments with multiple CPU cores, increase the number of workers
# to be equal to the cores available.
# Timeout is set to 0 to disable the timeouts of the workers to allow Cloud Run to handle instance scaling.
CMD exec gunicorn --bind :$PORT --timeout 0 main:app