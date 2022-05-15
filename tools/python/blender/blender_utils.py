import sys

def get_parameter(param_name):
    for i in range(len(sys.argv)):                                                                       
        if sys.argv[i]==param_name:
            return sys.argv[i+1]
    return None