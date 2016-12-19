
#MP4Box

import subprocess

filename = '20161003_222953_t1_after'

convCommand = 'MP4Box -add {0}.h264 {1}.mp4'.format(filename, filename)
conv = subprocess.Popen(convCommand, shell = True)


print 'done'