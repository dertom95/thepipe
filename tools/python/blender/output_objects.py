import bpy,sys


output = None
for i in range(len(sys.argv)):                                                                       
    if sys.argv[i]=="--output-file":
        output=sys.argv[i+1]
        break

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