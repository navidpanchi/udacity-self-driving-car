#parsing command line arguments
import argparse
#decoding camera images
import base64
#for frametimestamp saving
from datetime import datetime
#reading and writing files
import os
#high level file operations
import shutil
#matrix math
import numpy as np
#real-time server
import socketio
#concurrent networking
import eventlet
#web server gateway interface
import eventlet.wsgi
#image manipulation
from PIL import Image
#web framework
from flask import Flask
#input output
from io import BytesIO

#load our saved model
import tflearn
from tflearn.layers.conv import conv_2d
from tflearn.layers.core import fully_connected, input_data, flatten
from tflearn.layers.normalization import batch_normalization
from tflearn.layers.estimator import regression
#helper class
import utils

#model
#model
# X_train=X_train.reshape([-1,66,200,3])
# Y_train=Y_train.reshape([-1,1])

#input layer
network=input_data(shape=[None,66,200,3], name='input')

#convolutional layers
network=conv_2d(network, 24, activation='elu', strides=2, filter_size=5)
# network=batch_normalization(network)
network=conv_2d(network, 36, activation='elu', strides=2, filter_size=5)
# network=batch_normalization(network)
network=conv_2d(network, 48, activation='elu', strides=2, filter_size=5)
# network=batch_normalization(network)
network=conv_2d(network, 64, activation='elu', filter_size=3)
# network=batch_normalization(network)
network=conv_2d(network, 64, activation='elu', filter_size=3)
# network=batch_normalization(network)

#fully connected layers
network=fully_connected(network, 100, activation='elu')
# network=batch_normalization(network)
network=fully_connected(network, 50, activation='elu')
# network=batch_normalization(network)
network=fully_connected(network, 10, activation='elu')
# network=batch_normalization(network)
network=fully_connected(network, 1)
network=regression(network,optimizer='adam', learning_rate=0.0001, loss='mean_square', name='targets')

model=tflearn.DNN(network)


#initialize our server
sio = socketio.Server()
#our flask (web) app
app = Flask(__name__)
#init our model and image array as empty
prev_image_array = None

#set min/max speed for our autonomous car
MAX_SPEED = 25
MIN_SPEED = 10

#and a speed limit
speed_limit = MAX_SPEED

#registering event handler for the server
@sio.on('telemetry')
def telemetry(sid, data):
    if data:
        # The current steering angle of the car
        steering_angle = float(data["steering_angle"])
        # The current throttle of the car, how hard to push peddle
        throttle = float(data["throttle"])
        # The current speed of the car
        speed = float(data["speed"])
        # The current image from the center camera of the car
        image = Image.open(BytesIO(base64.b64decode(data["image"])))
        try:
            image = np.asarray(image)       # from PIL image to numpy array
            image = utils.preprocess(image) # apply the preprocessing
            image = np.array([image])       # the model expects 4D array
            image=image.reshape([-1,66,200,3])
            # predict the steering angle for the image
            steering_angle = float(model.predict(image))
            # lower the throttle as the speed increases
            # if the speed is above the current speed limit, we are on a downhill.
            # make sure we slow down first and then go back to the original max speed.
            global speed_limit
            if speed > speed_limit:
                speed_limit = MIN_SPEED  # slow down
            else:
                speed_limit = MAX_SPEED
            throttle = 1.0 - steering_angle**2 - (speed/speed_limit)**2

            print('{} {} {}'.format(steering_angle, throttle, speed))
            send_control(steering_angle, throttle)
        except Exception as e:
            print(e)

        # save frame
        if args.image_folder != '':
            timestamp = datetime.utcnow().strftime('%Y_%m_%d_%H_%M_%S_%f')[:-3]
            image_filename = os.path.join(args.image_folder, timestamp)
            image.save('{}.jpg'.format(image_filename))
    else:

        sio.emit('manual', data={}, skip_sid=True)


@sio.on('connect')
def connect(sid, environ):
    print("connect ", sid)
    send_control(0, 0)


def send_control(steering_angle, throttle):
    sio.emit(
        "steer",
        data={
            'steering_angle': steering_angle.__str__(),
            'throttle': throttle.__str__()
        },
        skip_sid=True)


if __name__ == '__main__':
    

    #load model
    model.load("autonomous-driving-car.tflearn")
    app = socketio.Middleware(sio, app)

    # deploy as an eventlet WSGI server
    eventlet.wsgi.server(eventlet.listen(('', 4567)), app)
