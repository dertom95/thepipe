from opcode import hasconst
import pytmx
import math
from PIL import Image
from pathlib import Path

map={0:0}

def Parse(tilemap):
    used_tiles = {}
    used_types = {}
    tiled_map = pytmx.TiledMap(tilemap)
    images = {}
    object_types = {
        "":0
    }

    tilemaps = []
    got_object_layer = False
    for layer in tiled_map.layers:
        lid = layer.id-1
        tilemaps.append(layer)
        row_nr = 0
        col_nr = 0
        
        layer_type=type(layer)
        if layer_type==pytmx.pytmx.TiledTileLayer:
            for tile in layer.tiles():
                (x,y,image_data) = tile
                if not image_data:
                    continue
                gid = layer.data[y][x]
                props = tiled_map.get_tile_properties_by_gid(gid)
                _type = "all"
                if props and "type" in props:
                    _type = props["type"]
                filename = image_data[0]
                if not filename in images:
                    images[filename] = Image.open(filename)
                image_data += (images[filename],)
                used_tiles[gid]=image_data
                if _type not in used_types:
                    used_types[_type]=[]
                ut = used_types[_type]
                if gid not in ut:
                    ut.append(gid)

        elif layer_type==pytmx.pytmx.TiledObjectGroup:
            got_object_layer=True
            for obj in layer:
                if obj.type:
                    if obj.type not in object_types:
                        object_types[obj.type]=len(object_types)

    return (used_tiles,used_types,tilemaps,tilemap,(got_object_layer,object_types))

def CreatePSXTilesetImage(data):
    global map
    used_tiles = data[0]
    used_types = data[1]
    tilemap_filebase=Path(data[3]).stem
    amount_tiles = len(used_tiles)

    (filename,rect,flags,image) = used_tiles[1]
    tileW = rect[2]
    tileH = rect[3]

    cols = (amount_tiles * tileH)/256
    rows = math.floor(256/tileH)
    height = 256
    width = cols*tileW
    width = math.ceil(width/64)*64
        
    empty_image = Image.new("RGBA",(width,height),(0,0,0,255))
    
    destXPx=0
    destYPx=0
    destX=0
    destY=0
    current_start=0
    current_count=0
    for _type in used_types:
        current_start=current_count
        for tileNr in used_types[_type]:
#   for tileNr in used_tiles:
            (filename,(x,y,w,h),flags,image)=used_tiles[tileNr]
            box = (x,y,x+w,y+w)
            region = image.crop(box)

            box = (destXPx,destYPx,destXPx+w,destYPx+h)
            empty_image.paste(region,box) 
            destX+=1
            if destX>=cols:
                destX=0
                destY+=1
            destXPx=destX*tileW
            destYPx=destY*tileH
            current_count+=1
            map[tileNr]=current_count

        used_types[_type]={
            "start" : current_start,
            "end" : current_count
        }

    empty_image.save("%s.png" % tilemap_filebase)

def make_safe_filename(s):
    def safe_char(c):
        if c.isalnum():
            return c
        else:
            return "_"
    return "".join(safe_char(c) for c in s).rstrip("_")

def CreatePSXTileMapFile(data):
    (used_tiles,used_types,tilemaps,tilemapfile,flags) = data
    (got_object_layer,object_types) = flags
    tilemap_filebase=Path(tilemapfile).stem

    object_types_data = {}
    object_types_data_amount = {}

    result="""
#ifndef __tilemap__{0}
#define __tilemap__{0}

#include<stdint.h>
#include<stdbool.h>

    """.format(make_safe_filename(tilemap_filebase))

    if got_object_layer:
        result+="""
  #ifndef object_data_struct
  # define object_data_struct        
    typedef struct _objectdata {
        int x,y,w,h,rotation;
        int object_type;
        char* name;
        unsigned char visible;
        short* point_data;
        unsigned char points_amount;        
    } ObjectData;
  #endif  

    #define _OBJTYPE_NO_TYPE 0
        """
        for obj_type in object_types:
            if obj_type=="":
                continue
            result+="""
    #define _OBJTYPE_{0} {1}
            """.format(obj_type.upper(),object_types[obj_type])

        for _type in used_types:
            data = used_types[_type]
            result+="""
    bool is_{0}(uint16_t tile_id){{
        return tile_id>={1} && tile_id<{2};
    }}
            
            """.format(_type,data["start"],data["end"])
    
    layer_nr=0
    for layer in tilemaps:
        layer_type = type(layer)
        lname = make_safe_filename("_%s_%s_%s" % (layer_nr,tilemap_filebase,layer.name))
        if layer_type==pytmx.pytmx.TiledTileLayer:
            data="{"
            for line in layer.data:
                for gid in line:
                    data+="%s,"%map[gid]
            data = data[:len(data)-1]+"}"

            output="""
    unsigned short {0}_width={1};
    unsigned short {0}_height={2};
    unsigned short {0}_data[]={3};

            """.format(lname,layer.width,layer.height,data)
        
            result+=output
            layer_nr+=1
        elif layer_type==pytmx.pytmx.TiledObjectGroup:
            data=""
            points=""
            obj_nr = 0
            for obj in layer:
                if not obj.type:
                    obj.type=""
                if not hasattr(obj,"points"):
                    obj.points=[]

                points_name = "path_%s_%s" % (lname,obj_nr)
                current_points=""
                for pnt in obj.points:
                    current_points+="%s,%s," % (math.floor(pnt.x),math.floor(pnt.y))
                points+="short %s[]={%s};\n" % (points_name,current_points)

                data+="""
        {{.x={0},.y={1},.w={2},.h={3},.object_type={4},.name="{5}",.rotation={6},.visible={7},.point_data={8},.points_amount={9} }},
                """.format(obj.x,obj.y,obj.width,obj.height,object_types[obj.type],obj.name,obj.rotation,obj.visible,points_name,len(obj.points))


                if obj.type:
                    if not obj.type in object_types_data:
                        object_types_data[obj.type]=""
                        object_types_data_amount[obj.type]=0
                    object_types_data[obj.type]+="&{0}_data[{1}],".format(lname,obj_nr)
                    object_types_data_amount[obj.type]+=1

                obj_nr+=1
            
            output="""
            %s

    ObjectData %s_data[]={
        %s
    };
            """ % (points,lname,data)

            result+=output


    for objtype in object_types_data:
        result+="""
        const unsigned short all_{0}_amount={2};
        ObjectData* all_{0}[]={{ {1} }};
        """.format(objtype,object_types_data[objtype],object_types_data_amount[objtype])

    result+="""
#endif
    """


    data_file = open(tilemap_filebase+".h","w")
    n = data_file.write(result)
    data_file.close()
    

data = Parse('tests/data/tiled/map2.tmx')   
CreatePSXTilesetImage(data) 
CreatePSXTileMapFile(data)    
