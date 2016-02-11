#!/usr/bin/env python
# created by chris@drumminhands.com
# see instructions at http://www.drumminhands.com/2014/06/15/raspberry-pi-photo-booth/

import os
import glob
import random
import time
import traceback
from time import sleep
import RPi.GPIO as GPIO
import picamera # http://picamera.readthedocs.org/en/release-1.4/install2.html
import atexit
import sys
import socket
import uuid
import pygame
import pytumblr # https://github.com/tumblr/pytumblr
import config
from signal import alarm, signal, SIGALRM, SIGKILL

########################
### Variables Config ###
########################
generated_tag = ""
generated_filepath = ""

led1_pin = 15 # LED 1
led2_pin = 19 # LED 2
led3_pin = 21 # LED 3
led4_pin = 23 # LED 4

button1_pin = 22 # pin for the big red button
button2_pin = 18 # pin for button to shutdown the pi
button3_pin = 16 # pin for button to end the program, but not shutdown the pi

enable_color_effects = 0 # default 1. Change to 0 if you don't want to upload pics.
enable_image_effects = 0 # default 1. Change to 0 if you don't want to upload pics.
post_online = 1 # default 1. Change to 0 if you don't want to upload pics.

total_pics = 4 # number of pics to be taken
capture_delay = 4 # delay between pics
prep_delay = 3 # number of seconds at step 1 as users prep to have photo taken
gif_delay = 100 # How much time between frames in the animated gif
restart_delay = 4 # how long to display finished message before beginning a new session

monitor_w = 800
monitor_h = 480
transform_x = 800 # how wide to scale the jpg when replaying
transfrom_y = 480 # how high to scale the jpg when replaying

offset_x = 0 # how far off to left corner to display photos
offset_y = 0 # how far off to left corner to display photos
replay_delay = 1 # how much to wait in-between showing pics on-screen after taking
replay_cycles = 1 # how many times to show each photo on-screen after taking

test_server = 'www.google.com'
real_path = os.path.dirname(os.path.realpath(__file__))

# Setup the tumblr OAuth Client
client = pytumblr.TumblrRestClient(
    config.consumer_key,
    config.consumer_secret,
    config.oath_token,
    config.oath_secret,
);

####################
### Other Config ###
####################
GPIO.setmode(GPIO.BOARD)

GPIO.setup(led1_pin,GPIO.OUT) # LED 1
GPIO.setup(led2_pin,GPIO.OUT) # LED 2
GPIO.setup(led3_pin,GPIO.OUT) # LED 3
GPIO.setup(led4_pin,GPIO.OUT) # LED 4

GPIO.setup(button1_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP) # falling edge detection on button 1
GPIO.setup(button2_pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN) # falling edge detection on button 2
GPIO.setup(button3_pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN) # falling edge detection on button 3

GPIO.output(led1_pin,False);
GPIO.output(led2_pin,False);
GPIO.output(led3_pin,False);
GPIO.output(led4_pin,False); 

#################
### Functions ###
#################

def cleanup():
  print('Ended abruptly')
  GPIO.cleanup()
atexit.register(cleanup)

def shut_it_down(channel):  
    print "Shutting down..." 
    GPIO.output(led1_pin,True);
    GPIO.output(led2_pin,True);
    GPIO.output(led3_pin,True);
    GPIO.output(led4_pin,True);
    time.sleep(3)
    os.system("sudo halt")

def exit_photobooth(channel):
    print "Photo booth app ended. RPi still running" 
    GPIO.output(led1_pin,False);
    GPIO.output(led2_pin,False);
    GPIO.output(led3_pin,False);
    GPIO.output(led4_pin,False);
    time.sleep(3)
    sys.exit()
      
def is_connected():
  try:
    # see if we can resolve the host name -- tells us if there is
    # a DNS listening
    host = socket.gethostbyname(test_server)
    # connect to the host -- tells us if the host is actually
    # reachable
    s = socket.create_connection((host, 80), 2)
    return True
  except:
     pass
  return False  

def tag_gen(size=5):
    random = str(uuid.uuid4()) # Convert UUID format to a Python string.
    random = random.upper() # Make all characters uppercase.
    random = random.replace("-","") # Remove the UUID '-'.
    return random[0:size] # Return the random string. 

def init_pygame():
    pygame.init()
    size = (pygame.display.Info().current_w, pygame.display.Info().current_h)
    pygame.display.set_caption('Photo Booth Pics')
    pygame.mouse.set_visible(False) #hide the mouse cursor	
    return pygame.display.set_mode(size, pygame.FULLSCREEN)

def show_image(image_path):
    screen = init_pygame()
    img=pygame.image.load(image_path) 
    img = pygame.transform.scale(img,(transform_x,transfrom_y))
    screen.blit(img,(offset_x,offset_y))
    pygame.display.flip()

def display_pics(jpg_group):
    # this section is an unbelievable nasty hack - for some reason Pygame
    # needs a keyboardinterrupt to initialise in some limited circs (second time running)
    class Alarm(Exception):
        pass
    def alarm_handler(signum, frame):
        raise Alarm
    signal(SIGALRM, alarm_handler)
    alarm(3)
    try:
        screen = init_pygame()
        alarm(0)
    except Alarm:
        raise KeyboardInterrupt
    for i in range(0, replay_cycles): #show pics a few times
		for i in range(1, total_pics+1): #show each pic
			filename = generated_filepath + jpg_group + "-0" + str(i) + ".jpg"
                        show_image(filename);
			time.sleep(replay_delay) # pause 

				
# define the photo taking function for when the big button is pressed 
def start_photobooth(): 
	################################# Begin Step 1 ################################# 
	show_image(real_path + "/blank.png")
	print "Get Ready"
	GPIO.output(led1_pin,True);
	show_image(real_path + "/instructions.png")
	sleep(prep_delay) 

	GPIO.output(led1_pin,False)
	show_image(real_path + "/blank.png")
	
	camera = picamera.PiCamera()
	pixel_width = 1200 #use a smaller size to process faster, and tumblr will only take up to 500 pixels wide for animated gifs
	pixel_height = monitor_h * pixel_width // monitor_w
	camera.resolution = (pixel_width, pixel_height) 
	camera.vflip = True
	camera.hflip = False

	#random effect (filter and color)
	if enable_color_effects:
		colour = (random.randint(0, 256),random.randint(0, 256))
		print "Colour effect: " + str(colour)
		camera.color_effects = colour
	
	if enable_image_effects:
		image_effect = picamera.PiCamera.IMAGE_EFFECTS.keys()[random.randint(0, len(picamera.PiCamera.IMAGE_EFFECTS))]	
		print "Filter effect: " + image_effect
		camera.image_effect = image_effect
	
	
	# camera.saturation = -100 # comment out this line if you want color images
	camera.start_preview()

	sleep(2) #warm up camera

	################################# Begin Step 2 #################################
	print "Taking pics" 
	now = time.strftime("%Y-%m-%d-%H:%M:%S") #get the current date and time for the start of the filename
	try: #take the photos
		for i, filename in enumerate(camera.capture_continuous(generated_filepath + now + '-' + '{counter:02d}.jpg')):
			GPIO.output(led2_pin,True) #turn on the LED
			print(filename)
			sleep(1) #pause the LED on for just a bit was 0.25
			GPIO.output(led2_pin,False) #turn off the LED
			sleep(capture_delay) # pause in-between shots
			if i == total_pics-1:
				break
	finally:
		camera.stop_preview()
		camera.close()
	########################### Begin Step 3 #################################
	print "Creating an animated gif" 
	if post_online:
		show_image(real_path + "/uploading.png")
	else:
		show_image(real_path + "/processing.png")

	GPIO.output(led3_pin,True) #turn on the LED
	graphicsmagick = "gm convert -delay " + str(gif_delay) + " " + generated_filepath + now + "*.jpg " + generated_filepath + now + ".gif" 
	os.system(graphicsmagick) #make the .gif
	print "Uploading to tumblr. Please check " + config.tumblr_blog + ".tumblr.com soon."

	if post_online: # turn off posting pics online in the variable declarations at the top of this document
		connected = is_connected() #check to see if you have an internet connection
		while connected: 
			try:
				file_to_upload = generated_filepath + now + ".gif"
				client.create_photo(config.tumblr_blog, state="published", tags=["PartyPics", generated_tag], data=file_to_upload)
				break
			except ValueError:
				print "Oops. No internect connection. Upload later."
				try: #make a text file as a note to upload the .gif later
					file = open(generated_filepath + now + "-FILENOTUPLOADED.txt",'w')   # Trying to create a new file or open one
					file.close()
				except:
					print('Something went wrong. Could not write file.')
					sys.exit(0) # quit Python
	GPIO.output(led3_pin,False) #turn off the LED
	
	########################### Begin Step 4 #################################
	GPIO.output(led4_pin,True) #turn on the LED
	try:
		display_pics(now)
	except Exception, e:
		tb = sys.exc_info()[2]
		traceback.print_exception(e.__class__, e, tb)
		
	#pygame.quit()
	print "Done"
	GPIO.output(led4_pin,False) #turn off the LED
	
	if post_online:
		show_image(real_path + "/finished.png")
	else:
		show_image(real_path + "/finished2.png")
	
	time.sleep(restart_delay)
	show_image(real_path + "/intro.png");
	
	GPIO.remove_event_detect(button2_pin)
	GPIO.add_event_detect(button2_pin, GPIO.BOTH, callback=shut_it_down, bouncetime=100) 
	
####################
### Main Program ###
####################

# when a falling edge is detected on button2_pin and button3_pin, regardless of whatever   
# else is happening in the program, their function will be run   
#GPIO.add_event_detect(button2_pin, GPIO.FALLING, callback=shut_it_down, bouncetime=300)
generated_tag = tag_gen(6)
generated_filepath = config.file_path + "/" + generated_tag + "/"
if not os.path.exists(generated_filepath):
    os.makedirs(generated_filepath)

print "PartyPics app running..." 
GPIO.output(led1_pin,True); #light up the lights to show the app is running
GPIO.output(led2_pin,True);
GPIO.output(led3_pin,True);
GPIO.output(led4_pin,True);

time.sleep(2)

GPIO.output(led1_pin,False); #turn off the lights
GPIO.output(led2_pin,False);
GPIO.output(led3_pin,False);
GPIO.output(led4_pin,False);

show_image(real_path + "/intro.png");
GPIO.add_event_detect(button2_pin, GPIO.BOTH, callback=shut_it_down, bouncetime=100) 

while True:
        GPIO.wait_for_edge(button1_pin, GPIO.FALLING)
	time.sleep(0.2) #debounce
	start_photobooth()
