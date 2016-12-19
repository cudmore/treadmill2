platformio run #compile arduino code
platformio run --target upload #compile and upload
platformio run --target clean #clean project 

platformio serialports monitor -p /dev/ttyACM0 -b 115200
