#(1) need to use eventlet, otherwise .run() defaults to gevent() which is SLOW
#(2) monkey_path() wraps some functions to call eventlet equivalents
#   in particular time.sleep() is redirected to coresponding eventlet() call
#
from flask import Flask, abort, render_template, send_file, request
from flask.ext.socketio import SocketIO, emit

import random # testing
import os, time, random
from datetime import datetime
from threading import Thread
import eventlet
import json
import subprocess # to get ip address
#import logging

from treadmill import treadmill
from treadmillAnalysis import treadmillAnalysis
from plotly_plot import myplotlyplot

from settings import APP_ROOT

'''
logging.basicConfig(filename='treadmill_app.log',level=logging.DEBUG,format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('treadmill_app')
logger.debug('xxx This message is from treadmill_app')
'''

#see: https://github.com/miguelgrinberg/Flask-SocketIO/issues/192
eventlet.monkey_patch()

#eventlet.debug.hub_prevent_multiple_readers(False)

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
app.debug = True
app.config['DATA_FOLDER'] = 'data/'

#socketio = SocketIO(app)
socketio = SocketIO(app, async_mode='eventlet')

#namespace = '/test'
namespace = ''

thread = None #second thread used by background_thread()
ser = None

mytreadmill = None
myanalysis = None

def background_thread():
	"""Example of how to send server generated events to clients."""
	while True:
		try:
			time.sleep(.7)
			response = MakeServerResponse()		
	
			jsonResponse = json.dumps(response)
			#print 'background_thread() sending serverUpdate:', jsonResponse
			socketio.emit('serverUpdate', jsonResponse, namespace=namespace)
		except:
			print 'ERROR: treadmill_app.background_thread()'
				
def MakeServerResponse():

	#print 'MakeServerResponse()'
	now = datetime.now()
	dateStr = now.strftime("%m/%d/%y")
	timeStr = now.strftime("%H:%M:%S.%f")

	#logging.debug('MakeServerResponse ' + timeStr)
	
	response = {}
	response['currentdate'] = dateStr
	response['currenttime'] = timeStr
	try:

		response['savepath'] = mytreadmill.savepath
		response['animalID'] = mytreadmill.animalID
	
		response['filePath'] = mytreadmill.trial['filePath']
		response['fileName'] = mytreadmill.trial['fileName']
	
		response['trialRunning'] = mytreadmill.trialRunning
		response['trialNumber'] = mytreadmill.trial['trialNumber']
		response['epochNumber'] = mytreadmill.trial['epochNumber']
		response['frameNumber'] = mytreadmill.trial['frameNumber']

		response['epochDur'] = mytreadmill.trialParam['epochDur']	
		response['numEpoch'] = mytreadmill.trialParam['numEpoch']	
		response['useMotor'] = mytreadmill.trialParam['useMotor']
		response['motorDel'] = mytreadmill.trialParam['motorDel']
		response['motorDur'] = mytreadmill.trialParam['motorDur']
		response['trialDur'] = mytreadmill.trialParam['trialDur'] / 1000
		
		if mytreadmill.trialRunning:
			response['elapsedSeconds'] = round(time.time() - mytreadmill.trial['startSeconds'], 2)
			
		if mytreadmill.trial['trialMessage']:
			socketio.emit('trialupdate', {'data': mytreadmill.trial['trialMessage']})
		
		if mytreadmill.camera:
			response['useCamera'] = 1
			response['cameraArmed'] = mytreadmill.camera.isArmed
		else:
			response['useCamera'] = 0
			response['cameraArmed'] = 0
		
		response['armStartTrigger'] = mytreadmill.trial['armStartTrigger']
		
	except:
		print 'ERROR: treadmill_app.MakeServerResponse()'
		
	return response
	
@app.route('/')
def index():
	global thread
	if thread is None:
		print('starting background thread')
		thread = Thread(target=background_thread)
		thread.daemon  = True; #as a daemon the thread will stop when *this stops
		thread.start()
	theRet = render_template('index.html', treadmill=mytreadmill)
	return theRet

@app.route('/form2')
def form2():
	return render_template('form_sandbox.html')

'''
@app.route('/', defaults={'req_path': ''})
@app.route('/<path:req_path>')
def dir_listing(req_path):
    BASE_DIR = '/Users/vivek/Desktop'

    # Joining the base and the requested path
    abs_path = os.path.join(BASE_DIR, req_path)

    # Return 404 if path doesn't exist
    if not os.path.exists(abs_path):
        return abort(404)

    # Check if path is a file and serve
    if os.path.isfile(abs_path):
        return send_file(abs_path)

    # Show directory contents
    files = os.listdir(abs_path)
    return render_template('files.html', files=files)
'''

#from: http://stackoverflow.com/questions/23718236/python-flask-browsing-through-directory-with-files
@app.route('/', defaults={'req_path': ''})
@app.route('/<path:req_path>')
def dir_listing(req_path):

	print '\n'
	print 'req_path:', req_path
	
	# Joining the base and the requested path
	abs_path = os.path.join(APP_ROOT, req_path)

	print 'abs_path:', abs_path

	# Return 404 if path doesn't exist
	if not os.path.exists(abs_path):
		return abort(404)

	# Check if path is a file and serve
	if os.path.isfile(abs_path):
		return send_file(abs_path)

	# Show directory contents
	if os.path.isdir(abs_path):
		print 'IS DIRECTORY:', abs_path
	files = os.listdir(abs_path)
	return render_template('files.html', path=req_path.replace('data/','') + '/', files=files)

@app.route('/analysis')
def analysis():
	#list = myAnalysis.getlist()
	#return render_template('analysis.html', list=list)
	myAnalysis.builddb('')
	return render_template('analysis2.html')
	
@app.route('/help')
def help():
	return render_template('help.md')
	
@app.route('/p5')
def index_highchart():
	return render_template('p5.html')

@app.route('/grafica')
def index_grafica():
	return render_template('grafica.html')

# 20161105, when prairie finished with a stack
# signal folder name it just created/saved .tif fies into
# return a string igor can parse as a list
@app.route('/setprairiefolder=<folderName>')
def setprairiefolder(folderName):
	print 'setprairiefolder folderName:', folderName
	mytreadmill.trial['prairieFolder'] = folderName
	ret = ''
	for item in mytreadmill.trial:
		ret += item + '=' + str(mytreadmill.trial[item]) + ';'
	return ret
	#return jsonify({'trial:' : mytreadmill.trial})


'''
@app.route('/plotly')
def plotly():
	file = 'data/20160306_211227_t4_d.txt'
	print 'file=', file
	plotheader, plothtml = myplotlyplot('data/' + file)
	print 'plothtml=', plothtml
	plothtml = os.path.basename(plothtml)
	return render_template(plothtml)
'''

@socketio.on('connectArduino', namespace=namespace) #
def connectArduino(message):
	emit('my response', {'data': message['data']})
	print 'connectArduino', message['data']

@socketio.on('startarduinoButtonID', namespace=namespace) #
def startarduinoButton(message):
	print 'startarduinoButtonID'
	mytreadmill.startTrial()
	
@socketio.on('stoparduinoButtonID', namespace=namespace) #
def stoparduinoButtonID(message):
	print 'stoparduinoButtonID'
	mytreadmill.stopTrial()
	
@socketio.on('printArduinoStateID', namespace=namespace) #
def printArduinoStateID(message):
	emit('serialdata', {'data': '=== Arduino State'})
	list = mytreadmill.talktoserial('p')
	for item in list:
		emit('serialdata', {'data': item})
	#
	emit('serialdata', {'data': '=== Last Trial'})
	list = mytreadmill.talktoserial('d')
	for item in list:
		emit('serialdata', {'data': item})
	
@socketio.on('emptySerialID', namespace=namespace) #
def printArduinoStateID(message):
	emit('serialdata', {'data': '=== Empty Serial'})
	list = mytreadmill.emptySerial()
	for item in list:
		emit('serialdata', {'data': item})

@socketio.on('checkserialportID', namespace=namespace) #
def checkserialportID(message):
	exists, str = mytreadmill.checkserialport()
	if exists:
		emit('serialdata', {'data': "OK: " + str})
	else:
		emit('serialdata', {'data': "ERROR: " + str})

@socketio.on('setSerialPortID', namespace=namespace) #
def setSerialPort(message):
	portStr = message['data']
	ok = mytreadmill.setserialport(portStr)
	if ok:
		emit('serialdata', {'data': "OK: " + portStr})
	else:
		emit('serialdata', {'data': "ERROR: " + portStr})

@socketio.on('arduinoVersionID', namespace=namespace) #
def arduinoVersionID(message):
	list = mytreadmill.talktoserial('v')
	for item in list:
		emit('serialdata', {'data': item})

@socketio.on('my event', namespace=namespace) #responds to echo
def test_message(message):
	emit('my response', {'data': message['data']})

@socketio.on('my broadcast event', namespace=namespace)
def test_message(message):
	emit('my response', {'data': message['data']}, broadcast=True)

@socketio.on('connect', namespace=namespace)
def test_connect():
	emit('my response', {'data': 'Connected'})

@socketio.on('disconnect', namespace=namespace)
def test_disconnect():
	print('*** treadmill_app -- Client disconnected')

@socketio.on('trialform', namespace=namespace)
def trialform(message):
	'''message is trailFormDict from treadmill object'''
	print '\n=== treadmill_app.trialform():', message

	mytreadmill.settrial2(message)

	trialDiv = myAnalysis.plottrialparams(mytreadmill.trialParam)
	emit('trialPlotDiv', {'data': trialDiv})

	#I am using this to turn off spinner
	emit('serialdata', {'data': "=== Trial Form Done ==="})

@socketio.on('animalform', namespace=namespace)
def animalform(message):
	print 'animalform:', message
	animalID = message['animalID']
	mytreadmill.animalID = animalID
	#mytreadmill.settrial('dur', dur)
	emit('my response', {'data': "animal id is now '" + animalID + "'"})


@socketio.on('plotTrialButtonID', namespace=namespace)
def plotTrialButton(message):
	filePath = message['data']
	print 'plotTrialButton() filename:' + filePath
	divStr = myplotlyplot(filePath,'div')
	emit('lastTrialPlot', {'plotDiv': divStr})

@socketio.on('plotTrialHeaderID', namespace=namespace)
def plotTrialHeader(message):
	filename = message['data']
	print 'plotTrialHeader() filename:' + filename
	headerStr = myAnalysis.loadheader(filename)
	emit('headerDiv', {'headerStr': headerStr})

@socketio.on('filterTrial', namespace=namespace)
def filterTrial(message):
	filename = myAnalysis.builddb(message['data'])
	emit('refreshList', {'data': filename})

@socketio.on('armvideo', namespace=namespace)
def armvideo(message):
	mytreadmill.ArmVideo(int(message['data']))
	emit('my response', {'data': 'armvideo'})

@socketio.on('armtrigger', namespace=namespace)
def armtrigger(message):
	print 'treadmill_app:armtrigger() ' + str(message['data'])
	mytreadmill.ArmTrigger(int(message['data']))
	emit('my response', {'data': 'armtrigger'})

def whatismyip():
	arg='ip route list'
	p=subprocess.Popen(arg,shell=True,stdout=subprocess.PIPE)
	data = p.communicate()
	split_data = data[0].split()
	ipaddr = split_data[split_data.index('src')+1]
	return ipaddr

if __name__ == '__main__':
	try:
	
		print '\tteadmill_app::__main__'
		mytreadmill = treadmill()
		
		#dataRoot = os.path.join(APP_ROOT, "data") + '/'
		#mytreadmill.savepath(dataRoot)
		dataRoot = mytreadmill.SavePath()
		
		mytreadmill.attachsocket(socketio)
		
		#print 'initializing treadmillAnalysis'
		myAnalysis = treadmillAnalysis()
		myAnalysis.assignfolder(dataRoot)
		
		print('\tstarting server')
		socketio.run(app, host=whatismyip(), port=5010, use_reloader=False)
		#socketio.run(app, host='0.0.0.0', port=5010, use_reloader=True)
		print('\tfinished')
	except:
		print '\t... treadmill_app is exiting'
		raise