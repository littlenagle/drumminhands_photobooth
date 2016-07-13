#!/usr/bin/env python
# created by chris@drumminhands.com
# see instructions at http://www.drumminhands.com/2014/06/15/raspberry-pi-photo-booth/
# This code is a mashup of three separate but related projects that I have combined to make it function how I envision
# The bulk of the code comes from here, along with the inspiration:  https://github.com/drumminhands/drumminhands_photobooth
# Part of the countdown setup comes from here:  https://github.com/galadril/drumminhands_photobooth/  (I had trouble with the screen going black after the 3rd picture and not 
#coming back on until the processing image appeared.)
# The changes to the countdown setup came from here:  https://github.com/jrleeman/PiBooth/ (really neat ideas in his code.  Very clean and well documented, however, no preview of 
# the images afterwards.)  Also has code for uploading to twitter as an expansion.
# Future development I want to add to the code is the idea that galadril had to create a short press for animated gif and long press for mosaic.  I think that would be an awesome 
# addition to the code



import os
import glob
import random
import time
import traceback
import re
from time import sleep
import RPi.GPIO as GPIO #using physical pin numbering change in future?
import picamera # http://picamera.readthedocs.org/en/release-1.4/install2.html
import atexit
import sys, getopt
import socket
import pygame
#import cups
import fcntl
import struct
import commands
import uuid
from PIL import Image, ImageDraw, ImageFont
import pytumblr # https://github.com/tumblr/pytumblr
#from twython import Twython
import config
import shutil
import datetime as dt
from signal import alarm, signal, SIGALRM, SIGKILL
from PIL import Image, ImageDraw

########################
### Variables Config ###
########################
generated_tag = ""
generated_filepath = ""

led1_pin = 15 # LED 1
led2_pin = 19 # LED 2
led3_pin = 21 # LED 3
led4_pin = 23 # LED 4

MakeAnimatedGif = 1 # 1 = animated gif, 0 = mosaic

button1_pin = 22 # pin for the big red button
button2_pin = 18 # pin for button to shutdown the pi
button3_pin = 16 # pin for button to end the program, but not shutdown the pi

enable_color_effects = 0 # default 1. Change to 0 if you don't want to upload pics.
enable_image_effects = 0 # default 1. Change to 0 if you don't want to upload pics.
post_online = 0 # default 1. Change to 0 if you don't want to upload pics.

total_pics = 4 # number of pics to be taken
capture_delay = 0 # delay between pics
prep_delay = 3 # number of seconds at step 1 as users prep to have photo taken
gif_delay = 100 # How much time between frames in the animated gif
restart_delay = 4 # how long to display finished message before beginning a new session
count_from = 3 # How long should the countdown be before each photo

monitor_w = 800
monitor_h = 600
transform_x = 800 # how wide to scale the jpg when replaying
transfrom_y = 600 # how high to scale the jpg when replaying

offset_x = 0 # how far off to left corner to display photos
offset_y = 0 # how far off to left corner to display photos
replay_delay = 1 # how much to wait in-between showing pics on-screen after taking
replay_cycles = 2 # how many times to show each photo on-screen after taking

test_server = 'www.google.com'
real_path = os.path.dirname(os.path.realpath(__file__))

font = ImageFont.truetype("/usr/share/fonts/truetype/freefont/FreeSans.ttf", 200)
bigfont = pygame.font.Font(None, 800)
smfont = pygame.font.Font(None, 600)
tinyfont = pygame.font.Font(None, 300)

#extract the ip address (or addresses) from ifconfig
found_ips = []
ips = re.findall( r'[0-9]+(?:\.[0-9]+){3}', commands.getoutput("/sbin/ifconfig"))
for ip in ips:
  if ip.startswith("255") or ip.startswith("127") or ip.endswith("255"):
    continue
  found_ips.append(ip)

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
GPIO.setup(button2_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP) # falling edge detection on button 2
GPIO.setup(button3_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP) # falling edge detection on button 3

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
	
def drawText(font, textstr, clear_screen=True, color=(250, 10, 10)):
    """
    Draws the given string onto the pygame screen.
    Parameters:
    -----------
    font : object
        pygame font object
    textstr: string
        text to be written to the screen
    clean_screan : boolean
        determines if previously shown text should be cleared
    color : tuple
        RGB tuple of font color
    Returns:
    --------
    None
    """
    if clear_screen:
        screen.fill(black)  # black screen

    # Render font
    pltText = font.render(textstr, 1, color)

    # Center text
    textpos = pltText.get_rect()
    textpos.centerx = screen.get_rect().centerx
    textpos.centery = screen.get_rect().centery

    # Blit onto screen
    screen.blit(pltText, textpos)

    # Update
    pygame.display.update()


def clearScreen():
    """
    Clears the pygame screen of all drawn objects.
    Parameters:
    -----------
    None
    Returns:
    --------
    None
    """
    screen.fill(black)
    pygame.display.update()

	
#def countdown(camera):
#	overlay_renderer = None
#	for j in range(1,4):
#		img = Image.new("RGB", (monitor_w, monitor_h))
#		draw = ImageDraw.Draw(img)
#		draw.text(((monitor_w/2)-50,(monitor_h/2)-50), str(4-j), (255, 255, 255), font=font)
#		if not overlay_renderer:
#			overlay_renderer = camera.add_overlay(img.tostring(),layer=3,size=img.size,alpha=28);
#		else:
#			overlay_renderer.update(img.tostring())
#		sleep(1)
#
#	img = Image.new("RGB", (monitor_w, monitor_h))
#	draw = ImageDraw.Draw(img)
#	draw.text((monitor_w/2,monitor_h/2), " ", (255, 255, 255), font=font)
#	overlay_renderer.update(img.tostring())

def doCountdown(pretext="Ready", pretext_fontsize=600, count_from):
    """
    Performs on screen countdown
    Parameters:
    -----------
    pretext : string
        Text shown before countdown starts
    pretext_fontsize : int
        Size of pretext font
    countfrom : int
        Number to count down from
    """
    pretext_font = pygame.font.Font(None, pretext_fontsize)
    drawText(pretext_font, pretext)
    sleep(1)
    clearScreen()

    # Count down on the display
    for i in range(count_from, 0, -1):
        # Draw text on the screen
        drawText(bigfont, str(i))

        # Flash the LED during the second of dead time
        #for j in range(4):
        #    outputToggle(ledPin, False, time=0.125)
        #    outputToggle(ledPin, True, time=0.125)

    # Clear the screen one final time so no numbers are left
    clearScreen()
	
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
	black = 0, 0, 0
	return pygame.display.set_mode(size, pygame.FULLSCREEN)

def show_image(image_path, t):
	screen = init_pygame()
	img=pygame.image.load(image_path).convert()
	img = pygame.transform.scale(img,(transform_x,transfrom_y))
	
	sprite = pygame.sprite.Sprite()
	sprite.image = img
	sprite.rect = img.get_rect()
	
	font = pygame.font.SysFont('Sans', 20)
	text=font.render(t, 1,(255,255,255))
	sprite.image.blit(text, (10, 10))
	
	group = pygame.sprite.Group()
	group.add(sprite)
	group.draw(screen)
	
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
		for i in range(0, total_pics): #show each pic
			filename = generated_filepath + jpg_group + "-0" + str(i) + ".jpg"
                        show_image(filename, "");
			time.sleep(replay_delay) # pause 

def create_mosaic(jpg_group): 
	now = jpg_group 
	#moving original pics to backup
	# copypics = "cp " +file_path + now + "*.jpg "+ file_path+"PB_archive/"
	# print copypics
	# os.system(copypics)

	#resizing + montaging
	print "Resizing Pics..." #necessary?
	#convert -resize 968x648 /home/pi/photobooth/pics/*.jpg /home/pi/photobooth/pics_tmp/*_tmp.jpg
	graphicsmagick = "gm mogrify -resize 968x648 " + generated_filepath + now + "*.jpg" 
	#print "Resizing with command: " + graphicsmagick
	os.system(graphicsmagick) 

	print "Montaging Pics..."
	graphicsmagick = "gm montage " + generated_filepath + now + "*.jpg -tile 2x2 -geometry 1000x699+10+10 " + generated_filepath + now + "_mosaic.jpg" 
	#print "Montaging images with command: " + graphicsmagick
	os.system(graphicsmagick) 
	
# define the photo taking function for when the big button is pressed 
def start_photobooth(): 
	################################# Begin Step 1 ################################# 
	show_image(real_path + "/blank.png", "")
	print "Get Ready"
	GPIO.output(led1_pin,True);
	show_image(real_path + "/instructions.png", "")
	sleep(prep_delay) 

	GPIO.output(led1_pin,False)
	show_image(real_path + "/blank.png", "")
	
	camera = picamera.PiCamera()
	pixel_width = 1000 #use a smaller size to process faster, and tumblr will only take up to 500 pixels wide for animated gifs
	pixel_height = monitor_h * pixel_width // monitor_w
	camera.resolution = (pixel_width, pixel_height) 
	camera.vflip = False
	camera.hflip = False
	
	#camera.sharpness = 10
	#camera.contrast = 30
	#camera.brightness = 60
	#camera.saturation = 50
	
	#camera.video_stabilization = True
	#camera.exposure_compensation = 0
	#camera.exposure_mode = 'night'
	camera.meter_mode = 'average'
	camera.awb_mode = 'auto'
	
	#random effect (filter and color)
	#if enable_color_effects:
	#	colour = (random.randint(0, 256),random.randint(0, 256))
	#	print "Colour effect: " + str(colour)
	#	camera.color_effects = colour
	
	#if enable_image_effects:
	#	image_effect = picamera.PiCamera.IMAGE_EFFECTS.keys()[random.randint(0, len(picamera.PiCamera.IMAGE_EFFECTS))]	
	#	print "Filter effect: " + image_effect
	#	camera.image_effect = image_effect
	
	camera.saturation = -20 # comment out this line if you want color images
	camera.start_preview()
	sleep(2) #warm up camera
	
	################################# Begin Step 2 #################################
	print "Taking pics"
	now = time.strftime("%Y-%m-%d-%H:%M:%S") #get the current date and time for the start of the filename
	try: #take the photos
		#for i, filename in enumerate(camera.capture_continuous(config.file_path + now + '-' + '{counter:02d}.jpg')):
		for i in range(0, total_pics):
			filename = generated_filepath + now + "-0" + str(i) + ".jpg"
			doCountdown()
			#countdown(camera)
			GPIO.output(led2_pin,True) #turn on the LED
			camera.capture(filename)
			print(filename)
			sleep(0.25) #pause the LED on for just a bit
			GPIO.output(led2_pin,False) #turn off the LED
			sleep(capture_delay) # pause in-between shots
			if i == total_pics-1:
				break
	finally:
		camera.stop_preview()
		camera.close()
		
	########################### Begin Step 3 #################################
	show_image(real_path + "/processing.png", "")

	if MakeAnimatedGif:
		print "Creating an animated gif" 
	
		GPIO.output(led3_pin,True) #turn on the LED
		graphicsmagick = "gm convert -delay " + str(gif_delay) + " " + generated_filepath + now + "*.jpg " + generated_filepath + now + ".gif" 
		os.system(graphicsmagick) #make the .gif
	else:
		print "Creating an Mosaic" 
		try:
			create_mosaic(now)
		except Exception, e:
			tb = sys.exc_info()[2]
			traceback.print_exception(e.__class__, e, tb)
	
	if post_online:
		show_image(real_path + "/uploading.png", "")
		
	print "Uploading to tumblr. Please check " + config.tumblr_blog + ".tumblr.com soon."
	if post_online: # turn off posting pics online in the variable declarations at the top of this document
		connected = is_connected() #check to see if you have an internet connection
		while connected: 
			try:
				if MakeAnimatedGif:
					file_to_upload = generated_filepath + now + ".gif"
				else:
					file_to_upload = generated_filepath + now + "_mosaic.jpg"
					
				client.create_photo(config.tumblr_blog, state="published", tags=["Photobooth", generated_tag], data=file_to_upload)
				break
			except ValueError:
				print "Oops. No internect connection. Upload later."
				try: #make a text file as a note to upload the .gif later
					file = open(generated_filepath + now + "-FILENOTUPLOADED.txt",'w')   # Trying to create a new file or open one
					file.close()
				except:
					print('Something went wrong. Could not write file.')
					#sys.exit(0) # quit Python
					
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
		show_image(real_path + "/finished.png", "")
	else:
		show_image(real_path + "/finished2.png", "")
	
	time.sleep(restart_delay)
	show_image(real_path + "/intro.png", "");
	
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

print "Photobooth running..." 
GPIO.output(led1_pin,True); #light up the lights to show the app is running
GPIO.output(led2_pin,True);
GPIO.output(led3_pin,True);
GPIO.output(led4_pin,True);

time.sleep(2)

GPIO.output(led1_pin,False); #turn off the lights
GPIO.output(led2_pin,False);
GPIO.output(led3_pin,False);
GPIO.output(led4_pin,False);

print "IP: "+"\r\n".join(found_ips)
show_image(real_path + "/intro.png", "IP: "+"\r\n".join(found_ips));
time.sleep(5)

#GPIO.add_event_detect(button2_pin, GPIO.BOTH, callback=exit_photobooth, bouncetime=100)
GPIO.add_event_detect(button3_pin, GPIO.FALLING, callback=exit_photobooth, bouncetime=300)


try:  
	while True:
		GPIO.wait_for_edge(button1_pin, GPIO.BOTH)
		time.sleep(0.5) #debounce
		start_photobooth()
except KeyboardInterrupt:  
    # here you put any code you want to run before the program   
    # exits when you press CTRL+C  
    print "\n", counter # print value of counter  
  
except:  
    # this catches ALL other exceptions including errors.  
    # You won't get any error messages for debugging  
    # so only use it once your code is working  
    print "Other error or exception occurred!"  
  
finally:  
    GPIO.cleanup() # this ensures a clean exit  