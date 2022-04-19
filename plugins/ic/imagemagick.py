from re import M
from tools import BoolValue, CLICommand,NumberValue

image_converter = {
    "indexed" : {
        "parameters" : {
            "colors" : NumberValue(16,0,255,True),
            "dither" : BoolValue(False),
        },
        "command": CLICommand("convert #in# -colors #colors# #dither|+dither# #out#")
    },
    "psx-tim" : {
        "parameters" : {
            
        },
        "command":CLICommand("tools/psx/img2tim -o #out# #vpos|-org @# #bpp|-bpp @# #plt|-plt @#    ")
    }
}


