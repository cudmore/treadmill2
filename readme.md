This is documentation for controlling a behavioral experiment using an Arduino microcontroller with a Python based web interface. First, we document building an Arduino controlled motorized circular treadmill. Next, we provide Python source code to control an experiment through a web-browser. Our aim is to provide a starting point for open-source behavioral experiments that can be extended to new experimental designs.

Please see the documentation site at: [http://blog.cudmore.io/treadmill/](http://blog.cudmore.io/treadmill/)

<IMG SRC="https://github.com/cudmore/treadmill/blob/master/docs/docs/img/screenshot1.png" WIDTH=450 style="border:1px solid gray">

## Installation

 - This code is intended to run on a Raspberry Pi with an Arduino attached via USB.
 - **Important**: You need to download two repositories for this to work: (i) this repository, e.g. treadmill and (ii) the triggercamera repository. In the end the treadmill and triggercamera folders need to be sitting next to each other in the same parent folder.
 
## Running

 - **treadmill/treadmill_app.py**: Python code to run a web server and talk to an arduino connected from a Raspberry via USB.
 - **treadmill/treadmill.py**: Python code for backend. Does all the work. In particular (i) talks to arduino connected via USB, (ii) start/stop a trial with GPIO, (iii) saves text files at end of a trial.
 
 - **treadmill/arduino/src/treadmill_2.cpp**: Arduino code to run the treadmill

 - **triggercamera/triggercamera.py**: Python code to control a Rapsberry Pi Camera connected via a CSI cable.
 
 
## To Do

 - 20161003, add web button to re-parse config.ini
 