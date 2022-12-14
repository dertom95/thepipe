#!/usr/bin/python3

import re,argparse,os,time
import shutil,copy,glob

from sys import platform
from pathlib import Path
from xml.etree import ElementTree
from xsd_creator import XSDCreator
from tools import BoolValue, InputFile, MultiFileValue,NumberValue,FileValue,EnumValue,StringValue, VectorValue,InputFile

XMLNS=None
XMLR=None
HOST=None
HOST_EXPORT=None
HOST_ENV_SOURCE=None
ARG_AUTOCOMPLETE_REPOSITORIES=False
ARG_STOP_ON_ERROR=False
ARG_AUTOCOMPLETE_REPOSITORY_LEVELS=2
ARG_GENERATE_XSD=False
ARG_TP_XSD_FOLDER=None
ARG_TARGET="all"

INPUT_TYPE_SINGLEFILE = 0
INPUT_TYPE_MULTIFILE  = 1
INPUT_TYPE_STANDALONE = 2

if platform == "linux" or platform == "linux2":
    HOST="linux"
    HOST_EXPORT="export"
    HOST_ENV_SOURCE="source"
elif platform == "darwin":
    HOST="mac"
    HOST_EXPORT="export"
    HOST_ENV_SOURCE="source" #??
elif platform == "win32":
    HOST="win"
    HOST_EXPORT="set"
    HOST_ENV_SOURCE=""

else:
    raise AttributeError("Unknown platform: %s"  %  platform)

from xml.dom import minidom

def xml_pretty(xml):
    xmlstr = minidom.parseString(ElementTree.tostring(xml)).toprettyxml(indent="   ")
    return xmlstr

def write_string(filename,data):
    try:
        os.makedirs(os.path.dirname(filename))
    except:
        pass
    f = open(filename, "w")
    f.write(str(data))
    f.close()  

class XSDManager:
    instance=None

    def get():
        if not XSDManager.instance:
            XSDManager.instance=XSDManager()
        return XSDManager.instance

    def __init__(self):
        self.targets=[]
        self.files=[]
        self.ids=[]
        self.converter_qns=[]

        self.creator=XSDCreator("tp-runtime")      

        main=self.creator.create_block(None,"main")
        self.creator.add_attribute(main,"target")
        self.creator.add_attribute(main,"required")

        repositories=self.creator.create_block(main,"repositories")
        filerepo=self.creator.create_block(repositories,"file-repository")
        self.creator.add_attribute(filerepo,"name",True)
        self.creator.add_attribute(filerepo,"folder",True)
        self.creator.add_attribute(filerepo,"levels")

        fr_filter=self.creator.create_block(filerepo,"filter")
        self.creator.add_attribute(fr_filter,"extension")

        self.pipeline=self.creator.create_block(main,"pipeline")
        self.creator.add_attribute(self.pipeline,"pl-name",True)
        self.creator.add_attribute(self.pipeline,"target",False,"targettype")

        p_init=self.creator.create_block(self.pipeline,"init")
        pi_eval=self.creator.create_block(p_init,"eval",None,True)

        file_type=self.creator.create_type("file_type")
        self.creator.add_attribute(file_type,"filename",True,"files_enum" if ARG_AUTOCOMPLETE_REPOSITORIES else "xs:string")
        self.creator.add_attribute(file_type,"id")
        self.creator.add_attribute(file_type,"target")

        pi_input=self.creator.create_block(p_init,"input")
        pii_file=self.creator.create_block(pi_input,"file","file_type")
        pii_eval=self.creator.create_block(pi_input,"eval",None,True)

        multifile=self.creator.create_block(pi_input,"multifile")
        self.creator.add_attribute(multifile,"name",True)
        piim_file=self.creator.create_block(multifile,"file","file_type")
        piim_eval=self.creator.create_block(multifile,"eval",None,True)

        self.actions=self.creator.create_block(self.pipeline,"actions","actions_type")

        self.actions_type=self.creator.create_type("actions_type")
        self.creator.add_attribute(self.actions_type,"resetfiles",False,"booltype")
        self.creator.add_attribute(self.actions_type,"target",False,"targettype")

        self.set_input = self.creator.create_block(self.actions_type,"set-input")
        self.creator.add_attribute(self.set_input,"id",True,"ids_enum")

        #self.creator.add_attribute(pii_file,"filename",True,"filetype" if ARG_AUTOCOMPLETE_REPOSITORIES else "xs:string")

        p_eval=self.creator.create_block(self.actions_type,"eval",None,True)

        p_output=self.creator.create_block(self.actions_type,"output")
        self.creator.add_attribute(p_output,"target",False,"targettype")
        self.creator.add_attribute(p_output,"use_file",False,"booltype")
        self.creator.add_attribute(p_output,"copy_metafiles")
        #self.creator.add_attribute(p_output,"filename",True)
        self.creator.add_attribute(p_output,"filename",True,"files_enum" if ARG_AUTOCOMPLETE_REPOSITORIES else "xs:string")        

        p_multifile_create = self.creator.create_block(self.actions_type,"multifile-create")
        self.creator.add_attribute(p_multifile_create,"id")

        p_multifile_add = self.creator.create_block(self.actions_type,"multifile-add")
        self.creator.add_attribute(p_multifile_add,"id")

        loop = self.creator.create_block(self.actions_type,"loop")
        self.creator.add_attribute(loop,"init")
        self.creator.add_attribute(loop,"condition",True,"xs:string")
        self.creator.add_attribute(loop,"step")
        self.creator.add_attribute(loop,"use_folder")

        loop_actions=self.creator.create_block(loop,"loop-actions","actions_type")

        if_tag = self.creator.create_block(self.actions_type,"if")

        on_tag = self.creator.create_block(if_tag,"on")
        self.creator.add_attribute(on_tag,"condition",True)
        self.creator.create_block(on_tag,"if-actions","actions_type")
        
        else_tag = self.creator.create_block(if_tag,"else")
        self.creator.create_block(else_tag,"if-actions","actions_type")
        


    def add_files(self,files):
        self.files.extend(files)
    
    def add_target(self,target_name):
        if target_name not in self.targets:
            self.targets.append(target_name)

    def add_id(self,id):
        if id not in self.ids:
            self.ids.append(id)
            self.files.append("id://%s"%id)

    def add_converter(self,converter):
        qn_without_target = converter.qualified_name(False)
        add_qn_without_target =  qn_without_target not in self.converter_qns

        def add_converter_internal(name):
            xsdconverter=self.creator.create_block(self.actions_type,name)
            for (id,output,tool_type,type_signature,description,expose) in converter.params.values():
                if not expose:
                    continue
                tool_type.put_xsd(self.creator,xsdconverter,name,id)
        
        add_converter_internal(converter.qualified_name())
        if add_qn_without_target:
            add_converter_internal(qn_without_target)
            self.converter_qns.append(qn_without_target)


    def xsdcreator_write(self,filename):
        self.creator.create_enum_type("targettype",self.targets)
        self.creator.create_enum_type("files_enum",self.files)
        self.creator.create_enum_type("ids_enum",self.ids)
        self.creator.create_enum_type("booltype",["true","false"],True)

        result=self.creator.to_string()
        #print(result)

        xsd_file = open(filename,"w")
        xsd_file.write(result)
        xsd_file.close()    


def xgetrequired(xml,attrib):
    if attrib in xml.attrib:
        return xml.attrib[attrib]
    else:
        raise NameError("required attribute '%s' was not found in:\n%s" %(attrib,ElementTree.tostring(xml)))




def xget(xml,attrib,default_value=None,to_lower=False):
    result=default_value
    if attrib in xml.attrib:
        result=xml.attrib[attrib]
    if result==None:
        return None
    if to_lower:
        return result.lower()
    else:
        return result

def xget_b(xml,attrib,default_value):
    if attrib in xml.attrib:
        return xml.attrib[attrib].lower()=="true"
    else:
        return default_value

def xget_parameters(xml):
    global XMLNS
    params={}
    for param in xml.iter("%sparam"%XMLNS):
        id = xgetrequired(param,"id")
        output = xget(param,"output","")
        default_value = xget(param,"default","")
        required = xget_b(param,"required",False)
        expose = xget_b(param,"expose",True if id!="in" and id!="out" else False )
        type_signature = xget(param,"type","string",True)
        description = xget(param,"description","")
        tool_type=create_type(type_signature,default_value,required,param)
        params[id]=(id,output,tool_type,type_signature,description,expose)
    return params

def create_parameter_tuple(id,output,tool_type,description,expose=True):
    return (id,output,tool_type,None,description,expose)    

def trim_text(text):
    prefix=None
    result=""
    for line in text.split("\n"):
        if len(line)==0:
            continue
        if not prefix:
            prefix=line.replace(line.lstrip(),"")
        result+="%s\n"%line.replace(prefix,"",1)
    return result

def replace_special_characters(input):
    quotes_pattern=r"''(.*?)''"
    m=re.search(quotes_pattern,input)
    while m:
        replacement="\"%s\"" % m.group(1)
        input = input.replace(m.group(0),replacement)
        m=re.search(quotes_pattern,input)
    return input



def create_type(type_signature,default_value,required,xml_param):
    if type_signature=="bool":
        return BoolValue(default_value,required)
    elif type_signature=="string":
        return StringValue(default_value,required)
    elif type_signature.startswith("vec"):
        m=re.match(r"vec\[(.+?)\]",type_signature)
        if not m:
            raise AttributeError("Unknown vectortype:%s" % type_signature)
        dim = int(m.group(1))
        return VectorValue(dim,default_value,required)
    elif type_signature.startswith("number"):
        if type_signature=="number":
            return NumberValue(0,0,float("inf"),required)
        
        m = re.match(r"number\[([0-9.]+?)-([0-9.]+?)\]",type_signature)
        
        if m:
            from_value = m.group(1)
            to_value   = m.group(2)
            return NumberValue(default_value,from_value,to_value,required)
        else:
            raise AttributeError("Unknown number-signature:%s" % type_signature)
    elif type_signature=="file":
        return FileValue(required)
    elif "enum" in type_signature:
        strict=type_signature.startswith("strict-enum")
        result_type = EnumValue(default_value,required,strict)
#        enum_pattern=r"enum\[(([\w\d]+?)(,|\]))"
        enum_pattern=r"enum\[((.+?)(,|\]))"
        
        m = re.search(enum_pattern,type_signature)
        while m:
            all=m.group(1)
            enum_value=m.group(2)
            result_type.add_enum_value(enum_value)

            type_signature=type_signature.replace(all,"")
            m = re.search(enum_pattern,type_signature)
        return result_type
    elif type_signature.startswith("multifile"):
        result = MultiFileValue(required)

        splits=type_signature.split(",")
        if len(splits)>1:
            #got additional data
            result.data=splits[1:]
        return result
    else:
        raise AttributeError("Unknown type:%s" % type_signature)

def walklevel(some_dir, level=1):
    some_dir = some_dir.rstrip(os.path.sep)
    if not os.path.exists(some_dir):
        return

    assert os.path.isdir(some_dir)
    num_sep = some_dir.count(os.path.sep)
    for root, dirs, files in os.walk(some_dir):
        yield root, dirs, files
        num_sep_this = root.count(os.path.sep)
        if num_sep + level <= num_sep_this:
            del dirs[:] 

class Converter:
    CONVERTERS = {}

    def __init__(self,xml):
        global XMLNS
        self.xml_filename=xgetrequired(xml,"xml_filename")
        self.xml_folder=os.path.dirname(self.xml_filename)        
        self.prefix = xgetrequired(xml,"prefix")
        self.name   = xgetrequired(xml,"name")
        self.target = xget(xml,"target","all")
        self.standalone = xget(xml,"standalone",False)
        if ARG_GENERATE_XSD:
            XSDManager.get().add_target(self.target)        
        
        cmd = xml.find("%scommand"%XMLNS)
        if cmd is None:
            raise AttributeError("Converter without command-tag!: %s" % ElementTree.tostring(xml))

        self.tool_id = xgetrequired(cmd,"toolid")
        self.tool_args = xgetrequired(cmd,"arguments")
        self.tool_out_ext = xget(cmd,"extension",None)
        self.metafiles = xget(cmd,"metafiles",None)

        self.params = xget_parameters(xml)
        id_param = create_parameter_tuple("id","",StringValue(""),"id to reference later in pipeline")
        self.params["id"]=id_param

        if ARG_GENERATE_XSD:
            XSDManager.get().add_converter(self)
    
    def qualified_name(self,add_target=True):
        if add_target:
            return "%s-%s-%s" % (self.prefix,self.name,self.target)
        else:
            return "%s-%s" % (self.prefix,self.name)

    def add(converter):
        qn = converter.qualified_name()
        if qn in Converter.CONVERTERS:
            raise KeyError("There is already a converter with the qn:%s" % qn)

        Converter.CONVERTERS[qn]=converter

    def add_from_xml(xml):
        converter = Converter(xml)
        Converter.add(converter)

    def reset_params(self):
        for key in self.params:
            id,output,tool_type,type_signature,description,expose=self.params[key]
            tool_type.reset()

    def execute(self,context_data,counter,temp_folder,input_data,xml_data,file_history,executions):
        self.reset_params()
        context,shared_locals=context_data
        input_type,name,input=input_data
        output_tool_type = None

        for attrib in xml_data.attrib:
            if attrib in self.params:
                value = xml_data.attrib[attrib]
                id,output,tool_type,type_signature,description,expose=self.params[attrib]
                tool_type.set(value)

        if not self.standalone:                       
            id,output,tool_type,type_signature,description,expose=self.params["in"]
        
            if input_type==INPUT_TYPE_MULTIFILE and type(tool_type)==FileValue:
                # multifiles on single-file converter. unfold and call this execute for each file inside of multifile
                output_files=[]

                output_result = 0
                output_metafiles = []
                output_id = None
                file_extension=None

                for m_repo,m_file in input:
                    xml_data_clone=copy.deepcopy(xml_data)
                    single_inputdata=(INPUT_TYPE_SINGLEFILE,m_repo,m_file)
                    id,name,result,input_type,input,file_extension,_metafiles = self.execute(context_data,counter,temp_folder,single_inputdata,xml_data_clone,[m_file],executions)
                    if id:
                        output_id=id

                    if result!=0:
                        output_result=result
                    output_files.append((m_repo,input))
                    
                    if _metafiles:
                        _metafiles=context.resolve_variables_in_string(_metafiles,shared_locals)
                        for mf in _metafiles.split(','):
                            if mf not in output_metafiles:
                                output_metafiles.append(mf) 

                return output_id,name,output_result,INPUT_TYPE_MULTIFILE,output_files,file_extension,output_metafiles

            tool_type.set(input)
            
            id,output,tool_type,type_signature,description,expose=self.params["out"]
            output_tool_type = tool_type

            if input_type==INPUT_TYPE_SINGLEFILE:
                filename, file_extension = os.path.splitext(input)
                file_extension=file_extension[1:]
                filename_without_folder = os.path.basename(filename)
                if "___" in filename_without_folder:
                    splits = filename_without_folder.split("___")
                    filename_without_folder = splits[1]
                if self.tool_out_ext:
                    file_extension=self.tool_out_ext

                if tool_type.value_set():
                    out_file = context.resolve_variables_in_string(tool_type.get(),shared_locals)
                    out_file = context.resolve_file(out_file,False)
                    dir_name = os.path.dirname(out_file)
                    shared_locals["temp_folder"]=dir_name
                    try:
                        os.makedirs(dir_name)
                    except:
                        pass
                else:
                    folder_name = "%s%s-%s" %(temp_folder,str(counter).rjust(4,'0'),self.qualified_name())
                    shared_locals["temp_folder"]=folder_name                    
                    out_file = "%s/%s.%s" % (folder_name,filename_without_folder,file_extension)
                    try:
                        os.makedirs(folder_name)
                    except:
                        pass

                if type(tool_type)==FileValue:
                    tool_type.set(out_file)
                    output_type=INPUT_TYPE_SINGLEFILE
                elif type(tool_type)==MultiFileValue:
                    output_type=INPUT_TYPE_MULTIFILE
                    _name = xget(xml_data,"name")
                    if _name:
                        name = _name

            else:
                file_extension=self.tool_out_ext
                ttype=type(tool_type)

                name_orig = name
                if "___" in name:
                    splits = name.split("___")
                    name_orig=splits[1]
                    
                if ttype==FileValue:
                    if tool_type.value_set():
                        out_file = context.resolve_variables_in_string(tool_type.get(),shared_locals)
                        out_file = context.resolve_file(out_file,False)
                        dir_name = os.path.dirname(out_file)
                        try:
                            os.makedirs(dir_name)
                        except:
                            pass
                        shared_locals["temp_folder"]=dir_name
                        
                    else:
                        folder_name = "%s%s-%s" %(temp_folder,str(counter).rjust(4,'0'),self.qualified_name())
                        shared_locals["temp_folder"]=folder_name

                        out_file = "%s/%s.%s" % (folder_name,name_orig,file_extension)
                        try:
                            os.makedirs(folder_name)
                        except:
                            pass                        
                        #out_file = "%s%s-%s___%s.%s" %(temp_folder,str(counter).rjust(4,'0'),self.qualified_name(),name_orig,file_extension)
                    
                    tool_type.set(out_file)
                    output_type=INPUT_TYPE_SINGLEFILE
                elif ttype==MultiFileValue:
                    output_type=INPUT_TYPE_MULTIFILE

                    # for filename in input:
                    #     filename, file_extension = os.path.splitext(file_history[0])
                    #     file_extension=file_extension[1:]
                    #     filename_without_folder = os.path.basename(filename)
                    #     if self.tool_out_ext:
                    #         file_extension=self.tool_out_ext

                    #     out_file = "%s%s-%s-%s.%s" %(temp_folder,str(counter).rjust(4,'0'),self.qualified_name(),filename_without_folder,file_extension)
                    # TODO
                    raise AttributeError("Output multifile here not supported,yet")
        else:
            # out_file = tool_type.get()
            # if "://" in out_file:
            #     out_file = context.resolve_file(out_file,False)
            print("STANDALONE")



        _,_,id_value,_,_,_=self.params["id"]
        converter_id = None
        if id_value.value_set():
            converter_id = id_value.get()                
        
        tool = Tool.get(self.tool_id)

        arguments = self.tool_args

        for p in self.params:
            (id,output,tool_type,type_signature,description,expose) = self.params[p]
            if not tool_type.value_set():
                continue
            
            direct_tag = r"@[%s]"%id
            output=replace_special_characters(output)

            param_output = None
            if type(tool_type)==FileValue:
                use_win_path = tool.use_win_path()
                if "://" in tool_type.get():
                    file_name = tool_type.get()
                    file_name = context.resolve_file(file_name,False)
                    tool_type.set(file_name)                
                
                param_output = tool_type.output(output)
                if use_win_path:
                    param_output = param_output.replace('\'','')
                    if not param_output.startswith("/"):
                        param_output = os.path.abspath(param_output)
                    param_output = "z:"+(param_output.replace("/","\\\\"))
#                    param_output = "z:"+(param_output.replace("/","\\"))
            else:
                param_output = tool_type.output(output)

            if direct_tag in arguments:
                arguments=arguments.replace(direct_tag,param_output)
            else:
                arguments=arguments.replace("@@","%s @@" % param_output)

        arguments=context.resolve_variables_in_string(arguments,shared_locals)
        arguments=arguments.replace("@@","")


        # let the Tool do the execution(!)
        retcode,execution_call = tool.execute(arguments)
        executions.append(execution_call)

        if not self.standalone:
            if output_type==INPUT_TYPE_MULTIFILE:
                out_file = output_tool_type.set_files_from_data(context,shared_locals)

            file_history.append(out_file)
            return converter_id,name,retcode,output_type,out_file,file_extension,self.metafiles
        else:
            filename, file_extension = os.path.splitext(input)
            file_extension=file_extension[1:]
            return converter_id,name,retcode,input_type,input,file_extension,self.metafiles
        
        

    
    def get(_qn,target):
        qn = "%s-%s" % (_qn,target)
        if qn not in Converter.CONVERTERS:
            qn = "%s-%s" % (_qn,"all")
            if qn not in Converter.CONVERTERS:
                return None
            #raise KeyError("there is no converter with the qn:%s" % qn)

        return Converter.CONVERTERS[qn]

    def has(qn):
        return qn in Converter.CONVERTERS

def add_to_listmap(map,key,value):
    if key not in map:
        map[key]=[]
    map[key].append(value)


class Tool:
    TOOLS={}
    EXE_COUNT=0

    def __init__(self,xml):
        global XMLNS
        print(ElementTree.tostring(xml))
        self.xml=xml
        self.xml_filename=xgetrequired(xml,"xml_filename")
        self.xml_folder=os.path.dirname(self.xml_filename)
        self.tool_type=xgetrequired(xml,"type")
        self.tool_id=xgetrequired(xml,"id")
        self.version=xget(xml,"version","unknown")
        self.is_default=xget_b(xml,"default",False)
        self.target=xget(xml,"target","all")
        self.environment_variables=[]
        self.environment_files=[]

        def parse_env(xml):
            env_variables = xml.findall("%senv"%XMLNS)
            if env_variables:
                for global_env in env_variables:
                    file = xget(global_env,"file")
                    if file:
                        file = self.replace_keyword(file)
                        self.environment_files.append(file)
                    else:
                        key   = xgetrequired(global_env,"key")
                        value = xgetrequired(global_env,"value")
                        value = self.replace_keyword(value)
                        self.environment_variables.append((key,value))

        parse_env(xml)

        if ARG_GENERATE_XSD:
            XSDManager.get().add_target(self.target)

        self.command=None
        for cmd in xml.iter("%scommand"%XMLNS):
            host    = xgetrequired(cmd,"host")
            if host!=HOST and host!="all":
                # ignore tools for other HOSTs
                continue
            
            parse_env(cmd)

            self.host = host
            self.wrapper = xget(cmd,"wrapper",None)

            if self.tool_type=="cli":
                file = xgetrequired(cmd,"file")
                self.command = self.replace_keyword(file)
                if not os.path.exists(self.command):
                    raise AttributeError("Could not locate tool:%s at %s" % (self.qualified_name(),self.command))
            else:
                raise AttributeError("Unknown ToolType:%s" % self.tool_type)

    def replace_keyword(self,input):
        input=input.replace("@",self.xml_folder)
        return input

    def qualified_name(self):
        return "%s.%s" % (self.tool_id,self.version)

    def add(tool):
        tid=tool.tool_id

        if  tid not in Tool.TOOLS:
            Tool.TOOLS[tid]={}
        tool_bag = Tool.TOOLS[tid]
        if tool.version in tool_bag:
            raise NameError("[%s] There was already a version %s registered!" % ( tid,tool.version ))

        tool_bag[tool.version]=tool
        if "default" not in tool_bag or tool.is_default:
            tool_bag["default"]=tool

    def get(tool_id,version="default"):
        # TODO: handle versions
        if tool_id not in Tool.TOOLS:
            raise KeyError("Unknown tool with tool_id: %s" % tool_id)
        
        return Tool.TOOLS[tool_id][version]

    # def get_command(self):
    #     if HOST not in self.commands:
    #         raise KeyError("[Tool:%s] Not command for OS[%s]" % (self.tool_id,HOST))
    #     return self.commands[HOST]

    def add_from_xml(xml):
        try:
            tool = Tool(xml)
            Tool.add(tool)
        except Exception as e:
            if ARG_STOP_ON_ERROR:
                raise e

    def use_win_path(self):
        # todo: this is a bit unflexible but for now
        return self.wrapper=="wine"

    def execute(self,arguments,_env_vars=[],_env_files=[]):
        env_vars  = _env_vars + self.environment_variables
        env_files = _env_files + self.environment_files
        
        execution_command = "%s %s" % (self.command,arguments)

        if self.wrapper:
            wrapper_tool = Tool.get(self.wrapper)
            retcode,execution_command = wrapper_tool.execute(execution_command,env_vars,env_files)
        else:
            environment_vars = ""
            
            for key,value in env_vars:
                environment_vars += f"{HOST_EXPORT} {key}={value} && "
            for file in env_files:
                environment_vars += f"{HOST_ENV_SOURCE} {file} && "

            exe = environment_vars + execution_command
            #execution_command = "bash -c \""+exe +" \""
            execution_command = exe
            print("exe:%s" % execution_command)
            #execution_command = "bash -c \""+environment_vars +" export -p > exports.out \""
            
            retcode = os.system(execution_command)

        return retcode,execution_command

class FileRepository:
    IGNORE_FOLDERS=["__pycache__",".vvalueenv",".vscode","temp",".git"]
    def __init__(self,repo_name,folder):
        self.folder=folder
        self.name=repo_name
        self.filters=[]
    
    def get_file(self,input,check_existence=True,resolve_pattern=False,keep_repo_prefix=False):
        # repo,all=FileRepository.get_repo_from_file(input)
        # if repo!=self.name:
        #     raise AttributeError("FileRepo[%s]. Tried to locate file from other filerepo!:%s" % (self.folder,input))

        # input = input.replace(all,"")
        filename="%s/%s" % (self.folder,input)
        if not resolve_pattern:
            if check_existence and not os.path.exists(filename):
                raise AttributeError("FileRepo[%s]. Could not locate file:%s" % (self.folder,input))

            return os.path.abspath(filename)
        else:
            filenames = sorted(glob.glob(filename))
            if keep_repo_prefix:
                for i in range(len(filenames)):
                    filenames[i]=filenames[i].replace(self.folder,"%s:/"%self.name)
            return filenames



    def add_filter(self,folder_filter,filename_filter,extension_filter):
        def filter(folder,filename,extension):
            if folder_filter and re.match(folder_filter,folder) is None:
                return False
            if filename_filter and re.match(filename_filter,filename) is None:
                return False
            if extension_filter and re.match(extension_filter,extension) is None:
                return False
            return True
        
        self.filters.append(filter)

    def write_file(self,input,output_in_repo):
        output_in_repo=output_in_repo.replace("%s://"%self.name,"")
        output_filename="%s/%s" % (self.folder,output_in_repo)
        directory = os.path.dirname(output_filename)
        try:
            os.makedirs(directory)
        except:
            pass
        shutil.copyfile(input,output_filename)

    def is_valid_folder(self,folder):
        if folder in FileRepository.IGNORE_FOLDERS:
            return False
        for invalid_folder in FileRepository.IGNORE_FOLDERS:
            if folder.startswith(invalid_folder):
                return False

        return True

    def execute_filer(self,folder,filename,extension):
        for filter in self.filters:
            if filter(folder,filename,extension):
                return True
        return False

    def get_all_files(self):
        listOfFiles = []
        for (dirpath, dirnames, filenames) in walklevel(self.folder,ARG_AUTOCOMPLETE_REPOSITORY_LEVELS):
            rel_folder = os.path.relpath(dirpath,self.folder)
            if not self.is_valid_folder(rel_folder):
                continue
            if rel_folder==".":
                rel_folder=""

            repodir="%s://%s" % (self.name,rel_folder)

            if len(self.filters)>0:
                for file in filenames:
                    filename, file_extension = os.path.splitext(file)
                    if self.execute_filer(rel_folder,filename,file_extension[1:]):
                        listOfFiles.append(os.path.join(repodir, file))
            else:
                listOfFiles += [os.path.join(repodir, file) for file in filenames]        
        return listOfFiles

    def get_repo_from_file(input):
        m=re.search(r"(.+?)://(.+)",input)
        if m is None:
            raise AttributeError("Could not filter file-repository:%s" % input)

        all=m.group(0)
        repo=m.group(1)
        relative=m.group(2)
        return repo,all,relative

def set_sharedlocals_for_file(input,id,shared_locals,dir_name):
    in_file = os.path.basename(input)
    filename_wo_ext, file_extension = os.path.splitext(in_file)
    file_extension=file_extension[1:]
    shared_locals["init_filename"]=in_file
    shared_locals["init_file_wo_ext"]=filename_wo_ext
    shared_locals["init_file_ext"]=file_extension
    shared_locals["init_file_id"]=id
    shared_locals["init_folder"]=dir_name
    shared_locals["init_input_type"]="single_file"
    shared_locals["current_file_folders"]=None

class Context:
    def __init__(self,args):
        global ARG_STOP_ON_ERROR,ARG_AUTOCOMPLETE_REPOSITORIES,ARG_AUTOCOMPLETE_REPOSITORY_LEVELS,ARG_GENERATE_XSD,ARG_TP_XSD_FOLDER,ARG_TARGET

        self.input_files = args.input
        self.keep_intermediate = args.keep_intermediate_files
        ARG_AUTOCOMPLETE_REPOSITORIES = args.autocomplete_repositories
        ARG_AUTOCOMPLETE_REPOSITORY_LEVELS = args.autocomplete_repository_levels
        ARG_GENERATE_XSD = args.generate_xsd
        ARG_TP_XSD_FOLDER = args.export_tp_xsd_to_folder
        ARG_TARGET = args.target
        ARG_STOP_ON_ERROR = args.stop_on_error

        self.repositories={}
        self.allIDs={}

    def input_resolver(self,input_xml,output_xml):
        for ie in input_xml:
            if ie.tag=="%sfile"%XMLR:
                filename = xgetrequired(ie,"filename")
                _id = xget(ie,"id",None)
                _target = xget(ie,"target","all")
                repo_name,all,relative = FileRepository.get_repo_from_file(filename)
                
                input_files = InputFile(self,filename,repo_name,_target).retrieve(True)
                for input_file in input_files:
                    if _id:
                        xml_file = ElementTree.SubElement(output_xml,"%sfile"%XMLR,filename=input_file,id=_id,target=_target)
                    else:
                        xml_file = ElementTree.SubElement(output_xml,"%sfile"%XMLR,filename=input_file,target=_target)

            elif ie.tag=="%smultifile"%XMLR:
                mf_name = xgetrequired(ie,"name")
                multi_file=ElementTree.SubElement(output_xml,"%smultifile"%XMLR,name=mf_name)
                self.input_resolver(ie,multi_file)
            else:
                other=ElementTree.SubElement(output_xml,ie.tag,ie.attrib)
                other.text=ie.text
                

    def add_repository_from_xml(self,xml):
        name = xgetrequired(xml,"name")

        if name in self.repositories:
            raise AttributeError("Repositiory with name:%s already present!" % name)

        if xml.tag=="%sfile-repository"%XMLR:
            name = xgetrequired(xml,"name")
            folder = xgetrequired(xml,"folder")
            file_repo = FileRepository(name,folder)
            self.repositories[name]=file_repo

            for filter in xml.iter("%sfilter"%XMLR):
                filter_folder   = xget(filter,"folder",None)
                filter_filename = xget(filter,"filename",None) 
                filter_extension= xget(filter,"extension",None)
                file_repo.add_filter(filter_folder,filter_filename,filter_extension)

            if ARG_AUTOCOMPLETE_REPOSITORIES and ARG_GENERATE_XSD:
                files = file_repo.get_all_files()
                XSDManager.get().add_files(files)
        
    
    def get_repository(self,repo_name):
        return self.repositories[repo_name]

    def retrieve_input(self,xml_input):
        tag = xml_input.tag.lower().replace(XMLR,"")
        if tag=="file":
            filename = xgetrequired(xml_input,"filename")
            id = xget(xml_input,"id",None)
            target = xget(xml_input,"target","all")
            repo_name,all,relative = FileRepository.get_repo_from_file(filename)
            dir_name = os.path.dirname(relative)
            input_file = InputFile(self,filename,repo_name,target).retrieve()
            return (INPUT_TYPE_SINGLEFILE,repo_name,(id,input_file,target),None,dir_name)
        elif tag=="multifile":
            evals=[]
            print("XML:%s" % ElementTree.tostring(xml_input))
            multifile_name=xgetrequired(xml_input,"name")
            result=[]
            result_with_id=[]
            for xml_file in xml_input:
                tag=xml_file.tag.lower().replace(XMLR,"")
                
                if tag=="eval":
                    evals.append(xml_file)
                    continue
                elif tag!="file":
                    raise AttributeError("Invalid element in multifile:%s\n%s"%(tag,ElementTree.tostring(xml_file)))
                
                filename = xgetrequired(xml_file,"filename")
                id = xget(xml_file,"id",None)
                target = xget(xml_file,"target","all")

                repo_name,all,relative = FileRepository.get_repo_from_file(filename)
                input_file = InputFile(self,filename,repo_name,target).retrieve()
                result.append((repo_name,input_file))
                if id:
                    result_with_id.append((id,input_file))
            return (INPUT_TYPE_MULTIFILE,multifile_name,(result,result_with_id,target),evals,"")
        else:
            raise AttributeError("Unknown input-type:%s" % tag)

    def resolve_variables_in_string(self,string_data,shared_locals):
        pattern = r"@\[(.+?)\]"
        m = re.search(pattern,string_data)
        while m:
            all = m.group(0)
            var_name = m.group(1)
            if var_name in shared_locals:
                data = shared_locals[var_name]
                string_data=string_data.replace(all,str(data))
            else:
                raise AttributeError("Unknown variable:%s in %s" % (var_name,string_data) )
                string_data=string_data.replace(all,str(data))
            m = re.search(pattern,string_data)

        if "@[" in string_data:
            raise AttributeError("Could not resolve all variables:%s" % string_data)

        return string_data

    def resolve_attribute_variables(self,xml,shared_locals):
        for attrib in xml.attrib:
            resolved = self.resolve_variables_in_string(xml.attrib[attrib],shared_locals)
            xml.attrib[attrib]=resolved

    def resolve_file(self,filename,check_existance):
        repo_name,all,relative = FileRepository.get_repo_from_file(filename)
        if repo_name=="id":
            (id,input_type,input,file_extension,_metafiles) = self.allIDs[relative]
            return input
        else:                    
            repo = self.get_repository(repo_name)
            result = repo.get_file(relative,check_existance)
            return result

    def check_condition(shared_locals,condition):
        result = eval(condition,shared_locals)
        return result

    def set_shared_single_file_locals(self,shared_locals,input):
        shared_locals["full_filename"]=input
        in_file = os.path.basename(input)
        filename_wo_ext, file_extension = os.path.splitext(in_file)
        file_extension=file_extension[1:]
        shared_locals["filename"]=in_file
        shared_locals["file_wo_ext"]=filename_wo_ext
        shared_locals["file_ext"]=file_extension

    def execute_commands(self,ctx,xml,iter_expression):
            found_action = False
            for action in xml.iter(iter_expression):
                found_action = True
                block_data,command_counter,input_type,name,input,metafiles,shared_globals,shared_locals,execution_calls,IDs,multifiles,target,pipeline_name,pipeline_folder,file_history,file_target=ctx
                # execute pipeline for every input
                first_iteration=True

                # TODO: do the block need this information?
                if block_data:
                    # TODO: this data is not used.... remove soon?
                    if block_data[0]=="loop":
                        type,loop_init,loop_condition,loop_step=block_data
                    elif block_data[0]=="if":
                        pass

                old_pipeline_folder=pipeline_folder

                pipeline_target = target                
                _action_target = xget(action,"target",None)
                
                try:
                    targets = _action_target.split('|')
                except:
                    targets = ["all"]
                
                found_target_action = False

                for action_target in targets:
                    block_data,command_counter,input_type,name,input,metafiles,shared_globals,shared_locals,execution_calls,IDs,multifiles,target,pipeline_name,pipeline_folder,file_history,file_target=ctx

                    if action_target!=None and action_target!="all" and pipeline_target!="all" and action_target!=ARG_TARGET:
                        continue

                    if pipeline_target!="all" and _action_target==None:
                        # take outer-scoped target if inner-scoptarget not specified
                        target = pipeline_target
                    else:
                        target = action_target

                    if file_target!="all" and target!=file_target:
                        continue

                    shared_locals["target"]=target

                    for _command in action:
                        found_target_action=True
                        command = copy.deepcopy(_command)
                        input_data=(input_type,name,input)
                        if input_type==INPUT_TYPE_SINGLEFILE:
                            self.set_shared_single_file_locals(shared_locals,input)
                        else:
                            shared_locals["input_type"]="multi_file"
                            shared_locals["mf_name"]=name
                            shared_locals["mf_files"]=input


                        tag = command.tag.lower().replace(XMLR,"")
                        if tag=="init":
                            continue

                        ## CONVERTER ##
                        converter = Converter.get(tag,target)
                        if converter:
                            self.resolve_attribute_variables(command,shared_locals)
                            id,name,result,input_type,input,file_extension,_metafiles = converter.execute((self,shared_locals),command_counter,pipeline_folder,input_data,command,file_history,execution_calls)
                            
                            if id:
                                IDs[id]=(id,input_type,input,file_extension,_metafiles)
                                self.allIDs[id]=(id,input_type,input,file_extension,_metafiles)
                                XSDManager.get().add_id(id)
                            
                            if input_type==INPUT_TYPE_SINGLEFILE:
                                if _metafiles:
                                    _metafiles=self.resolve_variables_in_string(_metafiles,shared_locals)
                                    for mf in _metafiles.split(','):
                                        if mf not in metafiles:
                                            metafiles.append(mf)
                            else:
                                if _metafiles:
                                    for mf in _metafiles:
                                        if mf not in metafiles:
                                            metafiles.append(mf)

                            command_counter+=1
                            shared_locals["file_ext"]=file_extension
                            if result!=0:
                                raise AttributeError("command resulted in error!")
                        ## PYTHON-EVAL ##
                        elif tag=="eval":
                            ev_str = trim_text(command.text)
                            exec(ev_str,shared_globals,shared_locals)
                            execution_calls.append("eval start:\n%s\neval end:------" % ev_str)
                        ## OUTPUT / COPY ##
                        elif tag=="output":
                            filename=xgetrequired(command,"filename")
                            
                            m = re.match(r"(.+?)://.*",filename)
                            if m:
                                name = m.group(1)
                            else:
                                raise AttributeError("output-command: no filerepository specified: %s" % filename)

                            target_before=target
                            target=xget(command,"target",target)
                            use_file=xget(command,"use_file",False)
                            if use_file:
                                a=0
                            copy_metafiles=xget_b(command,"copy_metafiles",True)

                            shared_locals["target"]=target

                            def write(input,name,filename):
                                nonlocal shared_locals
                                filename=self.resolve_variables_in_string(filename,shared_locals)

                                repo = self.get_repository(name)

                                folder=os.path.dirname(filename)
                                
                                repo.write_file(input,filename)
                                if copy_metafiles and metafiles:
                                    for mf in metafiles:
                                        meta_filename="%s/%s" % (folder,os.path.basename(mf))
                                        repo.write_file(mf,meta_filename)
                                        print("Output to %s" %meta_filename)

                                return filename
                            
                            if input_type==INPUT_TYPE_SINGLEFILE:
                                resolved_filename = write(input,name,filename)
                            else:
                                for _,_input in input:
                                    set_sharedlocals_for_file(_input,None,shared_locals)
                                    write(_input,name,filename)

                            if use_file:
                                repo_name,all,relative = FileRepository.get_repo_from_file(resolved_filename)
                                repo = self.get_repository(repo_name)
                                input = repo.get_file(relative)
                                self.set_shared_single_file_locals(shared_locals,input)                                

                            execution_calls.append("output:%s => [%s]:%s" % (input,name,filename))
                            target=target_before
                            shared_locals["target"]=target   
                        elif tag=="set-input":
                            id=xgetrequired(command,"id")
                            if id not in IDs:
                                raise KeyError("SetInput: unknown ID:%s" % id)
                            id,input_type,input,file_extension,_metafiles=IDs[id]
                            # TODO: not sure about that:
                            name = id
                        elif tag=="loop":
                            init = xget(command,"init",None)
                            condition = xgetrequired(command,"condition")
                            step = xget(command,"step",None)
                            use_loop_folder = xget_b(command,"use_folder",False)

                            loop_data=("loop",init,condition,step)

                            if init:
                                lines=init.replace(';','\n')
                                exec(lines,shared_locals)
                            while Context.check_condition(shared_locals,condition):
                                if use_loop_folder:
                                    loop_folder = "%sloop.%s/"%(old_pipeline_folder,command_counter)
                                    try:
                                        os.makedirs(loop_folder)
                                    except:
                                        pass
                                else:
                                    loop_folder = old_pipeline_folder

                                loop_ctx = (loop_data,command_counter,input_type,name,input,metafiles,shared_globals,shared_locals,execution_calls,IDs,multifiles,target,pipeline_name,loop_folder,file_history,file_target)
                                output_ctx = self.execute_commands(loop_ctx,command,"%sloop-actions"%XMLR)
                                #TODO process output? at the moment you need to create output for loops via multifile-create and -add
                                if step:
                                    lines=step.replace(';','\??')
                                    exec(lines,shared_locals)
                                command_counter+=1
                        elif tag=="if":
                            found_valid_condition=False
                            if_data=("if")
                            for on_tag in command.iter("%son"%XMLR):
                                condition=xgetrequired(on_tag,"condition")
                                if Context.check_condition(shared_locals,condition):
                                    if_ctx = (if_data,command_counter,input_type,name,input,metafiles,shared_globals,shared_locals,execution_calls,IDs,multifiles,target,pipeline_name,pipeline_folder,file_history,file_target)
                                    found_valid_condition=True
                                    output_context =  self.execute_commands(if_ctx,on_tag,"%sif-actions"%XMLR)
                                    if_data,command_counter,input_type,name,input,metafiles,shared_globals,shared_locals,execution_calls,IDs,multifiles,target,pipeline_name,pipeline_folder,file_history,file_target=output_context
                                    break

                            if not found_valid_condition:
                                else_tag = command.find("%selse"%XMLR)
                                if else_tag:
                                    if_ctx = (if_data,command_counter,input_type,name,input,metafiles,shared_globals,shared_locals,execution_calls,IDs,multifiles,target,pipeline_name,pipeline_folder,file_history,file_target)
                                    found_valid_condition=True
                                    output_context = self.execute_commands(if_ctx,else_tag,"%sif-actions"%XMLR)
                                    if_data,command_counter,input_type,name,input,metafiles,shared_globals,shared_locals,execution_calls,IDs,multifiles,target,pipeline_name,pipeline_folder,file_history,file_target=output_context

                        elif tag=="multifile-create":
                            multifile_id = xgetrequired(command,"id")
                            # TODO: what to do if this already exists?
                            multifile = MultiFileValue()
                            # TODO unify this?
                            multifiles[multifile_id]=multifile
                            IDs[multifile_id]=(multifile_id,INPUT_TYPE_MULTIFILE,[],file_extension,[])
                        elif tag=="multifile-add":
                            multifile_id = xgetrequired(command,"id")
                            if multifile_id not in multifiles:
                                raise KeyError("Unknown multifile-id: %s" % multifile_id)
                            
                            multifile = multifiles[multifile_id]
                            # todo: metafiles
                            mf_id,mf_input_type,mf_input,mf_file_extension,mf_metafiles=IDs[multifile_id]
                            if input_type==INPUT_TYPE_SINGLEFILE:
                                multifile.add_file(("cwd",input))
                                mf_input.append(("cwd",input))
                                a=0
                            else:
                                multifile.add_files(input)
                                mf_input=mf_input+input
                                IDs[multifile_id]=(mf_id,mf_input_type,mf_input,mf_file_extension,mf_metafiles)


                        else:
                            raise AttributeError("Unknown pipeline-command:%s"%tag)
            if found_action and found_target_action:
                return (block_data,command_counter,input_type,name,input,metafiles,shared_globals,shared_locals,execution_calls,IDs,multifiles,target,pipeline_name,old_pipeline_folder,file_history,file_target)
            else:
                return None
    

    def init_funcs(self,shared_data):  
        shared_data["write_string"]=write_string
        shared_data["xml_pretty"]=xml_pretty
        # TODO make this a dedicated script
        exec("""
from math import sqrt,ceil
import math,os
from xml.etree import ElementTree as ET

def lower(a,b):
    return a<b
def greater(a,b):
    return a>b        
def lower_equal(a,b):
    return a<=b
def greater_equal(a,b):
    return a>=b

        """,shared_data)

    def execute_pipeline(self,xml_pipeline):
        shared_globals=dict()
        shared_locals=dict()

        self.init_funcs(shared_locals)

        execution_calls=[]
        IDs = {}
        multifiles={}
        files_ids={}
        files_id_order=[]

        def add_file_id(id,file):
            if not id in files_id_order:
                files_id_order.append(id)
                files_ids[id]=[]
            if file not in files_ids:
                files_ids[id].append(file)

        target = xget(xml_pipeline,"target",ARG_TARGET)
        # target = xget(xml_pipeline,"target","all")

        # if target!="all" and target!=ARG_TARGET:
        #     return

        pipeline_name = xgetrequired(xml_pipeline,"pl-name")

        print("\nEXECUTE PIPELINE:%s target:%s\n\n"%(pipeline_name,target))

        pipeline_folder = "temp/%s%s/" % (pipeline_name,time.time())
        try:
            os.makedirs(pipeline_folder)
        except:
            pass

        shared_locals["target"]=target
        shared_locals["temp_folder"]=pipeline_folder
        shared_locals["cwd_folder"]=os.getcwd()
        shared_locals["tp_folder"]=os.path.dirname(os.path.realpath(__file__))
        shared_locals["all_file_id_folders"]=files_ids
        shared_locals["current_file_id_order"]=files_id_order

        init=xml_pipeline.find("%sinit"%XMLR)
        if init is None:
            raise AttributeError("Pipeline without init:\n%s" % ElementTree.tostring(xml_pipeline))

        for ev in init.findall("./%seval"%XMLR):
            ev_str = trim_text(ev.text)
            exec(ev_str,shared_globals,shared_locals)
            execution_calls.append("eval start:\n%s\neval end:------" % ev_str)

        xml_input=init.find("%sinput"%XMLR)
        if xml_input is None:
            raise AttributeError("Pipeline.Init without <input/>\n%s" % ElementTree.tostring(xml_pipeline))

        # resolve file-pattern first
        resolved_input=ElementTree.SubElement(init,"%sinput"%XMLR)
        command_counter=1
        metafiles=[]
        
        def resolve_input_files():
            self.input_resolver(xml_input,resolved_input)
            print(ElementTree.tostring(resolved_input))
            result = []
            id = None
            for _input in resolved_input:
                #todo do we want to clear? yes, i guesss
                files_id_order.clear()

                #execute input-eval
                if _input.tag=="%seval"%XMLR:
                    ev_str = trim_text(_input.text)
                    exec(ev_str,shared_globals,shared_locals)
                    execution_calls.append("eval start:\n%s\neval end:------" % ev_str)
                    continue       

                input_type,name,input_info,evals,dir_name = input_data = self.retrieve_input(_input)
                shared_locals["in_repo_folder"]=dir_name
                if input_type==INPUT_TYPE_SINGLEFILE:
                    id,input,target=input_info
                    if id:
                        add_file_id(id,input)

                    file_history=[input]
                    execution_calls.append("\nInput-File:%s" %input)
                    
                    filename, file_extension = os.path.splitext(input)
                    file_extension=file_extension[1:]                
                    IDs["orig"]=("orig",input_type,input,file_extension,None)
                    result.append((input,input_type,name,input_info,evals,dir_name,file_history,id,target))
                elif input_type==INPUT_TYPE_MULTIFILE:
                    input,files_with_id,target=input_info
                    for id,file in files_with_id:
                        add_file_id(id,file)

                    file_history=[input]
                    shared_locals["init_input_type"]="multi_file"
                    shared_locals["init_mf_name"]=name
                    shared_locals["init_mf_files"]=input
                    current_id_folders=[]
                    for id_folder in files_id_order:
                        current_id_folders.append((id_folder,files_ids[id_folder]))
                    shared_locals["current_file_folders"]=current_id_folders
                    result.append( (input,input_type,name,input_info,evals,dir_name,file_history,id,target) )
                else:
                    raise AttributeError("Unknown input_type:%s [%s]" % (input_type,ElementTree.tostring(_input)))

                if evals:
                    for eval in evals:
                        ev_str = trim_text(eval.text)
                        exec(ev_str,shared_globals,shared_locals)
                        execution_calls.append("eval start:\n%s\neval end:------" % ev_str)
                #TODO check if this return is really at the right position at it will retur at first _input of the loop
            return result

        resolve_result_list = resolve_input_files()
        if not resolve_result_list:
            return

        for resolve_result in resolve_result_list:
            input,input_type,name,input_info,evals,dir_name,file_history,id,file_target = resolve_result

            if type(input) is str:
                set_sharedlocals_for_file(input,id,shared_locals,dir_name)
                shared_locals["init_full_filename"]=input
                shared_locals["init_repo_name"]=name
            else:
                #multifile
                pass


            block_data = None
            pipeline_context = (block_data,command_counter,input_type,name,input,metafiles,shared_globals,shared_locals,execution_calls,IDs,multifiles,target,pipeline_name,pipeline_folder,file_history,file_target)
            
            # execution command
            execution_ctx = self.execute_commands(pipeline_context,xml_pipeline,"%sactions"%XMLR)
            if not execution_ctx:
                continue
            # unfold data from execution
            # block_data,command_counter,input_type,name,input,metafiles,shared_globals,shared_locals,execution_calls,IDs,target,pipeline_name,pipeline_folder,file_history=execution_ctx

            execution_file = open("%s%s-exe-list.%s.txt" % (pipeline_folder,pipeline_name,time.time()),"w")
            execution_text = "\n".join(execution_calls)        
            execution_file.write(execution_text)
            execution_file.close()

            if not self.keep_intermediate:
                shutil.rmtree(pipeline_folder)


    def execute_file(self,filename):
        xml = ElementTree.parse(filename).getroot()
        global XMLR
        XMLR=namespace(xml)        

        repos = xml.find("%srepositories"%XMLR)
        if repos is not None:
            for repo in repos:
                self.add_repository_from_xml(repo)
        default_repo=self.repositories["cwd"]=FileRepository("cwd",os.getcwd())
        if ARG_AUTOCOMPLETE_REPOSITORIES and ARG_GENERATE_XSD:
            files = default_repo.get_all_files()
            XSDManager.get().add_files(files)        

        for pipeline in xml.iter("%spipeline"%XMLR):
            self.execute_pipeline(pipeline)
                

    def run(self):
        if self.input_files:
            for file in self.input_files:
                self.execute_file(file)


def namespace(element):
    m = re.match(r'\{.*\}', element.tag)
    return m.group(0) if m else ''

def load_plugins(folders):
    xml_element_tree = None
    for folder in folders:
        xml_files = Path(folder).rglob("*.xml")
        for xml_file in xml_files:
            data = ElementTree.parse(xml_file).getroot()
            for elem in data:
                _xml_file = str(xml_file.resolve())
                elem.set("xml_filename",_xml_file)
            if xml_element_tree is None:
                xml_element_tree=data
            else:
                xml_element_tree.extend(data)

    write_string("all.xml_",xml_pretty(xml_element_tree))
    return xml_element_tree

def parse_tools(xml_data):
    global XMLNS
    XMLNS=namespace(xml_data)

    print(ElementTree.tostring(xml_data))
    for tool in xml_data.iter("%stool"%XMLNS):
        Tool.add_from_xml(tool)

    for converter in xml_data.iter("%sconverter"%XMLNS):
        Converter.add_from_xml(converter)

def parse_arguments():
    parser = argparse.ArgumentParser(description="thepipeline - universal assets processor")
    parser.add_argument("--input",action="append",help="input xml-files")
    parser.add_argument("--keep-intermediate-files",type=bool,default=False,help="keep files generated during runtime")
    parser.add_argument("--autocomplete-repositories",type=bool,default=False,help="iterates over repositories for autocompletion")
    parser.add_argument("--autocomplete-repository-levels",type=int,default=2,help="folder depth to use")
    parser.add_argument("--generate-xsd",type=bool,default=False,help="generate runtime.xsd (default:plugins/tpruntime.xsd)")
    parser.add_argument("--xsd-output-filename",default="plugins/tpruntime.xsd",help="output folder of the runtime xsd (default: plugins/tpruntime.xsd) ")
    parser.add_argument("--export-tp-xsd-to-folder",default=None,help="exports thepipeline-xsd to use for additional plugins in your folder)")
    parser.add_argument("--plugins-folder",action="append",help="search path for plugins folder (default: plugins ) ")
    parser.add_argument("--target",default="all",help="set target for execution")
    parser.add_argument("--stop-on-error",type=bool,default=False,help="stop process on error parsing! e.g. tool not found")
    #parser.add_argument("--pipeline",default="all",help="set specific pipeline to execute")
    args = parser.parse_args()

    ctx = Context(args)
    return ctx,args

def execute_context(ctx):
    pass    

def startup():
    current_folder = os.path.dirname(os.path.realpath(__file__))    

    ctx,args = parse_arguments()
    
    external_plugin_folders = args.plugins_folder or []
    plugin_folders = ["%s/plugins"%current_folder]+external_plugin_folders
    xml = load_plugins(plugin_folders)
    parse_tools(xml)


    ctx.run()

    # try:
    #     ctx.run()
    # except Exception as e:
    #     print(e)
        

    if ARG_GENERATE_XSD:
        try:
            dirname = os.path.dirname(args.xsd_output_filename)
            os.makedirs(dirname)
        except:
            pass
        XSDManager.get().xsdcreator_write(args.xsd_output_filename)

    if ARG_TP_XSD_FOLDER:
        destfolder = os.path.abspath(ARG_TP_XSD_FOLDER)
        try:
            os.makedirs(destfolder)
        except:
            pass
        dest_path = destfolder+"/thepipeline.xsd"
        shutil.copyfile(current_folder+"/plugins/xsd/thepipeline.xsd",dest_path)
        a=0


startup()