'''
20160229
treadmill

this is a master driver to run an experiment
this is NOT implemented to be a slave

if on Raspberry, turn on dio
	- dio to trigger a trial
	- dio on a new frame
	- dio to stop a trial
	
todo:
	include VideoServer.py
	not sure how to quickly trigger camera?
	if we are really master, then on startTrial we can just start the video
	- pass dio new frame to running pi camera
	
	- not sure if two python threads can share same dio pin (probably not)
	
	- maybe just make camera respond to dio start/stop/frame on its own set of three pins
		different from the start/stop/frame we are using here !!!
		
'''

import serial
import time
import os.path
from threading import Thread
import ConfigParser # to load config_treadmill.ini
#import logging

import RPi.GPIO as GPIO

try:
	import picamera
except ImportError:
	print "\t=========================================================="
	print "\tWarning: treadmill.py did not find python library picamera"
	print '\t\tThis usually happens when code is not running on Raspberry Pi'
	print "\t=========================================================="

# this imports from sibling directory triggercamera
import sys
from os import path
sys.path.append( path.dirname( path.dirname( path.abspath(__file__) ) ) )
from triggercamera import triggercamera

# i would prefer something like this but it requires **this to by run as a package 'python -m treadmill'
# from ..triggercamera import triggercamera
# import triggercamera.triggercamera

'''
logger = logging.getLogger('triggercamera')
logger.debug('treadmill body')
'''

##########################################
# this needs to take into acount (date, session)
class bRemoteFileServer():
	def __init__(self, sharPath='/mnt/datashare'):
		self.sharePath = sharPath # /mnt/datashare # //10.16.80.212/share
		if not os.path.isdir(self.sharePath):
			print 'ERROR: bRemoteFileServer() did not find sharePath:', self.sharePath
			
		self.origFolderList = ''
		
	def GetFolderList(self):
		d = self.sharePath
		self.origFolderList = [os.path.join(d,o) for o in os.listdir(d) if not o.startswith('.') and os.path.isdir(os.path.join(d,o))]

	def FindNewFolders(self):	
		# get the list of folders again and compare to find new folders
		d = self.sharePath
		newFolderList = [os.path.join(d,o) for o in os.listdir(d) if not o.startswith('.') and os.path.isdir(os.path.join(d,o))]
		newFolders = list(set(self.origFolderList) - set(newFolderList))
		print 'bRemoteFileServer.FindNewFolders() found', len(newFolders), 'in', self.sharePath
		mostRecentFolder = ''
		mostRecentTime = 0
		for folder in newFolders:
			mTime = os.path.getmtime(folder) 
			if mTime>mostRecentTime:
				mostRecentTime = mTime
				mostRecentFolder = folder
		return mostRecentFolder
		
##########################################
class treadmill():
	def __init__(self):
		print 'treadmill.treadmill() is starting, please wait ...'
		
		#logger.warning('treadmill constructor')
	
		self.trialRunning = 0

		self.animalID = 'default'
				
		self.socketio = None
		self.ser = None
		
		self.trial = {}
		self.trial['armStartTrigger'] = 0
		self.trial['savePath'] = ''
		self.trial['startDate'] = ''
		self.trial['startTime'] = ''
		self.trial['startSeconds'] = ''
		self.trial['filePath'] = ''
		self.trial['fileName'] = ''
		self.trial['trialNumber'] = 0
		self.trial['epochNumber'] = 0
		self.trial['frameNumber'] = 0
		self.trial['encoderNumber'] = 0
		self.trial['trialMessage'] = ''
		self.trial['prairieFolder'] = ''

		# lists of seconds as we receive events
		self.epochSeconds = []
		self.motorSeconds = []
		self.frameSeconds = []
		self.encoderSeconds = []
		
		# keep a list of (seconds, event, val)
		self.trialEvents = []
		
		#
		self.trialVideoBefore = ''
		self.trialVideoAfter = ''
		
		# user params
		self.ParseConfigFile()
		self.updatetrialdur()
		
		#save all serial data to file, set in setsavepath
		#self.savepath = '/home/pi/video/'
		
		# grab list of folders on startTrial(), find newest folder on stopTrial()
		#self.remoteFileServer = bRemoteFileServer()
		# replaced by self.trial['prairiefolder']
		#self.newestFolder = ''
		
		if self.options['usecamera']:
			self.camera = triggercamera.TriggerCamera()
			# self.camera.isArmed tells us if camera is armed (e.g. video is recording into a memory loop)
			self.camera.startArm() #start a circular stream
		else:
			self.camera = None
			
		self.trialStopSignal = 0 #used by backgroundTrial_thread()

		thread = Thread(target=self.backgroundTrial_thread, args=())
		thread.daemon  = True; #as a daemon the thread will stop when *this stops
		thread.start()
			
		GPIO.setwarnings(False)
		GPIO.setmode(GPIO.BCM)	 # set up BCM GPIO numbering  

		# self.triggerOutPin = 21 #output trigger to arduino/scope
		GPIO.setup(self.outpin['triggerOutPin'], GPIO.OUT)
		GPIO.output(self.outpin['triggerOutPin'], 1) # prairie expects trigger to be LOW

		# start trial with external trigger from prairie
		GPIO.setup(self.inpin['triggerInPin'], GPIO.IN)
		GPIO.setup(self.inpin['trialRunningPin'], GPIO.IN, pull_up_down=GPIO.PUD_UP) # prairie is always 5V and 0V on trigger
		GPIO.add_event_detect(self.inpin['triggerInPin'], GPIO.FALLING, callback=self.triggerInPin_callback) #, bouncetime=10)

		# self.trialRunningPin = 20 #input on when arduino trial running
		GPIO.setup(self.inpin['trialRunningPin'], GPIO.IN)
		# GPIO.setup(self.inpin['trialRunningPin'], GPIO.IN, pull_up_down=GPIO.PUD_UP) # prairie is always 5V and 0V on trigger
		GPIO.add_event_detect(self.inpin['trialRunningPin'], GPIO.BOTH, callback=self.trialRunningPin_callback) #, bouncetime=10)

		#self.motorOnPin = 16 #input on when arduino motor running
		GPIO.setup(self.inpin['motorOnPin'], GPIO.IN)
		GPIO.add_event_detect(self.inpin['motorOnPin'], GPIO.BOTH, callback=self.motorOnPin_callback) #, bouncetime=10)

		GPIO.setup(self.inpin['epochPin'], GPIO.IN)
		GPIO.add_event_detect(self.inpin['epochPin'], GPIO.BOTH, callback=self.epochPin_callback) #, bouncetime=10)

		GPIO.setup(self.inpin['framePin'], GPIO.IN)
		GPIO.add_event_detect(self.inpin['framePin'], GPIO.BOTH, callback=self.framePin_callback) #, bouncetime=10)

		GPIO.setup(self.inpin['encoderPin'], GPIO.IN)
		GPIO.add_event_detect(self.inpin['encoderPin'], GPIO.BOTH, callback=self.encoderPin_callback) #, bouncetime=10)

		#output trigger force stop on arduino
		
		#input pulsed for each new epoch
		
		#input pulsed for each rotary encoder update
				
	def newTrialEvent(self, seconds, event, val):
		eventStr = str(seconds) + ',' + event + ',' + str(val)
		self.trialEvents.append(eventStr)
		
	def ParseConfigFile(self):
		if self.trialRunning:
			print 'Warning: treadmill.ParseConfigFile() not alowed while trial is running'
			return
			
		print 'treadmill.ParseConfigFile() is reading config file from config_treadmill.ini'

		#Config = ConfigParser.ConfigParser()
		Config = ConfigParser.SafeConfigParser()
		configLoaded = Config.read('config.ini')
		if not configLoaded:
			print 'error: treadmill could not load config.ini file'
			return
		Config.sections()
		
		self.options = {}
		self.options['serialport'] = Config.get('serial','port')
		self.options['serialbaud'] = int(Config.get('serial','baud'))
		self.options['usecamera'] = bool(Config.get('camera','usecamera'))
		self.options['startcameradelay'] = int(Config.get('camera','startcameradelay')) # ms

		self.trialParam = {}
		self.trialParam['preDur'] = int(Config.get('trialParam','preDur'))
		self.trialParam['postDur'] = int(Config.get('trialParam','postDur'))
		self.trialParam['epochDur'] = int(Config.get('trialParam','epochDur'))
		self.trialParam['numEpoch'] = int(Config.get('trialParam','numEpoch'))
		self.trialParam['useMotor'] = Config.get('trialParam','useMotor') #{motorOn, motorLocked, motorFree}
		self.trialParam['motorDel'] = int(Config.get('trialParam','motorDel'))
		self.trialParam['motorDur'] = int(Config.get('trialParam','motorDur'))
		self.trialParam['motorSpeed'] = int(Config.get('trialParam','motorSpeed'))
		self.trialParam['trialDur'] = 0
		
		self.inpin = {}
		self.inpin['triggerInPin'] = int(Config.get('inpin','triggerInPin'))
		self.inpin['trialRunningPin'] = int(Config.get('inpin','trialRunningPin'))
		self.inpin['motorOnPin'] = int(Config.get('inpin','motorOnPin'))
		self.inpin['epochPin'] = int(Config.get('inpin','epochPin'))
		self.inpin['framePin'] = int(Config.get('inpin','framePin'))
		self.inpin['encoderPin'] = int(Config.get('inpin','encoderPin'))
		
		self.outpin = {}
		self.outpin['triggerOutPin'] = int(Config.get('outpin','triggerOutPin'))

		self.savepath = Config.get('system','savepath')

	def triggerInPin_callback(self, pin):
		if self.trial['armStartTrigger']:
			pinIsUp = GPIO.input(pin)
			pinIsDown = not pinIsUp
			# print 'trialRunningPin_callback()', 'pin:', pin, 'pinIsUp:', pinIsUp
			# when we get triggered by prairie, pin goes from 5 V to 0 V
			if pinIsDown and not self.trialRunning:
				# start
				# this will not work as it starts video than has seconds long delay for camera to startup
				print 'triggerInPin_callback() starting trial'
				self.startTrial(startNow=True)
			elif pinIsUp and self.trialRunning:
				# stop
				print 'triggerInPin_callback() stopping trial'
				self.trialStopSignal = 1
				self.stopTrial()
		
	def trialRunningPin_callback(self, pin):
		pinIsUp = GPIO.input(pin)
		pinIsDown = not pinIsUp
		# print 'trialRunningPin_callback()', 'pin:', pin, 'pinIsUp:', pinIsUp
		if pinIsUp and not self.trialRunning:
			pass
			#self.startTrial()
		elif not pinIsUp and self.trialRunning:
			print 'treadmill.trialRunningPin_callback() is forcing stop'
			self.trialStopSignal = 1
			#self.stopTrial()
		
	def motorOnPin_callback(self, pin):
		pinIsUp = GPIO.input(pin)
		now = time.time()
		#print 'motorOnPin_callback()', 'pin:', pin, 'pinIsUp:', pinIsUp
		if self.trialRunning:
			if pinIsUp:
				self.motorSeconds.append(now)
				self.newTrialEvent(now, 'motorOn', 1)
			else:
				self.newTrialEvent(now, 'motorOff', 1)
			
	def epochPin_callback(self, pin):
		pinIsUp = GPIO.input(pin)
		now = time.time()
		print 'epochPin_callback()', 'pin:', pin, 'pinIsUp:', pinIsUp
		if self.trialRunning:
			self.trial['epochNumber'] += 1
			self.epochSeconds.append(now)
			self.newTrialEvent(now, 'epoch', self.trial['epochNumber'])
			message = str(time.time() - self.trial['startSeconds']) + ',' + 'newEpoch' + ',' + str(self.trial['epochNumber'])
			self.trial['trialMessage'] = message
			#if pinIsUp:
			#	self.trial['epochNumber'] += 1
			#else:
			#	pass
			
	def framePin_callback(self, pin):
		pinIsUp = GPIO.input(pin)
		now = time.time()
		# print 'framePin_callback()', 'pin:', pin, 'pinIsUp:', pinIsUp
		if self.trialRunning:
			self.trial['frameNumber'] += 1
			self.frameSeconds.append(now)
			self.newTrialEvent(now, 'frame', self.trial['frameNumber'])
			#if pinIsUp:
			#	self.trial['frameNumber'] += 1
			#else:
			#	pass
			
	def encoderPin_callback(self, pin):
		pinIsUp = GPIO.input(pin)
		now = time.time()
		#print 'encoderPin_callback()', 'pin:', pin, 'pinIsUp:', pinIsUp
		if self.trialRunning:
			self.trial['encoderNumber'] += 1
			self.encoderSeconds.append(now)
			self.newTrialEvent(now, 'encoder', self.trial['encoderNumber'])
			'''
			if pinIsUp:
				self.trial['encoderNumber'] += 1
				self.encoderSeconds.append(now)
				self.newTrialEvent(now, 'encoder', self.trial['encoderNumber'])
			else:
				pass
			'''
			
	def attachsocket(self, socketio):
		print 'treadmill.attachsocket() attaching socketio:', socketio
		self.socketio = socketio

	def sendtosocket(self,str):
		if self.socketio:
			self.socketio.emit('serialdata', {'data': str})

	def backgroundTrial_thread(self):
		'''
		This needs to be thread because we do not want to call self.stopTrial()
		from within trialRunningPin_callback()
		'''
		while True:
			if self.trialRunning:
				if self.trialStopSignal:
					self.trialStopSignal=0
					self.stopTrial()
					print 'treadmill.backgroundTrial_thread() stopped trial'
			time.sleep(0.01)

	def ArmTrigger(self,on):
		if on:
			if self.trial['armStartTrigger']:
				print 'warning: treadmill.ArmTrigger(), trigger is alreay armed'
			else:
				self.trial['armStartTrigger'] = 1		
		else:
			self.trial['armStartTrigger'] = 0		
			
	def ArmVideo(self,on):
		if on:
			if self.camera.isArmed:
				print 'warning: treadmill.ArmVideo(), camera is alreay armed'
			else:
				self.camera.startArm() #start a circular stream			
		else:
			self.camera.stopArm()
			
	def startTrial(self, startNow=False):
		if self.trialRunning:
			print 'Warning: trial is already running -->> no action taken'
			return 0
			
		dateStr = time.strftime("%Y%m%d")
		
		self.trial['startDate'] = dateStr
		self.trial['startTime'] = time.strftime("%H%M%S")
		self.trial['trialNumber'] += 1
		self.trial['epochNumber'] = 0
		self.trial['frameNumber'] = 0
		self.trial['encoderNumber'] = 0
		self.trial['prairieFolder'] = ''
		
		self.trialEvents = []
		
		self.trialRunning = 1

		if startNow:
			# prairie expects trigger to be LOW
			GPIO.output(self.outpin['triggerOutPin'], 0)
			GPIO.output(self.outpin['triggerOutPin'], 1)
		
		self.sendtosocket('=== starting trial ' + str(self.trial['trialNumber']))

		# create a save path wih optional session name
		# use this to save *this files as well as video
		#
		# get a list of folder from a remote server (where prairie saves it folders/files)
		#self.remoteFileServer.GetFolderList()
		sessionStr = ''
		sessionFolder = ''
		if self.animalID and not (self.animalID == 'default'):
			sessionStr = self.animalID + '_'
			sessionFolder = dateStr + '_' + self.animalID
		
		thisSavePath = self.savepath + dateStr + '/'
		if not os.path.exists(thisSavePath):
			os.makedirs(thisSavePath)
		thisSavePath += sessionFolder + '/'
		if not os.path.exists(thisSavePath):
			os.makedirs(thisSavePath)
		self.trial['savePath'] = thisSavePath
		
		# start video here and then use GPIO trigger to start both arduino/scanimage
		if self.camera:
			if self.camera.isArmed:
				self.sendtosocket('starting camera')
				#self.camera.startArm() #start a circular stream
				self.camera.startVideo(thisTrial = self.trial['trialNumber'], savePath = thisSavePath)
				startcameradelay = self.options['startcameradelay']
				if not startNow and startcameradelay > 0:
					self.sendtosocket('waiting ' + str(startcameradelay) + ' (ms) before trigger')
					time.sleep(startcameradelay/1000)
			else:
				print 'Warning: treadmill.startTrial() did not start camera, it is not armed'
				
		# send out one digital pulse to trigger both (arduino and scope)		
		now = time.time() # seconds
		self.trial['startSeconds'] = now 
		self.newTrialEvent(now, 'startTrial', self.trial['trialNumber'])

		if not startNow:
			# prairie expects trigger to be LOW
			GPIO.output(self.outpin['triggerOutPin'], 0)
			GPIO.output(self.outpin['triggerOutPin'], 1)
			#GPIO.output(self.outpin['triggerOutPin'], 1)
			#GPIO.output(self.outpin['triggerOutPin'], 0)

		#print 'treadmill.startTrial() finished'
		
		return 1
		
	def stopTrial(self):
		self.trialRunning = 0

		self.sendtosocket('stopping trial ' + str(self.trial['trialNumber']))

		now = time.time() # seconds
		self.newTrialEvent(now, 'stopTrial', self.trial['trialNumber'])

		if self.camera:
			self.sendtosocket('stopping camera')
			self.camera.stopVideo()
			#self.camera.stopArm()
			self.trialVideoBefore = self.camera.beforefilename
			self.trialVideoAfter = self.camera.afterfilename
			
		#stop arduino
		#self.ser.write('stopTrial\n')

		#insert bRemoteFileServer
		#self.newestFolder = self.remoteFileServer.FindNewFolders() # may be empty
			
		#save the trial file
		self.newtrialfile()

		self.sendtosocket('finished trial ' + str(self.trial['trialNumber']))
		print 'treadmill.stopTrial() finished'
		
	def newtrialfile(self):
		dateStr = self.trial['startDate']
		timeStr = self.trial['startTime']
		trialNumber = self.trial['trialNumber']
		datetimeStr = dateStr + '_' + timeStr

		sessionStr = ''
		sessionFolder = ''
		if self.animalID and not (self.animalID == 'default'):
			sessionStr = self.animalID + '_'
			sessionFolder = dateStr + '_' + self.animalID
		
		thisSavePath = self.savepath + dateStr + '/'
		if not os.path.exists(thisSavePath):
			os.makedirs(thisSavePath)
		thisSavePath += sessionFolder + '/'
		if not os.path.exists(thisSavePath):
			os.makedirs(thisSavePath)
		
		trialFileName = sessionStr + datetimeStr + '_t' + str(trialNumber) + '.txt'
		trialFilePath = thisSavePath + trialFileName
		
		self.sendtosocket('saving file ' + trialFileName)

		self.trial['filePath'] = trialFilePath
		self.trial['fileName'] = trialFileName

		#
		# save arduino state to a file
		filePtr = open(trialFilePath, 'w')

		filePtr.write('date='+dateStr+';')
		filePtr.write('time='+timeStr+';')
		
		#
		# get state from arduino
		stateList = self.talktoserial('p')		
		for state in stateList:
			filePtr.write(state + ';')
			
		filePtr.write('\n')
		
		stateList = self.talktoserial('d')
		for line in stateList:
			filePtr.write(line + '\n')
			
		filePtr.close()
		
		#
		# save our python trial state to a file
		self.writeRaspberryTrialFile()
		
		
	def writeRaspberryTrialFile(self):
		
		dateStr = self.trial['startDate']
		timeStr = self.trial['startTime']
		trialNumber = self.trial['trialNumber']
		datetimeStr = dateStr + '_' + timeStr

		sessionStr = ''
		sessionFolder = ''
		if self.animalID and not (self.animalID == 'default'):
			sessionStr = self.animalID + '_'
			sessionFolder = dateStr + '_' + self.animalID

		thisSavePath = self.savepath + dateStr + '/'
		if not os.path.exists(thisSavePath):
			os.makedirs(thisSavePath)
		thisSavePath += sessionFolder + '/'
		if not os.path.exists(thisSavePath):
			os.makedirs(thisSavePath)

		raspberryFile = sessionStr + datetimeStr + '_t' + str(trialNumber) + "_r" + '.txt'
		raspberryFilePath = thisSavePath + raspberryFile

		self.sendtosocket('saving file ' + raspberryFilePath)

		filePtr = open(raspberryFilePath, 'w')
		filePtr.write('date='+dateStr+';')
		filePtr.write('time='+timeStr+';')
		if self.camera and self.camera.isArmed:
			filePtr.write('videoBefore=' + self.trialVideoBefore + ';')
			filePtr.write('videoAfter=' + self.trialVideoAfter + ';')
		if self.trial['prairieFolder']:
			filePtr.write('prairieFolder=' + self.trial['prairieFolder'] + ';') # was self.newestFolder
		filePtr.write('\n')
		filePtr.write('seconds,event,val\n')
		for event in self.trialEvents:
			filePtr.write(event + '\n')
		filePtr.close()
	
	def settrial2(self,trialDict):
		print 'treadmill.settrial2()'

		self.ser = serial.Serial(self.options['serialport'], self.options['serialbaud'], timeout=0.25)

		for key, value in trialDict.iteritems():
			#print key, value
			self.settrial(key, value)
			time.sleep(0.01)

		self.ser.close()
		self.ser = None
			
	def settrial(self, key, val):
		'''
		set value for *this
		send serial to set value on arduino
		'''
		if self.trialRunning:
			print 'warning: trial is running -->> no action taken'
			return 0

		#print "=== treadmill.settrial() key:'" + key + "' val:'" + val + "'"
		if key in self.trialParam:
			self.trialParam[key] = val
			serialCommand = 'settrial,' + key + ',' + val 
			serialCommand = str(serialCommand)
			print "\ttreadmill.settrial() writing to serial '" + serialCommand + "'"
			self.ser.write(serialCommand + '\n')
			
			self.updatetrialdur()
		else:
			print '\tERROR: treadmill:settrial() did not find', key, 'in trialParam dict'

	def talktoserial(self, this):
		#open serial
		self.ser = serial.Serial(self.options['serialport'], self.options['serialbaud'], timeout=0.25)
		
		time.sleep(.02)
		
		throwout = self.emptySerial()
		
		if this == 'd': #dump trial
			self.ser.write('d\n')
			theRet = self.emptySerial()
		if this == 'p': #print params
			self.ser.write('p\n')
			theRet = self.emptySerial()
		if this == 'v': #version
			self.ser.write('v\n')
			theRet = self.emptySerial()
		
		#close serial
		self.ser.close()
		self.ser = None
		
		return theRet
		
	def updatetrialdur(self):
		trialDur = int(self.trialParam['preDur']) + \
			(int(self.trialParam['numEpoch']) * int(self.trialParam['epochDur'])) + \
			int(self.trialParam['postDur'])
		self.trialParam['trialDur'] = trialDur
		
	def emptySerial(self):
		if self.trialRunning:
			print 'warning: trial is already running'
			return 0

		theRet = []
		line = self.ser.readline()
		i = 0
		while line:
			line = line.rstrip()
			theRet.append(line)
			#self.NewSerialData(line)
			line = self.ser.readline()
			i += 1
		return theRet
		
	def setserialport(self, newPort):
		if self.trialRunning:
			print 'warning: trial is already running'
			return 0

		if os.path.exists(newPort) :
			print 'setserialport() port', newPort, 'exists'
			self.options['serialport'] = newPort
			return 1
		else:
			print 'setserialport() port', newPort, 'does not exist'
			return 0
			
	def checkserialport(self):
		if self.trialRunning:
			print 'warning: trial is already running'
			return 0

		port = self.options['serialport']
		print 'treadmill.checkserialport() checking post:', port
		if os.path.exists(port) :
			print '   -->> exists'
			return 1, port
		else:
			print '   -->> does not exist'
			return 0, port
			
	'''
	def checkarduinoversion(self):
		if self.trialRunning:
			print 'warning: trial is already running'
			return 0

		self.talktoserial('v')
		#self.ser.write('v\n')
		#self.emptySerial()
	'''
		
	def SavePath(self, str=''):
		if str:
			self.savepath = str
		return self.savepath

