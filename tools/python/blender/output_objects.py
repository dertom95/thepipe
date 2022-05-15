import bpy

import sys

def get_parameter(param_name):
    for i in range(len(sys.argv)):                                                                       
        if sys.argv[i]==param_name:
            try:
                return sys.argv[i+1]
            except:
                return True
    return None


output = get_parameter("--output-file")

if not output:
    raise AttributeError("Couldn't find --output-file: %s" % sys.argv)

data=""
for obj in bpy.data.objects:
    data+="%s\n" % obj.name

text_file = open(output, "w")
 
#write string to file
text_file.write(data)
 
#close file
text_file.close()