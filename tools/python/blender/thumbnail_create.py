import bpy
import sys,math
from mathutils import Vector

def get_parameter(param_name):
    for i in range(len(sys.argv)):                                                                       
        if sys.argv[i]==param_name:
            try:
                return sys.argv[i+1]
            except:
                return True
    return None

def get_bool(param_name,default_value=None):
    result = get_parameter(param_name)
    if not result:
        return default_value
    else:
        if result.lower()=="true":
            return True
        else:
            return False

def get_string(param_name,default_value=None):
    result = get_parameter(param_name)
    if not result:
        return default_value
    else:
        return result

def get_float(param_name,default_value=None):
    result = get_parameter(param_name)
    if not result:
        return default_value
    else:
        return float(result)


def get_int(param_name,default_value=None):
    result = get_parameter(param_name)
    if not result:
        return default_value
    else:
        return int(result)


output_folder = get_parameter("--output-folder")
if not output_folder:
    raise AttributeError("blender-thumbnail needs --output--folder but got [%s]" % sys.argv)

collections = get_parameter("--collections")
if not collections:
    raise AttributeError("blender-thumbnail needs --collections but got [%s]"%sys.argv)

rotation = get_string("--rotation","0,0,0")

scale = get_float("--cam-scale",18)

width = get_int("--width",128)
height = get_int("--height",128)

scene_name = get_string("--scene-name","__generic")

filename_postfix=get_string("--postfix","")

recursive_collections = get_parameter("--recursive-collections")

recursive_collections=recursive_collections is not None

if recursive_collections:
    from addon_tilemap_creator.tilemap_operators import parent_collection_to_csv_children    
    collection_names=""
    for colname in collections.split(","):
        col = bpy.data.collections[colname]
        collection_names=parent_collection_to_csv_children(col,collection_names,True)
        print("COLNAME %s => %s" % (colname,collection_names))
    collections = collection_names

print("args: %s",sys.argv)

print("output_folder={output_folder} cam_ortho_scale={scale} col_names={collections} recursive={recursive}".format(output_folder=output_folder,scale=scale,collections=collections,recursive=recursive_collections))
rotation=eval("Vector((%s))"%rotation)
rotation[0]=math.radians(rotation[0])
rotation[1]=math.radians(rotation[1])
rotation[2]=math.radians(rotation[2])
print("ROTATION: %s" % rotation)
bpy.ops.tmc.render_tiles(scene_name=scene_name,output_folder=output_folder,cam_ortho_scale=scale,col_names=collections,rotation=rotation,render_width=width,render_height=height,save_filenames_append=True,save_filename_postfix=filename_postfix)

sys.exit(0)